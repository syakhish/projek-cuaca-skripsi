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
URL_BMKG = "https://data.bmkg.go.id/DataMKG/MEWS/DigitalForecast/DigitalForecast-JawaTimur.xml"

# ----------------- FUNGSI BANTUAN ANTI-ERROR -----------------
def ensure_list(item):
    """Memaksa data menjadi list agar tidak crash"""
    if item is None: return []
    if isinstance(item, list): return item
    return [item]

# ----------------- FUNGSI BACA SENSOR (ESP32) -----------------
def baca_data_dari_api():
    try:
        headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache', 'Expires': '0'}
        response = requests.get(API_URL, timeout=15, headers=headers)
        if response.status_code != 200: return None
        
        data = response.json()
        if not data or not isinstance(data, list): return None
        
        df = pd.DataFrame(data)
        if 'timestamp' not in df.columns: return None
        
        df['timestamp_numeric'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df.dropna(subset=['timestamp_numeric'], inplace=True)
        
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_numeric'], unit='s', utc=True)
        zona_wib = pytz.timezone('Asia/Jakarta')
        df['timestamp'] = df['timestamp_utc'].dt.tz_convert(zona_wib)
        
        return df
    except:
        return None

# ----------------- FUNGSI BACA BMKG (DIAGNOSTIK) -----------------
@st.cache_data(ttl=3600)
def ambil_data_bmkg_tabel():
    debug_info = ""
    try:
        # 1. Coba Download XML
        try:
            response = requests.get(URL_BMKG, timeout=15)
            response.raise_for_status()
        except Exception as e:
            return None, f"Gagal Download XML: {str(e)}"

        # 2. Parsing XML
        try:
            data_dict = xmltodict.parse(response.content)
            forecast = data_dict.get('data', {}).get('forecast', {})
            areas = ensure_list(forecast.get('area'))
        except Exception as e:
            return None, f"Gagal Parsing XML: {str(e)}"

        if not areas: return None, "Data Area Kosong di XML"

        # 3. Cari Kota "Malang" (Case Insensitive)
        target_area = None
        daftar_kota_ditemukan = [] # Untuk debug
        
        for area in areas:
            desc = area.get('@description', '')
            daftar_kota_ditemukan.append(desc) # Simpan nama kota buat laporan jika gagal
            
            # Cek apakah ada kata "Malang" di deskripsi dan bukan kabupaten (opsional)
            # Kita ambil yang pertama kali muncul kata "Malang"
            if "Malang" in desc: 
                # Prioritaskan Kota Malang daripada Kabupaten
                if "Kota" in desc:
                    target_area = area
                    break
                # Jika belum nemu Kota, simpan Kabupaten dulu sebagai cadangan
                if target_area is None:
                    target_area = area

        if target_area is None:
            # Tampilkan 5 kota pertama yang ditemukan agar user tahu isinya apa
            contoh_kota = ", ".join(daftar_kota_ditemukan[:5])
            return None, f"Tidak ada 'Malang'. Kota yang ada: {contoh_kota}..."

        # 4. Ekstrak Data
        params = ensure_list(target_area.get('parameter'))
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
                        # Mapping Kode Cuaca
                        kode = val
                        status = "Berawan"
                        if kode in ['0', '1', '2']: status = "Cerah"
                        elif kode in ['3', '4']: status = "Berawan"
                        elif kode in ['5', '10', '45']: status = "Kabut"
                        elif kode in ['60', '61', '63', '80']: status = "Hujan"
                        elif kode in ['95', '97']: status = "Hujan Petir"
                        data_waktu[dt]['Cuaca'] = status

        if not data_waktu: return None, "Struktur Parameter XML Berubah"

        # 5. Finalisasi DataFrame
        list_data = list(data_waktu.values())
        df_bmkg = pd.DataFrame(list_data).sort_values('Waktu')
        
        # Format Jam
        df_bmkg['Jam (WIB)'] = df_bmkg['Waktu'].dt.strftime('%d-%m %H:%M')
        
        # Susun Kolom
        cols = ['Jam (WIB)', 'Cuaca', 'Suhu (°C)', 'Kelembapan (%)']
        cols_final = [c for c in cols if c in df_bmkg.columns]
        
        return df_bmkg[cols_final], target_area.get('@description')

    except Exception as e:
        return None, f"Unknown Error: {str(e)}"

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

# ----------------- UI DASHBOARD -----------------
st.title("🌦️ Monitoring Cuaca")
st.markdown("---")

placeholder = st.empty()

while True:
    st.cache_data.clear()
    df_sensor = baca_data_dari_api()
    df_bmkg, info_bmkg = ambil_data_bmkg_tabel()

    if df_sensor is not None and not df_sensor.empty:
        with placeholder.container():
            current = df_sensor.iloc[-1]
            status, icon = tentukan_status_sensor(current)
            
            # HEADER
            st.subheader("Status Terkini")
            c1, c2 = st.columns([1, 3])
            with c1: st.markdown(f"<h1 style='text-align: center; font-size: 80px;'>{icon}</h1>", unsafe_allow_html=True)
            with c2:
                st.info(f"Kondisi: **{status}**")
                st.caption(f"Last Update: {current['timestamp'].strftime('%d %b %Y, %H:%M:%S')} WIB")
                if "Hujan" in status or "BADAI" in status: st.error("PERINGATAN HUJAN!")

            st.markdown("---")

            # METRICS
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("🌡️ Suhu", f"{current.get('suhu', 0):.1f} °C")
            k2.metric("💧 Kelembapan", f"{current.get('kelembapan', 0):.1f} %")
            k3.metric("🎈 Tekanan", f"{current.get('tekanan', 0):.1f} hPa")
            k4.metric("☀️ Cahaya", f"{current.get('cahaya', 0)}")
            k5.metric("🌧️ Hujan (ADC)", f"{current.get('hujan', 4095)}")

            st.markdown("---")

            # GRAFIK
            st.subheader("📈 Grafik Sensor")
            g1, g2 = st.columns(2)
            df_plot = df_sensor.set_index('timestamp')
            
            with g1:
                st.markdown("**Lingkungan**")
                cols = ['suhu', 'kelembapan', 'tekanan']
                valid = [c for c in cols if c in df_plot.columns]
                st.line_chart(df_plot[valid])
            with g2:
                st.markdown("**Cahaya & Hujan**")
                cols = ['cahaya', 'hujan']
                if set(cols).issubset(df_plot.columns): st.area_chart(df_plot[cols])

            st.markdown("---")

            # TABEL
            tab1, tab2 = st.tabs(["📂 Data Sensor", "🏢 Data BMKG"])
            with tab1:
                st.dataframe(df_sensor.sort_values(by='timestamp', ascending=False).head(1000))
            with tab2:
                # LOGIKA DIAGNOSTIK
                if df_bmkg is not None:
                    st.success(f"Berhasil Memuat Data: {info_bmkg}")
                    st.dataframe(df_bmkg, use_container_width=True, hide_index=True)
                else:
                    st.error("⚠️ Data BMKG Tidak Muncul")
                    st.warning(f"Pesan Error Sistem: {info_bmkg}")
                    st.info("Tips: Jika error 'Gagal Download', cek koneksi internet. Jika 'Kota Tidak Ditemukan', BMKG mungkin mengubah nama kota di XML.")

    else:
        with placeholder.container():
            st.warning("Menunggu data ESP32...")
            st.spinner("Connecting...")
            
    time.sleep(15)
