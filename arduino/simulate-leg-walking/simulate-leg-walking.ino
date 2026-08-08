#include <PololuMaestro.h>
#include <SoftwareSerial.h>

SoftwareSerial maestroSerial(10, 11);
// Arduino connections:
// pin 11 --> RX (maestro controller)
// pin 10 <-- TX (maestro controller)

MiniMaestro maestro(maestroSerial, Maestro::noResetPin, 12);
/* 
MiniMaestro object name: maestro
Serial port used:        maestroSerial
Reset pin:               no reset pin used
Device number:           12
*/

String line = "";

void setup()
{
  // Serial.begin(9600);          // Terminal / Serial Monitor
  maestroSerial.begin(9600);     // Maestro serial baud rate
  // set initial resting positions
  setPosition(0,80,40,1000);
  setPosition(1,80,40,2000);
  setPosition(2,80,40,2000);
  // femur & foot is lifted & joint is in back
}

void loop()
{
  // take the foot forward & down
  // move joint forward
  setPosition(0,80,40,1700);
  delay(100);
  // make foot stright
  setPosition(2,80,40,1500);
  delay(100);
  // put femur down
  setPosition(1,80,40,1300);
  delay(1500);

  // move the foot back
  // move joint back
  setPosition(0,85,40,1000);
  delay(2000);

  // lift the foot
  // lift the femur
  setPosition(1,70,40,2000);
  delay(100);
  // lift the ankle
  setPosition(2,80,40,1000);
  delay(1500);
}

void setPosition(int channel, int speed, int acceleration, int pwmWidth_us){
  if(pwmWidth_us < 800 || pwmWidth_us > 2300){
    return;
  }
  unsigned int target = pwmWidth_us * 4;
  maestro.setSpeed(channel, speed);
  maestro.setAcceleration(channel, acceleration);
  maestro.setTarget(channel, target);
}

