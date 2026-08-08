#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(10, 9); // CE, CSN - Use for integrated rf nano
const byte ADDRESS_SERVER[6] = "node0";
const byte ADDRESS_CLIENT[6] = "node1";
const int CHANNEL = 0;
const uint8_t MAX_MSG_LEN = 26; // 32 - 1 (size byte) - 5 ("ECHO-") = 26

void setup() {
  Serial.begin(9600);
  Serial.println(radio.begin());
  radio.openWritingPipe(ADDRESS_SERVER);
  radio.openReadingPipe(1, ADDRESS_CLIENT);
  radio.setPALevel(RF24_PA_MAX);
  radio.setChannel(CHANNEL);
  radio.stopListening();
  Serial.println(radio.isChipConnected());
  Serial.println("Client Ready. Type a message and press Enter:");
}

void loop() {
  if (Serial.available()) {
    char text[32] = "";
    uint8_t len = Serial.readBytesUntil('\n', text, MAX_MSG_LEN);

    // Trim trailing \r if present
    if (len > 0 && text[len - 1] == '\r') {
      len--;
    }
    text[len] = '\0';

    if (len == 0) return;

    Serial.print("Sending: ");
    Serial.println(text);

    // Send: [1 byte: length][N bytes: payload]
    bool ok = radio.write(&len, sizeof(len));
    if (!ok) {
      Serial.println("Failed to send length byte");
      return;
    }
    ok = radio.write(text, len);
    if (!ok) {
      Serial.println("Failed to send payload");
      return;
    }

    // Switch to RX and wait for echo response
    radio.startListening();
    int readAttempts = 10;
    bool ready = false;
    while(readAttempts > 0){
      if(radio.available()){
        ready = true;
        break;
      }
      delay(1000);
      readAttempts--;
    }

    if (!ready) {
      Serial.println("Response timeout");
    } else {
      uint8_t echoLen = 0;
      radio.read(&echoLen, sizeof(echoLen));

      if (echoLen > 0 && echoLen <= 31) {
        char echo[32] = "";
        radio.read(echo, echoLen);
        echo[echoLen] = '\0';
        Serial.print("Response: ");
        Serial.println(echo);
      }
    }

    radio.stopListening();
  }
}
