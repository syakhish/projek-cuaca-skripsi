import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import pytz
import xmltodict

# ----------------- KONFIGURASI HALAMAN -----------------
st.set_page_config(
    page_title="Monitoring Cuaca",
    page_icon="🍎",
    layout="wide",
)

# --- KONFIGURASI ---
API_URL = "http://syakhish.pythonanywhere.com/get_data"
# URL XML BMKG Jawa Timur
URL_BMKG = "https://data.bmkg.go.id/DataMKG/MEWS/DigitalForecast/DigitalForecast-JawaTimur.xml"
KOTA_DICARI = "Kota Malang"

# --- KAMUS KODE CUACA BMKG ---
# Referensi: https://data.bmkg.go.id/prakiraan-cuaca/
KODE_CUACA_BMKG = {
    "0": "Cerah", "1": "Cerah Berawan", "2": "Cerah Berawan", "3": "Berawan", "4": "Berawan Tebal",
    "5": "Udara Kabur", "10": "Asap", "45": "Kabut",
    "60": "Hujan Ringan", "61": "Hujan Sedang", "63": "Hujan Lebat",
    "80": "Hujan Lokal", "95": "Hujan Petir", "97": "Hujan Petir"
}

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
        
        # Bersihkan Data Timestamp
        df['timestamp_numeric'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df.dropna(subset=['timestamp_numeric'], inplace=True)
        
        # Convert ke WIB
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_numeric'], unit='s', utc=True)
        zona_wib = pytz.timezone('Asia/Jakarta')
        df['timestamp'] = df['timestamp_utc'].dt.tz_convert(zona_wib)
        
        return df
    except Exception as e:
        return None

# ----------------- FUNGSI BACA BMKG (SUHU, LEMBAB, & CUACA) -----------------
@st.cache_data(ttl=3600)
def ambil_data_bmkg():
    try:
        response = requests.get(URL_BMKG, timeout=10)
        data_dict = xmltodict.parse(response.content)
        areas = data_dict['data']['forecast']['area']
        
        # 1. Cari Kota Malang
        target_area = None
        if isinstance(areas, list):
            for area in areas:
                if KOTA_DICARI.lower() in area['@description'].lower():
                    target_area = area
                    break
        else:
            if KOTA_DICARI.lower() in areas['@description'].lower(): target_area = areas

        if not target_area: return None, "Lokasi Tidak Ditemukan"
        
        nama_kota = target_area['@description']
        params = target_area['parameter']
        
        list_data = []

        # 2. Ekstrak Parameter
        # Kita butuh: Suhu (t), Kelembapan (hu), Cuaca (weather)
        temp_dict = {}
        hum_dict = {}
        weather_dict = {}

        for p in params:
            if p['@id'] == 't': # Suhu
                for t in p['timerange']:
                    dt = datetime.strptime(t['@datetime'], "%Y%m%d%H%M")
                    dt = pytz.utc.localize(dt).astimezone(pytz.timezone('Asia/Jakarta'))
                    temp_dict[dt] = float(t['value'][0]['#text'])
            
            if p['@id'] == 'hu': # Lembab
                for h in p['timerange']:
                    dt = datetime.strptime(h['@datetime'], "%Y%m%d%H%M")
                    dt = pytz.utc.localize(dt).astimezone(pytz.timezone('Asia/Jakarta'))
                    hum_dict[dt] = float(h['value']['#text'])

            if p['@id'] == 'weather': # KODE CUACA (Untuk info hujan)
                for w in p['timerange']:
                    dt = datetime.strptime(w['@datetime'], "%Y%m%d%H%M")
                    dt = pytz.utc.localize(dt).astimezone(pytz.timezone('Asia/Jakarta'))
                    code = w['value']['#text']
                    # Translate Kode ke Teks (misal: "Hujan Ringan")
                    text_cuaca = KODE_CUACA_BMKG.get(code, f"Code {code}")
                    weather_dict[dt] = text_cuaca

        # 3. Gabungkan jadi satu DataFrame Rapi
        # Ambil semua kunci waktu unik
        all_times = sorted(set(list(temp_dict.keys()) + list(hum_dict.keys()) + list(weather_dict.keys())))
        
        final_data = []
        for t in all_times:
            final_data.append({
                'timestamp': t,
                'Suhu BMKG': temp_dict.get(t, None),
                'Kelembapan BMKG': hum_dict.get(t, None),
                'Status BMKG': weather_dict.get(t, "Tidak Diketahui")
            })
            
        df_bmkg = pd.DataFrame(final_data).set_index('timestamp')
        return df_bmkg, nama_kota

    except Exception as e:
        return None, f"Error: {e}"

# ----------------- LOGIKA STATUS SENSOR -----------------
def tentukan_status_sensor(data):
    hujan = data.get('hujan', 4095) # Analog
    cahaya = data.get('cahaya', 0)
    
    if hujan < 1500: return "BADAI / HUJAN DERAS", "⛈️"
    elif hujan < 2500: return "Hujan Deras", "🌧️"
    elif hujan < 3200: return "Hujan Sedang", "🌧️"
    elif hujan < 3900: return "Gerimis", "🌦️"
    
    # Jika tidak hujan, cek cahaya
    if cahaya < 100: return "Malam Hari", "🌃"
    if cahaya > 2500: return "Cerah", "☀️"
    return "Berawan/Mendung", "☁️"

# ----------------- UI UTAMA -----------------
st.title("🍎 Monitoring Cuaca & Curah Hujan (Malang)")
st.markdown("---")

placeholder = st.empty()

while True:
    st.cache_data.clear()
    df_sensor = baca_data_dari_api()
    df_bmkg, lokasi = ambil_data_bmkg()

    if df_sensor is not None and not df_sensor.empty:
        with placeholder.container():
            now = df_sensor.iloc[-1]
            status_sensor, icon_sensor = tentukan_status_sensor(now)
            
            # --- BAGIAN 1: HEADER PERBANDINGAN STATUS ---
            col1, col2 = st.columns(2)
            
            # KIRI: SENSOR
            with col1:
                st.subheader("📡 Status Sensor (Real-time)")
                st.markdown(f"## {icon_sensor} {status_sensor}")
                st.caption(f"Update: {now['timestamp'].strftime('%H:%M:%S WIB')}")
                
            # KANAN: BMKG
            with col2:
                st.subheader(f"🏢 Prakiraan BMKG ({lokasi})")
                
                status_bmkg_text = "Menunggu Sinkronisasi..."
                temp_bmkg = 0
                
                if df_bmkg is not None:
                    # Ambil data BMKG terdekat jam sekarang
                    waktu_skrg = datetime.now(pytz.timezone('Asia/Jakarta'))
                    try:
                        idx = df_bmkg.index.get_indexer([waktu_skrg], method='nearest')[0]
                        row_bmkg = df_bmkg.iloc[idx]
                        status_bmkg_text = row_bmkg['Status BMKG'] # Ini teks misal "Hujan Ringan"
                        temp_bmkg = row_bmkg['Suhu BMKG']
                        hum_bmkg = row_bmkg['Kelembapan BMKG']
                    except: pass
                
                # Tampilkan Status Hujan BMKG
                icon_bmkg = "☁️"
                if "Hujan" in status_bmkg_text: icon_bmkg = "🌧️"
                elif "Cerah" in status_bmkg_text: icon_bmkg = "☀️"
                
                st.markdown(f"## {icon_bmkg} {status_bmkg_text}")
                st.caption("Sumber: DigitalForecast BMKG Jawa Timur")

            st.markdown("---")

            # --- BAGIAN 2: KOMPARASI METRIK ---
            st.markdown("### ⚖️ Data Kuantitatif")
            m1, m2, m3, m4 = st.columns(4)
            
            # Suhu
            t_sens = now.get('suhu', 0)
            m1.metric("Suhu Sensor", f"{t_sens:.1f}°C")
            m2.metric("Suhu BMKG", f"{temp_bmkg:.1f}°C", f"{t_sens - temp_bmkg:.1f}°C", delta_color="inverse")
            
            # Hujan (Perbandingan Konsep)
            hujan_val = now.get('hujan', 4095)
            # Kita bandingkan Nilai Analog vs Status Teks
            m3.metric("Sensor Hujan (Analog)", f"{hujan_val}", "Semakin kecil = Basah")
            m4.metric("Status Hujan BMKG", f"{status_bmkg_text}")

            st.markdown("---")

            # --- BAGIAN 3: GRAFIK (DIPERBAIKI AGAR MENYAMBUNG) ---
            st.subheader("📈 Grafik Perbandingan")
            
            g1, g2 = st.columns(2)
            
            # Siapkan Data Sensor (Index Waktu)
            df_plot = df_sensor.set_index('timestamp')
            
            with g1:
                st.markdown("**🌡️ Suhu & Kelembapan**")
                if df_bmkg is not None:
                    # 1. Ambil kolom Suhu/Lembab Sensor
                    df_chart = df_plot[['suhu', 'kelembapan']].copy()
                    
                    # 2. Resample BMKG agar sesuai dengan index Sensor (Interpolasi)
                    # Ini trik kuncinya: Reindex data BMKG ke index Sensor, lalu isi data kosong
                    df_bmkg_reindexed = df_bmkg.reindex(df_chart.index, method='nearest', tolerance=timedelta(hours=3))
                    
                    # 3. Gabungkan
                    df_chart['Suhu BMKG'] = df_bmkg_reindexed['Suhu BMKG']
                    # df_chart['Kelembapan BMKG'] = df_bmkg_reindexed['Kelembapan BMKG'] (Opsional, biar grafik gak penuh)
                    
                    st.line_chart(df_chart[['suhu', 'Suhu BMKG']])
                else:
                    st.line_chart(df_plot[['suhu']])
                    
            with g2:
                st.markdown("**🌧️ Monitoring Hujan (Sensor)**")
                # Area chart untuk nilai hujan analog
                st.area_chart(df_plot[['hujan']])
                st.caption("*Grafik BMKG untuk hujan tidak ditampilkan karena format datanya adalah Kategori (Teks), bukan Angka.*")

            # --- TABEL ---
            with st.expander("Lihat Data Tabel"):
                st.dataframe(df_sensor.sort_values(by='timestamp', ascending=False).head(1000))

    else:
        st.warning("Menunggu Data Sensor...")
        time.sleep(2)
        
    time.sleep(15)
