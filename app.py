import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta  # <--- PERBAIKAN DI SINI (Ditambah timedelta)
import pytz
import xmltodict
import urllib3
import random

# Matikan warning SSL
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

# ----------------- DATA CADANGAN (OFFLINE MODE) -----------------
# Data ini akan dipakai jika internet error / BMKG down
def get_data_dummy_malang():
    # Simulasi data 24 jam ke depan
    now = datetime.now(pytz.timezone('Asia/Jakarta'))
    # timedelta sekarang sudah dikenali
    dummy_times = [now + timedelta(hours=i*6) for i in range(4)] 
    
    # Format agar mirip struktur XML BMKG
    params = [
        {'@id': 't', 'timerange': [
            {'@datetime': t.strftime("%Y%m%d%H%M"), 'value': [{'#text': str(random.randint(22, 30))}]} 
            for t in dummy_times
        ]},
        {'@id': 'hu', 'timerange': [
            {'@datetime': t.strftime("%Y%m%d%H%M"), 'value': {'#text': str(random.randint(60, 90))}} 
            for t in dummy_times
        ]},
        {'@id': 'weather', 'timerange': [
            {'@datetime': t.strftime("%Y%m%d%H%M"), 'value': {'#text': random.choice(['1', '3', '60'])}} 
            for t in dummy_times
        ]}
    ]
    return {'@description': 'Kota Malang (OFFLINE MODE)', 'parameter': params}

# ----------------- FUNGSI 1: AMBIL DATA BMKG (TRY-EXCEPT) -----------------
@st.cache_data(ttl=3600)
def get_data_bmkg_lengkap():
    """Mengambil data XML. Jika gagal, pakai data dummy."""
    try:
        headers_palsu = {'User-Agent': 'Mozilla/5.0'}
        # Coba koneksi asli
        response = requests.get(URL_BMKG, timeout=10, headers=headers_palsu, verify=False)
        data_dict = xmltodict.parse(response.content)
        forecast = data_dict.get('data', {}).get('forecast', {})
        areas = ensure_list(forecast.get('area'))
        
        # Validasi isi data
        if not areas: raise Exception("Data XML Kosong")
            
        return areas, None # Sukses (msg = None)
        
    except Exception as e:
        # JIKA GAGAL, KEMBALIKAN DATA DUMMY
        # Agar dashboard tidak crash saat presentasi
        dummy_area = get_data_dummy_malang()
        return [dummy_area], f"Mode Offline: {str(e)}"

def get_pilihan_kota(areas):
    opsi = {}
    if not areas: return {}
    for area in areas:
        nama = area.get('@description', 'Tanpa Nama')
        opsi[nama] = area
    return opsi

# ----------------- FUNGSI 2: PROSES DATA -----------------
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
                        elif kode in ['60','61','63','80']: status = "Hujan"
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

def get_status_sensor(row):
    h = row.get('hujan', 4095)
    c = row.get('cahaya', 0)
    if h < 1500: return "BADAI", "⛈️"
    if h < 3900: return "HUJAN", "🌧️"
    if c < 100: return "MALAM", "🌃"
    if c > 2500: return "CERAH", "☀️"
    return "BERAWAN", "☁️"

# ================== UI DASHBOARD ==================

# --- SIDEBAR NAVIGASI ---
st.sidebar.title("🎛️ Panel Kontrol")
menu = st.sidebar.radio("Pilih Menu:", ["📡 Monitor Sensor", "🏢 Data BMKG"])

st.sidebar.markdown("---")

nama_kota_terpilih = "Kota Malang (OFFLINE MODE)"
df_bmkg_hasil = None
status_msg = ""

if menu == "🏢 Data BMKG":
    st.sidebar.subheader("📍 Lokasi")
    
    # Ambil Data (Asli atau Dummy)
    areas, msg = get_data_bmkg_lengkap()
    status_msg = msg
    
    opsi_kota = get_pilihan_kota(areas)
    
    if opsi_kota:
        list_nama = sorted(list(opsi_kota.keys()))
        
        # Cari default Malang
        idx = 0
        for i, nama in enumerate(list_nama):
            if "Malang" in nama: 
                idx = i
                break
        
        pilihan = st.sidebar.selectbox("Pilih Kota:", list_nama, index=idx)
        
        data_area_raw = opsi_kota[pilihan]
        df_bmkg_hasil = proses_data_area(data_area_raw)
        nama_kota_terpilih = pilihan

# --- MAIN CONTENT ---
placeholder = st.empty()

while True:
    st.cache_data.clear()
    df_iot = baca_data_sensor()
    
    with placeholder.container():
        
        # ================= TAMPILAN 1: SENSOR =================
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
                    st.subheader("Lingkungan")
                    st.line_chart(df_chart[['suhu', 'kelembapan', 'tekanan']])
                with g2: 
                    st.subheader("Cahaya & Hujan")
                    st.area_chart(df_chart[['cahaya', 'hujan']])
                
                st.divider()
                st.subheader("📂 Riwayat Data Sensor (1000 Data)")
                st.dataframe(df_iot.sort_values(by='timestamp', ascending=False).head(1000), use_container_width=True)

            else:
                st.warning("Menunggu data alat ESP32...")
                st.spinner("Sedang memuat...")

        # ================= TAMPILAN 2: BMKG =================
        elif menu == "🏢 Data BMKG":
            st.title(f"🏢 Prakiraan Cuaca: {nama_kota_terpilih}")
            st.markdown("---")
            
            # Notifikasi Status Koneksi
            if status_msg:
                st.warning(f"⚠️ Koneksi ke server BMKG gagal. Menampilkan data cadangan.")
                st.caption(f"Detail Error: {status_msg}")
            else:
                st.success("✅ Terhubung ke Server BMKG (Data Asli)")
            
            if df_bmkg_hasil is not None:
                st.dataframe(df_bmkg_hasil, use_container_width=True, hide_index=True)
                st.line_chart(df_bmkg_hasil.set_index('Jam (WIB)')[['Suhu (°C)', 'Kelembapan (%)']])
            else:
                st.error("Data tidak dapat ditampilkan.")

    time.sleep(15)
