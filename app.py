import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import os # Pastikan os diimpor jika belum

# ----------------- KONFIGURASI HALAMAN -----------------
st.set_page_config(
    page_title="Dasbor Monitoring Cuaca",
    page_icon="☁️",
    layout="wide",
)

# --- PASTIKAN USERNAME ANDA BENAR ---
API_URL = "http://syakhish.pythonanywhere.com/get_data"
# ------------------------------------

# ----------------- JUDUL APLIKASI -----------------
st.title("☁️ Dasbor Monitoring Cuaca Real-Time")
st.markdown("---")

# ----------------- FUNGSI BACA DATA DARI API -----------------
# Cache data selama 15 detik untuk mengurangi beban API
@st.cache_data(ttl=15)
def baca_data_dari_api():
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            st.warning("Menunggu data masuk dari sensor...")
            return None
        
        df = pd.DataFrame(data)
        
        # Konversi UNIX timestamp ke Datetime WIB (UTC+7)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=7)
        return df
        
    except requests.exceptions.RequestException as e:
        st.error(f"Gagal terhubung ke server API: {e}")
        return None
    except Exception as e:
        st.error(f"Terjadi error saat memproses data dari API: {e}")
        return None

# ----------------- FUNGSI PENENTU STATUS CUACA -----------------
def tentukan_status_cuaca(data):
    """ Menganalisis data sensor terkini dan memberikan kesimpulan status cuaca. """
    imcs = data.get('imcs', 0) # Gunakan .get() untuk keamanan jika kunci tidak ada
    cahaya = data.get('cahaya', 4095) # Nilai analog TEMT6000 (0-4095), default gelap
    kelembapan = data.get('kelembapan', 0)
    
    # PERHATIAN: Nilai ambang batas cahaya ini HANYA PERKIRAAN. Sesuaikan!
    # Ingat: Semakin KECIL nilai analog TEMT6000, semakin TERANG.
    AMBANG_CERAH = 800
    AMBANG_BERAWAN = 2000
    AMBANG_MENDUNG = 3000
    AMBANG_MALAM = 3800 # Di atas ini diasumsikan malam
    
    if cahaya > AMBANG_MALAM:
        return "🌃 Malam Hari"
    elif imcs > 1.05 and cahaya > AMBANG_MENDUNG:
        if kelembapan > 90:
             return "🌧️ Hujan Deras"
        else:
             return "🌦️ Hujan Ringan"
    elif imcs > 0.95 and cahaya > AMBANG_BERAWAN:
        return "☁️ Mendung (Potensi Hujan)"
    elif cahaya < AMBANG_CERAH:
        if kelembapan < 70:
            return "☀️ Cerah"
        else:
            return "🌤️ Cerah Berawan (Lembab)"
    elif cahaya < AMBANG_BERAWAN:
        return "🌥️ Cerah Berawan"
    elif cahaya < AMBANG_MENDUNG:
        return "☁️ Berawan"
    else: # Kondisi cahaya di atas AMBANG_MENDUNG tapi imcs tidak tinggi
         return "🌫️ Sangat Mendung / Berkabut"

# ----------------- LAYOUT UTAMA APLIKASI -----------------
placeholder = st.empty()

# ----------------- LOOP UTAMA (UNTUK REAL-TIME) -----------------
while True:
    df = baca_data_dari_api()
    
    if df is not None and not df.empty:
        with placeholder.container():
            # --- DATA TERKINI & KESIMPULAN ---
            data_terkini = df.iloc[-1]
            status_cuaca = tentukan_status_cuaca(data_terkini)
            
            waktu_update = data_terkini['timestamp'].strftime('%d %b %Y, %H:%M:%S')
            
            # Kolom untuk waktu update dan kesimpulan
            col1, col2 = st.columns([3, 2]) # Buat 2 kolom
            with col1:
                st.subheader(f"📍 Data Sensor Terkini")
                st.caption(f"(Diperbarui pada: {waktu_update} WIB)")
            with col2:
                 st.subheader(f"Kesimpulan Cuaca:")
                 st.header(status_cuaca) # Tampilkan kesimpulan dengan font lebih besar

            st.markdown("---") # Garis pemisah

            # --- METRIK DETAIL ---
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric(label="🌡️ Suhu (°C)", value=f"{data_terkini.get('suhu', 'N/A'):.1f}")
            k2.metric(label="💧 Kelembapan (%)", value=f"{data_terkini.get('kelembapan', 'N/A'):.1f}")
            k3.metric(label="🌀 Tekanan (hPa)", value=f"{data_terkini.get('tekanan', 'N/A'):.1f}")
            k4.metric(label="☀️ Cahaya (Analog)", value=f"{data_terkini.get('cahaya', 'N/A'):.0f}", help="Nilai 0-4095. Semakin kecil = semakin terang")
            k5.metric(label="☔️ IMCS", value=f"{data_terkini.get('imcs', 'N/A'):.2f}",
                      help="Indeks di atas 1.0 menunjukkan peluang hujan tinggi")

            st.markdown("---")

            # --- GRAFIK HISTORIS ---
            st.subheader("📈 Grafik Historis Data Sensor")
            # Pastikan kolom timestamp ada sebelum dijadikan index
            if 'timestamp' in df.columns:
                df_grafik = df.set_index('timestamp')
                # Pilih kolom yang pasti ada di data Anda
                kolom_grafik = ['suhu', 'kelembapan', 'tekanan']
                kolom_valid = [kol for kol in kolom_grafik if kol in df_grafik.columns]
                if kolom_valid:
                     st.line_chart(df_grafik[kolom_valid])
                else:
                     st.warning("Kolom data untuk grafik tidak ditemukan.")
            else:
                st.warning("Kolom 'timestamp' tidak ditemukan untuk membuat grafik.")


            # --- DATA MENTAH ---
            st.subheader("📋 Data Mentah (10 Data Terakhir)")
            if 'timestamp' in df.columns:
                st.dataframe(df.sort_values(by='timestamp', ascending=False).head(10).set_index('timestamp'))
            else:
                 st.dataframe(df.tail(10)) # Tampilkan tanpa index jika timestamp bermasalah

    # Tunggu 15 detik sebelum refresh
    time.sleep(15)

