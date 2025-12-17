import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import pytz
import xmltodict

# ----------------- KONFIGURASI HALAMAN -----------------
st.set_page_config(
    page_title="Sistem Monitoring Cuaca",
    page_icon="🌦️",
    layout="wide",
)

# --- KONFIGURASI API ---
API_URL = "http://syakhish.pythonanywhere.com/get_data"
URL_BMKG = "https://data.bmkg.go.id/DataMKG/MEWS/DigitalForecast/DigitalForecast-JawaTimur.xml"

# ----------------- FUNGSI BANTUAN -----------------
def ensure_list(item):
    if item is None: return []
    if isinstance(item, list): return item
    return [item]

# ----------------- FUNGSI 1: AMBIL LIST KOTA BMKG -----------------
@st.cache_data(ttl=3600)
def get_daftar_kota_bmkg():
    try:
        response = requests.get(URL_BMKG, timeout=10)
        data_dict = xmltodict.parse(response.content)
        forecast = data_dict.get('data', {}).get('forecast', {})
        areas = ensure_list(forecast.get('area'))
        
        opsi_kota = {}
        for area in areas:
            nama = area.get('@description', 'Tanpa Nama')
            opsi_kota[nama] = area
        return opsi_kota
    except: return {}

# ----------------- FUNGSI 2: PROSES DATA BMKG -----------------
def proses_data_bmkg(area_data):
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
                        if kode in ['0','1','2']: status = "Cerah"
                        elif kode in ['3','4']: status = "Berawan"
                        elif kode in ['5','10','45']: status = "Kabut"
                        elif kode in ['60','61','63','80']: status = "Hujan"
                        elif kode in ['95','97']: status = "Hujan Petir"
                        data_waktu[dt]['Cuaca'] = status

        if not data_waktu: return None
        list_data = list(data_waktu.values())
        df = pd.DataFrame(list_data).sort_values('Waktu')
        
        df['Jam (WIB)'] = df['Waktu'].dt.strftime('%d-%m %H:%M')
        cols = ['Jam (WIB)', 'Cuaca', 'Suhu (°C)', 'Kelembapan (%)']
        return df[[c for c in cols if c in df.columns]]
    except: return None

# ----------------- FUNGSI 3: BACA SENSOR -----------------
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

# ----------------- LOGIKA STATUS -----------------
def get_status_sensor(row):
    h = row.get('hujan', 4095)
    c = row.get('cahaya', 0)
    if h < 1500: return "BADAI", "⛈️"
    if h < 3900: return "HUJAN", "🌧️"
    if c < 100: return "MALAM", "🌃"
    if c > 2500: return "CERAH", "☀️"
    return "BERAWAN", "☁️"

# ================== INTERFACE (UI) ==================

# 1. SIDEBAR NAVIGASI
st.sidebar.title("🎛️ Panel Kontrol")
menu_pilihan = st.sidebar.radio(
    "Pilih Tampilan:", 
    ["📡 Monitor Sensor", "🏢 Data BMKG"]
)

st.sidebar.markdown("---")

# Logic Pilihan Kota (Hanya muncul jika menu BMKG dipilih atau untuk info)
nama_kota_bmkg = "Belum Dipilih"
df_bmkg_view = None

if menu_pilihan == "🏢 Data BMKG":
    daftar_kota = get_daftar_kota_bmkg()
    if daftar_kota:
        list_nama = sorted(list(daftar_kota.keys()))
        idx_def = 0
        if "Kota Malang" in list_nama: idx_def = list_nama.index("Kota Malang")
        
        kota_pilihan = st.sidebar.selectbox("Pilih Lokasi:", list_nama, index=idx_def)
        
        # Proses Data
        raw = daftar_kota[kota_pilihan]
        df_bmkg_view = proses_data_bmkg(raw)
        nama_kota_bmkg = kota_pilihan

st.sidebar.info("Auto-refresh setiap 15 detik.")

# 2. MAIN LOOP
placeholder = st.empty()

while True:
    st.cache_data.clear() # Clear cache agar sensor update
    df_iot = baca_data_sensor()
    
    with placeholder.container():
        
        # ================= TAMPILAN 1: SENSOR =================
        if menu_pilihan == "📡 Monitor Sensor":
            st.title("📡 Monitoring Cuaca Real-Time")
            st.markdown("---")
            
            if df_iot is not None and not df_iot.empty:
                now = df_iot.iloc[-1]
                stat, ico = get_status_sensor(now)
                
                # Header
                c1, c2 = st.columns([1, 4])
                with c1: st.markdown(f"# {ico}")
                with c2: 
                    st.info(f"Status: **{stat}**")
                    st.caption(f"Update: {now['timestamp'].strftime('%d %b %Y, %H:%M:%S')} WIB")
                    if "Hujan" in stat or "BADAI" in stat: st.error("PERINGATAN HUJAN!")
                
                st.divider()

                # Metrics
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("🌡️ Suhu", f"{now.get('suhu',0):.1f} °C")
                m2.metric("💧 Lembab", f"{now.get('kelembapan',0):.1f} %")
                m3.metric("🎈 Tekanan", f"{now.get('tekanan',0):.1f} hPa")
                m4.metric("☀️ Cahaya", f"{now.get('cahaya',0)}")
                m5.metric("🌧️ Hujan (ADC)", f"{now.get('hujan',4095)}")
                
                st.divider()

                # Grafik
                g1, g2 = st.columns(2)
                df_chart = df_iot.set_index('timestamp')
                with g1: 
                    st.subheader("📈 Lingkungan")
                    st.line_chart(df_chart[['suhu', 'kelembapan', 'tekanan']])
                with g2: 
                    st.subheader("📈 Cahaya & Hujan")
                    st.area_chart(df_chart[['cahaya', 'hujan']])
                
                # Tabel History
                st.divider()
                st.subheader("📂 Riwayat Data Sensor (1000 Data)")
                st.dataframe(df_iot.sort_values(by='timestamp', ascending=False).head(1000), use_container_width=True)
                
            else:
                st.warning("Menunggu data dari alat ESP32...")
                st.spinner("Sedang memuat...")

        # ================= TAMPILAN 2: BMKG =================
        elif menu_pilihan == "🏢 Data BMKG":
            st.title(f"🏢 Prakiraan Cuaca BMKG: {nama_kota_bmkg}")
            st.markdown("---")
            
            if df_bmkg_view is not None:
                st.success(f"Menampilkan data prakiraan untuk wilayah **{nama_kota_bmkg}**")
                
                # Tampilkan Tabel
                st.dataframe(df_bmkg_view, use_container_width=True, hide_index=True)
                
                # Tampilkan Grafik Sederhana BMKG
                st.subheader("Grafik Tren Prakiraan")
                st.line_chart(df_bmkg_view.set_index('Jam (WIB)')[['Suhu (°C)', 'Kelembapan (%)']])
            else:
                st.warning("Silakan pilih kota di Sidebar sebelah kiri, atau data sedang tidak tersedia.")

    # Refresh Rate
    time.sleep(15)
