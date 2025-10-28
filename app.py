import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import os
import pytz # Library untuk timezone

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

# ----------------- FUNGSI BACA DATA DARI API (KONVERSI TIMEZONE EKSPLISIT) -----------------
@st.cache_data(ttl=15)
def baca_data_dari_api():
    """Mengambil data JSON dari API, mengonversi ke DataFrame pandas, dan memproses timestamp ke WIB secara eksplisit."""
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data:
            return None

        df = pd.DataFrame(data)

        # --- VALIDASI DAN KONVERSI TIMESTAMP (EKSPLISIT) ---
        if 'timestamp' not in df.columns:
            st.error("Kolom 'timestamp' tidak ditemukan.")
            return None

        df['timestamp_numeric'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df.dropna(subset=['timestamp_numeric'], inplace=True)
        if df.empty:
            st.warning("Data timestamp tidak valid.")
            return None

        # 1. Konversi UNIX timestamp ke Datetime pandas, dan langsung tandai sebagai UTC
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_numeric'], unit='s', utc=True, errors='coerce')

        df.dropna(subset=['timestamp_utc'], inplace=True)
        if df.empty:
            st.warning("Gagal konversi timestamp ke datetime UTC.")
            return None

        # 2. Tentukan zona waktu WIB
        zona_wib = pytz.timezone('Asia/Jakarta')

        # 3. Konversi dari UTC ke zona waktu WIB
        #    Gunakan .dt.tz_convert() pada kolom yang sudah timezone-aware (UTC)
        df['timestamp'] = df['timestamp_utc'].dt.tz_convert(zona_wib)
        # ----------------------------------------------------

        # Hapus kolom sementara
        # df = df.drop(columns=['timestamp_numeric', 'timestamp_utc'])

        return df

    # ... (blok except tetap sama) ...
    except requests.exceptions.ConnectionError:
        st.error(f"Gagal terhubung ke server API di {API_URL}.")
        return None
    except requests.exceptions.Timeout:
        st.error("Koneksi ke server API timeout.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error saat request ke API: {e}")
        return None
    except Exception as e:
        st.error(f"Error saat memproses data API: {e}")
        return None

# --- FUNGSI tentukan_status_cuaca() TETAP SAMA ---
def tentukan_status_cuaca(data):
    # ... (kode fungsi ini tidak perlu diubah) ...
    imcs = data.get('imcs', 0.0)
    cahaya = data.get('cahaya', 4095)
    kelembapan = data.get('kelembapan', 0.0)
    AMBANG_CERAH = 800
    AMBANG_BERAWAN = 2000
    AMBANG_MENDUNG = 3000
    AMBANG_MALAM = 3800
    try:
        cahaya = int(cahaya); imcs = float(imcs); kelembapan = float(kelembapan)
    except (ValueError, TypeError, AttributeError): return "Data Tidak Valid", "❓"
    if cahaya > AMBANG_MALAM: return "Malam Hari", "🌃"
    elif imcs > 1.05 and cahaya > AMBANG_MENDUNG: return ("Hujan Deras", "🌧️") if kelembapan > 90 else ("Hujan Ringan", "🌦️")
    elif imcs > 0.95 and cahaya > AMBANG_BERAWAN: return "Mendung (Potensi Hujan)", "☁️"
    elif cahaya < AMBANG_CERAH: return ("Cerah", "☀️") if kelembapan < 70 else ("Cerah Berawan (Lembab)", "🌤️")
    elif cahaya < AMBANG_BERAWAN: return "Cerah Berawan", "🌥️"
    elif cahaya < AMBANG_MENDUNG: return "Berawan", "☁️"
    else: return "Sangat Mendung / Berkabut", "🌫️"


# --- LAYOUT UTAMA & LOOP UTAMA TETAP SAMA ---
placeholder = st.empty()
while True:
    df = baca_data_dari_api()
    if df is not None and not df.empty:
        with placeholder.container():
            # --- DATA TERKINI & KESIMPULAN ---
            data_terkini = df.iloc[-1]
            status_text, status_emoji = tentukan_status_cuaca(data_terkini)
            waktu_update_str = "N/A"
            if 'timestamp' in data_terkini and pd.notnull(data_terkini['timestamp']):
                 try:
                      # Format waktu, sekarang sudah dalam zona waktu WIB
                      waktu_update_str = data_terkini['timestamp'].strftime('%d %b %Y, %H:%M:%S')
                 except AttributeError:
                      waktu_update_str = "Format Waktu Salah"

            col_info, col_status = st.columns([3, 2])
            with col_info:
                st.subheader(f"📍 Data Sensor Terkini")
                st.caption(f"(Diperbarui pada: {waktu_update_str} WIB)") # Tambahkan WIB di sini jika perlu
            with col_status:
                 st.subheader(f"Kesimpulan Cuaca:")
                 st.markdown(f"<h2 style='text-align: left;'>{status_emoji} {status_text}</h2>", unsafe_allow_html=True)

            st.markdown("---")
            # --- METRIK DETAIL ---
            k1, k2, k3, k4, k5 = st.columns(5)
            delta_suhu = df['suhu'].iloc[-1] - df['suhu'].iloc[-2] if len(df) > 1 else 0
            delta_kelembapan = df['kelembapan'].iloc[-1] - df['kelembapan'].iloc[-2] if len(df) > 1 else 0
            k1.metric(label="🌡️ Suhu (°C)", value=f"{data_terkini.get('suhu', 0):.1f}", delta=f"{delta_suhu:.1f}")
            k2.metric(label="💧 Kelembapan (%)", value=f"{data_terkini.get('kelembapan', 0):.1f}", delta=f"{delta_kelembapan:.1f}")
            k3.metric(label="🌀 Tekanan (hPa)", value=f"{data_terkini.get('tekanan', 0):.1f}")
            k4.metric(label="☀️ Cahaya (Analog)", value=f"{data_terkini.get('cahaya', 0):.0f}", help="Nilai 0-4095. Semakin KECIL = semakin TERANG")
            k5.metric(label="☔️ IMCS", value=f"{data_terkini.get('imcs', 0):.2f}", help="Indeks di atas 1.0 menunjukkan peluang hujan tinggi")
            st.markdown("---")
            # --- GRAFIK HISTORIS (LINE CHART) ---
            st.subheader("📈 Grafik Historis Data Sensor")
            if 'timestamp' in df.columns:
                try:
                    # Index sekarang sudah WIB
                    df_grafik = df.set_index('timestamp')
                    kolom_grafik = ['suhu', 'kelembapan', 'tekanan']
                    kolom_valid = [kol for kol in kolom_grafik if kol in df_grafik.columns]
                    if kolom_valid:
                        st.line_chart(df_grafik[kolom_valid])
                    else:
                        st.warning("Kolom data grafik tidak ditemukan.")
                except Exception as e:
                    st.error(f"Gagal membuat grafik: {e}")
            else:
                 st.warning("Kolom 'timestamp' tidak ditemukan.")
            # --- DATA MENTAH (DALAM EXPANDER) ---
            with st.expander("Lihat Data Lengkap (Hingga 100 Data Terakhir)"):
                 if 'timestamp' in df.columns:
                     try:
                         # Tampilkan DataFrame, urutkan terbaru, index WIB
                         st.dataframe(df.sort_values(by='timestamp', ascending=False).set_index('timestamp'))
                     except Exception as e:
                          st.error(f"Gagal menampilkan tabel: {e}")
                          st.dataframe(df)
                 else:
                      st.dataframe(df.tail(100))
    else:
         with placeholder.container():
             st.info("🔄 Menunggu atau mencoba mengambil data terbaru dari sensor...")
             st.spinner("Memuat data...")
    time.sleep(15)
