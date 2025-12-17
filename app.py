import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import pytz

# ----------------- KONFIGURASI HALAMAN -----------------
st.set_page_config(
    page_title="Sistem Monitoring Cuaca",
    page_icon="🌦️",
    layout="wide",
)

# --- KONFIGURASI API ---
# 1. API Sensor ESP32 (Backend Kamu)
API_SENSOR = "http://syakhish.pythonanywhere.com/get_data"

# 2. API OpenWeatherMap (Key yang baru kamu berikan)
OWM_API_KEY = "29ff3120fea57ee5ee3298bef9c55b3f" 
KOTA_OWM = "Malang"

# URL untuk mengambil data Forecast (Perkiraan 5 hari / per 3 jam)
URL_OWM = f"https://api.openweathermap.org/data/2.5/forecast?q={KOTA_OWM}&appid={OWM_API_KEY}&units=metric&lang=id"

# ----------------- FUNGSI 1: BACA SENSOR (ESP32) -----------------
def baca_data_sensor():
    try:
        headers = {'Cache-Control': 'no-cache'}
        # Request data ke PythonAnywhere
        r = requests.get(API_SENSOR, timeout=10, headers=headers)
        if r.status_code != 200: return None
        
        data = r.json()
        if not isinstance(data, list): return None
        
        df = pd.DataFrame(data)
        if 'timestamp' not in df.columns: return None
        
        # Konversi Timestamp UNIX ke Waktu WIB
        df['ts'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df.dropna(subset=['ts'], inplace=True)
        df['dt'] = pd.to_datetime(df['ts'], unit='s', utc=True)
        df['timestamp'] = df['dt'].dt.tz_convert(pytz.timezone('Asia/Jakarta'))
        return df
    except: return None

# ----------------- FUNGSI 2: BACA OPENWEATHERMAP -----------------
@st.cache_data(ttl=1800) # Simpan cache selama 30 menit
def baca_data_owm():
    try:
        r = requests.get(URL_OWM, timeout=10)
        data = r.json()
        
        # Cek kode response dari OWM
        if str(data.get("cod")) != "200":
            return None, f"Error OWM: {data.get('message', 'Gagal')}"
        
        # Ambil List Data
        forecast_list = data.get('list', [])
        parsed_data = []
        
        for item in forecast_list:
            # Waktu (UTC -> WIB)
            dt_txt = item['dt_txt']
            dt_obj = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
            dt_utc = pytz.utc.localize(dt_obj)
            dt_wib = dt_utc.astimezone(pytz.timezone('Asia/Jakarta'))
            
            # Data Utama
            temp = item['main']['temp']
            hum = item['main']['humidity']
            desc = item['weather'][0]['description'] # Deskripsi cuaca (Bahasa Indo)
            
            # Icon Mapping (Sederhana)
            icon_code = item['weather'][0]['icon']
            status_simpel = "Berawan"
            if "01" in icon_code: status_simpel = "Cerah"
            elif "02" in icon_code: status_simpel = "Cerah Berawan"
            elif "09" in icon_code or "10" in icon_code: status_simpel = "Hujan"
            elif "11" in icon_code: status_simpel = "Petir"
            
            parsed_data.append({
                'Waktu': dt_wib,
                'Jam': dt_wib.strftime("%d-%m %H:%M"),
                'Suhu (°C)': float(temp),
                'Kelembapan (%)': float(hum),
                'Cuaca': desc.title(),
                'Status': status_simpel
            })
            
        df = pd.DataFrame(parsed_data)
        nama_kota = data.get('city', {}).get('name', KOTA_OWM)
        return df, nama_kota

    except Exception as e:
        return None, str(e)

# ----------------- LOGIKA STATUS SENSOR (RULE-BASED) -----------------
def get_status_sensor(row):
    # Logika menentukan ikon berdasarkan nilai sensor
    h = row.get('hujan', 4095)
    c = row.get('cahaya', 0)
    
    if h < 1500: return "BADAI / LEBAT", "⛈️"
    if h < 2500: return "HUJAN DERAS", "🌧️"
    if h < 3900: return "GERIMIS", "🌦️"
    
    if c < 100: return "MALAM HARI", "🌃"
    if c > 2500: return "CERAH", "☀️"
    return "BERAWAN", "☁️"

# ================== TAMPILAN DASHBOARD (UI) ==================

# --- SIDEBAR NAVIGASI ---
st.sidebar.title("🎛️ Navigasi")
menu = st.sidebar.radio("Pilih Menu:", ["📡 Monitor Sensor", "🌍 Data Pembanding (OWM)"])
st.sidebar.markdown("---")

# Cek Koneksi OWM di Sidebar
df_owm, info_owm = baca_data_owm()

if menu == "🌍 Data Pembanding (OWM)":
    st.sidebar.subheader("📍 Info Lokasi")
    if df_owm is not None:
        st.sidebar.success(f"Terhubung ke: {info_owm}")
    else:
        st.sidebar.warning("Sedang menghubungkan ke API...")
        st.sidebar.caption("Jika error 'Invalid API Key', tunggu 10-60 menit setelah pendaftaran.")

# --- KONTEN UTAMA ---
placeholder = st.empty()

while True:
    st.cache_data.clear() # Agar sensor selalu update real-time
    df_iot = baca_data_sensor()
    
    with placeholder.container():
        
        # ============ TAB 1: SENSOR SENDIRI ============
        if menu == "📡 Monitor Sensor":
            st.title("📡 Monitoring Cuaca Real-Time")
            st.markdown("---")
            
            if df_iot is not None and not df_iot.empty:
                now = df_iot.iloc[-1]
                stat, ico = get_status_sensor(now)
                
                # Header Status
                c1, c2 = st.columns([1, 4])
                with c1: st.markdown(f"# {ico}")
                with c2: 
                    st.info(f"Status: **{stat}**")
                    st.caption(f"Update Terakhir: {now['timestamp'].strftime('%d %b %Y, %H:%M:%S')} WIB")
                    if "Hujan" in stat or "BADAI" in stat: st.error("PERINGATAN: Sedang turun hujan!")
                
                st.divider()

                # Metrik Data
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("🌡️ Suhu", f"{now.get('suhu',0):.1f} °C")
                m2.metric("💧 Lembab", f"{now.get('kelembapan',0):.1f} %")
                m3.metric("🎈 Tekanan", f"{now.get('tekanan',0):.1f} hPa")
                m4.metric("☀️ Cahaya", f"{now.get('cahaya',0)}")
                m5.metric("🌧️ Hujan (ADC)", f"{now.get('hujan',4095)}")
                
                st.divider()

                # Grafik Sensor
                g1, g2 = st.columns(2)
                df_chart = df_iot.set_index('timestamp')
                
                with g1: 
                    st.subheader("📈 Lingkungan")
                    st.line_chart(df_chart[['suhu', 'kelembapan', 'tekanan']])
                with g2: 
                    st.subheader("📈 Cahaya & Hujan")
                    st.area_chart(df_chart[['cahaya', 'hujan']])
                
                # Tabel Riwayat
                st.divider()
                st.subheader("📂 Riwayat Data Sensor (1000 Data Terakhir)")
                st.dataframe(df_iot.sort_values(by='timestamp', ascending=False).head(1000), use_container_width=True)

            else:
                st.warning("Menunggu data masuk dari alat ESP32...")
                st.spinner("Sedang memuat...")

        # ============ TAB 2: OPEN WEATHER MAP ============
        elif menu == "🌍 Data Pembanding (OWM)":
            st.title(f"🌍 Prakiraan Cuaca: {info_owm}")
            st.markdown("---")
            
            if df_owm is not None:
                # Ambil data forecast paling awal (Cuaca saat ini/mendekati saat ini)
                now_owm = df_owm.iloc[0]
                
                # Info Utama
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Suhu (OWM)", f"{now_owm['Suhu (°C)']} °C")
                col_b.metric("Kelembapan (OWM)", f"{now_owm['Kelembapan (%)']} %")
                col_c.metric("Kondisi", f"{now_owm['Cuaca']}")
                
                st.divider()
                
                # Grafik Tren Forecast
                st.subheader("Grafik Tren Prakiraan (5 Hari Kedepan)")
                st.line_chart(df_owm.set_index('Jam')[['Suhu (°C)', 'Kelembapan (%)']])
                
                # Tabel Data Forecast
                st.subheader("Data Lengkap Forecast")
                st.dataframe(df_owm[['Jam', 'Cuaca', 'Suhu (°C)', 'Kelembapan (%)']], use_container_width=True, hide_index=True)
                
            else:
                st.error("Gagal mengambil data dari OpenWeatherMap.")
                st.warning(f"Pesan Sistem: {info_owm}")
                st.info("Catatan: Jika API Key baru dibuat, mohon tunggu 30-60 menit agar aktif.")

    time.sleep(15)
