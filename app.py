import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import pytz
import os  # Library untuk cek file lokal

# ----------------- KONFIGURASI HALAMAN -----------------
st.set_page_config(
    page_title="Sistem Monitoring Cuaca",
    page_icon="🌦️",
    layout="wide",
)

# --- KONFIGURASI GAMBAR LOGO ---
# Ganti "UBLOGO.png" sesuai dengan nama file dan ekstensi gambar kamu (.jpg/.png)
FILE_LOGO_LOKAL = "UBLOGO.png" 
URL_LOGO_ONLINE = "https://upload.wikimedia.org/wikipedia/commons/b/bb/Logo_Universitas_Brawijaya.png"

# --- KONFIGURASI API ---
API_SENSOR = "http://syakhish.pythonanywhere.com/get_data"
OWM_API_KEY = "29ff3120fea57ee5ee3298bef9c55b3f" 
KOTA_OWM = "Malang"
URL_OWM = f"https://api.openweathermap.org/data/2.5/forecast?q={KOTA_OWM}&appid={OWM_API_KEY}&units=metric&lang=id"

# ----------------- FUNGSI BACA SENSOR -----------------
def baca_data_sensor():
    try:
        headers = {'Cache-Control': 'no-cache'}
        r = requests.get(API_SENSOR, timeout=10, headers=headers)
        if r.status_code != 200: return None
        data = r.json()
        if not isinstance(data, list): return None
        df = pd.DataFrame(data)
        if 'timestamp' not in df.columns: return None
        
        df['ts'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df.dropna(subset=['ts'], inplace=True)
        df['dt'] = pd.to_datetime(df['ts'], unit='s', utc=True)
        df['timestamp'] = df['dt'].dt.tz_convert(pytz.timezone('Asia/Jakarta'))
        return df
    except: return None

# ----------------- FUNGSI BACA OWM -----------------
@st.cache_data(ttl=1800) 
def baca_data_owm():
    try:
        r = requests.get(URL_OWM, timeout=10)
        data = r.json()
        
        if str(data.get("cod")) != "200":
            return None, f"Error OWM: {data.get('message', 'Gagal')}"
        
        forecast_list = data.get('list', [])
        parsed_data = []
        
        for item in forecast_list:
            dt_txt = item['dt_txt']
            dt_obj = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
            dt_utc = pytz.utc.localize(dt_obj)
            dt_wib = dt_utc.astimezone(pytz.timezone('Asia/Jakarta'))
            
            temp = item['main']['temp']
            hum = item['main']['humidity']
            desc = item['weather'][0]['description']
            
            parsed_data.append({
                'Waktu': dt_wib,
                'Jam': dt_wib.strftime("%d-%m %H:%M"),
                'Suhu (°C)': float(temp),
                'Kelembapan (%)': float(hum),
                'Cuaca': desc.title()
            })
            
        df = pd.DataFrame(parsed_data)
        nama_kota = data.get('city', {}).get('name', KOTA_OWM)
        return df, nama_kota

    except Exception as e:
        return None, str(e)

# ----------------- LOGIKA STATUS SENSOR -----------------
def get_status_sensor(row):
    h = row.get('hujan', 4095)
    c = row.get('cahaya', 0)
    
    if h < 1500: return "BADAI / LEBAT", "⛈️"
    if h < 2500: return "HUJAN DERAS", "🌧️"
    if h < 3900: return "GERIMIS", "🌦️"
    
    if c < 100: return "MALAM HARI", "🌃"
    if c > 2500: return "CERAH", "☀️"
    return "BERAWAN", "☁️"

# ================== TAMPILAN DASHBOARD ==================

# --- SIDEBAR (HEADER KHUSUS UB) ---
with st.sidebar:
    # 1. Tampilkan Logo
    # Cek apakah file lokal ada?
    col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
    with col_logo2:
        if os.path.exists(FILE_LOGO_LOKAL):
            st.image(FILE_LOGO_LOKAL, use_container_width=True)
        else:
            # Fallback ke online jika file lokal tidak ada
            st.image(URL_LOGO_ONLINE, use_container_width=True)
    
    # 2. Teks Universitas Brawijaya (Tebal & Tengah)
    st.markdown("<h3 style='text-align: center;'>Universitas Brawijaya</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: small;'>Skripsi Teknik Komputer</p>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 3. Navigasi
    st.title("🎛️ Navigasi")
    menu = st.radio("Pilih Menu:", [
        "📡 Monitor Sensor", 
        "🌍 Data API (OWM)", 
        "⚖️ Komparasi & Validasi"
    ])
    
    st.markdown("---")
    
    # Info Lokasi API
    df_owm, info_owm = baca_data_owm()
    if menu != "📡 Monitor Sensor":
        st.subheader("📍 Lokasi API")
        if df_owm is not None:
            st.success(f"{info_owm}")
        else:
            st.warning("Menghubungkan...")

# --- KONTEN UTAMA ---
placeholder = st.empty()

while True:
    st.cache_data.clear() 
    df_iot = baca_data_sensor()
    
    with placeholder.container():
        
        # ============ TAB 1: SENSOR SENDIRI ============
        if menu == "📡 Monitor Sensor":
            st.title("📡 Monitoring Cuaca Real-Time")
            st.markdown("---")
            
            if df_iot is not None and not df_iot.empty:
                now = df_iot.iloc[-1]
                stat, ico = get_status_sensor(now)
                
                c1, c2 = st.columns([1, 4])
                with c1: st.markdown(f"# {ico}")
                with c2: 
                    st.info(f"Status: **{stat}**")
                    st.caption(f"Update: {now['timestamp'].strftime('%d %b %Y, %H:%M:%S')} WIB")
                    if "Hujan" in stat or "BADAI" in stat: st.error("PERINGATAN HUJAN!")
                
                st.divider()

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("🌡️ Suhu", f"{now.get('suhu',0):.1f} °C")
                m2.metric("💧 Lembab", f"{now.get('kelembapan',0):.1f} %")
                m3.metric("🎈 Tekanan", f"{now.get('tekanan',0):.1f} hPa")
                m4.metric("☀️ Cahaya", f"{now.get('cahaya',0)}")
                m5.metric("🌧️ Hujan (ADC)", f"{now.get('hujan',4095)}")
                
                st.divider()

                g1, g2 = st.columns(2)
                df_chart = df_iot.set_index('timestamp')
                with g1: 
                    st.subheader("📈 Lingkungan")
                    st.line_chart(df_chart[['suhu', 'kelembapan', 'tekanan']])
                with g2: 
                    st.subheader("📈 Cahaya & Hujan")
                    st.area_chart(df_chart[['cahaya', 'hujan']])
                
                st.divider()
                st.subheader("📂 Riwayat Data Sensor")
                st.dataframe(df_iot.sort_values(by='timestamp', ascending=False).head(1000), use_container_width=True)

            else:
                st.warning("Menunggu data alat ESP32...")
                st.spinner("Sedang memuat...")

        # ============ TAB 2: OPEN WEATHER MAP ============
        elif menu == "🌍 Data API (OWM)":
            st.title(f"🌍 Prakiraan Cuaca: {info_owm}")
            st.markdown("---")
            
            if df_owm is not None:
                now_owm = df_owm.iloc[0]
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Suhu (OWM)", f"{now_owm['Suhu (°C)']} °C")
                col_b.metric("Kelembapan (OWM)", f"{now_owm['Kelembapan (%)']} %")
                col_c.metric("Kondisi", f"{now_owm['Cuaca']}")
                
                st.divider()
                st.subheader("Grafik Tren 5 Hari")
                st.line_chart(df_owm.set_index('Jam')[['Suhu (°C)', 'Kelembapan (%)']])
                
                st.subheader("Data Lengkap Forecast")
                st.dataframe(df_owm[['Jam', 'Cuaca', 'Suhu (°C)', 'Kelembapan (%)']], use_container_width=True, hide_index=True)
            else:
                st.error("Gagal mengambil data OpenWeatherMap.")

        # ============ TAB 3: KOMPARASI & VALIDASI ============
        elif menu == "⚖️ Komparasi & Validasi":
            st.title("⚖️ Validasi Data: Sensor vs API")
            st.markdown("---")

            if df_iot is not None and df_owm is not None:
                sensor_now = df_iot.iloc[-1]
                owm_now = df_owm.iloc[0]

                st.subheader("1. Perbandingan Nilai Terkini")
                
                t_sensor = sensor_now.get('suhu', 0)
                t_owm = owm_now['Suhu (°C)']
                delta_t = t_sensor - t_owm

                h_sensor = sensor_now.get('kelembapan', 0)
                h_owm = owm_now['Kelembapan (%)']
                delta_h = h_sensor - h_owm

                col_comp1, col_comp2 = st.columns(2)
                
                col_comp1.markdown("### 🌡️ Temperatur")
                col_comp1.metric("Sensor (Alat)", f"{t_sensor:.1f} °C")
                col_comp1.metric("API (OpenWeather)", f"{t_owm:.1f} °C", f"{delta_t:.1f} °C (Selisih)", delta_color="inverse")
                
                col_comp2.markdown("### 💧 Kelembapan")
                col_comp2.metric("Sensor (Alat)", f"{h_sensor:.1f} %")
                col_comp2.metric("API (OpenWeather)", f"{h_owm:.1f} %", f"{delta_h:.1f} % (Selisih)", delta_color="inverse")

                st.divider()

                st.subheader("2. Tabel Validasi")
                comparison_data = {
                    "Parameter": ["Suhu (°C)", "Kelembapan (%)", "Status Cuaca"],
                    "📡 Sensor ESP32": [f"{t_sensor:.1f}", f"{h_sensor:.1f}", get_status_sensor(sensor_now)[0]],
                    "🌍 OpenWeatherMap": [f"{t_owm:.1f}", f"{h_owm:.1f}", owm_now['Cuaca']],
                    "Selisih (Error)": [f"{abs(delta_t):.1f}", f"{abs(delta_h):.1f}", "-"]
                }
                st.table(pd.DataFrame(comparison_data))
                
                st.divider()
                
                st.subheader("3. Visualisasi Perbandingan")
                bar_data = pd.DataFrame({
                    "Sumber": ["Sensor", "API", "Sensor", "API"],
                    "Tipe": ["Suhu", "Suhu", "Kelembapan", "Kelembapan"],
                    "Nilai": [t_sensor, t_owm, h_sensor, h_owm]
                })
                
                g_comp1, g_comp2 = st.columns(2)
                
                with g_comp1:
                    st.caption("Perbandingan Suhu (°C)")
                    st.bar_chart(bar_data[bar_data["Tipe"] == "Suhu"].set_index("Sumber")["Nilai"])
                
                with g_comp2:
                    st.caption("Perbandingan Kelembapan (%)")
                    st.bar_chart(bar_data[bar_data["Tipe"] == "Kelembapan"].set_index("Sumber")["Nilai"])

            else:
                st.warning("Menunggu data lengkap dari Sensor dan API untuk melakukan komparasi...")

    time.sleep(15)
