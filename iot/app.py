from flask import Flask, render_template, request, redirect, url_for, session, \
                  flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import logging
import requests
from datetime import datetime, timedelta

# Import helper DB (get_db_connection & init_db)
from db import get_db_connection, init_db

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

# Token Blynk Anda
BLYNK_TOKEN = "xbC-JEuKmxpdry7iTOd8n2h_bCsaOf-I"

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Inisialisasi database saat start aplikasi
with app.app_context():
    init_db()
    # Tambahkan kolom baru untuk bookings jika belum ada
    conn = get_db_connection()
    try:
        conn.execute('ALTER TABLE bookings ADD COLUMN booking_time TEXT')
        conn.execute('ALTER TABLE bookings ADD COLUMN duration INTEGER')  # Dalam menit
        conn.execute('ALTER TABLE bookings ADD COLUMN remaining_duration INTEGER')  # Dalam menit
    except sqlite3.OperationalError:
        pass  # Kolom mungkin sudah ada

    # Buat tabel booking_history jika belum ada
    conn.execute('''
        CREATE TABLE IF NOT EXISTS booking_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            slot_id TEXT,
            booking_time TEXT,
            duration INTEGER,
            total_price INTEGER,
            end_time TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

# Jinja Filter: format angka dengan ribuan
@app.template_filter('format_number')
def format_number(value):
    try:
        return "{:,}".format(int(value))
    except (ValueError, TypeError):
        return str(value)

# Halaman beranda (redirect ke dashboard jika login)
@app.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# REGISTER
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (username, password) VALUES (?, ?)',
                (username, password)
            )
            conn.commit()
            flash('Registrasi berhasil! Silakan login.', 'info')  # Ubah ke 'info' untuk warna biru
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username sudah dipakai!', 'danger')
        except Exception as e:
            logger.error(f"Error during registration: {e}")
            flash('Terjadi kesalahan saat registrasi.', 'danger')
        finally:
            conn.close()
    return render_template('register.html')

# LOGIN
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        try:
            user = conn.execute(
                'SELECT * FROM users WHERE username = ?',
                (username,)
            ).fetchone()

            if user and check_password_hash(user['password'], password):
                # Simpan session
                session['user_id']  = user['id']
                session['username'] = user['username']
                session['role']     = user['role']
                flash('Login berhasil!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Username atau password salah!', 'danger')

        except Exception as e:
            logger.error(f"Error during login: {e}")
            flash('Terjadi kesalahan saat login.', 'danger')
        finally:
            conn.close()

    return render_template('login.html')

# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('login'))

# DASHBOARD
@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')  # kalau ada, ambil user_id; kalau tidak, None
    return render_template('dashboard.html', user_id=user_id)

# BOOK SLOT
@app.route('/book/<slot_id>', methods=['POST'])
def book_slot(slot_id):
    if 'user_id' not in session:
        flash('Silakan login untuk booking.', 'danger')
        return redirect(url_for('login'))

    hours = request.form.get('hours')
    minutes = request.form.get('minutes')
    if not hours or not minutes:
        flash('Durasi diperlukan.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        hours = int(hours)
        minutes = int(minutes)
        if hours < 0 or minutes < 0 or (hours == 0 and minutes == 0):
            flash('Durasi minimal 1 menit.', 'danger')
            return redirect(url_for('dashboard'))

        if hours > 24 or (hours == 24 and minutes > 0):
            flash('Durasi maksimal 24 jam.', 'danger')
            return redirect(url_for('dashboard'))

        if minutes >= 60:
            flash('Menit harus kurang dari 60.', 'danger')
            return redirect(url_for('dashboard'))

        duration = (hours * 60) + minutes  # Dalam menit
        total_price = (hours * 5000) + (minutes * 830)  # Rp5,000 per jam, Rp830 per menit
        booking_time = datetime.now().strftime('%Y-%m-%d %H:%M')
        remaining_duration = duration  # Dalam menit

    except ValueError:
        flash('Durasi tidak valid.', 'danger')
        return redirect(url_for('dashboard'))

    # Simpan booking
    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO bookings (user_id, slot_id, booking_time, duration, remaining_duration, total_price) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (session['user_id'], slot_id, booking_time, duration, remaining_duration, total_price)
        )
        conn.commit()
        flash(f'Slot {slot_id} dibooked (Rp{total_price:,}).', 'success')

    except Exception as e:
        logger.error(f"Error inserting booking: {e}")
        flash('Gagal menyimpan booking.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

# UNBOOK SLOT
@app.route('/unbook/<slot_id>', methods=['POST'])
def unbook_slot(slot_id):
    if 'user_id' not in session:
        flash('Silakan login dulu.', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()
    try:
        # Ambil data booking sebelum dihapus
        booking = conn.execute(
            'SELECT user_id, slot_id, booking_time, duration, total_price FROM bookings WHERE user_id = ? AND slot_id = ?',
            (session['user_id'], slot_id)
        ).fetchone()

        if booking:
            # Simpan ke booking_history
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            conn.execute(
                'INSERT INTO booking_history (user_id, slot_id, booking_time, duration, total_price, end_time) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (booking['user_id'], booking['slot_id'], booking['booking_time'], booking['duration'], booking['total_price'], end_time)
            )

        # Hapus booking
        conn.execute(
            'DELETE FROM bookings WHERE user_id = ? AND slot_id = ?',
            (session['user_id'], slot_id)
        )
        conn.commit()
        flash(f'Slot {slot_id} dilepas.', 'info')
    except Exception as e:
        logger.error(f"Error unbooking: {e}")
        flash('Gagal melepas booking.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

# API STATUS + AUTO-UNBOOK BERDASARKAN SISA WAKTU
@app.route('/api/status')
def get_status():
    logger.debug(f"API status request, session: {session}")

    try:
        # 1) Ambil status sensor dari Blynk
        status = {}
        for pin in ('v0','v1','v2'):
            try:
                resp = requests.get(
                    f'https://blynk.cloud/external/api/get?token={BLYNK_TOKEN}&{pin}',
                    timeout=5
                )
                if resp.status_code == 200:
                    status[pin] = resp.text.strip()
                else:
                    logger.warning(f"Failed to fetch Blynk data for {pin}: {resp.status_code}")
                    status[pin] = "Unknown"
            except Exception as e:
                logger.error(f"Error fetching Blynk data for {pin}: {e}")
                status[pin] = "Unknown"

        # 2) Auto-unbook: hapus booking ketika sisa waktu habis
        conn = get_db_connection()
        now = datetime.now()
        rows = conn.execute(
            'SELECT id, slot_id, user_id, booking_time, duration, remaining_duration, total_price FROM bookings'
        ).fetchall()

        expired_bookings = []
        with conn:
            for r in rows:
                try:
                    # Log untuk debugging
                    logger.debug(f"Processing booking ID={r['id']}, slot={r['slot_id']}, booking_time={r['booking_time']}")
                    booking_time = datetime.strptime(r['booking_time'], '%Y-%m-%d %H:%M')
                    duration_seconds = r['duration'] * 60  # Konversi menit ke detik
                    elapsed_seconds = (now - booking_time).total_seconds()
                    remaining_seconds = duration_seconds - elapsed_seconds
                    remaining_minutes = max(0, int(remaining_seconds / 60))

                    logger.debug(f"Booking ID={r['id']}: duration={r['duration']} menit, elapsed={elapsed_seconds:.2f} detik, remaining={remaining_seconds:.2f} detik")

                    # Update remaining_duration di database
                    conn.execute(
                        'UPDATE bookings SET remaining_duration = ? WHERE id = ?',
                        (remaining_minutes, r['id'])
                    )

                    if remaining_seconds <= 0:
                        logger.info(f"Auto-unbook ID={r['id']} slot={r['slot_id']} because duration has ended")
                        # Simpan ke booking_history sebelum hapus
                        end_time = now.strftime('%Y-%m-%d %H:%M')
                        conn.execute(
                            'INSERT INTO booking_history (user_id, slot_id, booking_time, duration, total_price, end_time) '
                            'VALUES (?, ?, ?, ?, ?, ?)',
                            (r['user_id'], r['slot_id'], r['booking_time'], r['duration'], r['total_price'], end_time)
                        )
                        # Hapus booking
                        conn.execute(
                            'DELETE FROM bookings WHERE id = ?',
                            (r['id'],)
                        )
                        expired_bookings.append({
                            'slot_id': r['slot_id'],
                            'user_id': r['user_id']
                        })
                except Exception as ex:
                    logger.error(f"Parsing error for booking ID={r['id']}: {ex}")

            conn.commit()

        # 3) Re-query booking valid
        rows2 = conn.execute('''
            SELECT b.slot_id, b.user_id, b.booking_time, b.duration, b.remaining_duration, b.total_price, u.username
            FROM bookings b
            JOIN users u ON b.user_id = u.id
        ''').fetchall()
        conn.close()

        # 4) Bentuk JSON
        is_admin = (session.get('role') == 'admin')
        bookings_list = []
        for b in rows2:
            bookings_list.append({
                'slot_id': b['slot_id'],
                'user_id': b['user_id'],
                'username': b['username'] if is_admin else None,
                'booking_time': b['booking_time'],
                'duration': b['duration'],
                'remaining_duration': b['remaining_duration'],
                'total_price': b['total_price'],
            })

        return jsonify({
            'v0': status['v0'],
            'v1': status['v1'],
            'v2': status['v2'],
            'bookings': bookings_list,
            'expired_bookings': expired_bookings,
            'current_user': session.get('user_id')
        })

    except Exception as e:
        logger.error(f"Error in get_status: {e}")
        return jsonify({'error': str(e)}), 500

# USER HISTORY
@app.route('/history')
def user_history():
    if 'user_id' not in session:
        flash('Silakan login untuk melihat riwayat.', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()
    try:
        data = conn.execute('''
            SELECT slot_id, booking_time, duration, total_price, end_time
            FROM booking_history
            WHERE user_id = ?
            ORDER BY booking_time DESC
        ''', (session['user_id'],)).fetchall()

        history = []
        for b in data:
            history.append({
                'slot_id': b['slot_id'],
                'booking_time': b['booking_time'],
                'duration': b['duration'],
                'total_price': b['total_price'],
                'end_time': b['end_time'],
            })
    except Exception as e:
        logger.error(f"Error user_history: {e}")
        flash('Gagal memuat riwayat.', 'danger')
        history = []
    finally:
        conn.close()

    return render_template('user_history.html', history=history)

# ADMIN HISTORY
@app.route('/admin/history')
def admin_history():
    if session.get('role') != 'admin':
        flash('Akses ditolak. Hanya admin.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    try:
        data = conn.execute('''
            SELECT b.slot_id, b.booking_time, b.duration, b.total_price, b.end_time, u.username
            FROM booking_history b
            JOIN users u ON b.user_id = u.id
            ORDER BY b.booking_time DESC
        ''').fetchall()

        history = []
        for b in data:
            history.append({
                'slot_id': b['slot_id'],
                'username': b['username'],
                'booking_time': b['booking_time'],
                'duration': b['duration'],
                'total_price': b['total_price'],
                'end_time': b['end_time'],
            })
    except Exception as e:
        logger.error(f"Error admin_history: {e}")
        flash('Gagal memuat riwayat.', 'danger')
        history = []
    finally:
        conn.close()

    return render_template('admin_history.html', history=history)

# ADMIN PANEL
@app.route('/admin')
def admin_panel():
    if session.get('role') != 'admin':
        flash('Akses ditolak. Hanya admin.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    try:
        data = conn.execute('''
            SELECT b.id, b.slot_id, b.booking_time, b.duration, b.remaining_duration, b.total_price, b.timestamp, u.username
            FROM bookings b
            JOIN users u ON b.user_id = u.id
        ''').fetchall()

        bookings = []
        for b in data:
            bookings.append({
                'id': b['id'],
                'slot_id': b['slot_id'],
                'booking_time': b['booking_time'],
                'duration': b['duration'],
                'remaining_duration': b['remaining_duration'],
                'total_price': b['total_price'],
                'timestamp': b['timestamp'],
                'username': b['username'],
            })
    except Exception as e:
        logger.error(f"Error admin_panel: {e}")
        flash('Gagal memuat data.', 'danger')
        bookings = []
    finally:
        conn.close()

    return render_template('admin_panel.html', bookings=bookings)

@app.route('/admin/unbook/<int:booking_id>', methods=['POST'])
def admin_unbook(booking_id):
    if session.get('role') != 'admin':
        flash('Akses ditolak.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    try:
        # Ambil data booking sebelum dihapus
        booking = conn.execute(
            'SELECT user_id, slot_id, booking_time, duration, total_price FROM bookings WHERE id = ?',
            (booking_id,)
        ).fetchone()

        if booking:
            # Simpan ke booking_history
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            conn.execute(
                'INSERT INTO booking_history (user_id, slot_id, booking_time, duration, total_price, end_time) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (booking['user_id'], booking['slot_id'], booking['booking_time'], booking['duration'], booking['total_price'], end_time)
            )

        # Hapus booking
        conn.execute(
            'DELETE FROM bookings WHERE id = ?',
            (booking_id,)
        )
        conn.commit()
        flash('Booking dihapus oleh admin.', 'info')
    except Exception as e:
        logger.error(f"Error admin_unbook: {e}")
        flash('Gagal menghapus.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('admin_panel'))

# ADMIN USERS - Menampilkan dan Menambah User
@app.route('/admin/users', methods=['GET', 'POST'])
def admin_users():
    if session.get('role') != 'admin':
        flash('Akses ditolak. Hanya admin.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    try:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            hashed_password = generate_password_hash(password)

            conn.execute(
                'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                (username, hashed_password, 'user')
            )
            conn.commit()
            flash(f'User {username} berhasil ditambahkan.', 'success')

        # Ambil semua user
        users = conn.execute('SELECT id, username, role FROM users').fetchall()
    except sqlite3.IntegrityError:
        flash('Username sudah dipakai!', 'danger')
        users = conn.execute('SELECT id, username, role FROM users').fetchall()
    except Exception as e:
        logger.error(f"Error admin_users: {e}")
        flash('Terjadi kesalahan.', 'danger')
        users = []
    finally:
        conn.close()

    return render_template('admin_users.html', users=users)

# DELETE USER
@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'admin':
        flash('Akses ditolak. Hanya admin.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    try:
        # Jangan hapus user admin
        user = conn.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
        if user['username'] == 'admin':
            flash('Tidak bisa menghapus user admin!', 'danger')
        else:
            # Hapus booking terkait terlebih dahulu
            conn.execute('DELETE FROM bookings WHERE user_id = ?', (user_id,))
            # Hapus riwayat booking
            conn.execute('DELETE FROM booking_history WHERE user_id = ?', (user_id,))
            # Hapus user
            conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            flash('User berhasil dihapus.', 'info')
    except Exception as e:
        logger.error(f"Error delete_user: {e}")
        flash('Gagal menghapus user.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('admin_users'))

# RUN FLASK
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
