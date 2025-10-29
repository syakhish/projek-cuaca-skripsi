import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import os
import pytz # Library penting untuk timezone

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
st.title("🌦️ Dasbor Monitoring Cuaca Real-Time (DEBUG v2)") # Tambahkan v2 di judul
st.markdown("---")

# ----------------- FUNGSI BACA DATA DARI API (TANPA CACHE, HEADER NO-CACHE) -----------------
# @st.cache_data(ttl=15) # <<< CACHE MASIH DINONAKTIFKAN
def baca_data_dari_api():
    """Mengambil data JSON dari API, mengonversi timestamp ke WIB, dengan header no-cache."""
    try:
        # Tambahkan header untuk mencoba mencegah cache di sisi client/proxy
        headers = {'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache', 'Expires': '0'}
        response = requests.get(API_URL, timeout=15, headers=headers) # Tambahkan headers
        response.raise_for_status()
        data = response.json()

        if not data or not isinstance(data, list):
             return None

        df = pd.DataFrame(data)

        # --- VALIDASI DAN KONVERSI TIMESTAMP (EKSPLISIT) ---
        if 'timestamp' not in df.columns: return None
        df['timestamp_numeric'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df.dropna(subset=['timestamp_numeric'], inplace=True)
        if df.empty: return None
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_numeric'], unit='s', utc=True, errors='coerce')
        df.dropna(subset=['timestamp_utc'], inplace=True)
        if df.empty: return None
        zona_wib = pytz.timezone('Asia/Jakarta')
        df['timestamp'] = df['timestamp_utc'].dt.tz_convert(zona_wib) # Konversi ke WIB
        # -------------------------------------------------------------
        return df
    except Exception as e:
        st.error(f"Error di baca_data_dari_api: {e}", icon="🚨")
        # import traceback # Aktifkan jika perlu traceback detail
        # st.code(traceback.format_exc())
        return None

# --- FUNGSI tentukan_status_cuaca() TETAP SAMA ---
def tentukan_status_cuaca(data):
    # ... (kode fungsi ini tidak perlu diubah) ...
    imcs = data.get('imcs', 0.0); cahaya = data.get('cahaya', 4095); kelembapan = data.get('kelembapan', 0.0)
    AMBANG_CERAH = 800; AMBANG_BERAWAN = 2000; AMBANG_MENDUNG = 3000; AMBANG_MALAM = 3800
    try: cahaya = int(cahaya); imcs = float(imcs); kelembapan = float(kelembapan)
    except (ValueError, TypeError, AttributeError): return "Data Tidak Valid", "❓"
    if cahaya > AMBANG_MALAM: return "Malam Hari", "🌃"
    elif imcs > 1.05 and cahaya > AMBANG_MENDUNG: return ("Hujan Deras", "🌧️") if kelembapan > 90 else ("Hujan Ringan", "🌦️")
    elif imcs > 0.95 and cahaya > AMBANG_BERAWAN: return "Mendung (Potensi Hujan)", "☁️"
    elif cahaya < AMBANG_CERAH: return ("Cerah", "☀️") if kelembapan < 70 else ("Cerah Berawan (Lembab)", "🌤️")
    elif cahaya < AMBANG_BERAWAN: return "Cerah Berawan", "🌥️"
    elif cahaya < AMBANG_MENDUNG: return "Berawan", "☁️"
    else: return "Sangat Mendung / Berkabut", "🌫️"

# --- LAYOUT UTAMA & LOOP UTAMA ---
placeholder = st.empty()
while True:
    st.cache_data.clear() # Hapus cache setiap iterasi

    df = baca_data_dari_api() # Panggil fungsi baca data (TANPA CACHE!)

    if df is not None and not df.empty:
        with placeholder.container():
            # --- DATA TERKINI & KESIMPULAN ---
            data_terkini = df.iloc[-1]
            status_text, status_emoji = tentukan_status_cuaca(data_terkini)
            waktu_update_str = "N/A"
            final_timestamp_object_wib = None
            raw_wib_string = "N/A" # Untuk menampilkan objek mentah

            if 'timestamp' in data_terkini and pd.notnull(data_terkini['timestamp']):
                 try:
                      final_timestamp_object_wib = data_terkini['timestamp']
                      # Simpan representasi string dari objek mentah
                      raw_wib_string = str(final_timestamp_object_wib)
                      # Format waktu final yang sudah WIB
                      waktu_update_str = final_timestamp_object_wib.strftime('%d %b %Y, %H:%M:%S')
                 except AttributeError as e:
                      waktu_update_str = "Error Format"
                      raw_wib_string = f"Error: {e}"

            col_info, col_status = st.columns([3, 2])
            with col_info:
                st.subheader(f"📍 Data Sensor Terkini")
                # --- TAMPILKAN KEDUANYA UNTUK PERBANDINGAN ---
                st.caption(f"Hasil strftime: {waktu_update_str} WIB")
                st.caption(f"Objek Mentah WIB: {raw_wib_string}") # Tampilkan objek mentah
                # ----------------------------------------------
            with col_status:
                 st.subheader(f"Kesimpulan Cuaca:")
                 st.markdown(f"<h2 style='text-align: left;'>{status_emoji} {status_text}</h2>", unsafe_allow_html=True)

            # ... (sisa kode metrik, grafik, tabel tetap sama) ...
            st.markdown("---") # Metrik dst
            k1, k2, k3, k4, k5 = st.columns(5); delta_suhu = df['suhu'].iloc[-1] - df['suhu'].iloc[-2] if len(df) > 1 else 0; delta_kelembapan = df['kelembapan'].iloc[-1] - df['kelembapan'].iloc[-2] if len(df) > 1 else 0
            k1.metric(label="🌡️ Suhu (°C)", value=f"{data_terkini.get('suhu', 0):.1f}", delta=f"{delta_suhu:.1f}"); k2.metric(label="💧 Kelembapan (%)", value=f"{data_terkini.get('kelembapan', 0):.1f}", delta=f"{delta_kelembapan:.1f}"); k3.metric(label="🌀 Tekanan (hPa)", value=f"{data_terkini.get('tekanan', 0):.1f}"); k4.metric(label="☀️ Cahaya (Analog)", value=f"{data_terkini.get('cahaya', 0):.0f}", help="Nilai 0-4095. Semakin KECIL = semakin TERANG"); k5.metric(label="☔️ IMCS", value=f"{data_terkini.get('imcs', 0):.2f}", help="Indeks di atas 1.0 menunjukkan peluang hujan tinggi")
            st.markdown("---") # Grafik
            st.subheader("📈 Grafik Historis Data Sensor")
            if 'timestamp' in df.columns:
                try: df_grafik = df.set_index('timestamp'); kolom_grafik = ['suhu', 'kelembapan', 'tekanan']; kolom_valid = [kol for kol in kolom_grafik if kol in df_grafik.columns];
                if kolom_valid: st.line_chart(df_grafik[kolom_valid])
                else: st.warning("Kolom data grafik tidak ditemukan.")
                except Exception as e: st.error(f"Gagal membuat grafik: {e}")
            else: st.warning("Kolom 'timestamp' tidak ditemukan.")
            with st.expander("Lihat Data Lengkap (Hingga 100 Data Terakhir)"):
                 if 'timestamp' in df.columns:
                     try: st.dataframe(df.sort_values(by='timestamp', ascending=False).set_index('timestamp'))
                     except Exception as e: st.error(f"Gagal menampilkan tabel: {e}"); st.dataframe(df)
                 else: st.dataframe(df.tail(100))

    else:
         with placeholder.container():
             st.info("🔄 Menunggu atau mencoba mengambil data terbaru dari sensor...")
             st.spinner("Memuat data...")

    # Tunggu 10 detik sebelum refresh
    time.sleep(10)

