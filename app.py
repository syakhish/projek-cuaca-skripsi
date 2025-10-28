import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import os

# ----------------- KONFIGURASI HALAMAN -----------------
st.set_page_config(
    page_title="Dasbor Monitoring Cuaca",
    page_icon="🌦️",
    layout="wide",
)

# --- PASTIKAN USERNAME ANDA BENAR ---
API_URL = "http://syakhish.pythonanywhere.com/get_data"
# ------------------------------------

# ----------------- JUDUL APLIKASI -----------------
st.title("🌦️ Dasbor Monitoring Cuaca Real-Time")
st.markdown("---")

# ----------------- FUNGSI BACA DATA DARI API -----------------
@st.cache_data(ttl=15) # Cache data selama 15 detik
def baca_data_dari_api():
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data:
            # st.warning("Menunggu data masuk dari sensor...") # Komentari agar tidak terlalu ramai
            return None

        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=7)
        return df

    except requests.exceptions.RequestException as e:
        st.error(f"Gagal terhubung ke server API: {e}")
        return None
    except Exception as e:
        st.error(f"Terjadi error saat memproses data dari API: {e}")
        return None

# ----------------- FUNGSI PENENTU STATUS CUACA & EMOJI -----------------
def tentukan_status_cuaca(data):
    imcs = data.get('imcs', 0)
    cahaya = data.get('cahaya', 4095)
    kelembapan = data.get('kelembapan', 0)

    # PERKIRAAN AMBANG BATAS (Sesuaikan!)
    AMBANG_CERAH = 800
    AMBANG_BERAWAN = 2000
    AMBANG_MENDUNG = 3000
    AMBANG_MALAM = 3800

    if cahaya > AMBANG_MALAM:
        return "Malam Hari", "🌃"
    elif imcs > 1.05 and cahaya > AMBANG_MENDUNG:
        if kelembapan > 90:
             return "Hujan Deras", "🌧️"
        else:
             return "Hujan Ringan", "🌦️"
    elif imcs > 0.95 and cahaya > AMBANG_BERAWAN:
        return "Mendung (Potensi Hujan)", "☁️"
    elif cahaya < AMBANG_CERAH:
        if kelembapan < 70:
            return "Cerah", "☀️"
        else:
            return "Cerah Berawan (Lembab)", "🌤️"
    elif cahaya < AMBANG_BERAWAN:
        return "Cerah Berawan", "🌥️"
    elif cahaya < AMBANG_MENDUNG:
        return "Berawan", "☁️"
    else:
         return "Sangat Mendung / Berkabut", "🌫️"

# ----------------- LAYOUT UTAMA APLIKASI -----------------
placeholder = st.empty()

# ----------------- LOOP UTAMA (UNTUK REAL-TIME) -----------------
while True:
    df = baca_data_dari_api()

    if df is not None and not df.empty:
        with placeholder.container():
            # --- DATA TERKINI & KESIMPULAN ---
            data_terkini = df.iloc[-1]
            status_text, status_emoji = tentukan_status_cuaca(data_terkini)

            waktu_update = data_terkini['timestamp'].strftime('%d %b %Y, %H:%M:%S')

            col1, col2 = st.columns([3, 2])
            with col1:
                st.subheader(f"📍 Data Sensor Terkini")
                st.caption(f"(Diperbarui pada: {waktu_update} WIB)")
            with col2:
                 st.subheader(f"Kesimpulan Cuaca:")
                 st.header(f"{status_emoji} {status_text}")

            st.markdown("---")

            # --- METRIK DETAIL ---
            k1, k2, k3, k4, k5 = st.columns(5)
            delta_suhu = df['suhu'].iloc[-1] - df['suhu'].iloc[-2] if len(df) > 1 else 0
            delta_kelembapan = df['kelembapan'].iloc[-1] - df['kelembapan'].iloc[-2] if len(df) > 1 else 0

            k1.metric(label="🌡️ Suhu (°C)", value=f"{data_terkini.get('suhu', 'N/A'):.1f}", delta=f"{delta_suhu:.1f}")
            k2.metric(label="💧 Kelembapan (%)", value=f"{data_terkini.get('kelembapan', 'N/A'):.1f}", delta=f"{delta_kelembapan:.1f}")
            k3.metric(label="🌀 Tekanan (hPa)", value=f"{data_terkini.get('tekanan', 'N/A'):.1f}")
            k4.metric(label="☀️ Cahaya (Analog)", value=f"{data_terkini.get('cahaya', 'N/A'):.0f}", help="Nilai 0-4095. Semakin kecil = semakin terang")
            k5.metric(label="☔️ IMCS", value=f"{data_terkini.get('imcs', 'N/A'):.2f}",
                      help="Indeks di atas 1.0 menunjukkan peluang hujan tinggi")

            st.markdown("---")

            # --- GRAFIK HISTORIS (MENGGUNAKAN LINE CHART) --- # <--- PERUBAHAN DI SINI
            st.subheader("📈 Grafik Historis Data Sensor")
            if 'timestamp' in df.columns:
                df_grafik = df.set_index('timestamp')
                kolom_grafik = ['suhu', 'kelembapan', 'tekanan']
                kolom_valid = [kol for kol in kolom_grafik if kol in df_grafik.columns]
                if kolom_valid:
                     # Menggunakan st.line_chart
                     st.line_chart(df_grafik[kolom_valid]) # <--- KEMBALI KE LINE CHART
                else:
                     st.warning("Kolom data untuk grafik tidak ditemukan.")
            else:
                st.warning("Kolom 'timestamp' tidak ditemukan untuk membuat grafik.")


            # --- DATA MENTAH (DALAM EXPANDER) ---
            with st.expander("Lihat Data (10 Terakhir)"):
                 if 'timestamp' in df.columns:
                     st.dataframe(df.sort_values(by='timestamp', ascending=False).head(10).set_index('timestamp'))
                 else:
                      st.dataframe(df.tail(10))

    # Tunggu 15 detik sebelum refresh
    time.sleep(15)


