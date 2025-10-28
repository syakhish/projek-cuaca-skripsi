import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import os

# ----------------- KONFIGURASI HALAMAN -----------------
st.set_page_config(
    page_title="Dasbor Monitoring Cuaca",
    page_icon="🌦️", # Menggunakan emoji yang lebih relevan
    layout="wide",
)

# --- PASTIKAN USERNAME ANDA BENAR (SUDAH SESUAI) ---
API_URL = "http://syakhish.pythonanywhere.com/get_data"
# -----------------------------------------------------

# ----------------- JUDUL APLIKASI -----------------
st.title("🌦️ Dasbor Monitoring Cuaca Real-Time")
st.markdown("---")

# ----------------- FUNGSI BACA DATA DARI API -----------------
# Fungsi ini mengambil data dari server API Anda, dengan cache 15 detik.
@st.cache_data(ttl=15)
def baca_data_dari_api():
    """Mengambil data JSON dari API, mengonversi ke DataFrame pandas, dan memproses timestamp."""
    try:
        # Melakukan permintaan ke URL API dengan timeout
        response = requests.get(API_URL, timeout=10)
        # Memeriksa apakah request berhasil (status code 2xx)
        response.raise_for_status()
        data = response.json()

        # Jika API mengembalikan list kosong, berarti belum ada data
        if not data:
            # st.info("Menunggu data pertama masuk dari sensor...") # Bisa diaktifkan jika perlu
            return None

        # Ubah data JSON (list of dictionaries) menjadi DataFrame pandas
        df = pd.DataFrame(data)

        # --- VALIDASI DAN KONVERSI TIMESTAMP ---
        # 1. Pastikan kolom 'timestamp' ada
        if 'timestamp' not in df.columns:
            st.error("Data dari API tidak memiliki kolom 'timestamp'.")
            return None
        # 2. Coba konversi ke numerik, paksa error menjadi NaN (Not a Number)
        df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
        # 3. Hapus baris di mana konversi gagal (timestamp adalah NaN)
        df.dropna(subset=['timestamp'], inplace=True)
        if df.empty:
            st.warning("Data timestamp tidak valid atau kosong setelah konversi.")
            return None

        # 4. Konversi UNIX timestamp (asumsi UTC) ke objek Datetime (masih UTC)
        df['timestamp_utc'] = pd.to_datetime(df['timestamp'], unit='s')
        # 5. Konversi dari UTC ke WIB (UTC+7)
        df['timestamp'] = df['timestamp_utc'] + pd.Timedelta(hours=7)
        # ----------------------------------------

        return df

    except requests.exceptions.ConnectionError:
        st.error(f"Gagal terhubung ke server API di {API_URL}. Periksa URL dan koneksi internet server.")
        return None
    except requests.exceptions.Timeout:
        st.error("Koneksi ke server API timeout. Server mungkin lambat merespons.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Terjadi error saat request ke API: {e}")
        return None
    except Exception as e:
        st.error(f"Terjadi error saat memproses data dari API: {e}")
        return None

# ----------------- FUNGSI PENENTU STATUS CUACA & EMOJI -----------------
def tentukan_status_cuaca(data):
    """ Menganalisis data sensor terkini dan memberikan kesimpulan status cuaca beserta emoji. """
    # Gunakan .get() untuk mengambil nilai dengan aman, berikan default jika kunci tidak ada
    imcs = data.get('imcs', 0.0)
    cahaya = data.get('cahaya', 4095) # Default gelap jika data tidak ada
    kelembapan = data.get('kelembapan', 0.0)

    # PERKIRAAN AMBANG BATAS (Sesuaikan berdasarkan pengamatan Anda!)
    AMBANG_CERAH = 800
    AMBANG_BERAWAN = 2000
    AMBANG_MENDUNG = 3000
    AMBANG_MALAM = 3800

    # Pastikan tipe data benar sebelum membandingkan, tangani potensi error
    try:
        cahaya = int(cahaya)
        imcs = float(imcs)
        kelembapan = float(kelembapan)
    except (ValueError, TypeError, AttributeError):
         return "Data Tidak Valid", "❓" # Jika data tidak bisa dikonversi

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
    else: # Kondisi cahaya di atas AMBANG_MENDUNG tapi imcs tidak cukup tinggi
         return "Sangat Mendung / Berkabut", "🌫️"

# ----------------- LAYOUT UTAMA APLIKASI -----------------
placeholder = st.empty() # Placeholder untuk update elemen tanpa reload

# ----------------- LOOP UTAMA (UNTUK REAL-TIME) -----------------
while True:
    # Ambil data terbaru dari API (akan menggunakan cache jika belum 15 detik)
    df = baca_data_dari_api()

    # Hanya lanjutkan jika data berhasil diambil dan tidak kosong
    if df is not None and not df.empty:
        with placeholder.container(): # Menggambar ulang semua elemen di dalam container ini
            # --- BAGIAN DATA TERKINI & KESIMPULAN ---
            # Ambil baris data terakhir
            data_terkini = df.iloc[-1]
            # Tentukan status cuaca berdasarkan data terakhir
            status_text, status_emoji = tentukan_status_cuaca(data_terkini)

            # Format waktu update
            waktu_update_str = "N/A" # Default jika timestamp bermasalah
            if 'timestamp' in data_terkini and pd.notnull(data_terkini['timestamp']):
                 try:
                      waktu_update_str = data_terkini['timestamp'].strftime('%d %b %Y, %H:%M:%S')
                 except AttributeError:
                      waktu_update_str = "Format Waktu Salah"


            # Tampilkan Waktu Update dan Kesimpulan dalam dua kolom
            col_info, col_status = st.columns([3, 2])
            with col_info:
                st.subheader(f"📍 Data Sensor Terkini")
                st.caption(f"(Diperbarui pada: {waktu_update_str} WIB)")
            with col_status:
                 st.subheader(f"Kesimpulan Cuaca:")
                 # Gunakan font lebih besar untuk kesimpulan
                 st.markdown(f"<h2 style='text-align: left;'>{status_emoji} {status_text}</h2>", unsafe_allow_html=True)

            st.markdown("---") # Garis pemisah

            # --- BAGIAN METRIK DETAIL ---
            # Siapkan kolom untuk metrik
            k1, k2, k3, k4, k5 = st.columns(5)

            # Hitung delta (perubahan dari data sebelumnya) jika memungkinkan
            delta_suhu = df['suhu'].iloc[-1] - df['suhu'].iloc[-2] if len(df) > 1 else 0
            delta_kelembapan = df['kelembapan'].iloc[-1] - df['kelembapan'].iloc[-2] if len(df) > 1 else 0

            # Tampilkan metrik dengan .get() untuk keamanan jika kolom tidak ada
            k1.metric(label="🌡️ Suhu (°C)", value=f"{data_terkini.get('suhu', 0):.1f}", delta=f"{delta_suhu:.1f}")
            k2.metric(label="💧 Kelembapan (%)", value=f"{data_terkini.get('kelembapan', 0):.1f}", delta=f"{delta_kelembapan:.1f}")
            k3.metric(label="🌀 Tekanan (hPa)", value=f"{data_terkini.get('tekanan', 0):.1f}")
            k4.metric(label="☀️ Cahaya (Analog)", value=f"{data_terkini.get('cahaya', 0):.0f}", help="Nilai 0-4095. Semakin KECIL = semakin TERANG")
            k5.metric(label="☔️ IMCS", value=f"{data_terkini.get('imcs', 0):.2f}",
                      help="Indeks di atas 1.0 menunjukkan peluang hujan tinggi")

            st.markdown("---") # Garis pemisah

            # --- BAGIAN GRAFIK HISTORIS (LINE CHART) ---
            st.subheader("📈 Grafik Historis Data Sensor")
            # Pastikan kolom timestamp ada sebelum membuat index
            if 'timestamp' in df.columns:
                try:
                    # Buat DataFrame baru dengan timestamp sebagai index
                    df_grafik = df.set_index('timestamp')
                    # Tentukan kolom yang ingin digambarkan
                    kolom_grafik = ['suhu', 'kelembapan', 'tekanan']
                    # Filter hanya kolom yang benar-benar ada di DataFrame
                    kolom_valid = [kol for kol in kolom_grafik if kol in df_grafik.columns]
                    if kolom_valid:
                        # Tampilkan grafik garis
                        st.line_chart(df_grafik[kolom_valid])
                    else:
                        st.warning("Kolom data ('suhu', 'kelembapan', 'tekanan') tidak ditemukan.")
                except Exception as e:
                    # Tangani error jika gagal membuat index atau grafik
                    st.error(f"Gagal membuat grafik: {e}")
            else:
                 st.warning("Kolom 'timestamp' tidak ditemukan untuk membuat grafik.")


            # --- BAGIAN DATA MENTAH (DALAM EXPANDER) ---
            # Gunakan expander agar tidak terlalu memenuhi layar
            with st.expander("Lihat Data Lengkap (Hingga 100 Data Terakhir)"):
                 # Pastikan kolom timestamp ada sebelum diurutkan dan dijadikan index
                 if 'timestamp' in df.columns:
                     try:
                         # Tampilkan DataFrame, urutkan dari terbaru, jadikan timestamp index
                         st.dataframe(df.sort_values(by='timestamp', ascending=False).set_index('timestamp'))
                     except Exception as e:
                          st.error(f"Gagal menampilkan tabel data: {e}")
                          st.dataframe(df) # Tampilkan tanpa index jika gagal
                 else:
                      st.dataframe(df.tail(100)) # Tampilkan 100 data terakhir jika timestamp bermasalah

    else:
         # Jika df is None (gagal ambil data API) atau kosong (API belum ada data)
         with placeholder.container():
             st.info("🔄 Menunggu atau mencoba mengambil data terbaru dari sensor...")
             # Tambahkan indikator loading
             st.spinner("Memuat data...")

    # Tunggu 15 detik sebelum mengulang loop dan mengambil data lagi
    time.sleep(15)

