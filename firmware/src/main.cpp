// RERelogio: hora, clima (Open-Meteo) e limite do Claude numa tela 240x240.
// A tela é composta em faixas: fundo do tema (LittleFS, gerado por
// design/gerar.py) + partes dinâmicas desenhadas como em design/tela.py
// (desenha_dinamico). Mudou o visual? Mude lá, gere e confira a prévia.
#include <Arduino.h>
#include <ArduinoJson.h>
#include <ArduinoOTA.h>
#include <ESP8266HTTPClient.h>
#include <ESP8266WebServer.h>
#include <ESP8266WiFi.h>
#include <ESP8266mDNS.h>
#include <LittleFS.h>
#include <TFT_eSPI.h>
#include <time.h>

#include "recursos.h"
#include "segredos.h"

const char *NOME_REDE = "relogio";
const char *FUSO = "<-03>3";  // Brasília, sem horário de verão
const char *URL_CLIMA =
    "http://api.open-meteo.com/v1/forecast?latitude=LAT&longitude=LON"
    "&current=temperature_2m,weather_code,is_day&daily=sunrise,sunset"
    "&timezone=America%2FSao_Paulo&forecast_days=1";
const unsigned long CLIMA_MS = 10UL * 60 * 1000;
const unsigned long CLIMA_ERRO_MS = 60UL * 1000;
const unsigned long CLIMA_VALIDADE_MS = 60UL * 60 * 1000;  // depois disso, esconde o clima
const unsigned long CLAUDE_VELHO_MS = 15UL * 60 * 1000;    // depois disso, mostra em cinza

enum Tema { NOITE, DIA, POR_DO_SOL, MINIMALISTA };  // mesma ordem de TEMAS em tela.py
const int BRILHO_NORMAL = 255;
const int BRILHO_QUARTO = 38;  // ~15%, das 23h às 7h

const char *DIAS[] = {"DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"};
const char *MESES[] = {"JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
                       "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"};

TFT_eSPI tft;
ESP8266WebServer servidor(80);

struct Clima {
  bool ok = false;
  float temp = 0;
  int codigo = 0;
  bool dia = true;
  int nascer = -1;  // minutos desde 00:00
  int por = -1;
} clima;

struct Claude {
  bool ok = false;
  int sessao = 0;       // % da janela de 5h
  time_t reinicio = 0;  // quando a janela reinicia (epoch)
  int semana = 0;       // % da janela de 7 dias
} claude;

bool redeIniciada = false;
bool redesenhar = true;
unsigned long ultimoClima = 0;    // última tentativa
unsigned long climaSucesso = 0;   // último sucesso
bool climaFalhou = false;
time_t agoraTela = 0;
unsigned long claudeLido = 0;  // millis() em que o ai-usagebar leu os números  // lido uma vez por desenho, para a tela não sair "rasgada"
int minutoDesenhado = -1;
int temaForcado = -1;  // teste: /tema?n=0..3; -1 = automático

bool horaValida() { return time(nullptr) > 1700000000; }
bool climaValido() { return clima.ok && millis() - climaSucesso < CLIMA_VALIDADE_MS; }

// Luz de fundo invertida: sinal baixo acende. nivel 0..255 (255 = máximo).
void brilho(int nivel) { analogWrite(PINO_LUZ, 255 - constrain(nivel, 0, 255)); }

int temaAtual() {
  if (temaForcado >= 0) return temaForcado;
  if (agoraTela < 1700000000) return NOITE;
  struct tm *lt = localtime(&agoraTela);
  if (lt->tm_hour >= 23 || lt->tm_hour < 7) return MINIMALISTA;
  int m = lt->tm_hour * 60 + lt->tm_min;
  int nascer = clima.nascer >= 0 ? clima.nascer : 6 * 60;
  int por = clima.por >= 0 ? clima.por : 18 * 60 + 15;
  if (m < nascer) return NOITE;
  if (m < por - 45) return DIA;
  if (m < por + 30) return POR_DO_SOL;
  return NOITE;
}

// ---------- composição em faixas ----------

const int FAIXA = 16;
uint16_t faixa[240 * FAIXA];
int faixaY0 = 0;

uint16_t mistura(uint16_t fundo, uint16_t cor, int a, int maximo) {
  int r = ((fundo >> 11) * (maximo - a) + (cor >> 11) * a) / maximo;
  int g = (((fundo >> 5) & 63) * (maximo - a) + ((cor >> 5) & 63) * a) / maximo;
  int b = ((fundo & 31) * (maximo - a) + (cor & 31) * a) / maximo;
  return (r << 11) | (g << 5) | b;
}

inline void ponto(int x, int y, uint16_t cor, int a = 1, int maximo = 1) {
  if (x < 0 || x >= 240 || y < faixaY0 || y >= faixaY0 + FAIXA) return;
  uint16_t &p = faixa[(y - faixaY0) * 240 + x];
  p = a == maximo ? cor : mistura(p, cor, a, maximo);
}

// Retângulo com cantos inclusivos, como o ImageDraw.rectangle do Pillow.
void retangulo(int x0, int y0, int x1, int y1, uint16_t cor) {
  for (int y = max(y0, faixaY0); y <= min(y1, faixaY0 + FAIXA - 1); y++)
    for (int x = max(x0, 0); x <= min(x1, 239); x++) faixa[(y - faixaY0) * 240 + x] = cor;
}

uint16_t proximoCp(const char *&s) {
  uint8_t c = *s++;
  if (c < 0x80) return c;
  if ((c & 0xE0) == 0xC0 && *s) return ((c & 0x1F) << 6) | (*s++ & 0x3F);
  return '?';
}

bool achaGlifo(const Fonte &f, uint16_t cp, Glifo &g) {
  for (int i = 0; i < f.n; i++) {
    memcpy_P(&g, &f.g[i], sizeof g);
    if (g.cp == cp) return true;
  }
  return false;
}

int largura(const Fonte &f, const char *s) {
  int w = 0;
  Glifo g;
  while (*s)
    if (achaGlifo(f, proximoCp(s), g)) w += g.av;
  return w;
}

// y é a linha de base; alinha: 'e' esquerda, 'd' direita, 'c' centro.
void texto(const Fonte &f, int x, int y, const char *s, uint16_t cor, char alinha = 'e') {
  if (alinha == 'd') x -= largura(f, s);
  if (alinha == 'c') x -= largura(f, s) / 2;
  int maximo = (1 << f.bpp) - 1;
  Glifo g;
  while (*s) {
    if (!achaGlifo(f, proximoCp(s), g)) continue;
    int topo = y + g.dy;
    int r0 = max(0, faixaY0 - topo), r1 = min((int)g.h, faixaY0 + FAIXA - topo);
    for (int r = r0; r < r1; r++)
      for (int c = 0; c < g.w; c++) {
        int bit = (r * g.w + c) * f.bpp;
        uint8_t byte = pgm_read_byte(f.px + g.ofs + bit / 8);
        int v = (byte >> (8 - f.bpp - bit % 8)) & maximo;
        if (v) ponto(x + g.dx + c, topo + r, cor, v, maximo);
      }
    x += g.av;
  }
}

void icone(const Icone &ic, int x, int y, uint16_t cor) {
  int r0 = max(0, faixaY0 - y), r1 = min((int)ic.h, faixaY0 + FAIXA - y);
  for (int r = r0; r < r1; r++)
    for (int c = 0; c < ic.w; c++) {
      int bit = r * ic.w + c;
      if (pgm_read_byte(ic.px + bit / 8) & (0x80 >> (bit % 8))) ponto(x + c, y + r, cor);
    }
}

void barra(int x0, int y0, int x1, int y1, int pct, uint16_t cor) {
  retangulo(x0, y0, x1, y1, COR_TRILHO);
  int cheio = (x1 - x0) * constrain(pct, 0, 100) / 100;
  if (cheio) retangulo(x0, y0, x0 + cheio, y1, cor);
}

uint16_t corDoUso(int p) {
  if (p > 85) return COR_VERMELHO;
  if (p >= 60) return COR_AMBAR;
  return COR_LARANJA;
}

void iconesClima(int tema) {
  int c = clima.codigo;
  if (c <= 1) {
    icone(clima.dia ? I_SOL : I_LUA, CLIMA_X, CLIMA_Y, COR_SOL);
    return;
  }
  icone(I_NUVEM, CLIMA_X, CLIMA_Y, TEMA_NUVEM[tema]);
  if ((c >= 51 && c <= 67) || (c >= 80 && c <= 82) || c >= 95)
    icone(I_GOTAS, CLIMA_X, CLIMA_Y, COR_CHUVA);
}

// Espelha desenha_dinamico() de design/tela.py.
void desenhaDinamico(int tema) {
  uint16_t c1 = TEMA_TEXTO[tema], c2 = TEMA_TEXTO_2[tema];
  char buf[32];

  // topo e hora
  if (agoraTela > 1700000000) {
    struct tm *lt = localtime(&agoraTela);
    texto(F_GRANDE, DIA_X, DIA_Y, DIAS[lt->tm_wday], c1);
    snprintf(buf, sizeof buf, "%02d %s", lt->tm_mday, MESES[lt->tm_mon]);
    texto(F_DATA, DATA_X, DATA_Y, buf, c2);
    strftime(buf, sizeof buf, "%H:%M", lt);
  } else {
    strcpy(buf, "--:--");
  }
  texto(F_HORA, HORA_X, HORA_Y, buf, c1, 'c');
  if (climaValido()) {
    snprintf(buf, sizeof buf, "%d°", (int)lroundf(clima.temp));
    texto(F_GRANDE, TEMP_X, TEMP_Y, buf, c1, 'd');
    iconesClima(tema);
  }

  // cartão Claude: dado velho (>15 min) em cinza; reinício passado = sessão em 0%
  icone(I_CLAUDE, CC_X0 + 8, CC_Y0 + 7, COR_LARANJA);
  texto(F_TITULO, CC_X0 + 26, CC_Y0 + 19, "Claude", COR_TEXTO);
  unsigned long idadeMs = millis() - claudeLido;
  bool velho = claude.ok && idadeMs > CLAUDE_VELHO_MS;
  if (claude.ok) {
    long falta = agoraTela > 1700000000 ? (long)(claude.reinicio - agoraTela) : 1;
    bool renovada = falta <= 0;
    int sessao = renovada ? 0 : claude.sessao;
    snprintf(buf, sizeof buf, "%d%%", sessao);
    texto(F_PCT, CC_X1 - 8, CC_Y0 + 20, buf, velho && !renovada ? COR_CINZA : COR_TEXTO, 'd');
    barra(CC_X0 + 8, CC_Y0 + 26, CC_X1 - 8, CC_Y0 + 31, sessao,
          velho ? COR_CINZA : corDoUso(sessao));
    texto(F_PEQ, CC_X0 + 8, CC_Y0 + 46, "janela 5h", COR_TEXTO_2);
    if (renovada) {
      strcpy(buf, "sessão renovada");
    } else if (velho) {
      unsigned long min = idadeMs / 60000;
      if (min < 60)
        snprintf(buf, sizeof buf, "atualizado há %lu min", min);
      else if (min < 24 * 60)
        snprintf(buf, sizeof buf, "atualizado há %luh", min / 60);
      else
        snprintf(buf, sizeof buf, "atualizado há %lud", min / (24 * 60));
    } else {
      long min = (falta + 59) / 60;
      if (min >= 60)
        snprintf(buf, sizeof buf, "reinicia %ldh%02ld", min / 60, min % 60);
      else
        snprintf(buf, sizeof buf, "reinicia %ld min", min);
    }
    texto(F_PEQ, CC_X1 - 8, CC_Y0 + 46, buf, COR_TEXTO_2, 'd');
  } else {
    barra(CC_X0 + 8, CC_Y0 + 26, CC_X1 - 8, CC_Y0 + 31, 0, COR_LARANJA);
    texto(F_PEQ, CC_X0 + 8, CC_Y0 + 46, "sem dados", COR_TEXTO_2);
  }

  // cartão Semana
  icone(I_CALENDARIO, CS_X0 + 8, CS_Y0 + 7, COR_AZUL);
  texto(F_PEQ, CS_X0 + 26, CS_Y0 + 19, "Semana", COR_TEXTO);
  texto(F_PEQ, CS_X0 + 26 + largura(F_PEQ, "Semana "), CS_Y0 + 19, "7d", COR_TEXTO_2);
  barra(CS_X0 + 104, CS_Y0 + 12, CS_X1 - 44, CS_Y0 + 17, claude.ok ? claude.semana : 0,
        velho ? COR_CINZA : COR_AZUL);
  if (claude.ok) {
    snprintf(buf, sizeof buf, "%d%%", claude.semana);
    texto(F_PEQ, CS_X1 - 8, CS_Y0 + 19, buf, velho ? COR_CINZA : COR_TEXTO, 'd');
  }
}

void desenhaTela() {
  agoraTela = time(nullptr);
  int tema = temaAtual();
  brilho(tema == MINIMALISTA && temaForcado < 0 ? BRILHO_QUARTO : BRILHO_NORMAL);
  char caminho[16];
  snprintf(caminho, sizeof caminho, "/tema%d.rgb", tema);
  File arq = LittleFS.open(caminho, "r");
  for (faixaY0 = 0; faixaY0 < 240; faixaY0 += FAIXA) {
    if (!arq || arq.read((uint8_t *)faixa, sizeof faixa) != sizeof faixa)
      memset(faixa, 0, sizeof faixa);  // sem fundo: preto (rodar uploadfs)
    desenhaDinamico(tema);
    tft.pushImage(0, faixaY0, 240, FAIXA, faixa);
  }
  if (arq) arq.close();
}

// ---------- rede ----------

void iniciaRede() {
  MDNS.begin(NOME_REDE);
  ArduinoOTA.setHostname(NOME_REDE);
  ArduinoOTA.begin();
  servidor.on("/tema", []() {
    temaForcado = servidor.hasArg("n") ? constrain(servidor.arg("n").toInt(), -1, N_TEMAS - 1) : -1;
    redesenhar = true;
    servidor.send(200, "text/plain", "tema " + String(temaForcado) + "\n");
  });
  servidor.on("/claude", HTTP_POST, []() {
    JsonDocument doc;
    if (deserializeJson(doc, servidor.arg("plain")) || !doc["sessao"].is<int>() ||
        !doc["semana"].is<int>() || !doc["reinicio"].is<long long>()) {
      servidor.send(400, "text/plain", "esperado {sessao, reinicio, semana}\n");
      return;
    }
    claude.sessao = constrain((int)doc["sessao"], 0, 100);
    claude.semana = constrain((int)doc["semana"], 0, 100);
    claude.reinicio = (time_t)doc["reinicio"].as<long long>();
    long idade = constrain((long)(doc["idade"] | 0), 0L, 86400L);  // segundos desde a leitura
    claudeLido = millis() - (unsigned long)idade * 1000UL;
    claude.ok = true;
    redesenhar = true;
    servidor.send(200, "text/plain", "ok\n");
  });
  servidor.begin();
  Serial.printf("rede ok: %s (%s.local)\n", WiFi.localIP().toString().c_str(), NOME_REDE);
  redeIniciada = true;
}

int minutosDe(const char *iso) {  // "2026-10-31T05:21" -> 321
  if (!iso || strlen(iso) < 16) return -1;
  return atoi(iso + 11) * 60 + atoi(iso + 14);
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
  clima.nascer = minutosDe(doc["daily"]["sunrise"][0]);
  clima.por = minutosDe(doc["daily"]["sunset"][0]);
  clima.ok = true;
  Serial.printf("clima: %.1f C, código %d, sol %d-%d min\n", clima.temp, clima.codigo,
                clima.nascer, clima.por);
  return true;
}

// ---------- principal ----------

void setup() {
  Serial.begin(115200);
  tft.init();
  tft.setRotation(0);
  tft.setSwapBytes(true);  // buffer em RGB565 nativo (little-endian)
  pinMode(PINO_LUZ, OUTPUT);
  analogWriteRange(255);
  if (!LittleFS.begin()) Serial.println("LittleFS: falhou ao montar");
  desenhaTela();
  brilho(BRILHO_NORMAL);

  WiFi.persistent(false);  // não regravar a config do Wi-Fi na flash a cada boot
  WiFi.mode(WIFI_STA);
  WiFi.hostname(NOME_REDE);
  WiFi.begin(WIFI_NOME, WIFI_SENHA);
  configTime(FUSO, "a.st1.ntp.br", "pool.ntp.org");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!redeIniciada) iniciaRede();
    ArduinoOTA.handle();
    MDNS.update();
    servidor.handleClient();
    unsigned long espera = climaFalhou ? CLIMA_ERRO_MS : CLIMA_MS;
    if (ultimoClima == 0 || millis() - ultimoClima > espera) {
      ultimoClima = millis();
      climaFalhou = !buscaClima();
      if (!climaFalhou) climaSucesso = millis();
      redesenhar = true;
    }
  }

  time_t agora = time(nullptr);
  int minuto = horaValida() ? localtime(&agora)->tm_min : -2;
  if (minuto != minutoDesenhado || redesenhar) {
    minutoDesenhado = minuto;
    redesenhar = false;
    desenhaTela();
  }
  delay(20);
}
