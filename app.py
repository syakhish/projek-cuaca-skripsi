import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import os
import pytz # Library timezone


# ----------------- KONFIGURASI HALAMAN -----------------
st.set_page_config(
   page_title="Dasbor Monitoring Cuaca",
   page_icon="🌦️",
   layout="wide",
)


# --- URL API ANDA ---
API_URL = "http://syakhish.pythonanywhere.com/get_data"
# --------------------


# ----------------- JUDUL APLIKASI -----------------
st.title("🌦️ Dasbor Monitoring Cuaca Real-Time")
st.markdown("---")


# ----------------- FUNGSI BACA DATA (NO CACHE) -----------------
def baca_data_dari_api():
   """Mengambil data JSON dari API, mengonversi timestamp ke WIB."""
   try:
       # Header untuk mencegah cache
       headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache', 'Expires': '0'}
       response = requests.get(API_URL, timeout=15, headers=headers)
       response.raise_for_status()
       data = response.json()


       if not data or not isinstance(data, list):
            return None


       df = pd.DataFrame(data)


       # Validasi Timestamp
       if 'timestamp' not in df.columns: return None
      
       # Konversi ke Numerik -> Datetime UTC -> Datetime WIB
       df['timestamp_numeric'] = pd.to_numeric(df['timestamp'], errors='coerce')
       df.dropna(subset=['timestamp_numeric'], inplace=True)
       if df.empty: return None
      
       df['timestamp_utc'] = pd.to_datetime(df['timestamp_numeric'], unit='s', utc=True, errors='coerce')
       df.dropna(subset=['timestamp_utc'], inplace=True)
       if df.empty: return None
      
       zona_wib = pytz.timezone('Asia/Jakarta')
       df['timestamp'] = df['timestamp_utc'].dt.tz_convert(zona_wib)
      
       return df
   except Exception as e:
       st.error(f"Error membaca data: {e}")
       return None


# ----------------- FUNGSI STATUS CUACA -----------------
def tentukan_status_cuaca(data):
   imcs = data.get('imcs', 0.0); cahaya = data.get('cahaya', 4095); kelembapan = data.get('kelembapan', 0.0)
  
   # AMBANG BATAS (Sesuaikan jika perlu)
   AMBANG_CERAH = 800; AMBANG_BERAWAN = 2000; AMBANG_MENDUNG = 3000; AMBANG_MALAM = 3800
  
   try: cahaya = int(cahaya); imcs = float(imcs); kelembapan = float(kelembapan)
   except: return "Data Tidak Valid", "❓"
  
   if cahaya > AMBANG_MALAM: return "Malam Hari", "🌃"
   elif imcs > 1.05 and cahaya > AMBANG_MENDUNG: return ("Hujan Deras", "🌧️") if kelembapan > 90 else ("Hujan Ringan", "🌦️")
   elif imcs > 0.95 and cahaya > AMBANG_BERAWAN: return "Mendung (Potensi Hujan)", "☁️"
   elif cahaya < AMBANG_CERAH: return ("Cerah", "☀️") if kelembapan < 70 else ("Cerah Berawan (Lembab)", "🌤️")
   elif cahaya < AMBANG_BERAWAN: return "Cerah Berawan", "🌥️"
   elif cahaya < AMBANG_MENDUNG: return "Berawan", "☁️"
   else: return "Sangat Mendung / Berkabut", "🌫️"


# ----------------- LOOP UTAMA -----------------
placeholder = st.empty()


while True:
   st.cache_data.clear() # Hapus cache agar data selalu baru
   df = baca_data_dari_api()


   if df is not None and not df.empty:
       with placeholder.container():
           # --- DATA TERKINI ---
           data_terkini = df.iloc[-1]
           status_text, status_emoji = tentukan_status_cuaca(data_terkini)
          
           waktu_str = "N/A"
           if 'timestamp' in data_terkini and pd.notnull(data_terkini['timestamp']):
                try:
                     # Format waktu yang aman
                     waktu_str = data_terkini['timestamp'].to_pydatetime().strftime('%d %b %Y, %H:%M:%S')
                except: pass


           col1, col2 = st.columns([3, 2])
           with col1:
               st.subheader("📍 Data Sensor Terkini")
               st.caption(f"(Diperbarui pada: {waktu_str} WIB)")
           with col2:
                st.subheader("Kesimpulan Cuaca:")
                st.markdown(f"<h2>{status_emoji} {status_text}</h2>", unsafe_allow_html=True)


           st.markdown("---")
          
           # --- METRIK ---
           k1, k2, k3, k4, k5 = st.columns(5)
           # Hitung perubahan (delta)
           d_suhu = df['suhu'].iloc[-1] - df['suhu'].iloc[-2] if len(df)>1 else 0
           d_hum = df['kelembapan'].iloc[-1] - df['kelembapan'].iloc[-2] if len(df)>1 else 0
          
           k1.metric("🌡️ Suhu (°C)", f"{data_terkini.get('suhu',0):.1f}", f"{d_suhu:.1f}")
           k2.metric("💧 Kelembapan (%)", f"{data_terkini.get('kelembapan',0):.1f}", f"{d_hum:.1f}")
           k3.metric("🌀 Tekanan (hPa)", f"{data_terkini.get('tekanan',0):.1f}")
           k4.metric("☀️ Cahaya", f"{data_terkini.get('cahaya',0):.0f}")
           k5.metric("☔️ IMCS", f"{data_terkini.get('imcs',0):.2f}")
          
           st.markdown("---")


           # --- GRAFIK (DIPISAH MENJADI 2) ---
           st.subheader("📈 Grafik Historis Data Sensor")
          
           if 'timestamp' in df.columns:
               try:
                   df_grafik = df.set_index('timestamp')
                  
                   # MEMBAGI LAYAR JADI 2 KOLOM
                   grafik_kiri, grafik_kanan = st.columns(2)
                  
                   # 1. GRAFIK LINGKUNGAN (KIRI)
                   with grafik_kiri:
                       st.markdown("**🌡️ Suhu, Kelembapan & Tekanan**")
                       cols_env = ['suhu', 'kelembapan', 'tekanan']
                       valid_cols = [c for c in cols_env if c in df_grafik.columns]
                       if valid_cols:
                           st.line_chart(df_grafik[valid_cols])
                       else:
                           st.warning("Data lingkungan tidak ada.")
                          
                   # 2. GRAFIK CAHAYA (KANAN)
                   with grafik_kanan:
                       st.markdown("**☀️ Intensitas Cahaya (Area Chart)**")
                       if 'cahaya' in df_grafik.columns:
                           # Pakai Area Chart warna Oranye biar beda
                           st.area_chart(df_grafik[['cahaya']], color="#FFaa00")
                       else:
                           st.warning("Data cahaya tidak ada.")
                          
               except Exception as e:
                   st.error(f"Gagal membuat grafik: {e}")
           else:
               st.warning("Kolom timestamp tidak ditemukan.")


           # --- TABEL DATA ---
           with st.expander("Lihat Data Lengkap (100 Terakhir)"):
               if 'timestamp' in df.columns:
                   st.dataframe(df.sort_values(by='timestamp', ascending=False).set_index('timestamp'))
               else:
                   st.dataframe(df.tail(100))


   else:
       with placeholder.container():
           st.info("🔄 Menunggu data dari alat ESP32...")
           st.spinner("Sedang memuat...")


   time.sleep(10)
