// F1: teste de hardware. Desenha blocos de cor e alterna o PWM da luz de fundo,
// para confirmar pinos, ordem de cores e polaridade do brilho.
#include <Arduino.h>
#include <TFT_eSPI.h>

TFT_eSPI tft;

const int niveis[] = {0, 40, 255};
int passo = 0;

void desenha(int pwm) {
  tft.fillScreen(TFT_BLACK);
  tft.fillRect(0, 0, 80, 70, TFT_RED);
  tft.fillRect(80, 0, 80, 70, TFT_GREEN);
  tft.fillRect(160, 0, 80, 70, TFT_BLUE);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.drawString("R    G    B", 120, 90, 4);
  tft.drawString("PWM " + String(pwm), 120, 150, 4);
  tft.drawString("RERelogio F1", 120, 210, 2);
}

void setup() {
  Serial.begin(115200);
  pinMode(PINO_LUZ, OUTPUT);
  analogWriteRange(255);
  tft.init();
  tft.setRotation(0);
  Serial.println("\nF1 iniciado");
}

void loop() {
  int pwm = niveis[passo];
  analogWrite(PINO_LUZ, pwm);
  desenha(pwm);
  Serial.printf("PWM luz de fundo = %d\n", pwm);
  passo = (passo + 1) % 3;
  delay(4000);
}
