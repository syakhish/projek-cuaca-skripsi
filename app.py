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
        headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache', 'Expires': '0'}
        response = requests.get(API_URL, timeout=15, headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data or not isinstance(data, list):
             return None

        df = pd.DataFrame(data)

        if 'timestamp' not in df.columns: return None
        
        # Konversi Timestamp
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

# ----------------- FUNGSI STATUS CUACA (LOGIKA BARU) -----------------
# Ini adalah logika yang Anda buat berdasarkan masukan dosen
def tentukan_status_cuaca(data):
    # Ambil semua data
    imcs = data.get('imcs', 0.0)
    cahaya = data.get('cahaya', 0)      # 0-4095 (Rendah=Gelap, Tinggi=Terang)
    kelembapan = data.get('kelembapan', 0.0)
    hujan = data.get('hujan', 4095)     # 0-4095 (Rendah=Basah, Tinggi=Kering)
    
    # --- PATOKAN (THRESHOLD) ---
    # Sensor Cahaya (TEMT6000)
    BATAS_MALAM = 100        
    BATAS_MENDUNG = 1000     
    BATAS_BERAWAN = 2500     
    
    # Sensor Hujan (YL-83) - INI RUMUSNYA
    BATAS_HUJAN_RINGAN = 3800  # Di bawah ini mulai gerimis
    BATAS_HUJAN_DERAS = 2500   # Di bawah ini sudah deras
    
    try: 
        cahaya = int(cahaya); imcs = float(imcs); 
        kelembapan = float(kelembapan); hujan = int(hujan)
    except: return "Data Tidak Valid", "❓"
    
    # --- LOGIKA UTAMA ---
    
    # 1. Prioritas Tertinggi: CEK FISIK AIR HUJAN (YL-83)
    if hujan < BATAS_HUJAN_DERAS:
        return "Hujan Deras", "🌧️"
    elif hujan < BATAS_HUJAN_RINGAN:
        return "Hujan Ringan / Gerimis", "🌦️"

    # 2. Cek Malam (Jika tidak hujan)
    if cahaya < BATAS_MALAM: 
        return "Malam Hari", "🌃"
        
    # 3. Cek Potensi Hujan (IMCS & Langit Gelap)
    elif imcs > 0.95 and cahaya < BATAS_BERAWAN:
        return "Mendung (Potensi Hujan)", "☁️"
        
    # 4. Cek Kondisi Siang
    elif cahaya > BATAS_BERAWAN: 
        if kelembapan < 70: return "Cerah", "☀️"
        else: return "Cerah (Lembab)", "🌤️"
            
    elif cahaya > BATAS_MENDUNG: 
        return "Cerah Berawan", "🌥️"
        
    else: 
        return "Berawan / Redup", "☁️"

# ----------------- LOOP UTAMA -----------------
placeholder = st.empty()

while True:
    st.cache_data.clear()
    df = baca_data_dari_api()

    if df is not None and not df.empty:
        with placeholder.container():
            # --- DATA TERKINI ---
            data_terkini = df.iloc[-1]
            status_text, status_emoji = tentukan_status_cuaca(data_terkini)
            
            waktu_str = "N/A"
            if 'timestamp' in data_terkini and pd.notnull(data_terkini['timestamp']):
                 try: waktu_str = data_terkini['timestamp'].to_pydatetime().strftime('%d %b %Y, %H:%M:%S')
                 except: pass

            # --- ALERT SISTEM ---
            if "Hujan" in status_text:
                st.error(f"⚠️ PERINGATAN: Sedang terjadi {status_text}! Harap waspada.", icon="🌧️")
                st.toast(f"Terdeteksi: {status_text}!", icon="☔")
            elif "Mendung" in status_text:
                st.warning(f"Siaga: Kondisi saat ini {status_text}.", icon="☁️")

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
            d_suhu = df['suhu'].iloc[-1] - df['suhu'].iloc[-2] if len(df)>1 else 0
            d_hum = df['kelembapan'].iloc[-1] - df['kelembapan'].iloc[-2] if len(df)>1 else 0
            
            k1.metric("🌡️ Suhu (°C)", f"{data_terkini.get('suhu',0):.1f}", f"{d_suhu:.1f}")
            k2.metric("💧 Kelembapan (%)", f"{data_terkini.get('kelembapan',0):.1f}", f"{d_hum:.1f}")
            k3.metric("🌀 Tekanan (hPa)", f"{data_terkini.get('tekanan',0):.1f}")
            k4.metric("☀️ Cahaya", f"{data_terkini.get('cahaya',0):.0f}")
            k5.metric("☔️ Hujan (Analog)", f"{data_terkini.get('hujan',4095):.0f}") # Menampilkan nilai sensor hujan
            
            st.markdown("---")

            # --- GRAFIK (DIPISAH) ---
            st.subheader("📈 Grafik Historis Data Sensor")
            
            if 'timestamp' in df.columns:
                try:
                    df_grafik = df.set_index('timestamp')
                    col_grafik1, col_grafik2 = st.columns(2)
                    
                    # Grafik Lingkungan
                    with col_grafik1:
                        st.markdown("**🌡️ Lingkungan**")
                        cols_env = ['suhu', 'kelembapan', 'tekanan']
                        valid_cols = [c for c in cols_env if c in df_grafik.columns]
                        if valid_cols: st.line_chart(df_grafik[valid_cols])
                        else: st.warning("Data lingkungan tidak ada.")

                    # Grafik Cahaya & Hujan
                    with col_grafik2:
                        st.markdown("**☀️ Cahaya & 🌧️ Hujan**")
                        # Kita gabung Cahaya dan Hujan di grafik kanan agar efisien
                        cols_light = ['cahaya', 'hujan']
                        valid_cols_light = [c for c in cols_light if c in df_grafik.columns]
                        if valid_cols_light:
                            st.area_chart(df_grafik[valid_cols_light]) 
                        else:
                            st.warning("Data cahaya/hujan tidak ditemukan.")

                except Exception as e: st.error(f"Gagal membuat grafik: {e}")
            else: st.warning("Kolom timestamp tidak ditemukan.")

            # --- TABEL DATA ---
            with st.expander("Lihat Data Lengkap (1000 Terakhir)"):
                if 'timestamp' in df.columns:
                    st.dataframe(df.sort_values(by='timestamp', ascending=False).head(1000).set_index('timestamp'))
                else:
                    st.dataframe(df.tail(1000))

    else:
        with placeholder.container():
            st.info("🔄 Menunggu data dari alat ESP32...")
            st.spinner("Sedang memuat...")

    time.sleep(10)
