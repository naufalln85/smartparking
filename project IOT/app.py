from flask import Flask, render_template_string
import requests

app = Flask(__name__)

@app.route("/")
def index():
    try:
        response = requests.get(BLYNK_URL)
        status = response.text.strip()
        color = "green" if status == "Kosong" else "red"
    except:
        status = "Tidak Dapat Terhubung"
        color = "gray"
    return render_template_string(HTML, status=status, color=color)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)