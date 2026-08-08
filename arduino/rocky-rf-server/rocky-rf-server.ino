#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(10, 9); // CE, CSN - Use for integrated rf nano
const byte ADDRESS_SERVER[6] = "node0";
const byte ADDRESS_CLIENT[6] = "node1";
const int CHANNEL = 0;

char text[32] = "";
char echo[32] = "ECHO-";
uint8_t prefixLen = 5;

void setup() {
  Serial.begin(9600);
  Serial.println(radio.begin());
  radio.openReadingPipe(1, ADDRESS_SERVER);
  radio.openWritingPipe(ADDRESS_CLIENT);
  radio.setPALevel(RF24_PA_MAX);
  radio.setChannel(CHANNEL);
  radio.startListening();
  Serial.println(radio.isChipConnected());
  Serial.println("Server Ready");
}

void loop() {
  if (radio.available()) {
    uint8_t nBytes = 0;
    radio.read(&nBytes, sizeof(nBytes));

    if (nBytes > 0 && nBytes <= 31) {
      radio.read(text, nBytes);
      text[nBytes] = '\0';

      Serial.print("Received: ");
      Serial.println(text);

      uint8_t copyLen = (nBytes + prefixLen > 31) ? (31 - prefixLen) : nBytes;
      char* echoWritePtr = &(echo[0]) + (sizeof(char) * prefixLen);
      memcpy(echoWritePtr, text, copyLen);
      echo[prefixLen + copyLen] = '\0';

      uint8_t echoLen = prefixLen + copyLen;

      // Send echo back
      radio.stopListening();
      radio.write(&echoLen, sizeof(echoLen));
      radio.write(echo, echoLen);
      radio.startListening();

      Serial.print("Sent: ");
      Serial.println(echo);
    }
  }
}
