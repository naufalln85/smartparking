from flask import Flask, jsonify, render_template
import requests
import logging
import time
import jwt

app = Flask(__name__)

# Konfigurasi ThingsBoard
THINGSBOARD_URL = "http://192.168.1.7:8080"
DEVICE_TOKEN = "9f1dee50-2065-11f0-b7c8-7d49e6997362"
USERNAME = "tenant@thingsboard.org"
PASSWORD = "tenant"

# Variabel global untuk menyimpan token
JWT_TOKEN = None  # Akan diisi saat login
REFRESH_TOKEN = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Fungsi untuk memperbarui token menggunakan refreshToken
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

# Fungsi untuk login ulang dan mendapatkan token baru
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

# Endpoint untuk dashboard
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

# Endpoint untuk mengambil status parkir dari ThingsBoard
@app.route('/api/parking_status')
def get_parking_status():
    try:
        token = get_valid_token()
        resp = requests.get(
            f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/values/timeseries",
            headers={"X-Authorization": f"Bearer {token}"},
            timeout=5
        )
        resp.raise_for_status()
        data = resp.json()
        # Ambil status booking dari Shared Attributes
        attr_resp = requests.get(
            f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/values/attributes",
            headers={"X-Authorization": f"Bearer {token}"},
            timeout=5
        )
        attr_resp.raise_for_status()
        attr_data = attr_resp.json()
        booked = {
            "slot1_booked": False,
            "slot2_booked": False,
            "slot3_booked": False
        }
        for attr in attr_data:
            if attr["key"] == "slot1_booked":
                booked["slot1_booked"] = attr["value"]
            elif attr["key"] == "slot2_booked":
                booked["slot2_booked"] = attr["value"]
            elif attr["key"] == "slot3_booked":
                booked["slot3_booked"] = attr["value"]
        return jsonify({
            "slot1": {
                "distance": data["slot1_distance"][0]["value"],
                "occupied": data["slot1_occupied"][0]["value"],
                "booked": booked["slot1_booked"]
            },
            "slot2": {
                "distance": data["slot2_distance"][0]["value"],
                "occupied": data["slot2_occupied"][0]["value"],
                "booked": booked["slot2_booked"]
            },
            "slot3": {
                "distance": data["slot3_distance"][0]["value"],
                "occupied": data["slot3_occupied"][0]["value"],
                "booked": booked["slot3_booked"]
            }
        })
    except Exception as e:
        logger.error(f"Error fetching parking status: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500

# Endpoint untuk booking slot
@app.route('/api/book_slot/<int:slot>', methods=['POST'])
def book_slot(slot):
    try:
        token = get_valid_token()
        booked_key = f"slot{slot}_booked"
        lamp_key = f"lamp{slot}"
        payload = {
            booked_key: True,
            lamp_key: False  # Matikan lampu saat booking
        }
        resp = requests.post(
            f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/SHARED_SCOPE",
            headers={
                "X-Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=5
        )
        resp.raise_for_status()
        return jsonify({"status": "success", "message": f"Slot {slot} booked"})
    except Exception as e:
        logger.error(f"Error booking slot: {e}")
        return jsonify({"error": "Failed to book slot"}), 500

# Endpoint untuk unbooking slot
@app.route('/api/unbook_slot/<int:slot>', methods=['POST'])
def unbook_slot(slot):
    try:
        token = get_valid_token()
        booked_key = f"slot{slot}_booked"
        lamp_key = f"lamp{slot}"
        payload = {
            booked_key: False,  # Reset booking
            lamp_key: True     # Nyalakan lampu
        }
        resp = requests.post(
            f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/SHARED_SCOPE",
            headers={
                "X-Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=5
        )
        resp.raise_for_status()
        return jsonify({"status": "success", "message": f"Slot {slot} unbooked"})
    except Exception as e:
        logger.error(f"Error unbooking slot: {e}")
        return jsonify({"error": "Failed to unbook slot"}), 500

# Endpoint untuk konfirmasi pop-up
@app.route('/api/confirm_slot/<int:slot>/<string:confirm>', methods=['POST'])
def confirm_slot(slot, confirm):
    try:
        token = get_valid_token()
        booked_key = f"slot{slot}_booked"
        lamp_key = f"lamp{slot}"
        payload = {}
        if confirm.lower() == "yes":
            payload = {
                booked_key: False,  # Reset booking
                lamp_key: True     # Nyalakan lampu
            }
        else:
            payload = {
                booked_key: True,  # Tetap booked
                lamp_key: False    # Lampu tetap mati
            }
        resp = requests.post(
            f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/SHARED_SCOPE",
            headers={
                "X-Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=5
        )
        resp.raise_for_status()
        return jsonify({"status": "success", "message": f"Slot {slot} confirmation: {confirm}"})
    except Exception as e:
        logger.error(f"Error confirming slot: {e}")
        return jsonify({"error": "Failed to confirm slot"}), 500

# Endpoint untuk mengontrol lampu
@app.route('/api/control_lamp/<int:slot>/<string:state>', methods=['POST'])
def control_lamp(slot, state):
    try:
        token = get_valid_token()
        lamp_key = f"lamp{slot}"
        state_bool = state.lower() == "true"
        payload = {lamp_key: state_bool}
        resp = requests.post(
            f"{THINGSBOARD_URL}/api/plugins/telemetry/DEVICE/{DEVICE_TOKEN}/SHARED_SCOPE",
            headers={
                "X-Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=5
        )
        resp.raise_for_status()
        return jsonify({"status": "success", "message": f"Lamp {slot} set to {state}"})
    except Exception as e:
        logger.error(f"Error controlling lamp: {e}")
        return jsonify({"error": "Failed to control lamp"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)