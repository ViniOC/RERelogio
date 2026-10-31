// RERelogio: hora, temperatura (Open-Meteo) e limite do Claude numa tela 240x240.
// Layout C: hora e temperatura no topo, % da sessão grande, barra, reinício e semana.
#include <Arduino.h>
#include <ArduinoJson.h>
#include <ArduinoOTA.h>
#include <ESP8266HTTPClient.h>
#include <ESP8266WiFi.h>
#include <ESP8266mDNS.h>
#include <TFT_eSPI.h>
#include <time.h>

#include "segredos.h"

const char *NOME_REDE = "relogio";
const char *FUSO = "<-03>3";  // Brasília, sem horário de verão
const char *URL_CLIMA =
    "http://api.open-meteo.com/v1/forecast?latitude=LAT&longitude=LON"
    "&current=temperature_2m,weather_code,is_day";
const unsigned long CLIMA_MS = 10UL * 60 * 1000;
const unsigned long CLIMA_ERRO_MS = 60UL * 1000;

constexpr uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
}
const uint16_t COR_FUNDO = TFT_BLACK;
const uint16_t COR_TEXTO = TFT_WHITE;
const uint16_t COR_SUAVE = rgb(140, 140, 150);
const uint16_t COR_TRILHO = rgb(40, 40, 48);
const uint16_t COR_CLAUDE = rgb(217, 119, 87);
const uint16_t COR_AMBAR = rgb(240, 170, 40);
const uint16_t COR_VERMELHO = rgb(230, 70, 60);
const uint16_t COR_CHUVA = rgb(90, 160, 230);

TFT_eSPI tft;

struct Clima {
  bool ok = false;
  float temp = 0;
  int codigo = 0;
  bool dia = true;
} clima;

struct Claude {
  bool ok = false;
  int sessao = 0;       // % da janela de 5h
  time_t reinicio = 0;  // quando a sessão reinicia (epoch)
  int semana = 0;       // % da janela de 7 dias
} claude;

bool redeIniciada = false;
unsigned long ultimoClima = 0;
int minutoDesenhado = -1;

bool horaValida() { return time(nullptr) > 1700000000; }

// Luz de fundo invertida: sinal baixo acende. nivel 0..255 (255 = máximo).
void brilho(int nivel) { analogWrite(PINO_LUZ, 255 - constrain(nivel, 0, 255)); }

uint16_t corDoUso(int p) {
  if (p > 85) return COR_VERMELHO;
  if (p >= 60) return COR_AMBAR;
  return COR_CLAUDE;
}

// ---------- desenho ----------

void desenhaHora() {
  char txt[6] = "--:--";
  if (horaValida()) {
    time_t t = time(nullptr);
    strftime(txt, sizeof txt, "%H:%M", localtime(&t));
  }
  tft.setTextDatum(ML_DATUM);
  tft.setTextColor(COR_TEXTO, COR_FUNDO);
  tft.setTextPadding(tft.textWidth("88:88", 4));
  tft.drawString(txt, 14, 24, 4);
  tft.setTextPadding(0);
}

void nuvem(int cx, int cy, uint16_t cor) {
  tft.fillCircle(cx - 6, cy + 2, 5, cor);
  tft.fillCircle(cx, cy - 2, 7, cor);
  tft.fillCircle(cx + 6, cy + 2, 5, cor);
  tft.fillRect(cx - 6, cy + 2, 12, 6, cor);
}

void icone(int cx, int cy) {
  int c = clima.codigo;
  if (c <= 1) {
    if (clima.dia) {
      tft.fillCircle(cx, cy, 6, COR_AMBAR);
      for (int i = 0; i < 8; i++) {
        float a = i * PI / 4;
        tft.drawLine(cx + cos(a) * 9, cy + sin(a) * 9, cx + cos(a) * 12,
                     cy + sin(a) * 12, COR_AMBAR);
      }
    } else {
      tft.fillCircle(cx, cy, 8, COR_SUAVE);
      tft.fillCircle(cx + 5, cy - 4, 7, COR_FUNDO);
    }
  } else if ((c >= 51 && c <= 67) || (c >= 80 && c <= 82) || c >= 95) {
    nuvem(cx, cy - 3, COR_SUAVE);
    for (int i = -1; i <= 1; i++)
      tft.drawLine(cx + i * 6, cy + 8, cx + i * 6 - 2, cy + 13, COR_CHUVA);
  } else {
    nuvem(cx, cy, COR_SUAVE);
  }
}

void desenhaClima() {
  tft.fillRect(110, 4, 130, 40, COR_FUNDO);
  if (!clima.ok) return;
  String t = String((int)lroundf(clima.temp));
  int xIcone = 214;
  int xFim = xIcone - 22;  // texto + símbolo de grau terminam aqui
  tft.setTextDatum(MR_DATUM);
  tft.setTextColor(COR_TEXTO, COR_FUNDO);
  tft.drawString(t, xFim - 9, 24, 4);
  tft.drawCircle(xFim - 4, 15, 3, COR_TEXTO);
  icone(xIcone, 24);
}

void desenhaUso() {
  tft.fillRect(0, 50, 240, 190, COR_FUNDO);
  if (!claude.ok) {
    tft.setTextDatum(MC_DATUM);
    tft.setTextColor(COR_SUAVE, COR_FUNDO);
    tft.drawString("Claude: sem dados", 120, 140, 2);
    return;
  }
  uint16_t cor = corDoUso(claude.sessao);
  String num = String(claude.sessao);
  int wNum = tft.textWidth(num, 8);
  int wPct = tft.textWidth("%", 4);
  int x0 = 120 - (wNum + 4 + wPct) / 2;
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(cor, COR_FUNDO);
  tft.drawString(num, x0, 58, 8);
  tft.drawString("%", x0 + wNum + 4, 58 + 75 - 34, 4);

  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(COR_SUAVE, COR_FUNDO);
  tft.drawString("Claude  5h", 120, 150, 2);

  const int bx = 24, by = 166, bw = 192, bh = 10;
  tft.fillRoundRect(bx, by, bw, bh, bh / 2, COR_TRILHO);
  int cheio = bw * constrain(claude.sessao, 0, 100) / 100;
  if (cheio > 0) tft.fillRoundRect(bx, by, max(cheio, bh), bh, bh / 2, cor);

  tft.setTextColor(COR_SUAVE, COR_FUNDO);
  tft.drawString("semana " + String(claude.semana) + "%", 120, 222, 2);
}

void desenhaReinicio() {
  String txt = "";
  if (claude.ok && horaValida() && claude.reinicio > 0) {
    long falta = (long)(claude.reinicio - time(nullptr));
    if (falta <= 0) {
      txt = "sessao renovada";
    } else {
      long min = (falta + 59) / 60;
      txt = min >= 60 ? "reinicia em " + String(min / 60) + "h" +
                            (min % 60 < 10 ? "0" : "") + String(min % 60)
                      : "reinicia em " + String(min) + " min";
    }
  }
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(COR_SUAVE, COR_FUNDO);
  tft.setTextPadding(200);
  tft.drawString(txt, 120, 194, 2);
  tft.setTextPadding(0);
}

// ---------- rede ----------

void iniciaRede() {
  MDNS.begin(NOME_REDE);
  ArduinoOTA.setHostname(NOME_REDE);
  ArduinoOTA.begin();
  Serial.printf("rede ok: %s (%s.local)\n", WiFi.localIP().toString().c_str(),
                NOME_REDE);
  redeIniciada = true;
}

bool buscaClima() {
  WiFiClient cliente;
  HTTPClient http;
  http.useHTTP10(true);  // sem chunked, para ler o JSON direto do stream
  if (!http.begin(cliente, URL_CLIMA)) return false;
  int status = http.GET();
  if (status != 200) {
    Serial.printf("clima: HTTP %d\n", status);
    http.end();
    return false;
  }
  JsonDocument doc;
  DeserializationError erro = deserializeJson(doc, http.getStream());
  http.end();
  if (erro || doc["current"]["temperature_2m"].isNull()) {
    Serial.printf("clima: JSON inválido (%s)\n", erro.c_str());
    return false;
  }
  clima.temp = doc["current"]["temperature_2m"];
  clima.codigo = doc["current"]["weather_code"];
  clima.dia = doc["current"]["is_day"] | 1;
  clima.ok = true;
  Serial.printf("clima: %.1f C, código %d\n", clima.temp, clima.codigo);
  return true;
}

// ---------- principal ----------

void setup() {
  Serial.begin(115200);
  tft.init();
  tft.setRotation(0);
  pinMode(PINO_LUZ, OUTPUT);
  analogWriteRange(255);
  brilho(255);
  tft.fillScreen(COR_FUNDO);
  desenhaHora();
  desenhaUso();

  WiFi.persistent(false);  // não regravar a config do Wi-Fi na flash a cada boot
  WiFi.mode(WIFI_STA);
  WiFi.hostname(NOME_REDE);
  WiFi.begin(WIFI_NOME, WIFI_SENHA);
  configTime(FUSO, "a.st1.ntp.br", "pool.ntp.org");

  // F2: dados fixos de teste até o PC enviar os reais (F3)
  claude.ok = true;
  claude.sessao = 41;
  claude.semana = 35;
  desenhaUso();
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!redeIniciada) iniciaRede();
    ArduinoOTA.handle();
    MDNS.update();
    unsigned long espera = clima.ok ? CLIMA_MS : CLIMA_ERRO_MS;
    if (ultimoClima == 0 || millis() - ultimoClima > espera) {
      ultimoClima = millis();
      if (buscaClima()) desenhaClima();
    }
  }

  if (horaValida() && claude.reinicio == 0)
    claude.reinicio = time(nullptr) + 3 * 3600 + 31 * 60;  // F2: teste

  time_t agora = time(nullptr);
  int minuto = horaValida() ? localtime(&agora)->tm_min : -2;
  if (minuto != minutoDesenhado) {
    minutoDesenhado = minuto;
    desenhaHora();
    desenhaReinicio();
  }
  delay(50);
}
