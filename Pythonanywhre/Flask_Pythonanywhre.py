from flask import Flask, request, jsonify
import json
import os

# --- PENTING: Ganti 'syakhish' dengan username PythonAnywhere Anda ---
USERNAME = "syakhish"
DATA_FILE = f'/home/{USERNAME}/mysite/weather_data.json'
# --------------------------------------------------------------------

app = Flask(__name__)

# Endpoint untuk menerima data dari ESP32
@app.route('/update_data', methods=['POST'])
def update_data():
    try:
        new_data = request.get_json(force=True) # force=True untuk membantu jika header salah

        all_data = []
        # Baca data lama (jika ada)
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                try:
                    all_data = json.load(f)
                except json.JSONDecodeError:
                    all_data = [] # Jika file korup, mulai dari awal

        # Tambahkan data baru
        all_data.append(new_data)

        # Batasi hanya menyimpan 100 data terakhir
        if len(all_data) > 1000:
            all_data = all_data[-1000:]

        # Simpan kembali ke file
        with open(DATA_FILE, 'w') as f:
            json.dump(all_data, f)

        return "Data received!", 200
    except Exception as e:
        return f"Error processing data: {str(e)}", 400

# Endpoint untuk dibaca oleh Streamlit
@app.route('/get_data', methods=['GET'])
def get_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            all_data = json.load(f)
        return jsonify(all_data)
    else:
        return jsonify([]) # Kirim array kosong jika file belum ada