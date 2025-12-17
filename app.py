import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import pytz
import xmltodict  # Library untuk membaca data BMKG

# ----------------- KONFIGURASI HALAMAN -----------------
st.set_page_config(
    page_title="Cuaca Malang: Sensor vs BMKG",
    page_icon="🍎",  # Ikon Apel Malang
    layout="wide",
)

# --- KONFIGURASI API & LOKASI ---
# URL API Backend Kamu
API_URL = "http://syakhish.pythonanywhere.com/get_data"

# URL Data BMKG Provinsi JAWA TIMUR (Format XML)
URL_BMKG = "https://data.bmkg.go.id/DataMKG/MEWS/DigitalForecast/DigitalForecast-JawaTimur.xml"

# ID LOKASI: 501262 adalah ID resmi BMKG untuk "Kota Malang"
ID_KOTA_BMKG = "501262" 

# ----------------- FUNGSI 1: BACA DATA SENSOR IOT -----------------
def baca_data_dari_api():
    """Mengambil data dari ESP32 via PythonAnywhere"""
    try:
        # Header agar tidak membaca cache lama
        headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache', 'Expires': '0'}
        response = requests.get(API_URL, timeout=15, headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data or not isinstance(data, list): return None
        
        # Buat DataFrame
        df = pd.DataFrame(data)
        
        # Cek kolom timestamp
        if 'timestamp' not in df.columns: return None
        
        # Konversi Timestamp (Unix ke Datetime WIB)
        df['timestamp_numeric'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df.dropna(subset=['timestamp_numeric'], inplace=True)
        
        # Convert ke UTC dulu
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_numeric'], unit='s', utc=True)
        # Convert ke WIB (Asia/Jakarta)
        zona_wib = pytz.timezone('Asia/Jakarta')
        df['timestamp'] = df['timestamp_utc'].dt.tz_convert(zona_wib) 
        
        return df
    except Exception as e:
        st.error(f"Gagal membaca data sensor: {e}")
        return None

# ----------------- FUNGSI 2: BACA DATA BMKG (MALANG) -----------------
@st.cache_data(ttl=3600) # Cache data selama 1 jam agar server BMKG tidak berat
def ambil_data_bmkg():
    """Mengambil prakiraan cuaca dari XML BMKG Jawa Timur khusus Malang"""
    try:
        response = requests.get(URL_BMKG, timeout=10)
        # Parse XML menjadi Dictionary Python
        data_dict = xmltodict.parse(response.content)
        
        # Masuk ke struktur XML (Data -> Forecast -> Area)
        areas = data_dict['data']['forecast']['area']
        
        # Cari area dengan ID 501262 (Kota Malang)
        target_area = None
        if isinstance(areas, list):
            for area in areas:
                if area['@id'] == ID_KOTA_BMKG:
                    target_area = area
                    break
        else:
            # Jika cuma ada 1 area di file XML (jarang terjadi)
            if areas['@id'] == ID_KOTA_BMKG: target_area = areas

        if not target_area: return None, "Lokasi Tidak Ditemukan"

        nama_kota = target_area['@description'] # Harusnya "Kota Malang"
        params = target_area['parameter']
        
        # Kita akan ambil Suhu (id="t") dan Kelembapan (id="hu")
        temp_data = []
        hum_data = []
        
        for p in params:
            # 1. Ambil Data Suhu
            if p['@id'] == 't': 
                for t in p['timerange']:
                    # Format waktu XML BMKG: 202312171200 (YYYYMMDDHHmm)
                    waktu_str = t['@datetime']
                    waktu = datetime.strptime(waktu_str, "%Y%m%d%H%M")
                    # Set timezone asal (UTC) lalu convert ke WIB
                    waktu = pytz.utc.localize(waktu).astimezone(pytz.timezone('Asia/Jakarta'))
                    
                    val_celcius = float(t['value'][0]['#text']) # Nilai Celcius biasanya index 0
                    temp_data.append({'timestamp': waktu, 'Suhu BMKG': val_celcius})
            
            # 2. Ambil Data Kelembapan
            if p['@id'] == 'hu': 
                for h in p['timerange']:
                    waktu_str = h['@datetime']
                    waktu = datetime.strptime(waktu_str, "%Y%m%d%H%M")
                    waktu = pytz.utc.localize(waktu).astimezone(pytz.timezone('Asia/Jakarta'))
                    
                    val_hum = float(h['value']['#text'])
                    hum_data.append({'timestamp': waktu, 'Kelembapan BMKG': val_hum})

        # Gabungkan Data menjadi DataFrame tunggal
        if not temp_data or not hum_data: return None, nama_kota

        df_temp = pd.DataFrame(temp_data).set_index('timestamp')
        df_hum = pd.DataFrame(hum_data).set_index('timestamp')
        
        # Join Outer (gabung berdasarkan waktu)
        df_bmkg = df_temp.join(df_hum, how='outer')
        return df_bmkg, nama_kota

    except Exception as e:
        return None, f"Error BMKG: {str(e)}"

# ----------------- FUNGSI 3: LOGIKA STATUS CUACA -----------------
def tentukan_status_cuaca(data):
    # Ambil data sensor, gunakan nilai default jika kosong
    imcs = data.get('imcs', 0.0)
    cahaya = data.get('cahaya', 0)
    kelembapan = data.get('kelembapan', 0.0)
    hujan = data.get('hujan', 4095)
    
    # Threshold (Batas Nilai)
    BATAS_MALAM = 100        
    BATAS_BERAWAN = 2500     
    
    # Prioritas 1: Hujan (Sensor YL-83)
    if hujan < 1500: return "BADAI / LEBAT", "⛈️"
    elif hujan < 2500: return "Hujan Deras", "🌧️"
    elif hujan < 3900: return "Gerimis", "🌦️"
    
    # Prioritas 2: Kondisi Cahaya & Awan
    if cahaya < BATAS_MALAM: return "Malam Hari", "🌃"
    elif imcs > 0.95 and cahaya < BATAS_BERAWAN: return "Mendung", "☁️"
    elif cahaya > BATAS_BERAWAN:
        if kelembapan < 70: return "Cerah", "☀️"
        else: return "Cerah Lembab", "🌤️"
    else: return "Berawan", "☁️"

# ----------------- TAMPILAN UTAMA (LAYOUT) -----------------
st.title("🍎 Monitoring Cuaca Kota Malang: Sensor IoT vs BMKG")
st.markdown("---")

# Placeholder agar halaman tidak flicker saat refresh
placeholder = st.empty()

while True:
    # Bersihkan cache sensor agar selalu real-time
    st.cache_data.clear()
    
    # Ambil Data
    df_sensor = baca_data_dari_api()
    df_bmkg, lokasi_bmkg = ambil_data_bmkg()

    if df_sensor is not None and not df_sensor.empty:
        with placeholder.container():
            # Ambil data paling baru (baris terakhir)
            current = df_sensor.iloc[-1]
            status, icon = tentukan_status_cuaca(current)
            waktu_update = current['timestamp'].strftime('%d %b %Y, %H:%M:%S')
            
            # --- BAGIAN HEADER ---
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader("📡 Status Sensor (Real-time)")
                # Tampilkan Alert jika Hujan
                if "Hujan" in status or "BADAI" in status:
                    st.error(f"PERINGATAN: {status}!", icon="🌧️")
                else:
                    st.info(f"Kondisi: {status} | Update: {waktu_update}")
                
                # Tampilkan Emoji Besar
                st.markdown(f"<h1 style='text-align: left; font-size: 50px;'>{icon} {status}</h1>", unsafe_allow_html=True)

            with c2:
                st.subheader(f"🏢 Data BMKG ({lokasi_bmkg})")
                
                # Cari data BMKG yang jam-nya paling dekat dengan sekarang
                data_bmkg_now = None
                if df_bmkg is not None:
                    now_wib = datetime.now(pytz.timezone('Asia/Jakarta'))
                    # Metode 'nearest' mencari jam terdekat
                    try:
                        idx_terdekat = df_bmkg.index.get_indexer([now_wib], method='nearest')[0]
                        data_bmkg_now = df_bmkg.iloc[idx_terdekat]
                        
                        # Tampilkan Info BMKG
                        st.success(f"🌡️ Suhu: {data_bmkg_now['Suhu BMKG']}°C")
                        st.info(f"💧 Lembab: {data_bmkg_now['Kelembapan BMKG']}%")
                        st.caption(f"Validasi Jam: {data_bmkg_now.name.strftime('%H:%M')} WIB")
                    except:
                        st.warning("Data waktu BMKG belum sinkron")
                else:
                    st.warning("Gagal koneksi ke server BMKG")

            st.markdown("---")

            # --- BAGIAN KOMPARASI (METRIC) ---
            st.markdown("### ⚖️ Perbandingan Nilai (Validasi Alat)")
            k1, k2, k3, k4 = st.columns(4)
            
            # Nilai Sensor
            temp_sensor = current.get('suhu', 0)
            hum_sensor = current.get('kelembapan', 0)
            
            # Nilai BMKG (Handle jika None)
            temp_bmkg = data_bmkg_now['Suhu BMKG'] if data_bmkg_now is not None else 0
            hum_bmkg = data_bmkg_now['Kelembapan BMKG'] if data_bmkg_now is not None else 0
            
            # Hitung Selisih (Delta)
            delta_t = temp_sensor - temp_bmkg
            delta_h = hum_sensor - hum_bmkg
            
            # Tampilkan Metric
            k1.metric("Suhu Sensor", f"{temp_sensor:.1f}°C")
            k2.metric("Suhu BMKG", f"{temp_bmkg}°C", f"{delta_t:.1f}°C", delta_color="inverse")
            
            k3.metric("Kelembapan Sensor", f"{hum_sensor:.1f}%")
            k4.metric("Kelembapan BMKG", f"{hum_bmkg}%", f"{delta_h:.1f}%", delta_color="inverse")
            
            st.caption("*Catatan: Delta (selisih) wajar terjadi karena perbedaan lokasi mikro (titik pemasangan alat) dengan stasiun BMKG.*")
            st.markdown("---")

            # --- BAGIAN GRAFIK (CHART) ---
            st.subheader("📈 Grafik Tren: Sensor vs BMKG")
            
            if df_bmkg is not None:
                # Siapkan data sensor (Ambil kolom suhu & lembab saja)
                df_plot = df_sensor.set_index('timestamp')[['suhu', 'kelembapan']].copy()
                df_plot.columns = ['Suhu Sensor', 'Kelembapan Sensor']
                
                # Buat 2 Kolom Grafik
                g1, g2 = st.columns(2)
                
                with g1:
                    st.markdown("**Perbandingan Temperatur (°C)**")
                    # Gabung data Sensor + BMKG dalam satu chart
                    chart_suhu = pd.concat([df_plot['Suhu Sensor'], df_bmkg['Suhu BMKG']], axis=1)
                    st.line_chart(chart_suhu)
                
                with g2:
                    st.markdown("**Perbandingan Kelembapan (%)**")
                    chart_hum = pd.concat([df_plot['Kelembapan Sensor'], df_bmkg['Kelembapan BMKG']], axis=1)
                    st.line_chart(chart_hum)
                
                # Area Chart untuk Hujan & Cahaya (Sensor Only)
                st.markdown("**Monitoring Cahaya & Hujan (Sensor Only)**")
                df_hujan_cahaya = df_sensor.set_index('timestamp')[['cahaya', 'hujan']]
                st.area_chart(df_hujan_cahaya)
                
            else:
                st.warning("Data BMKG tidak tersedia untuk grafik.")

            # --- BAGIAN TABEL DATA ---
            with st.expander("📂 Lihat Data Mentah (Tabel)"):
                st.dataframe(df_sensor.sort_values(by='timestamp', ascending=False).head(100))

    else:
        with placeholder.container():
            st.warning("⏳ Menunggu data masuk dari alat ESP32...")
            st.spinner("Sedang memuat...")
            
    # Refresh setiap 15 detik (Sesuai interval kirim ESP32)
    time.sleep(15)
