import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import pytz
import xmltodict
import urllib3

# MATIKAN WARNING SSL (Supaya tidak muncul pesan error merah di terminal)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

# ----------------- FUNGSI 1: AMBIL DATA BMKG (BYPASS SSL) -----------------
@st.cache_data(ttl=3600)
def get_data_bmkg_lengkap():
    """Mengambil data XML dengan mematikan verifikasi SSL"""
    try:
        # HEADER PALSU (Agar dianggap browser Chrome, bukan bot Python)
        headers_palsu = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # verify=False adalah KUNCI untuk menembus masalah SSL
        response = requests.get(URL_BMKG, timeout=30, headers=headers_palsu, verify=False)
        
        # Parsing XML
        data_dict = xmltodict.parse(response.content)
        forecast = data_dict.get('data', {}).get('forecast', {})
        areas = ensure_list(forecast.get('area'))
        return areas, None
        
    except Exception as e:
        return [], str(e)

def get_pilihan_kota(areas):
    """Membuat dictionary Nama Kota -> Data Area"""
    opsi = {}
    if not areas: return {}
    
    for area in areas:
        nama = area.get('@description')
        if not nama: nama = f"ID {area.get('@id')}"
        opsi[nama] = area
    return opsi

# ----------------- FUNGSI 2: PROSES DATA KOTA TERPILIH -----------------
def proses_data_area(area_data):
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
        
        df = pd.DataFrame(list(data_waktu.values())).sort_values('Waktu')
        df['Jam (WIB)'] = df['Waktu'].dt.strftime('%d-%m %H:%M')
        
        cols = ['Jam (WIB)', 'Cuaca', 'Suhu (°C)', 'Kelembapan (%)']
        final_cols = [c for c in cols if c in df.columns]
        return df[final_cols]
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

# ----------------- LOGIKA STATUS SENSOR -----------------
def get_status_sensor(row):
    h = row.get('hujan', 4095)
    c = row.get('cahaya', 0)
    if h < 1500: return "BADAI", "⛈️"
    if h < 3900: return "HUJAN", "🌧️"
    if c < 100: return "MALAM", "🌃"
    if c > 2500: return "CERAH", "☀️"
    return "BERAWAN", "☁️"

# ================== UI DASHBOARD ==================

# --- SIDEBAR ---
st.sidebar.title("🎛️ Navigasi")
menu = st.sidebar.radio("Menu:", ["📡 Monitor Sensor", "🏢 Data BMKG"])
st.sidebar.markdown("---")

nama_kota_terpilih = "Belum Dipilih"
df_bmkg_hasil = None
status_koneksi = "OK"

if menu == "🏢 Data BMKG":
    st.sidebar.subheader("📍 Lokasi BMKG")
    areas, error_msg = get_data_bmkg_lengkap()
    
    if error_msg:
        st.sidebar.error("Gagal koneksi ke BMKG")
        st.sidebar.caption(f"Error: {error_msg}")
        status_koneksi = "ERROR"
    else:
        opsi_kota = get_pilihan_kota(areas)
        if opsi_kota:
            list_nama = sorted(list(opsi_kota.keys()))
            idx = 0
            if "Kota Malang" in list_nama: idx = list_nama.index("Kota Malang")
            
            pilihan = st.sidebar.selectbox("Pilih Kota:", list_nama, index=idx)
            
            data_area_raw = opsi_kota[pilihan]
            df_bmkg_hasil = proses_data_area(data_area_raw)
            nama_kota_terpilih = pilihan
        else:
            st.sidebar.warning("Data XML Kosong")

# --- MAIN CONTENT ---
placeholder = st.empty()

while True:
    st.cache_data.clear()
    df_iot = baca_data_sensor()
    
    with placeholder.container():
        
        # ---------------- MENU 1: SENSOR ----------------
        if menu == "📡 Monitor Sensor":
            st.title("📡 Monitoring Cuaca Real-Time")
            st.markdown("---")
            
            if df_iot is not None and not df_iot.empty:
                now = df_iot.iloc[-1]
                stat, ico = get_status_sensor(now)
                
                c1, c2 = st.columns([1, 4])
                with c1: st.markdown(f"# {ico}")
                with c2: 
                    st.info(f"Kondisi: **{stat}**")
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
                    st.subheader("Lingkungan")
                    st.line_chart(df_chart[['suhu', 'kelembapan', 'tekanan']])
                with g2: 
                    st.subheader("Cahaya & Hujan")
                    st.area_chart(df_chart[['cahaya', 'hujan']])
                
                st.divider()
                st.subheader("📂 Riwayat Data")
                st.dataframe(df_iot.sort_values(by='timestamp', ascending=False).head(1000), use_container_width=True)

            else:
                st.warning("Menunggu data alat ESP32...")
                st.spinner("Sedang memuat...")

        # ---------------- MENU 2: BMKG ----------------
        elif menu == "🏢 Data BMKG":
            st.title(f"🏢 Prakiraan Cuaca: {nama_kota_terpilih}")
            st.markdown("---")
            
            if status_koneksi == "ERROR":
                st.error("⚠️ Gagal terhubung ke BMKG.")
                st.warning("Cek koneksi internet Anda atau coba matikan VPN/Proxy.")
            elif df_bmkg_hasil is not None:
                st.success(f"Data Prakiraan Cuaca untuk **{nama_kota_terpilih}**")
                st.dataframe(df_bmkg_hasil, use_container_width=True, hide_index=True)
                st.line_chart(df_bmkg_hasil.set_index('Jam (WIB)')[['Suhu (°C)', 'Kelembapan (%)']])
            else:
                st.info("Sedang memuat data...")

    time.sleep(15)
