from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import logging
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
DATABASE = os.path.join('instance', 'parking.db')
BLYNK_TOKEN = "xbC-JEuKmxpdry7iTOd8n2h_bCsaOf-I"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        logger.debug("Database connection established")
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

# Define format_number filter
def format_number(value):
    try:
        return "{:,.0f}".format(float(value)).replace(",", ".")
    except (ValueError, TypeError):
        logger.error(f"Error formatting number: {value}")
        return str(value)

app.jinja_env.filters['format_number'] = format_number

# Initialize DB and admin
with app.app_context():
    try:
        logger.debug("Starting database initialization")
        if not os.path.exists('instance'):
            os.makedirs('instance')
            logger.debug("Created instance directory")
        
        conn = get_db_connection()
        cur = conn.cursor()

        logger.debug("Creating users table if not exists")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user'
            )
        ''')
        logger.debug("Users table created or already exists")

        logger.debug("Creating bookings table if not exists")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                slot_id TEXT,
                start_time TEXT,
                total_price INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        logger.debug("Bookings table created or already exists")

        logger.debug("Checking for admin user")
        admin = cur.execute('SELECT * FROM users WHERE username = "admin"').fetchone()
        if not admin:
            admin_pw = generate_password_hash("admin123#")
            cur.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                        ("admin", admin_pw, "admin"))
            logger.debug("Admin user created")

        conn.commit()
        logger.debug("Database initialization completed")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            flash('Registrasi berhasil! Silakan login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username sudah dipakai!', 'danger')
        except Exception as e:
            logger.error(f"Error during registration: {e}")
            flash('Terjadi kesalahan saat registrasi.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    logger.debug(f"Session before login: {session}")
    username = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        try:
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                logger.debug(f"Session after login: {session}")
                flash('Login berhasil!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Username atau password salah!', 'danger')
        except Exception as e:
            logger.error(f"Error during login: {e}")
            flash('Terjadi kesalahan saat login.', 'danger')
        finally:
            conn.close()

    return render_template('login.html', username=username)

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    flash('Apakah Anda mau login kembali?', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    logger.debug(f"Accessing dashboard with session: {session}")
    try:
        conn = get_db_connection()
        bookings = conn.execute('SELECT * FROM bookings').fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"Error accessing bookings in dashboard: {e}")
        flash('Terjadi kesalahan saat memuat data booking.', 'danger')
        return render_template('dashboard.html', bookings=[], user_id=session.get('user_id'))

    user_id = session.get('user_id')
    return render_template('dashboard.html', bookings=bookings, user_id=user_id)

@app.route('/book/<slot_id>', methods=['POST'])
def book_slot(slot_id):
    logger.debug(f"Booking attempt for slot {slot_id} with session: {session}, form data: {request.form}")
    if 'user_id' not in session:
        logger.warning("No user_id in session, redirecting to login")
        flash('Silakan login untuk booking.', 'danger')
        return redirect(url_for('login'))

    start_time = request.form.get('start_time')
    if not start_time:
        flash('Waktu penempatan diperlukan.', 'danger')
        return redirect(url_for('dashboard'))

    # Validate slot_id
    valid_slots = ['B1', 'B2', 'B3', 'B4', 'A1', 'A2', 'A3', 'A4', 'A5', 'A6']
    if slot_id not in valid_slots:
        flash('Slot ID tidak valid.', 'danger')
        return redirect(url_for('dashboard'))

    # Validate and calculate price
    try:
        now = datetime.now()
        # Validate start_time format
        if not isinstance(start_time, str) or len(start_time) != 16 or start_time[10] != ' ':
            logger.error(f"Invalid start_time format: {start_time}")
            flash('Format waktu tidak valid.', 'danger')
            return redirect(url_for('dashboard'))

        start = datetime.strptime(start_time, '%Y-%m-%d %H:%M')
        logger.debug(f"Validating start_time: {start_time}, now: {now}, start: {start}")

        if start <= now:
            flash('Waktu penempatan tidak boleh di masa lalu atau saat ini.', 'danger')
            return redirect(url_for('dashboard'))

        # Calculate duration in hours (ceiling)
        duration_seconds = (start - now).total_seconds()
        duration_hours = max(1, int(duration_seconds / 3600 + 0.999))  # Ceiling to next hour
        # Limit maximum duration to 24 hours
        if duration_hours > 24:
            flash('Durasi booking tidak boleh lebih dari 24 jam.', 'danger')
            return redirect(url_for('dashboard'))

        total_price = duration_hours * 5000
        logger.debug(f"Received start_time: {start_time}, duration: {duration_hours} hours ({duration_seconds:.0f} seconds), total_price: Rp{total_price}")
    except ValueError as e:
        logger.error(f"Error parsing start_time: {start_time}, error: {e}")
        flash('Format waktu tidak valid.', 'danger')
        return redirect(url_for('dashboard'))
    except Exception as e:
        logger.error(f"Unexpected error in book_slot: {e}")
        flash('Terjadi kesalahan saat memproses booking.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        conn = get_db_connection()
        conn.execute('INSERT INTO bookings (user_id, slot_id, start_time, total_price) VALUES (?, ?, ?, ?)', 
                    (session['user_id'], slot_id, start_time, total_price))
        conn.commit()
        flash(f'Slot {slot_id} berhasil dibooked dengan total Rp{total_price}!', 'success')
    except Exception as e:
        logger.error(f"Error inserting booking: {e}")
        flash('Terjadi kesalahan saat menyimpan booking.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/unbook/<slot_id>', methods=['POST'])
def unbook_slot(slot_id):
    if 'user_id' not in session:
        flash('Silakan login untuk melepas booking.', 'danger')
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM bookings WHERE user_id = ? AND slot_id = ?', (session['user_id'], slot_id))
        conn.commit()
        flash(f'Slot {slot_id} berhasil dilepas!', 'info')
    except Exception as e:
        logger.error(f"Error unbooking slot: {e}")
        flash('Terjadi kesalahan saat melepas booking.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/admin/users', methods=['GET', 'POST'])
def admin_users():
    if 'username' not in session or session.get('role') != 'admin':
        flash('Akses ditolak.', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()
    try:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            if not username or not password:
                flash('Username dan password tidak boleh kosong.', 'danger')
                return redirect(url_for('admin_users'))

            existing_user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            if existing_user:
                flash('Username sudah ada.', 'danger')
            else:
                hashed = generate_password_hash(password)
                conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                            (username, hashed, 'user'))
                conn.commit()
                flash('User berhasil ditambahkan.', 'success')

        users = conn.execute('SELECT id, username, role FROM users').fetchall()
    except Exception as e:
        logger.error(f"Error in admin_users: {e}")
        flash('Terjadi kesalahan saat mengelola pengguna.', 'danger')
    finally:
        conn.close()

    return render_template('admin_users.html', users=users)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'username' not in session or session.get('role') != 'admin':
        flash('Akses ditolak.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM bookings WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        flash('User berhasil dihapus.', 'info')
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        flash('Terjadi kesalahan saat menghapus pengguna.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('admin_users'))

@app.route('/api/status')
def get_status():
    logger.debug(f"API status request with session: {session}")
    try:
        import requests
        pins = ['v0', 'v1', 'v2']
        status = {}
        for pin in pins:
            res = requests.get(f'https://blynk.cloud/external/api/get?token={BLYNK_TOKEN}&{pin}')
            status[pin] = res.text.strip()

        conn = get_db_connection()
        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d %H:%M')
        logger.debug(f"Checking for expired bookings before: {now_str} (now: {now})")

        # Fetch all bookings
        all_bookings = conn.execute('SELECT id, slot_id, start_time FROM bookings').fetchall()
        logger.debug(f"All bookings: {[(b['id'], b['slot_id'], b['start_time']) for b in all_bookings]}")

        # Delete expired bookings
        expired_bookings = []
        for booking in all_bookings:
            try:
                # Validate start_time format
                if not isinstance(booking['start_time'], str) or len(booking['start_time']) != 16 or booking['start_time'][10] != ' ':
                    logger.error(f"Invalid start_time format: {booking['start_time']} for booking id={booking['id']}")
                    continue

                booking_time = datetime.strptime(booking['start_time'], '%Y-%m-%d %H:%M')
                time_diff = (now - booking_time).total_seconds()
                logger.debug(f"Booking id={booking['id']}, slot_id={booking['slot_id']}, start_time={booking['start_time']}, time_diff={time_diff:.0f} seconds")

                if booking_time < now:
                    expired_bookings.append(booking)
                else:
                    logger.debug(f"Booking id={booking['id']} not expired (start_time {booking['start_time']} is in the future)")
            except ValueError as e:
                logger.error(f"Error parsing start_time: {booking['start_time']} for booking id={booking['id']}, error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error checking booking id={booking['id']}: {e}")

        if expired_bookings:
            logger.debug(f"Found {len(expired_bookings)} expired bookings: {[(b['id'], b['slot_id'], b['start_time']) for b in expired_bookings]}")
            for booking in expired_bookings:
                logger.info(f"Deleting expired booking: id={booking['id']}, slot_id={booking['slot_id']}, start_time={booking['start_time']}")
                conn.execute('DELETE FROM bookings WHERE id = ?', (booking['id'],))
            conn.commit()
        else:
            logger.debug("No expired bookings found")

        bookings = conn.execute('''
            SELECT bookings.slot_id, bookings.user_id, bookings.start_time, bookings.total_price, users.username
            FROM bookings
            JOIN users ON bookings.user_id = users.id
        ''').fetchall()
        conn.close()

        is_admin = session.get('role') == 'admin'
        bookings_list = [
            {
                'slot_id': b['slot_id'],
                'user_id': b['user_id'],
                'username': b['username'] if is_admin else None,
                'start_time': b['start_time'],
                'total_price': b['total_price']
            }
            for b in bookings
        ]

        return jsonify({
            'v0': status['v0'],
            'v1': status['v1'],
            'v2': status['v2'],
            'bookings': bookings_list,
            'current_user': session.get('user_id')
        })
    except Exception as e:
        logger.error(f"Error in get_status: {str(e)}")
        flash('Terjadi kesalahan saat memeriksa status.', 'danger')
        return jsonify({'error': str(e)}), 500

@app.route('/admin')
def admin_panel():
    if 'username' not in session or session.get('role') != 'admin':
        flash('Akses ditolak. Hanya admin yang bisa mengakses halaman ini.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    try:
        bookings = conn.execute('''
            SELECT bookings.id, bookings.slot_id, bookings.start_time, bookings.total_price, bookings.timestamp, users.username
            FROM bookings
            JOIN users ON bookings.user_id = users.id
        ''').fetchall()
    except Exception as e:
        logger.error(f"Error in admin_panel: {e}")
        flash('Terjadi kesalahan saat memuat data booking.', 'danger')
        bookings = []
    finally:
        conn.close()

    return render_template('admin_panel.html', bookings=bookings)

@app.route('/admin/unbook/<int:booking_id>', methods=['POST'])
def admin_unbook(booking_id):
    if 'username' not in session or session.get('role') != 'admin':
        flash('Akses ditolak.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
        conn.commit()
        flash('Booking berhasil dihapus.', 'info')
    except Exception as e:
        logger.error(f"Error in admin_unbook: {e}")
        flash('Terjadi kesalahan saat menghapus booking.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=81)
