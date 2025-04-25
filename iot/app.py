from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import logging
import requests
import time
import jwt
from datetime import datetime
from db import get_db_connection, init_db

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

# Konfigurasi ThingsBoard
THINGSBOARD_URL = "http://192.168.24.219:8080"
DEVICE_TOKEN = "bb05f420-1ffa-11f0-a0bc-33b4e39bb6f7"
USERNAME = "tenant@qtech.com"
PASSWORD = "tenant1140"

# Variabel global untuk menyimpan token
JWT_TOKEN = None
REFRESH_TOKEN = None

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Inisialisasi database
with app.app_context():
    init_db()
    conn = get_db_connection()
    try:
        conn.execute('ALTER TABLE bookings ADD COLUMN booking_time TEXT')
        conn.execute('ALTER TABLE bookings ADD COLUMN duration INTEGER')
        conn.execute('ALTER TABLE bookings ADD COLUMN remaining_duration INTEGER')
    except sqlite3.OperationalError:
        pass
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

# Jinja Filter: format angka
@app.template_filter('format_number')
def format_number(value):
    try:
        return "{:,}".format(int(value))
    except (ValueError, TypeError):
        return str(value)

# Fungsi untuk memeriksa masa berlaku token
def is_token_expired(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp = decoded.get("exp")
        current_time = int(time.time())
        return exp < current_time
    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        return True

# Fungsi untuk memperbarui token
def refresh_jwt_token():
    global JWT_TOKEN, REFRESH_TOKEN
    try:
        resp = requests.post(
            f"{THINGSBOARD_URL}/api/auth/token",
            headers={"Content-Type": "application/json"},
            json={"refreshToken": REFRESH_TOKEN},
            timeout=5
        )
        resp.raise_for_status()
        data = resp.json()
        JWT_TOKEN = data["token"]
        REFRESH_TOKEN = data["refreshToken"]
        logger.info("JWT Token refreshed successfully")
        return True
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        return False

# Fungsi untuk login ke ThingsBoard
def login_to_thingsboard():
    global JWT_TOKEN, REFRESH_TOKEN
    try:
        resp = requests.post(
            f"{THINGSBOARD_URL}/api/auth/login",
            headers={"Content-Type": "application/json"},
            json={"username": USERNAME, "password": PASSWORD},
            timeout=5
        )
        resp.raise_for_status()
        data = resp.json()
        JWT_TOKEN = data["token"]
        REFRESH_TOKEN = data["refreshToken"]
        logger.info("Logged in successfully")
        return True
    except Exception as e:
        logger.error(f"Error logging in: {e}")
        return False

# Fungsi untuk mendapatkan token yang valid
def get_valid_token():
    global JWT_TOKEN
    if JWT_TOKEN is None or is_token_expired(JWT_TOKEN):
        logger.info("JWT Token expired or not set, attempting to refresh")
        if REFRESH_TOKEN and refresh_jwt_token():
            return JWT_TOKEN
        logger.info("Refresh token failed, attempting to login")
        if login_to_thingsboard():
            return JWT_TOKEN
        raise Exception("Failed to obtain a valid token")
    return JWT_TOKEN

# Halaman beranda
@app.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# REGISTER
@app.route('/register', methods=['GET', 'POST'])
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
            flash('Registrasi berhasil! Silakan login.', 'info')
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
@app.route('/login', methods=['GET', 'POST'])
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
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
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
    user_id = session.get('user_id')
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

        duration = (hours * 60) + minutes
        total_price = (hours * 5000) + (minutes * 830)
        booking_time = datetime.now().strftime('%Y-%m-%d %H:%M')
        remaining_duration = duration

        # Update ThingsBoard
        token = get_valid_token()
        slot_number = '1' if slot_id == 'B2' else '2' if slot_id == 'A1' else '3' if slot_id == 'A4' else '0'
        booked_key = f"slot{slot_number}_booked"
        lamp_key = f"lamp{slot_number}"
        payload = {booked_key: True, lamp_key: False}
        resp = requests.post(
            f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/SHARED_SCOPE",
            headers={"X-Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=5
        )
        resp.raise_for_status()

        # Simpan ke database
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO bookings (user_id, slot_id, booking_time, duration, remaining_duration, total_price) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (session['user_id'], slot_id, booking_time, duration, remaining_duration, total_price)
        )
        conn.commit()
        conn.close()
        flash(f'Slot {slot_id} dibooked (Rp{total_price:,}).', 'success')

    except Exception as e:
        logger.error(f"Error booking slot: {e}")
        flash('Gagal booking slot.', 'danger')
        return redirect(url_for('dashboard'))

    return redirect(url_for('dashboard'))

# UNBOOK SLOT
@app.route('/unbook/<slot_id>', methods=['POST'])
def unbook_slot(slot_id):
    if 'user_id' not in session:
        flash('Silakan login dulu.', 'danger')
        return redirect(url_for('login'))

    try:
        # Update ThingsBoard
        token = get_valid_token()
        slot_number = '1' if slot_id == 'B2' else '2' if slot_id == 'A1' else '3' if slot_id == 'A4' else '0'
        booked_key = f"slot{slot_number}_booked"
        lamp_key = f"lamp{slot_number}"
        payload = {booked_key: False, lamp_key: True}
        resp = requests.post(
            f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/SHARED_SCOPE",
            headers={"X-Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=5
        )
        resp.raise_for_status()

        # Update database
        conn = get_db_connection()
        booking = conn.execute(
            'SELECT user_id, slot_id, booking_time, duration, total_price FROM bookings WHERE user_id = ? AND slot_id = ?',
            (session['user_id'], slot_id)
        ).fetchone()
        if booking:
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            conn.execute(
                'INSERT INTO booking_history (user_id, slot_id, booking_time, duration, total_price, end_time) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (booking['user_id'], booking['slot_id'], booking['booking_time'], booking['duration'], booking['total_price'], end_time)
            )
            conn.execute('DELETE FROM bookings WHERE user_id = ? AND slot_id = ?', (session['user_id'], slot_id))
            conn.commit()
        conn.close()
        flash(f'Slot {slot_id} dilepas.', 'info')

    except Exception as e:
        logger.error(f"Error unbooking slot: {e}")
        flash('Gagal melepas booking.', 'danger')

    return redirect(url_for('dashboard'))

# API STATUS
@app.route('/api/status')
def get_status():
    try:
        token = get_valid_token()
        # Ambil data dari ThingsBoard
        resp = requests.get(
            f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/values/timeseries",
            headers={"X-Authorization": f"Bearer {token}"},
            timeout=5
        )
        resp.raise_for_status()
        data = resp.json()
        attr_resp = requests.get(
            f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/values/attributes",
            headers={"X-Authorization": f"Bearer {token}"},
            timeout=5
        )
        attr_resp.raise_for_status()
        attr_data = attr_resp.json()
        booked = {"slot1_booked": False, "slot2_booked": False, "slot3_booked": False}
        for attr in attr_data:
            if attr["key"] == "slot1_booked":
                booked["slot1_booked"] = attr["value"]
            elif attr["key"] == "slot2_booked":
                booked["slot2_booked"] = attr["value"]
            elif attr["key"] == "slot3_booked":
                booked["slot3_booked"] = attr["value"]

        # Pastikan status booked di ThingsBoard sesuai dengan semua booking di database
        conn = get_db_connection()
        bookings = conn.execute('SELECT slot_id FROM bookings').fetchall()
        slot_ids = [booking['slot_id'] for booking in bookings]
        for slot_id in ['B2', 'A1', 'A4']:
            slot_number = '1' if slot_id == 'B2' else '2' if slot_id == 'A1' else '3'
            booked_key = f"slot{slot_number}_booked"
            is_booked = slot_id in slot_ids
            if booked[booked_key] != is_booked:
                payload = {booked_key: is_booked}
                requests.post(
                    f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/SHARED_SCOPE",
                    headers={"X-Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=5
                )

        # Auto-unbook berdasarkan waktu
        now = datetime.now()
        rows = conn.execute(
            'SELECT id, slot_id, user_id, booking_time, duration, remaining_duration, total_price FROM bookings'
        ).fetchall()
        expired_bookings = []
        for r in rows:
            booking_time = datetime.strptime(r['booking_time'], '%Y-%m-%d %H:%M')
            duration_seconds = r['duration'] * 60
            elapsed_seconds = (now - booking_time).total_seconds()
            remaining_seconds = duration_seconds - elapsed_seconds
            remaining_minutes = max(0, int(remaining_seconds / 60))
            conn.execute('UPDATE bookings SET remaining_duration = ? WHERE id = ?', (remaining_minutes, r['id']))
            if remaining_seconds <= 0:
                end_time = now.strftime('%Y-%m-%d %H:%M')
                conn.execute(
                    'INSERT INTO booking_history (user_id, slot_id, booking_time, duration, total_price, end_time) '
                    'VALUES (?, ?, ?, ?, ?, ?)',
                    (r['user_id'], r['slot_id'], r['booking_time'], r['duration'], r['total_price'], end_time)
                )
                conn.execute('DELETE FROM bookings WHERE id = ?', (r['id'],))
                expired_bookings.append({'slot_id': r['slot_id'], 'user_id': r['user_id']})
                # Update ThingsBoard untuk slot yang expired
                slot_number = '1' if r['slot_id'] == 'B2' else '2' if r['slot_id'] == 'A1' else '3' if r['slot_id'] == 'A4' else '0'
                booked_key = f"slot{slot_number}_booked"
                lamp_key = f"lamp{slot_number}"
                payload = {booked_key: False, lamp_key: True}
                requests.post(
                    f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/SHARED_SCOPE",
                    headers={"X-Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=5
                )
        conn.commit()

        # Ambil data booking untuk ditampilkan di dashboard
        rows2 = conn.execute('''
            SELECT b.slot_id, b.user_id, b.booking_time, b.duration, b.remaining_duration, b.total_price, u.username
            FROM bookings b JOIN users u ON b.user_id = u.id
        ''').fetchall()
        conn.close()

        bookings_list = []
        for b in rows2:
            bookings_list.append({
                'slot_id': b['slot_id'],
                'user_id': b['user_id'],
                'username': b['username'] if session.get('role') == 'admin' else None,
                'booking_time': b['booking_time'],
                'duration': b['duration'],
                'remaining_duration': b['remaining_duration'],
                'total_price': b['total_price'],
            })

        return jsonify({
            'slot1': {
                'occupied': data['slot1_occupied'][0]['value'],
                'booked': booked['slot1_booked']
            },
            'slot2': {
                'occupied': data['slot2_occupied'][0]['value'],
                'booked': booked['slot2_booked']
            },
            'slot3': {
                'occupied': data['slot3_occupied'][0]['value'],
                'booked': booked['slot3_booked']
            },
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
            FROM booking_history WHERE user_id = ? ORDER BY booking_time DESC
        ''', (session['user_id'],)).fetchall()
        history = [{'slot_id': b['slot_id'], 'booking_time': b['booking_time'], 'duration': b['duration'], 'total_price': b['total_price'], 'end_time': b['end_time']} for b in data]
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
            FROM booking_history b JOIN users u ON b.user_id = u.id
            ORDER BY b.booking_time DESC
        ''').fetchall()
        history = [{'slot_id': b['slot_id'], 'username': b['username'], 'booking_time': b['booking_time'], 'duration': b['duration'], 'total_price': b['total_price'], 'end_time': b['end_time']} for b in data]
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
            FROM bookings b JOIN users u ON b.user_id = u.id
        ''').fetchall()
        bookings = [{'id': b['id'], 'slot_id': b['slot_id'], 'booking_time': b['booking_time'], 'duration': b['duration'], 'remaining_duration': b['remaining_duration'], 'total_price': b['total_price'], 'timestamp': b['timestamp'], 'username': b['username']} for b in data]
    except Exception as e:
        logger.error(f"Error admin_panel: {e}")
        flash('Gagal memuat data.', 'danger')
        bookings = []
    finally:
        conn.close()
    return render_template('admin_panel.html', bookings=bookings)

# ADMIN UNBOOK
@app.route('/admin/unbook/<int:booking_id>', methods=['POST'])
def admin_unbook(booking_id):
    if session.get('role') != 'admin':
        flash('Akses ditolak.', 'danger')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    try:
        booking = conn.execute(
            'SELECT user_id, slot_id, booking_time, duration, total_price FROM bookings WHERE id = ?',
            (booking_id,)
        ).fetchone()
        if booking:
            slot_id = booking['slot_id']
            token = get_valid_token()
            slot_number = '1' if slot_id == 'B2' else '2' if slot_id == 'A1' else '3' if slot_id == 'A4' else '0'
            booked_key = f"slot{slot_number}_booked"
            lamp_key = f"lamp{slot_number}"
            payload = {booked_key: False, lamp_key: True}
            resp = requests.post(
                f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/SHARED_SCOPE",
                headers={"X-Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
                timeout=5
            )
            resp.raise_for_status()
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            conn.execute(
                'INSERT INTO booking_history (user_id, slot_id, booking_time, duration, total_price, end_time) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (booking['user_id'], booking['slot_id'], booking['booking_time'], booking['duration'], booking['total_price'], end_time)
            )
            conn.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
            conn.commit()
            flash('Booking dihapus oleh admin.', 'info')
    except Exception as e:
        logger.error(f"Error admin_unbook: {e}")
        flash('Gagal menghapus.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('admin_panel'))

# ADMIN USERS
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
        user = conn.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
        if user['username'] == 'admin':
            flash('Tidak bisa menghapus user admin!', 'danger')
        else:
            conn.execute('DELETE FROM bookings WHERE user_id = ?', (user_id,))
            conn.execute('DELETE FROM booking_history WHERE user_id = ?', (user_id,))
            conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            flash('User berhasil dihapus.', 'info')
    except Exception as e:
        logger.error(f"Error delete_user: {e}")
        flash('Gagal menghapus user.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('admin_users'))

# CONFIRM SLOT
@app.route('/api/confirm_slot/<int:slot>/<string:confirm>', methods=['POST'])
def confirm_slot(slot, confirm):
    try:
        token = get_valid_token()
        booked_key = f"slot{slot}_booked"
        lamp_key = f"lamp{slot}"
        payload = {}
        if confirm.lower() == "yes":
            payload = {
                booked_key: False,
                lamp_key: True
            }
            # Auto-unbook slot dari database
            slot_id = 'B2' if slot == 1 else 'A1' if slot == 2 else 'A4'
            conn = get_db_connection()
            booking = conn.execute(
                'SELECT user_id, slot_id, booking_time, duration, total_price FROM bookings WHERE slot_id = ?',
                (slot_id,)
            ).fetchone()
            if booking:
                end_time = datetime.now().strftime('%Y-%m-%d %H:%M')
                conn.execute(
                    'INSERT INTO booking_history (user_id, slot_id, booking_time, duration, total_price, end_time) '
                    'VALUES (?, ?, ?, ?, ?, ?)',
                    (booking['user_id'], booking['slot_id'], booking['booking_time'], booking['duration'], booking['total_price'], end_time)
                )
                conn.execute('DELETE FROM bookings WHERE slot_id = ?', (slot_id,))
                conn.commit()
            conn.close()
        else:
            payload = {
                booked_key: True,
                lamp_key: False
            }
        resp = requests.post(
            f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/SHARED_SCOPE",
            headers={"X-Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=5
        )
        resp.raise_for_status()
        return jsonify({"status": "success", "message": f"Slot {slot} confirmation: {confirm}"})
    except Exception as e:
        logger.error(f"Error confirming slot: {e}")
        return jsonify({"error": "Failed to confirm slot"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=81)
