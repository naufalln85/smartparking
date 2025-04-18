from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'secretkey123'  # Ganti dengan yang lebih aman di produksi
DATABASE = os.path.join('instance', 'parking.db')
BLYNK_TOKEN = "xbC-JEuKmxpdry7iTOd8n2h_bCsaOf-I"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Inisialisasi DB dan admin
with app.app_context():
    if not os.path.exists('instance'):
        os.makedirs('instance')
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            slot_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Tambahkan admin jika belum ada
    admin = cur.execute('SELECT * FROM users WHERE username = "admin"').fetchone()
    if not admin:
        admin_pw = generate_password_hash("admin123#")
        cur.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                    ("admin", admin_pw, "admin"))
    conn.commit()
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
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    username = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Login berhasil!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau password salah!', 'danger')
            return render_template('login.html', username=username)

    return render_template('login.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    flash('Apakah Anda mau login kembali?', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    bookings = conn.execute('SELECT * FROM bookings').fetchall()
    conn.close()

    user_id = session.get('user_id')
    return render_template('dashboard.html', bookings=bookings, user_id=user_id)

@app.route('/book/<slot_id>', methods=['POST'])
def book_slot(slot_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('INSERT INTO bookings (user_id, slot_id) VALUES (?, ?)', (session['user_id'], slot_id))
    conn.commit()
    conn.close()
    flash(f'Slot {slot_id} berhasil dibooking!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/unbook/<slot_id>', methods=['POST'])
def unbook_slot(slot_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM bookings WHERE user_id = ? AND slot_id = ?', (session['user_id'], slot_id))
    conn.commit()
    conn.close()
    flash(f'Slot {slot_id} berhasil dilepas!', 'info')
    return redirect(url_for('dashboard'))

@app.route('/admin/users', methods=['GET', 'POST'])
def admin_users():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash("Username dan password tidak boleh kosong.")
            return redirect(url_for('admin_users'))

        existing_user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if existing_user:
            flash("Username sudah ada.")
        else:
            hashed = generate_password_hash(password)
            conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                         (username, hashed, "user"))
            conn.commit()
            flash("User berhasil ditambahkan.")

    users = conn.execute("SELECT id, username, role FROM users").fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'username' not in session or session.get('role') != 'admin':
        flash("Akses ditolak.", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    conn.execute('DELETE FROM bookings WHERE user_id = ?', (user_id,))
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    flash("User berhasil dihapus.", "info")
    return redirect(url_for('admin_users'))

@app.route('/api/status')
def get_status():
    try:
        import requests
        pins = ['v0', 'v1', 'v2']
        status = {}
        for pin in pins:
            res = requests.get(f'https://blynk.cloud/external/api/get?token={BLYNK_TOKEN}&{pin}')
            status[pin] = res.text.strip()

        conn = get_db_connection()
        bookings = conn.execute('''
            SELECT bookings.slot_id, bookings.user_id, users.username
            FROM bookings
            JOIN users ON bookings.user_id = users.id
        ''').fetchall()
        conn.close()

        is_admin = session.get("role") == "admin"
        bookings_list = [
            {
                "slot_id": b["slot_id"],
                "user_id": b["user_id"],
                "username": b["username"] if is_admin else None
            }
            for b in bookings
        ]

        return jsonify({
            "v0": status['v0'],
            "v1": status['v1'],
            "v2": status['v2'],
            "bookings": bookings_list,
            "current_user": session.get("user_id")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin')
def admin_panel():
    if 'username' not in session or session.get('role') != 'admin':
        flash("Akses ditolak. Hanya admin yang bisa mengakses halaman ini.", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    bookings = conn.execute('''
        SELECT bookings.id, bookings.slot_id, bookings.timestamp, users.username
        FROM bookings
        JOIN users ON bookings.user_id = users.id
    ''').fetchall()
    conn.close()
    return render_template('admin_panel.html', bookings=bookings)

@app.route('/admin/unbook/<int:booking_id>', methods=['POST'])
def admin_unbook(booking_id):
    if 'username' not in session or session.get('role') != 'admin':
        flash("Akses ditolak.", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    conn.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
    conn.commit()
    conn.close()
    flash("Booking berhasil dihapus.", "info")
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
