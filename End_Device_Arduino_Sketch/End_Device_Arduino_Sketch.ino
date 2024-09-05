#include <MKRWAN.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <SensirionI2CScd4x.h>
#include <sps30.h> 

#define SEALEVELPRESSURE_HPA (1017.95)  // To be adjusted accordingly.

Adafruit_BME280 bme;
SensirionI2CScd4x scd4x;
LoRaModem modem;

int16_t ret;
uint8_t auto_clean_days = 4; // Interval for auto-cleaning in days
struct sps30_measurement m; // Struct to hold measurement data
uint16_t data_ready; // Variable to check if data is ready

// OTAA Credentials using String type as preferred
String appEui = "xxxxxxxxxxxx";  // Application EUI
String appKey = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx";  // Application Key

int currentDR = 0;  // Start with Data Rate 0
int transmissionCount = 0;  // Count the number of transmissions with the current DR
unsigned long packetsSent = 0;  // Track the number of packets sent (using unsigned long for larger count)

void setup() {
    Wire.begin();

    scd4x.begin(Wire);
    scd4x.startPeriodicMeasurement();

    if (!bme.begin(0x77)) {  // Check BME280 I2C address
        while (1);
    }

    // Initialize the I2C communication (required for the sensor)
    sensirion_i2c_init();

    // Probe the SPS30 sensor until it responds
    while (sps30_probe() != 0) {
        delay(500); // Wait for 500 milliseconds before retrying
    }

    // Set the auto-cleaning interval for the fan
    ret = sps30_set_fan_auto_cleaning_interval_days(auto_clean_days);
    if (ret) {
        // Error handling can be improved here if needed
    }

    // Start SPS30 measurement
    ret = sps30_start_measurement();
    if (ret < 0) {
        // Error handling can be improved here
    }

    if (!modem.begin(EU868)) {
        while (true);
    }

    if (!modem.joinOTAA(appEui, appKey)) {
        while (true);
    }

    modem.setPort(3);
    modem.setADR(true);  // Enable Adaptive Data Rate
}

void sendPacket(float pressure, uint16_t co2, float temperature, float humidity, float pm25, unsigned long packetCount) {
    // Set the current Data Rate (DR)
    modem.dataRate(currentDR);

    // Constructing the payload
    uint8_t payload[18];
    int16_t values[] = {
        static_cast<int16_t>(pressure * 100),
        co2,
        static_cast<int16_t>(temperature * 100),
        static_cast<int16_t>(humidity * 100),
        static_cast<int16_t>(pm25 * 100) // PM2.5 value
    };

    for (int i = 0; i < 5; i++) {
        payload[i * 2] = values[i] >> 8;
        payload[i * 2 + 1] = values[i] & 0xFF;
    }

    // Adding the packet count to the payload (4 bytes)
    payload[10] = (packetCount >> 24) & 0xFF; // High byte
    payload[11] = (packetCount >> 16) & 0xFF; // Second byte
    payload[12] = (packetCount >> 8) & 0xFF;  // Third byte
    payload[13] = packetCount & 0xFF;         // Low byte

    modem.beginPacket();
    modem.write(payload, sizeof(payload));
    int err = modem.endPacket(true);

    // Increment the transmission count
    transmissionCount++;
    if (transmissionCount >= 5) {
        // If 5 transmissions have been done with the current DR, move to the next DR
        transmissionCount = 0;
        currentDR++;
        if (currentDR > 5) {
            currentDR = 0;
        }
    }
}

void loop() {
    // Read pressure from BME280 sensor
    float pressure = bme.readPressure() / 100.0F;

    uint16_t co2 = 0;
    float temperature = 0.0f;
    float humidity = 0.0f;
    bool dataReady = false;
    scd4x.getDataReadyFlag(dataReady);
    if (dataReady) {
        scd4x.readMeasurement(co2, temperature, humidity);
    }

    // Read PM2.5 from SPS30
    float pm25 = 0.0;
    ret = sps30_read_data_ready(&data_ready);
    if (ret >= 0 && data_ready) {
        ret = sps30_read_measurement(&m);
        if (ret >= 0) {
            pm25 = m.mc_2p5;
        }
    }

    // Send the packet with sensor data and packet count
    sendPacket(pressure, co2, temperature, humidity, pm25, packetsSent);

    // Increment the packet count
    packetsSent++;

    delay(60000); // Delay between data transmissions
}
