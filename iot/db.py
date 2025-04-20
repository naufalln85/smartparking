# db.py
import sqlite3
import os
import logging
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)
DATABASE = os.path.join('instance', 'parking.db')

def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        logger.debug("Database connection established")
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

def init_db():
    if not os.path.exists('instance'):
        os.makedirs('instance')
        logger.debug("Created instance directory")

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Buat tabel users
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user'
            )
        ''')

        # Buat tabel bookings dengan skema baru
        cur.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                slot_id TEXT,
                booking_time TEXT,
                duration INTEGER,
                remaining_duration INTEGER,
                total_price INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')

        # Periksa skema tabel bookings dan lakukan migrasi jika perlu
        cursor = conn.execute('PRAGMA table_info(bookings)')
        existing_columns = [col[1] for col in cursor.fetchall()]

        # Tambah kolom baru jika belum ada
        required_columns = {
            'booking_time': 'TEXT',
            'duration': 'INTEGER',
            'remaining_duration': 'INTEGER',
            'total_price': 'INTEGER'
        }
        for col_name, col_type in required_columns.items():
            if col_name not in existing_columns:
                cur.execute(f'ALTER TABLE bookings ADD COLUMN {col_name} {col_type}')

        # Jika ada kolom lama (start_time, end_time, status), migrasi data
        if 'start_time' in existing_columns or 'end_time' in existing_columns:
            bookings = cur.execute('SELECT * FROM bookings').fetchall()
            for booking in bookings:
                if booking['booking_time'] is None and booking['start_time']:
                    # Gunakan start_time sebagai booking_time
                    booking_time = booking['start_time']
                    # Hitung duration dari total_price (Rp5,000 per jam)
                    duration = booking['total_price'] // 5000 if booking['total_price'] else 0
                    # Hitung remaining_duration
                    if booking['start_time'] and duration > 0:
                        from datetime import datetime
                        start_dt = datetime.strptime(booking['start_time'], '%Y-%m-%d %H:%M')
                        now = datetime.now()
                        elapsed_seconds = (now - start_dt).total_seconds()
                        duration_seconds = duration * 3600
                        remaining_seconds = max(0, duration_seconds - elapsed_seconds)
                    else:
                        remaining_seconds = 0

                    # Update data
                    cur.execute('''
                        UPDATE bookings
                        SET booking_time = ?, duration = ?, remaining_duration = ?
                        WHERE id = ?
                    ''', (booking_time, duration, remaining_seconds, booking['id']))

        # (Opsional) Hapus kolom lama jika ada
        columns_to_drop = ['start_time', 'end_time', 'status']
        for col in columns_to_drop:
            if col in existing_columns:
                try:
                    # SQLite tidak mendukung DROP COLUMN secara langsung, jadi kita buat tabel baru
                    cur.execute('''
                        CREATE TABLE bookings_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            slot_id TEXT,
                            booking_time TEXT,
                            duration INTEGER,
                            remaining_duration INTEGER,
                            total_price INTEGER,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY(user_id) REFERENCES users(id)
                        )
                    ''')
                    cur.execute('''
                        INSERT INTO bookings_new (id, user_id, slot_id, booking_time, duration, remaining_duration, total_price, timestamp)
                        SELECT id, user_id, slot_id, booking_time, duration, remaining_duration, total_price, timestamp
                        FROM bookings
                    ''')
                    cur.execute('DROP TABLE bookings')
                    cur.execute('ALTER TABLE bookings_new RENAME TO bookings')
                    break  # Keluar dari loop setelah migrasi
                except Exception as e:
                    logger.warning(f"Could not drop column {col}: {e}")

        # Pastikan admin ada
        admin = cur.execute('SELECT * FROM users WHERE username = "admin"').fetchone()
        if not admin:
            admin_pw = generate_password_hash("admin123#")
            cur.execute(
                'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                ("admin", admin_pw, "admin")
            )
        else:
            # Reset password admin jika sudah ada (opsional, hapus jika tidak diperlukan)
            admin_pw = generate_password_hash("admin123#")
            cur.execute(
                'UPDATE users SET password = ? WHERE username = "admin"',
                (admin_pw,)
            )

        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()
