#include <PololuMaestro.h>
#include <SoftwareSerial.h>

SoftwareSerial maestroSerial(10, 11);
// Arduino pin 10 RX  <-- Maestro TX
// Arduino pin 11 TX  --> Maestro RX

MiniMaestro maestro(maestroSerial, Maestro::noResetPin, 12);

const uint8_t SERVO_CHANNEL = 0;

// Maestro target units are quarter-microseconds:
// 6000 = 1500 µs = neutral / center

void setup()
{
  maestroSerial.begin(9600);

  maestro.setSpeed(SERVO_CHANNEL, 15);
  maestro.setAcceleration(SERVO_CHANNEL, 40);
}

void loop()
{
  maestro.setTarget(SERVO_CHANNEL, 6000);  // neutral / center
  delay(100);
}