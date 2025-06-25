#include <SPI.h>

// Pin-nummeret defineres til SS (Slave Select) til Arduino pin 10
const int ssPin = 10;

// Samplingstiden i millisekunder tilføjes (man vil kunne ændre værdien efter behov)
const int samplingTime = 10;

// SPI-indstillingerne
SPISettings settings(8000000, MSBFIRST, SPI_MODE0);

// For at kunne gennemføre en SPI-overførsel og returnere resultatet:
int getEKGADC() {
  digitalWrite(ssPin, LOW);                  // SPI-overførsel startes
  int result = SPI.transfer16(0x00);         // Gennemfører overførsel
  digitalWrite(ssPin, HIGH);                 // Afslutter SPI-overførsel
  return result;                             // resultatet af AD-konverteringen
}

void setup() {
  SPI.begin();                               //  SPI-porten startes
  SPI.beginTransaction(settings);            //  SPI-overførsel med de angivne indstillinger startes
  pinMode(ssPin, OUTPUT);                    //  SS-pin’en sættes som output
  digitalWrite(ssPin, HIGH);                 //  SS-pin’en sættes høj som standard
  Serial.begin(38400);                       //  Den serielle kommunikation med en baudrate på 38400 vælges
}

void loop() {
  //  AD-konvertering udføres  resultatet vil vises
  int adcValue = getEKGADC();


  //  Resultat sendes via den serielle forbindelse
  Serial.println(adcValue);

  // Samplingstiden
  delay(samplingTime);
}
