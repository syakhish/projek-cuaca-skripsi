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
st.title("🌦️ Dasbor Monitoring Cuaca Real-Time")
st.markdown("---")

# ----------------- FUNGSI BACA DATA DARI API (TANPA CACHE, DENGAN DEBUGGING) -----------------
# @st.cache_data(ttl=15) # <<< CACHE DINONAKTIFKAN TOTAL UNTUK DEBUGGING
def baca_data_dari_api():
    """Mengambil data JSON dari API, mengonversi timestamp ke WIB, dengan debugging rinci."""
    try:
        st.write(f"DEBUG (baca_data): Mencoba mengambil data dari {API_URL}...") # DEBUG 1
        response = requests.get(API_URL, timeout=15) # Tambah timeout sedikit
        response.raise_for_status()
        data = response.json()

        if not data or not isinstance(data, list): # Cek jika data kosong ATAU bukan list
             st.warning("DEBUG (baca_data): Data JSON dari API kosong atau formatnya bukan list.") # DEBUG 2
             return None

        st.write(f"DEBUG (baca_data): Data JSON mentah terakhir diterima:", data[-1]) # DEBUG 3

        df = pd.DataFrame(data)

        # --- VALIDASI DAN KONVERSI TIMESTAMP (EKSPLISIT) ---
        if 'timestamp' not in df.columns:
            st.error("Kolom 'timestamp' tidak ditemukan.")
            return None

        raw_ts = df['timestamp'].iloc[-1]
        st.write(f"DEBUG (baca_data): Nilai timestamp mentah terakhir dari DataFrame:", raw_ts, type(raw_ts)) # DEBUG 4

        df['timestamp_numeric'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df.dropna(subset=['timestamp_numeric'], inplace=True)
        if df.empty:
            st.warning("Data timestamp tidak valid setelah konversi ke numerik.")
            return None

        num_ts = df['timestamp_numeric'].iloc[-1]
        st.write(f"DEBUG (baca_data): Nilai timestamp setelah to_numeric:", num_ts, type(num_ts)) # DEBUG 5

        # 1. Konversi UNIX timestamp ke Datetime pandas (UTC)
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_numeric'], unit='s', utc=True, errors='coerce')
        df.dropna(subset=['timestamp_utc'], inplace=True)
        if df.empty:
            st.warning("Gagal konversi timestamp ke datetime UTC.")
            return None

        utc_dt = df['timestamp_utc'].iloc[-1]
        st.write(f"DEBUG (baca_data): Nilai timestamp setelah konversi ke UTC:", utc_dt, type(utc_dt)) # DEBUG 6

        # 2. Tentukan zona waktu WIB
        zona_wib = pytz.timezone('Asia/Jakarta')

        # 3. Konversi dari UTC ke zona waktu WIB
        df['timestamp'] = df['timestamp_utc'].dt.tz_convert(zona_wib)

        wib_dt = df['timestamp'].iloc[-1]
        st.write(f"DEBUG (baca_data): Nilai timestamp FINAL (WIB) di DataFrame:", wib_dt, type(wib_dt)) # DEBUG 7
        # -------------------------------------------------------------

        return df

    except Exception as e:
        # Tampilkan error lengkap saat debugging
        st.error(f"Error di baca_data_dari_api: {e}", icon="🚨")
        import traceback
        st.code(traceback.format_exc()) # Tampilkan traceback error
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
    st.write("DEBUG (Loop): Memulai iterasi loop...") # DEBUG A
    # Panggil fungsi baca data (TANPA CACHE!)
    df = baca_data_dari_api()

    # --- DEBUGGING SETELAH BACA DATA ---
    if df is not None:
        st.write("DEBUG (Loop): DataFrame berhasil dibaca, jumlah baris:", len(df)) # DEBUG B
        st.dataframe(df.tail(2)) # Tampilkan 2 data terakhir hasil konversi
    else:
        st.write("DEBUG (Loop): DataFrame kosong atau None setelah baca_data_dari_api.") # DEBUG C
    # -----------------------------------
    # --- DEBUGGING: Tampilkan Waktu Server Streamlit ---
        now_server_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        zona_wib = pytz.timezone('Asia/Jakarta')
        now_server_wib = now_server_utc.astimezone(zona_wib)
        st.write(f"DEBUG SERVER TIME: Waktu UTC Server saat ini:", now_server_utc.strftime('%Y-%m-%d %H:%M:%S %Z%z'))
        st.write(f"DEBUG SERVER TIME: Waktu WIB Server saat ini:", now_server_wib.strftime('%Y-%m-%d %H:%M:%S %Z%z'))
        # ---------------------------------------------------

    if df is not None and not df.empty:
        with placeholder.container():
            # --- DATA TERKINI & KESIMPULAN ---
            data_terkini = df.iloc[-1]
            status_text, status_emoji = tentukan_status_cuaca(data_terkini)
            waktu_update_str = "N/A"
            final_timestamp_object_wib = None

            if 'timestamp' in data_terkini and pd.notnull(data_terkini['timestamp']):
                 try:
                      final_timestamp_object_wib = data_terkini['timestamp']
                      # Format waktu final yang sudah WIB
                      waktu_update_str = final_timestamp_object_wib.strftime('%d %b %Y, %H:%M:%S')
                 except AttributeError as e:
                      st.error(f"DEBUG (Loop): Error saat formatting waktu: {e}")
                      waktu_update_str = f"Error Format ({type(final_timestamp_object_wib)})"

            # --- DEBUGGING SEBELUM TAMPIL ---
            st.write(f"DEBUG (Loop): Objek Waktu Final (WIB) sebelum strftime:", final_timestamp_object_wib) # DEBUG D
            st.write(f"DEBUG (Loop): Nilai waktu_update_str yang akan ditampilkan:", waktu_update_str) # DEBUG E
            # --------------------------------

            col_info, col_status = st.columns([3, 2])
            with col_info:
                st.subheader(f"📍 Data Sensor Terkini")
                st.caption(f"(Diperbarui pada: {waktu_update_str} WIB)") # Pastikan WIB tertulis
            with col_status:
                 st.subheader(f"Kesimpulan Cuaca:")
                 st.markdown(f"<h2 style='text-align: left;'>{status_emoji} {status_text}</h2>", unsafe_allow_html=True)

            # ... (sisa kode metrik, grafik, tabel tetap sama) ...
            st.markdown("---")
            k1, k2, k3, k4, k5 = st.columns(5)
            delta_suhu = df['suhu'].iloc[-1] - df['suhu'].iloc[-2] if len(df) > 1 else 0
            delta_kelembapan = df['kelembapan'].iloc[-1] - df['kelembapan'].iloc[-2] if len(df) > 1 else 0
            k1.metric(label="🌡️ Suhu (°C)", value=f"{data_terkini.get('suhu', 0):.1f}", delta=f"{delta_suhu:.1f}")
            k2.metric(label="💧 Kelembapan (%)", value=f"{data_terkini.get('kelembapan', 0):.1f}", delta=f"{delta_kelembapan:.1f}")
            k3.metric(label="🌀 Tekanan (hPa)", value=f"{data_terkini.get('tekanan', 0):.1f}")
            k4.metric(label="☀️ Cahaya (Analog)", value=f"{data_terkini.get('cahaya', 0):.0f}", help="Nilai 0-4095. Semakin KECIL = semakin TERANG")
            k5.metric(label="☔️ IMCS", value=f"{data_terkini.get('imcs', 0):.2f}", help="Indeks di atas 1.0 menunjukkan peluang hujan tinggi")
            st.markdown("---")
            st.subheader("📈 Grafik Historis Data Sensor")
            if 'timestamp' in df.columns:
                try:
                    df_grafik = df.set_index('timestamp')
                    kolom_grafik = ['suhu', 'kelembapan', 'tekanan']
                    kolom_valid = [kol for kol in kolom_grafik if kol in df_grafik.columns]
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


