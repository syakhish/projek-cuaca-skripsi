import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import pytz
import xmltodict

# ----------------- KONFIGURASI HALAMAN -----------------
st.set_page_config(
    page_title="Monitoring Cuaca",
    page_icon="🌦️",
    layout="wide",
)

# --- KONFIGURASI API ---
API_URL = "http://syakhish.pythonanywhere.com/get_data"
# URL XML BMKG Jawa Timur
URL_BMKG = "https://data.bmkg.go.id/DataMKG/MEWS/DigitalForecast/DigitalForecast-JawaTimur.xml"
KOTA_DICARI = "Kota Malang"

# ----------------- FUNGSI BACA SENSOR (ESP32) -----------------
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
        return None

# ----------------- FUNGSI BACA BMKG (TABEL) -----------------
@st.cache_data(ttl=3600)
def ambil_data_bmkg_tabel():
    try:
        response = requests.get(URL_BMKG, timeout=10)
        data_dict = xmltodict.parse(response.content)
        areas = data_dict['data']['forecast']['area']
        
        # Cari Kota Malang
        target_area = None
        if isinstance(areas, list):
            for area in areas:
                if KOTA_DICARI.lower() in area['@description'].lower():
                    target_area = area
                    break
        else:
            if KOTA_DICARI.lower() in areas['@description'].lower(): target_area = areas

        if not target_area: return None, "Lokasi Tidak Ditemukan"
        
        params = target_area['parameter']
        
        # Kita kumpulkan data ke dalam Dictionary waktu
        data_waktu = {}

        for p in params:
            param_id = p['@id']
            # Ambil Suhu (t), Kelembapan (hu), Cuaca (weather)
            if param_id in ['t', 'hu', 'weather']:
                for item in p['timerange']:
                    # Waktu
                    dt_str = item['@datetime']
                    dt = datetime.strptime(dt_str, "%Y%m%d%H%M")
                    dt = pytz.utc.localize(dt).astimezone(pytz.timezone('Asia/Jakarta'))
                    
                    if dt not in data_waktu:
                        data_waktu[dt] = {'Waktu': dt}
                    
                    val = item['value']
                    # Jika value berupa list, ambil yang pertama
                    if isinstance(val, list): val = val[0]['#text']
                    elif isinstance(val, dict): val = val['#text']
                    
                    if param_id == 't': data_waktu[dt]['Suhu (°C)'] = float(val)
                    if param_id == 'hu': data_waktu[dt]['Kelembapan (%)'] = float(val)
                    if param_id == 'weather': 
                        # Translate kode cuaca sederhana
                        kode = val
                        ket = "Berawan"
                        if kode in ['0', '1', '2']: ket = "Cerah"
                        elif kode in ['60', '61', '63']: ket = "Hujan"
                        elif kode in ['95', '97']: ket = "Badai Petir"
                        data_waktu[dt]['Cuaca'] = ket

        # Ubah ke DataFrame
        list_data = list(data_waktu.values())
        df_bmkg = pd.DataFrame(list_data).sort_values('Waktu')
        return df_bmkg, target_area['@description']

    except Exception as e:
        return None, f"Error: {e}"

# ----------------- LOGIKA STATUS SENSOR -----------------
def tentukan_status_sensor(data):
    hujan = data.get('hujan', 4095)
    cahaya = data.get('cahaya', 0)
    
    if hujan < 1500: return "BADAI / LEBAT", "⛈️"
    elif hujan < 2500: return "Hujan Deras", "🌧️"
    elif hujan < 3200: return "Hujan Sedang", "🌧️"
    elif hujan < 3900: return "Gerimis", "🌦️"
    
    if cahaya < 100: return "Malam Hari", "🌃"
    if cahaya > 2500: return "Cerah", "☀️"
    return "Berawan", "☁️"

# ----------------- TAMPILAN UTAMA -----------------
st.title("🌦️ Monitoring Cuaca")
st.markdown("---")

placeholder = st.empty()

while True:
    st.cache_data.clear()
    df_sensor = baca_data_dari_api()
    df_bmkg, lokasi_bmkg = ambil_data_bmkg_tabel()

    if df_sensor is not None and not df_sensor.empty:
        with placeholder.container():
            current = df_sensor.iloc[-1]
            status, icon = tentukan_status_sensor(current)
            
            # --- HEADER STATUS ---
            st.subheader("Status Terkini")
            col_head1, col_head2 = st.columns([1, 3])
            with col_head1:
                st.markdown(f"<h1 style='text-align: center; font-size: 80px;'>{icon}</h1>", unsafe_allow_html=True)
            with col_head2:
                st.info(f"Kondisi: **{status}**")
                st.caption(f"Terakhir update: {current['timestamp'].strftime('%d %b %Y, %H:%M:%S')} WIB")
                if "Hujan" in status or "BADAI" in status:
                    st.error("PERINGATAN: Sedang turun hujan!")

            st.markdown("---")

            # --- METRICS (HANYA SENSOR) ---
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("🌡️ Suhu", f"{current.get('suhu', 0):.1f} °C")
            k2.metric("💧 Kelembapan", f"{current.get('kelembapan', 0):.1f} %")
            k3.metric("🎈 Tekanan", f"{current.get('tekanan', 0):.1f} hPa")
            k4.metric("☀️ Cahaya", f"{current.get('cahaya', 0)}")
            k5.metric("🌧️ Hujan (ADC)", f"{current.get('hujan', 4095)}")

            st.markdown("---")

            # --- GRAFIK (FORMAT LAMA) ---
            st.subheader("📈 Grafik Data Sensor")
            g1, g2 = st.columns(2)
            
            df_plot = df_sensor.set_index('timestamp')

            # Grafik 1: Lingkungan (Suhu, Lembab, Tekanan)
            with g1:
                st.markdown("**Suhu, Kelembapan, & Tekanan**")
                cols_env = ['suhu', 'kelembapan', 'tekanan']
                valid_cols = [c for c in cols_env if c in df_plot.columns]
                st.line_chart(df_plot[valid_cols])
            
            # Grafik 2: Cahaya & Hujan
            with g2:
                st.markdown("**Intensitas Cahaya & Hujan**")
                cols_light = ['cahaya', 'hujan']
                if set(cols_light).issubset(df_plot.columns):
                    st.area_chart(df_plot[cols_light])

            st.markdown("---")

            # --- TABEL DATA (SENSOR & BMKG) ---
            tab1, tab2 = st.tabs(["📂 Data Sensor (History)", "🏢 Data Prakiraan BMKG"])
            
            with tab1:
                st.caption("Menampilkan 1000 data terakhir dari alat.")
                st.dataframe(df_sensor.sort_values(by='timestamp', ascending=False).head(1000))
            
            with tab2:
                st.caption(f"Sumber: Data Terbuka BMKG ({lokasi_bmkg})")
                if df_bmkg is not None:
                    # Format tabel BMKG agar rapi
                    st.dataframe(df_bmkg.style.format({
                        "Suhu (°C)": "{:.1f}",
                        "Kelembapan (%)": "{:.0f}"
                    }))
                else:
                    st.warning("Data BMKG tidak tersedia saat ini.")

    else:
        with placeholder.container():
            st.warning("Menunggu data masuk...")
            st.spinner("Connecting to server...")
            
    time.sleep(15)
