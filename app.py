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

# ----------------- FUNGSI BACA DATA DARI API (DENGAN DEBUGGING LANJUTAN) -----------------
# @st.cache_data(ttl=15) # <<< NONAKTIFKAN CACHE SEMENTARA
def baca_data_dari_api():
    """Mengambil data JSON dari API, mengonversi timestamp ke WIB, dengan debugging rinci."""
    try:
        st.write(f"DEBUG: Mengambil data dari {API_URL}...") # DEBUG 1
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data:
            st.warning("DEBUG: Data JSON dari API kosong.") # DEBUG 2
            return None

        # --- DEBUGGING MENTAH ---
        st.write("DEBUG: Data JSON mentah terakhir diterima:", data[-1] if isinstance(data, list) and data else "Format data tidak sesuai/kosong") # DEBUG 3
        # ------------------------

        df = pd.DataFrame(data)

        # --- VALIDASI DAN KONVERSI TIMESTAMP (EKSPLISIT) ---
        if 'timestamp' not in df.columns:
            st.error("Kolom 'timestamp' tidak ditemukan.")
            return None

        # Ambil timestamp terakhir untuk debugging
        raw_ts = df['timestamp'].iloc[-1]
        st.write(f"DEBUG: Nilai timestamp mentah terakhir dari DataFrame:", raw_ts, type(raw_ts)) # DEBUG 4

        df['timestamp_numeric'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df.dropna(subset=['timestamp_numeric'], inplace=True)
        if df.empty:
            st.warning("Data timestamp tidak valid setelah konversi ke numerik.")
            return None

        num_ts = df['timestamp_numeric'].iloc[-1]
        st.write(f"DEBUG: Nilai timestamp setelah to_numeric:", num_ts, type(num_ts)) # DEBUG 5

        # 1. Konversi UNIX timestamp ke Datetime pandas (UTC)
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_numeric'], unit='s', utc=True, errors='coerce')
        df.dropna(subset=['timestamp_utc'], inplace=True)
        if df.empty:
            st.warning("Gagal konversi timestamp ke datetime UTC.")
            return None

        utc_dt = df['timestamp_utc'].iloc[-1]
        st.write(f"DEBUG: Nilai timestamp setelah konversi ke UTC:", utc_dt, type(utc_dt)) # DEBUG 6

        # 2. Tentukan zona waktu WIB
        zona_wib = pytz.timezone('Asia/Jakarta')

        # 3. Konversi dari UTC ke zona waktu WIB
        df['timestamp'] = df['timestamp_utc'].dt.tz_convert(zona_wib)

        wib_dt = df['timestamp'].iloc[-1]
        st.write(f"DEBUG: Nilai timestamp FINAL setelah konversi ke WIB:", wib_dt, type(wib_dt)) # DEBUG 7
        # -------------------------------------------------------------

        return df

    # ... (blok except tetap sama) ...
    except requests.exceptions.ConnectionError: st.error(f"Gagal terhubung ke server API di {API_URL}.") ; return None
    except requests.exceptions.Timeout: st.error("Koneksi ke server API timeout.") ; return None
    except requests.exceptions.RequestException as e: st.error(f"Error saat request ke API: {e}") ; return None
    except Exception as e: st.error(f"Error saat memproses data API: {e}") ; return None

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

# --- LAYOUT UTAMA & LOOP UTAMA TETAP SAMA ---
placeholder = st.empty()
while True:
    # --- NONAKTIFKAN CACHE SEMENTARA ---
    st.cache_data.clear() # Hapus cache setiap iterasi
    # ------------------------------------
    df = baca_data_dari_api() # Panggil fungsi baca data

    # --- TAMBAHAN DEBUGGING: Tampilkan DataFrame hasil baca ---
    if df is not None:
        st.write("DEBUG: Isi DataFrame setelah dibaca dan dikonversi:") # DEBUG 8
        st.dataframe(df.tail(5)) # Tampilkan 5 data terakhir
    else:
        st.write("DEBUG: DataFrame kosong atau None.") # DEBUG 9
    # ---------------------------------------------------------


    if df is not None and not df.empty:
        with placeholder.container():
            # --- DATA TERKINI & KESIMPULAN ---
            data_terkini = df.iloc[-1]
            status_text, status_emoji = tentukan_status_cuaca(data_terkini)
            waktu_update_str = "N/A"
            final_timestamp_object = None # Untuk debugging tambahan

            if 'timestamp' in data_terkini and pd.notnull(data_terkini['timestamp']):
                 try:
                      final_timestamp_object = data_terkini['timestamp'] # Simpan objek datetime
                      # Format waktu final yang sudah WIB
                      waktu_update_str = final_timestamp_object.strftime('%d %b %Y, %H:%M:%S')
                 except AttributeError as e:
                      st.error(f"DEBUG: Error saat formatting waktu: {e}") # DEBUG 10
                      waktu_update_str = f"Error Format ({type(final_timestamp_object)})"

            # --- TAMBAHAN DEBUGGING: Tampilkan waktu yang akan dicetak ---
            st.write(f"DEBUG: Objek Waktu Final sebelum strftime:", final_timestamp_object) # DEBUG 11
            st.write(f"DEBUG: Nilai waktu_update_str yang akan ditampilkan:", waktu_update_str) # DEBUG 12
            # -------------------------------------------------------------

            col_info, col_status = st.columns([3, 2])
            with col_info:
                st.subheader(f"📍 Data Sensor Terkini")
                st.caption(f"(Diperbarui pada: {waktu_update_str} WIB)")
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

    # Tunggu 15 detik sebelum refresh
    # Kurangi waktu tunggu saat debugging agar lebih cepat terlihat
    time.sleep(10) # << Ubah ke 10 detik untuk debugging

