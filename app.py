import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# ----------------- KONFIGURASI HALAMAN -----------------
st.set_page_config(
    page_title="Dasbor Monitoring Cuaca",
    page_icon="☁️",
    layout="wide",
)

# --- PENTING: GANTI 'syakhish' DENGAN USERNAME PYTHONANYWHERE ANDA ---
API_URL = "http://syakhish.pythonanywhere.com/get_data"
# --------------------------------------------------------------------

# ----------------- JUDUL APLIKASI -----------------
st.title("☁️ Dasbor Monitoring Cuaca Real-Time")
st.markdown("---")

# ----------------- FUNGSI BACA DATA DARI API -----------------
# Fungsi ini mengambil data dari server API Anda, dengan cache 15 detik.
@st.cache_data(ttl=15)
def baca_data_dari_api():
    try:
        # Melakukan permintaan ke URL API
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()  # Akan error jika status code bukan 200 OK
        data = response.json()
        
        # Jika tidak ada data, kembalikan None
        if not data:
            st.warning("Menunggu data masuk dari sensor...")
            return None
        
        # Ubah data JSON menjadi DataFrame pandas
        df = pd.DataFrame(data)
        
        # Ubah UNIX timestamp dari ESP32 menjadi format tanggal dan waktu yang bisa dibaca
        # Tambah 7 jam untuk konversi dari UTC ke zona waktu WIB (UTC+7)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=7)
        return df
        
    except requests.exceptions.RequestException as e:
        st.error(f"Gagal terhubung ke server API: {e}")
        return None
    except Exception as e:
        st.error(f"Terjadi error saat memproses data dari API: {e}")
        return None

# ----------------- LAYOUT UTAMA APLIKASI -----------------
placeholder = st.empty()

# ----------------- LOOP UTAMA (UNTUK REAL-TIME) -----------------
while True:
    # Panggil fungsi untuk mendapatkan data terbaru dari API
    df = baca_data_dari_api()
    
    # Hanya lanjutkan jika data berhasil dibaca dan tidak kosong
    if df is not None and not df.empty:
        with placeholder.container():
            # --- TAMPILAN DATA TERKINI (METRIK) ---
            data_terkini = df.iloc[-1]
            
            # Tampilkan waktu data terakhir diperbarui
            st.subheader(f"📍 Data Sensor Terkini (Diperbarui pada: {data_terkini['timestamp'].strftime('%d %b %Y, %H:%M:%S')} WIB)")
            
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric(label="🌡️ Suhu (°C)", value=f"{data_terkini['suhu']:.1f}")
            k2.metric(label="💧 Kelembapan (%)", value=f"{data_terkini['kelembapan']:.1f}")
            k3.metric(label="🌀 Tekanan (hPa)", value=f"{data_terkini['tekanan']:.1f}")
            k4.metric(label="☀️ Cahaya (Analog)", value=f"{data_terkini['cahaya']:.0f}")
            k5.metric(label="☔️ IMCS", value=f"{data_terkini['imcs']:.2f}", 
                      help="Indeks di atas 1.0 menunjukkan peluang hujan tinggi")

            st.markdown("---")

            # --- TAMPILAN GRAFIK HISTORIS ---
            st.subheader("📈 Grafik Historis Data Sensor")
            df_grafik = df.set_index('timestamp')
            st.line_chart(df_grafik[['suhu', 'kelembapan', 'tekanan']])

            # --- TAMPILAN DATA MENTAH (TABEL) ---
            st.subheader("📋 Data Mentah (10 Data Terakhir)")
            # Mengurutkan data dari yang terbaru ke terlama untuk tampilan tabel
            st.dataframe(df.sort_values(by='timestamp', ascending=False).head(10).set_index('timestamp'))

    # Tunggu 15 detik sebelum mencoba mengambil data lagi
    time.sleep(15)

