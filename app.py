import streamlit as st
import pandas as pd
import time
import os

# ----------------- KONFIGURASI HALAMAN -----------------
# Mengatur judul tab, ikon, dan layout halaman.
# Ini harus menjadi perintah pertama di skrip Streamlit Anda.
st.set_page_config(
    page_title="Dasbor Monitoring Cuaca",
    page_icon="☁️",
    layout="wide",
)

# ----------------- JUDUL APLIKASI -----------------
st.title("☁️ Dasbor Monitoring Cuaca Real-Time")
st.markdown("---")


# ----------------- FUNGSI BACA DATA -----------------
# Fungsi ini bertanggung jawab untuk mencari dan membaca file CSV.
def baca_data():
    nama_file = 'data_contoh.csv'
    if not os.path.exists(nama_file):
        st.error(f"File '{nama_file}' tidak ditemukan. Pastikan file berada di folder yang sama dengan app.py.")
        return None
    
    try:
        df = pd.read_csv(nama_file)
        if df.empty:
            st.warning(f"File '{nama_file}' kosong atau formatnya salah. Mohon periksa kembali isinya.")
            return None
        return df
    except Exception as e:
        st.error(f"Gagal membaca file CSV. Error: {e}")
        return None


# ----------------- LAYOUT UTAMA APLIKASI -----------------
placeholder = st.empty()


# ----------------- LOOP UTAMA (UNTUK REAL-TIME) -----------------
while True:
    df = baca_data()
    
    # Hanya lanjutkan jika data berhasil dibaca (tidak None)
    if df is not None:
        with placeholder.container():
            # --- TAMPILAN DATA TERKINI (METRIK) ---
            data_terkini = df.iloc[-1]
            
            st.subheader("📍 Data Sensor Terkini")
            
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric(label="🌡️ Suhu (°C)", value=f"{data_terkini['suhu']:.1f}")
            k2.metric(label="💧 Kelembapan (%)", value=f"{data_terkini['kelembapan']:.1f}")
            k3.metric(label="🌀 Tekanan (hPa)", value=f"{data_terkini['tekanan']:.1f}")
            k4.metric(label="☀️ Cahaya (lux)", value=f"{data_terkini['cahaya']:.0f}")
            k5.metric(label="☔️ IMCS", value=f"{data_terkini['imcs']:.2f}", 
                      help="Indeks di atas 1.0 menunjukkan peluang hujan tinggi")

            st.markdown("---")

            # --- TAMPILAN GRAFIK HISTORIS ---
            st.subheader("📈 Grafik Historis Data Sensor")
            # Mengubah kolom 'timestamp' menjadi format datetime yang benar
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            # Mengatur 'timestamp' sebagai index untuk sumbu X grafik
            st.line_chart(df.set_index('timestamp')[['suhu', 'kelembapan', 'tekanan']])

            # --- TAMPILAN DATA MENTAH (TABEL) ---
            st.subheader("📋 Data Mentah (10 Data Terakhir)")
            st.dataframe(df.tail(10))

    # Tunggu 10 detik sebelum mengulang loop (refresh data).
    time.sleep(10)
