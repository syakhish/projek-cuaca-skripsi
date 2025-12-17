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
# URL XML BMKG Jawa Timur (Bisa diganti provinsi lain jika mau)
URL_BMKG = "https://data.bmkg.go.id/DataMKG/MEWS/DigitalForecast/DigitalForecast-JawaTimur.xml"

# ----------------- FUNGSI BANTUAN ANTI-ERROR -----------------
def ensure_list(item):
    """Memaksa data menjadi list agar tidak crash"""
    if item is None: return []
    if isinstance(item, list): return item
    return [item]

# ----------------- FUNGSI 1: AMBIL DAFTAR KOTA (CACHE) -----------------
@st.cache_data(ttl=3600)
def get_daftar_kota_bmkg():
    """Mengambil semua nama kota yang ada di XML untuk menu pilihan"""
    try:
        response = requests.get(URL_BMKG, timeout=10)
        data_dict = xmltodict.parse(response.content)
        forecast = data_dict.get('data', {}).get('forecast', {})
        areas = ensure_list(forecast.get('area'))
        
        # Buat Dictionary: {"Nama Kota": Data_Area_Full}
        opsi_kota = {}
        for area in areas:
            nama = area.get('@description', 'Tanpa Nama')
            opsi_kota[nama] = area
            
        return opsi_kota
    except Exception as e:
        return None

# ----------------- FUNGSI 2: PROSES DATA KOTA TERPILIH -----------------
def proses_data_bmkg(area_data):
    """Mengolah data area yang dipilih user menjadi DataFrame"""
    try:
        params = ensure_list(area_data.get('parameter'))
        data_waktu = {}

        for p in params:
            param_id = p.get('@id')
            if param_id in ['t', 'hu', 'weather']:
                timeranges = ensure_list(p.get('timerange'))
                for item in timeranges:
                    dt_str = item.get('@datetime')
                    try:
                        dt = datetime.strptime(dt_str, "%Y%m%d%H%M")
                        dt = pytz.utc.localize(dt).astimezone(pytz.timezone('Asia/Jakarta'))
                    except: continue

                    if dt not in data_waktu: data_waktu[dt] = {'Waktu': dt}
                    
                    val_raw = item.get('value')
                    val = "0"
                    if isinstance(val_raw, list): val = val_raw[0].get('#text', '0')
                    elif isinstance(val_raw, dict): val = val_raw.get('#text', '0')
                    else: val = str(val_raw)
                    
                    if param_id == 't': data_waktu[dt]['Suhu (°C)'] = float(val)
                    if param_id == 'hu': data_waktu[dt]['Kelembapan (%)'] = float(val)
                    if param_id == 'weather':
                        kode = val
                        status = "Berawan"
                        if kode in ['0', '1', '2']: status = "Cerah"
                        elif kode in ['3', '4']: status = "Berawan"
                        elif kode in ['5', '10', '45']: status = "Kabut"
                        elif kode in ['60', '61', '63', '80']: status = "Hujan"
                        elif kode in ['95', '97']: status = "Hujan Petir"
                        data_waktu[dt]['Cuaca'] = status

        if not data_waktu: return None

        list_data = list(data_waktu.values())
        df = pd.DataFrame(list_data).sort_values('Waktu')
        
        # Format Tampilan
        df['Jam (WIB)'] = df['Waktu'].dt.strftime('%d-%m %H:%M')
        cols = ['Jam (WIB)', 'Cuaca', 'Suhu (°C)', 'Kelembapan (%)']
        return df[[c for c in cols if c in df.columns]]

    except Exception as e:
        return None

# ----------------- FUNGSI 3: BACA SENSOR (ESP32) -----------------
def baca_data_sensor():
    try:
        headers = {'Cache-Control': 'no-cache'}
        r = requests.get(API_URL, timeout=10, headers=headers)
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

# ----------------- LOGIKA STATUS SENSOR -----------------
def get_status_sensor(row):
    h = row.get('hujan', 4095)
    c = row.get('cahaya', 0)
    if h < 1500: return "BADAI", "⛈️"
    if h < 3900: return "HUJAN", "🌧️"
    if c < 100: return "MALAM", "🌃"
    if c > 2500: return "CERAH", "☀️"
    return "BERAWAN", "☁️"

# ================= TAMPILAN UTAMA =================
st.sidebar.title("⚙️ Pengaturan")

# --- FITUR PENCARIAN KOTA (SIDEBAR) ---
daftar_kota = get_daftar_kota_bmkg()
target_bmkg_df = None
nama_kota_terpilih = "Tidak Diketahui"

if daftar_kota:
    # Buat Dropdown Pilihan
    list_nama = sorted(list(daftar_kota.keys()))
    
    # Default pilih "Kota Malang" jika ada, jika tidak pilih yang pertama
    index_default = 0
    if "Kota Malang" in list_nama:
        index_default = list_nama.index("Kota Malang")
        
    kota_pilihan = st.sidebar.selectbox(
        "Pilih Lokasi BMKG:", 
        list_nama, 
        index=index_default
    )
    
    st.sidebar.success(f"Lokasi: {kota_pilihan}")
    
    # Proses Data BMKG untuk kota yang dipilih
    raw_data_kota = daftar_kota[kota_pilihan]
    target_bmkg_df = proses_data_bmkg(raw_data_kota)
    nama_kota_terpilih = kota_pilihan
else:
    st.sidebar.error("Gagal memuat daftar kota dari BMKG")

st.sidebar.markdown("---")
st.sidebar.info("Dashboard auto-refresh setiap 15 detik.")

# --- MAIN CONTENT ---
st.title("🌦️ Monitoring Cuaca & Komparasi")
st.markdown("---")

placeholder = st.empty()

while True:
    # Baca Sensor Real-time
    st.cache_data.clear() # Clear cache sensor only
    df_iot = baca_data_sensor()
    
    with placeholder.container():
        if df_iot is not None and not df_iot.empty:
            now = df_iot.iloc[-1]
            stat, ico = get_status_sensor(now)
            
            # 1. HEADER
            c1, c2 = st.columns([1, 4])
            with c1: st.markdown(f"# {ico}")
            with c2: 
                st.info(f"Status Sensor: **{stat}**")
                st.caption(f"Update: {now['timestamp'].strftime('%H:%M:%S')}")
            
            st.divider()

            # 2. METRIK
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Suhu", f"{now.get('suhu',0):.1f} °C")
            m2.metric("Lembab", f"{now.get('kelembapan',0):.1f} %")
            m3.metric("Tekanan", f"{now.get('tekanan',0):.1f} hPa")
            m4.metric("Cahaya", f"{now.get('cahaya',0)}")
            m5.metric("Hujan (ADC)", f"{now.get('hujan',4095)}")
            
            st.divider()

            # 3. GRAFIK
            st.subheader("Grafik Sensor")
            g1, g2 = st.columns(2)
            df_chart = df_iot.set_index('timestamp')
            
            with g1: 
                st.caption("Lingkungan")
                st.line_chart(df_chart[['suhu', 'kelembapan', 'tekanan']])
            with g2: 
                st.caption("Cahaya & Hujan")
                st.area_chart(df_chart[['cahaya', 'hujan']])
            
            # 4. TABEL PEMBANDING (BMKG)
            st.divider()
            st.subheader(f"Data Pembanding BMKG: {nama_kota_terpilih}")
            
            if target_bmkg_df is not None:
                st.dataframe(target_bmkg_df, use_container_width=True, hide_index=True)
            else:
                st.warning("Data BMKG untuk kota ini tidak lengkap/gagal dimuat.")
        
        else:
            st.warning("Menunggu data dari alat ESP32...")
            
    time.sleep(15)
