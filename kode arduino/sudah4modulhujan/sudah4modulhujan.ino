/*
 * KODE FINAL STASIUN CUACA IOT (FIX CAHAYA TERBALIK)
 * ---------------------------------------------------------
 * Menggunakan 4 Sensor YL-83 untuk akurasi tinggi.
 * Pin Hujan: 34, 32, 33, 36 (ADC1 - Aman untuk Wi-Fi)
 * Pin Cahaya: 35 (ADC1)
 * * PERBAIKAN: Logika Cahaya dibalik (4095 - raw) agar Siang = Nilai Tinggi
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <NTPClient.h>
#include <WiFiUdp.h>

// ================= KONFIGURASI =================
const char* ssid = "iPhone 15";
const char* password = "opang110304";
const char* serverName = "http://syakhish.pythonanywhere.com/update_data";

// --- PIN SENSOR (ADC1 ONLY) ---
const int RAIN_PINS[4] = {34, 32, 33, 36}; 
const int LIGHT_SENSOR_PIN = 35; 

const float P_SEA_LEVEL = 1013.25; 
const long interval = 15000;       

// ================= OBJEK & VARIABEL =================
Adafruit_BME280 bme; 
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org", 25200); // UTC+7

float suhu, kelembapan, tekanan, imcs;
int nilaiCahaya; // Nilai final yang dikirim
int nilaiHujanRataRata; 
unsigned long timestamp;
unsigned long previousMillis = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== MEMULAI SISTEM (FIX CAHAYA) ===");

  // Set Pin Mode untuk Sensor Cahaya
  pinMode(LIGHT_SENSOR_PIN, INPUT);

  Wire.begin();
  if (!bme.begin(0x76)) { 
    Serial.println("ERROR: Sensor BME280 tidak ditemukan!");
    while (1); 
  }
  Serial.println("✅ Sensor BME280 OK.");

  connectToWiFi();

  timeClient.begin();
  while(!timeClient.update()) {
    timeClient.forceUpdate();
    delay(500);
  }
}

void loop() {
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    timeClient.update();
    timestamp = timeClient.getEpochTime();

    bacaSemuaSensor();
    kirimData();
  }
}

// ================= FUNGSI BACA SENSOR =================
void bacaSemuaSensor() {
  // 1. Baca BME280
  suhu = bme.readTemperature();
  kelembapan = bme.readHumidity();
  tekanan = bme.readPressure() / 100.0F;

  // ----------------------------------------------------
  // 2. PERBAIKAN BACA SENSOR CAHAYA
  // ----------------------------------------------------
  int rawCahaya = analogRead(LIGHT_SENSOR_PIN);
  
  // LOGIKA INVERSI:
  // Karena alatmu membaca 70 saat terang (Low), dan 4000an saat gelap (High),
  // Kita balik rumusnya supaya Dashboard menerima nilai Tinggi saat Terang.
  nilaiCahaya = 4095 - rawCahaya; 

  // Koreksi minus (jaga-jaga noise)
  if (nilaiCahaya < 0) nilaiCahaya = 0;

  // --- HITUNG IMCS ---
  if (tekanan > 0) {
    imcs = (kelembapan / 100.0) * (P_SEA_LEVEL / tekanan);
  } else {
    imcs = 0;
  }

  // --- LOGIKA HUJAN ---
  long totalHujan = 0;
  
  Serial.println("\n==========================================");
  Serial.println("       DATA MONITORING REAL-TIME          ");
  Serial.println("==========================================");

  Serial.print("🌡️  Suhu        : "); Serial.print(suhu); Serial.println(" °C");
  Serial.print("💧  Kelembapan  : "); Serial.print(kelembapan); Serial.println(" %");
  Serial.print("🎈  Tekanan     : "); Serial.print(tekanan); Serial.println(" hPa");
  
  // Debugging Cahaya di Serial Monitor
  Serial.print("☀️  Cahaya RAW  : "); Serial.print(rawCahaya); Serial.println(" (Asli Alat)");
  Serial.print("☀️  Cahaya FIX  : "); Serial.print(nilaiCahaya); Serial.println(" (Dikirim ke Web)");
  
  Serial.print("☁️  IMCS        : "); Serial.println(imcs);
  Serial.println("------------------------------------------");

  Serial.println("🌧️  Detail Sensor Hujan:");
  for (int i = 0; i < 4; i++) {
    int nilaiIndividu = analogRead(RAIN_PINS[i]);
    Serial.print("    Sensor "); Serial.print(i+1); 
    Serial.print(" (Pin "); Serial.print(RAIN_PINS[i]); 
    Serial.print(") : "); Serial.println(nilaiIndividu);
    totalHujan += nilaiIndividu; 
  }
  
  nilaiHujanRataRata = totalHujan / 4;
  
  Serial.println("------------------------------------------");
  Serial.print(">>> RATA-RATA HUJAN : "); 
  Serial.println(nilaiHujanRataRata);
  Serial.println("==========================================");
}

void connectToWiFi() {
  Serial.print("Menghubungkan ke Wi-Fi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    retry++;
    if (retry > 20) ESP.restart();
  }
  Serial.println("\n✅ Wi-Fi Terhubung!");
}

void kirimData() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    StaticJsonDocument<300> doc;
    
    doc["timestamp"] = timestamp;
    doc["suhu"] = suhu;
    doc["kelembapan"] = kelembapan;
    doc["tekanan"] = tekanan;
    
    // Kirim nilai yang sudah dibalik (Inverted)
    doc["cahaya"] = nilaiCahaya; 
    
    doc["hujan"] = nilaiHujanRataRata; 
    doc["imcs"] = imcs;

    String requestBody;
    serializeJson(doc, requestBody);

    Serial.println("Mengirim data ke server...");
    http.begin(serverName);
    http.addHeader("Content-Type", "application/json");
    int httpResponseCode = http.POST(requestBody);

    if (httpResponseCode > 0) {
      Serial.print("✅ Sukses! Kode: "); Serial.println(httpResponseCode);
    } else {
      Serial.print("❌ Gagal. Kode: "); Serial.println(httpResponseCode);
    }
    http.end();
  } else {
    connectToWiFi();
  }
}