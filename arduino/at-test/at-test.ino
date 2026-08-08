#include <SoftwareSerial.h>

SoftwareSerial hc05(10, 11); // Arduino RX, TX

void setup()
{
  Serial.begin(9600);
  hc05.begin(38400); // Common HC-05 full AT-mode baud
  Serial.println("HC-05 AT bridge ready");
}

void loop()
{
  while (Serial.available())
    hc05.write(Serial.read());

  while (hc05.available())
    Serial.write(hc05.read());
}