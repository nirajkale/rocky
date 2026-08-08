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
  Serial.begin(9600);          // Terminal / Serial Monitor
  maestroSerial.begin(9600);     // Maestro serial baud rate

  Serial.println("Enter: channel,speed,acceleration,pwmWidth_us");
  Serial.println("Example: 0,20,5,1500");
}

void loop()
{
  while (Serial.available())
  {
    char c = Serial.read();
    if (c == '\n' || c == '\r')
    {
      if (line.length() > 0)
      {
        processLine(line);
        line = "";
      }
    }
    else
    {
      line += c;
    }
  }
}

void processLine(String input)
{
  input.trim();
  int comma1 = input.indexOf(",");
  int comma2 = input.indexOf(",", comma1 + 1);
  int comma3 = input.indexOf(",", comma2 + 1);

  if(comma1 < 0 || comma2 < 0 || comma3 < 0){
    Serial.println("Error: expected speed,acceleration,target");
    return;
  }

  int channel = input.substring(0, comma1).toInt();
  int speed = input.substring(comma1 + 1, comma2).toInt();
  int acceleration = input.substring(comma2 + 1, comma3).toInt();
  int pwmWidth_us = input.substring(comma3 + 1).toInt();

  if(pwmWidth_us < 800 || pwmWidth_us > 2500){
    Serial.println("Error: target should be in between 800-2500");
  }

  unsigned int target = pwmWidth_us * 4;

  maestro.setSpeed(channel, speed);
  maestro.setAcceleration(channel, acceleration);
  maestro.setTarget(channel, target);

  Serial.print("OK: channel=");
  Serial.print(channel);
  Serial.print("speed=");
  Serial.print(speed);
  Serial.print(" accel=");
  Serial.print(acceleration);
  Serial.print(" pwmWidth_us=");
  Serial.print(pwmWidth_us);
  Serial.print(" maestro_target=");
  Serial.println(target);
}

