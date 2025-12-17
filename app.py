import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import pytz
import xmltodict  # Pastikan library ini terinstall

# ----------------- KONFIGURASI HALAMAN -----------------
st.set_page_config(
    page_title="Monitoring Cuaca Malang",
    page_icon="🍎",
    layout="wide",
)

# --- KONFIGURASI API & LOKASI ---
API_URL = "http://syakhish.pythonanywhere.com/get_data"
URL_BMKG = "https://data.bmkg.go.id/DataMKG/MEWS/DigitalForecast/DigitalForecast-JawaTimur.xml"
ID_KOTA_BMKG = "501262"  # ID Kota Malang

# ----------------- FUNGSI BACA DATA SENSOR -----------------
def baca_data_dari_api():
    try:
        headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache', 'Expires': '0'}
        response = requests.get(API_URL, timeout=15, headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data or not isinstance(data, list): return None
        df = pd.DataFrame(data)
        if 'timestamp' not in df.columns: return None
        
        # Konversi Timestamp
        df['timestamp_numeric'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df.dropna(subset=['timestamp_numeric'], inplace=True)
        
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_numeric'], unit='s', utc=True)
        zona_wib = pytz.timezone('Asia/Jakarta')
        df['timestamp'] = df['timestamp_utc'].dt.tz_convert(zona_wib) 
        
        return df
    except Exception as e:
        st.error(f"Error Sensor: {e}")
        return None

# ----------------- FUNGSI BACA DATA BMKG -----------------
@st.cache_data(ttl=3600)
def ambil_data_bmkg():
    try:
        response = requests.get(URL_BMKG, timeout=10)
        data_dict = xmltodict.parse(response.content)
        areas = data_dict['data']['forecast']['area']
        
        target_area = None
        if isinstance(areas, list):
            for area in areas:
                if area['@id'] == ID_KOTA_BMKG:
                    target_area = area
                    break
        else:
            if areas['@id'] == ID_KOTA_BMKG: target_area = areas

        if not target_area: return None, "Lokasi Tidak Ditemukan"

        nama_kota = target_area['@description']
        params = target_area['parameter']
        
        temp_data = []
        hum_data = []
        
        for p in params:
            if p['@id'] == 't': # Suhu
                for t in p['timerange']:
                    waktu = datetime.strptime(t['@datetime'], "%Y%m%d%H%M")
                    waktu = pytz.utc.localize(waktu).astimezone(pytz.timezone('Asia/Jakarta'))
                    val = float(t['value'][0]['#text'])
                    temp_data.append({'timestamp': waktu, 'Suhu BMKG': val})
            
            if p['@id'] == 'hu': # Kelembapan
                for h in p['timerange']:
                    waktu = datetime.strptime(h['@datetime'], "%Y%m%d%H%M")
                    waktu = pytz.utc.localize(waktu).astimezone(pytz.timezone('Asia/Jakarta'))
                    val = float(h['value']['#text'])
                    hum_data.append({'timestamp': waktu, 'Kelembapan BMKG': val})

        df_temp = pd.DataFrame(temp_data).set_index('timestamp')
        df_hum = pd.DataFrame(hum_data).set_index('timestamp')
        df_bmkg = df_temp.join(df_hum, how='outer')
        return df_bmkg, nama_kota

    except Exception as e:
        return None, f"Error BMKG: {str(e)}"

# ----------------- STATUS CUACA -----------------
def tentukan_status_cuaca(data):
    imcs = data.get('imcs', 0.0)
    cahaya = data.get('cahaya', 0)
    kelembapan = data.get('kelembapan', 0.0)
    hujan = data.get('hujan', 4095)
    
    BATAS_MALAM = 100        
    BATAS_BERAWAN = 2500     
    
    if hujan < 1500: return "BADAI / LEBAT", "⛈️"
    elif hujan < 2500: return "Hujan Deras", "🌧️"
    elif hujan < 3900: return "Gerimis", "🌦️"
    
    if cahaya < BATAS_MALAM: return "Malam Hari", "🌃"
    elif imcs > 0.95 and cahaya < BATAS_BERAWAN: return "Mendung", "☁️"
    elif cahaya > BATAS_BERAWAN:
        if kelembapan < 70: return "Cerah", "☀️"
        else: return "Cerah Lembab", "🌤️"
    else: return "Berawan", "☁️"

# ----------------- TAMPILAN DASHBOARD -----------------
st.title("🍎 Monitoring Cuaca Kota Malang")
st.markdown("---")

placeholder = st.empty()

while True:
    st.cache_data.clear()
    df_sensor = baca_data_dari_api()
    df_bmkg, lokasi_bmkg = ambil_data_bmkg()

    if df_sensor is not None and not df_sensor.empty:
        with placeholder.container():
            current = df_sensor.iloc[-1]
            status, icon = tentukan_status_cuaca(current)
            
            # --- HEADER INFO ---
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader("📡 Status Sensor")
                if "Hujan" in status or "BADAI" in status:
                    st.error(f"PERINGATAN: {status}!", icon="🌧️")
                else:
                    st.info(f"Kondisi: {status} | {current['timestamp'].strftime('%H:%M:%S')}")
                st.markdown(f"<h1 style='font-size: 40px;'>{icon} {status}</h1>", unsafe_allow_html=True)
            
            with c2:
                st.subheader(f"🏢 Data BMKG ({lokasi_bmkg})")
                if df_bmkg is not None:
                    now = datetime.now(pytz.timezone('Asia/Jakarta'))
                    # Cari data terdekat (nearest)
                    try:
                        idx = df_bmkg.index.get_indexer([now], method='nearest')[0]
                        bmkg_now = df_bmkg.iloc[idx]
                        st.success(f"🌡️ {bmkg_now['Suhu BMKG']}°C | 💧 {bmkg_now['Kelembapan BMKG']}%")
                    except:
                        st.warning("Menunggu Sinkronisasi BMKG")
                else:
                    st.warning("BMKG Offline")

            st.markdown("---")

            # --- METRIC KOMPARASI ---
            k1, k2, k3, k4, k5 = st.columns(5)
            
            # Sensor Values
            t_sens = current.get('suhu', 0)
            h_sens = current.get('kelembapan', 0)
            p_sens = current.get('tekanan', 0)
            l_sens = current.get('cahaya', 0)
            r_sens = current.get('hujan', 4095)
            
            # BMKG Values
            t_bmkg = bmkg_now['Suhu BMKG'] if df_bmkg is not None and 'bmkg_now' in locals() else 0
            h_bmkg = bmkg_now['Kelembapan BMKG'] if df_bmkg is not None and 'bmkg_now' in locals() else 0
            
            k1.metric("Suhu (°C)", f"{t_sens:.1f}", f"{t_sens - t_bmkg:.1f} vs BMKG", delta_color="inverse")
            k2.metric("Kelembapan (%)", f"{h_sens:.1f}", f"{h_sens - h_bmkg:.1f} vs BMKG", delta_color="inverse")
            k3.metric("Tekanan (hPa)", f"{p_sens:.1f}")
            k4.metric("Cahaya", f"{l_sens}")
            k5.metric("Hujan (ADC)", f"{r_sens}")
            
            st.markdown("---")

            # --- GRAFIK (LAYOUT LAMA KEMBALI) ---
            st.subheader("📈 Grafik Historis")
            
            col_grafik1, col_grafik2 = st.columns(2)
            
            # Persiapan Data Grafik
            df_plot = df_sensor.set_index('timestamp')
            
            # GRAFIK 1 (KIRI): LINGKUNGAN (Suhu, Lembab, Tekanan) + BMKG
            with col_grafik1:
                st.markdown("**🌡️ Lingkungan (Suhu, Kelembapan, Tekanan)**")
                
                # Kita gabungkan data Sensor dan BMKG agar muncul dalam satu grafik
                cols_env = ['suhu', 'kelembapan', 'tekanan']
                # Filter hanya kolom yang ada
                cols_env_valid = [c for c in cols_env if c in df_plot.columns]
                df_env = df_plot[cols_env_valid].copy()
                
                # Tambahkan garis BMKG jika ada (untuk perbandingan)
                if df_bmkg is not None:
                    # Gabungkan (Concatenate)
                    df_combined = pd.concat([df_env, df_bmkg[['Suhu BMKG', 'Kelembapan BMKG']]], axis=1)
                    st.line_chart(df_combined)
                else:
                    st.line_chart(df_env)

            # GRAFIK 2 (KANAN): CAHAYA & HUJAN
            with col_grafik2:
                st.markdown("**☀️ Cahaya & 🌧️ Hujan**")
                cols_light = ['cahaya', 'hujan']
                if set(cols_light).issubset(df_plot.columns):
                    st.area_chart(df_plot[cols_light])
                else:
                    st.warning("Data Cahaya/Hujan belum tersedia")

            # --- TABEL (FIX: TAMPILKAN 1000 DATA) ---
            with st.expander("📂 Data Lengkap (Hingga 1000 Data Terakhir)"):
                # Di sini saya ubah head(100) menjadi head(1000)
                st.dataframe(df_sensor.sort_values(by='timestamp', ascending=False).head(1000))

    else:
        with placeholder.container():
            st.warning("⏳ Menunggu data ESP32...")
            st.spinner("Sedang memuat...")
            
    time.sleep(15)
