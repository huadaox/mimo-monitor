/*
 * Mimo Monitor - ESP32 BLE Firmware
 *
 * Scans for Mimo Monitor BLE GATT service and subscribes to status notifications.
 * Service UUID: 0x1820
 * Status Characteristic UUID: 0x2B01 (Read + Notify)
 *
 * Status -> LED mapping:
 *   thinking  = blue blink
 *   running   = green breathing
 *   idle      = yellow solid
 *   error     = red fast flash
 *   stopped   = LED off
 *   waiting   = orange pulse
 */

#include <Arduino.h>
#include <NimBLEDevice.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>

// ============== Configuration ==============
const uint8_t LED_PIN = 48;       // Built-in NeoPixel; change as needed
const uint8_t NUM_PIXELS = 1;
const bool USE_NEOPIXEL = true;
const uint8_t PLAIN_LED_PIN = 2;

// BLE Service & Characteristic UUIDs (must match server)
static NimBLEUUID SERVICE_UUID("1820");
static NimBLEUUID STATUS_CHAR_UUID("2B01");

// Scan parameters
const uint32_t SCAN_DURATION = 0;  // 0 = scan forever
const uint16_t SCAN_INTERVAL = 160; // 100ms
const uint16_t SCAN_WINDOW = 80;    // 50ms

// Reconnect parameters
const unsigned long RECONNECT_DELAY = 5000;
const unsigned long STALE_TIMEOUT = 15000;

// ============== Globals ==============
Adafruit_NeoPixel strip(NUM_PIXELS, LED_PIN, NEO_GRB + NEO_KHZ800);

enum AgentState {
    STATE_STOPPED,
    STATE_IDLE,
    STATE_RUNNING,
    STATE_THINKING,
    STATE_WAITING,
    STATE_ERROR
};

AgentState currentState = STATE_STOPPED;
String currentAgentId = "";
String currentTool = "";
unsigned long lastNotifyTime = 0;

bool bleConnected = false;
bool doConnect = false;
bool doScan = false;
NimBLEAdvertisedDevice *targetDevice = nullptr;
NimBLEClient *pClient = nullptr;
NimBLERemoteCharacteristic *pStatusChar = nullptr;

// Forward declarations
void connectToServer();

// ============== LED Helpers ==============

void setPixelColor(uint8_t r, uint8_t g, uint8_t b) {
    if (USE_NEOPIXEL) {
        strip.setPixelColor(0, strip.Color(r, g, b));
        strip.show();
    } else {
        int brightness = (r + g + b) / 3;
        analogWrite(PLAIN_LED_PIN, brightness);
    }
}

void ledOff() {
    setPixelColor(0, 0, 0);
}

uint8_t breathe(unsigned long ms, uint16_t periodMs = 2000) {
    float phase = (float)(ms % periodMs) / periodMs * 2.0 * PI;
    return (uint8_t)((sinf(phase - PI / 2.0) + 1.0) / 2.0 * 255);
}

void updateLed() {
    unsigned long now = millis();

    if (lastNotifyTime > 0 && (now - lastNotifyTime > STALE_TIMEOUT)) {
        currentState = STATE_STOPPED;
    }

    switch (currentState) {
        case STATE_STOPPED:
            ledOff();
            break;
        case STATE_IDLE:
            setPixelColor(255, 193, 7);
            break;
        case STATE_RUNNING: {
            uint8_t b = breathe(now, 2000);
            setPixelColor(0, b, 0);
            break;
        }
        case STATE_THINKING: {
            bool on = (now / 500) % 2 == 0;
            setPixelColor(0, 0, on ? 255 : 0);
            break;
        }
        case STATE_WAITING: {
            uint8_t b = breathe(now, 3000);
            setPixelColor(255, b / 2, 0);
            break;
        }
        case STATE_ERROR: {
            bool on = (now / 200) % 2 == 0;
            setPixelColor(on ? 255 : 0, 0, 0);
            break;
        }
    }
}

// ============== State Parsing ==============

AgentState parseStatus(const char *status) {
    if (strcmp(status, "thinking") == 0) return STATE_THINKING;
    if (strcmp(status, "running") == 0)  return STATE_RUNNING;
    if (strcmp(status, "idle") == 0)     return STATE_IDLE;
    if (strcmp(status, "waiting") == 0)  return STATE_WAITING;
    if (strcmp(status, "error") == 0)    return STATE_ERROR;
    return STATE_STOPPED;
}

const char *stateToString(AgentState s) {
    switch (s) {
        case STATE_THINKING: return "THINKING";
        case STATE_RUNNING:  return "RUNNING";
        case STATE_IDLE:     return "IDLE";
        case STATE_WAITING:  return "WAITING";
        case STATE_ERROR:    return "ERROR";
        case STATE_STOPPED:  return "STOPPED";
    }
    return "UNKNOWN";
}

int statePriority(AgentState s) {
    switch (s) {
        case STATE_ERROR:    return 5;
        case STATE_THINKING: return 4;
        case STATE_RUNNING:  return 3;
        case STATE_WAITING:  return 2;
        case STATE_IDLE:     return 1;
        case STATE_STOPPED:  return 0;
    }
    return 0;
}

// ============== BLE Notification Callback ==============

void notifyCallback(NimBLERemoteCharacteristic *pChar, uint8_t *data, size_t len, bool isNotify) {
    // Ensure null-terminated
    char buf[1024];
    size_t copyLen = min(len, sizeof(buf) - 1);
    memcpy(buf, data, copyLen);
    buf[copyLen] = '\0';

    Serial.printf("[BLE] Notify received (%d bytes): %s\n", (int)len, buf);

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, buf);
    if (err) {
        Serial.printf("[WARN] JSON parse error: %s\n", err.c_str());
        return;
    }

    // Validate protocol version
    int version = doc["v"] | 0;
    if (version != 1) {
        Serial.printf("[WARN] Unknown protocol version: %d\n", version);
        return;
    }

    JsonArray agents = doc["agents"].as<JsonArray>();
    if (agents.isNull()) {
        Serial.println("[WARN] No agents array in data");
        return;
    }

    // Find highest-priority agent state
    AgentState bestState = STATE_STOPPED;
    String bestId = "";
    String bestTool = "";

    for (JsonObject agent : agents) {
        const char *id = agent["id"] | "unknown";
        const char *status = agent["status"] | "stopped";
        const char *tool = agent["tool"] | "";

        AgentState s = parseStatus(status);
        if (statePriority(s) > statePriority(bestState)) {
            bestState = s;
            bestId = id;
            bestTool = tool;
        }
    }

    currentState = bestState;
    currentAgentId = bestId;
    currentTool = bestTool;
    lastNotifyTime = millis();

    Serial.printf("[STATE] %s | agent=%s tool=%s | agents=%d\n",
                  stateToString(currentState),
                  currentAgentId.c_str(),
                  currentTool.c_str(),
                  (int)agents.size());
}

// ============== BLE Client Callbacks ==============

class ClientCallbacks : public NimBLEClientCallbacks {
    void onConnect(NimBLEClient *client) override {
        Serial.println("[BLE] Connected to server!");
        bleConnected = true;
    }

    void onDisconnect(NimBLEClient *client, int reason) override {
        Serial.printf("[BLE] Disconnected (reason: %d)\n", reason);
        bleConnected = false;
        currentState = STATE_STOPPED;
        doScan = true;  // Trigger re-scan
    }
};

// ============== BLE Scan Callbacks ==============

class ScanCallbacks : public NimBLEAdvertisedDeviceCallbacks {
    void onResult(NimBLEAdvertisedDevice *advertisedDevice) override {
        // Check if device advertises our service
        if (advertisedDevice->haveServiceUUID() &&
            advertisedDevice->isAdvertisingService(SERVICE_UUID)) {
            Serial.printf("[BLE] Found Mimo server: %s\n",
                          advertisedDevice->getAddress().toString().c_str());
            NimBLEDevice::getScan()->stop();
            targetDevice = advertisedDevice;
            doConnect = true;
        }
    }
};

// ============== BLE Connect to Server ==============

void connectToServer() {
    Serial.printf("[BLE] Connecting to %s...\n", targetDevice->getAddress().toString().c_str());

    pClient = NimBLEDevice::createClient();
    pClient->setClientCallbacks(new ClientCallbacks());

    if (!pClient->connect(targetDevice)) {
        Serial.println("[BLE] Connection failed!");
        NimBLEDevice::deleteClient(pClient);
        doScan = true;
        return;
    }

    Serial.printf("[BLE] Connected to %s\n", pClient->getPeerAddress().toString().c_str());

    // Get service
    NimBLERemoteService *pService = pClient->getService(SERVICE_UUID);
    if (!pService) {
        Serial.println("[BLE] Service not found!");
        pClient->disconnect();
        doScan = true;
        return;
    }

    // Get status characteristic
    pStatusChar = pService->getCharacteristic(STATUS_CHAR_UUID);
    if (!pStatusChar) {
        Serial.println("[BLE] Status characteristic not found!");
        pClient->disconnect();
        doScan = true;
        return;
    }

    // Read current value
    if (pStatusChar->canRead()) {
        std::string value = pStatusChar->readValue();
        Serial.printf("[BLE] Initial read: %s\n", value.c_str());
        notifyCallback(pStatusChar, (uint8_t *)value.data(), value.length(), false);
    }

    // Subscribe to notifications
    if (pStatusChar->canNotify()) {
        if (!pStatusChar->subscribe(true, notifyCallback)) {
            Serial.println("[BLE] Subscribe failed!");
            pClient->disconnect();
            doScan = true;
            return;
        }
        Serial.println("[BLE] Subscribed to status notifications");
    } else {
        Serial.println("[WARN] Characteristic does not support notify");
    }

    bleConnected = true;
    delete targetDevice;
    targetDevice = nullptr;

    // Connection success blink
    setPixelColor(0, 255, 255);
    delay(300);
    setPixelColor(0, 0, 0);
    delay(300);
    setPixelColor(0, 255, 255);
    delay(300);
}

// ============== Setup ==============

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n=== Mimo Monitor - ESP32 BLE ===");

    // LED setup
    if (USE_NEOPIXEL) {
        strip.begin();
        strip.setBrightness(40);
        strip.show();
    } else {
        pinMode(PLAIN_LED_PIN, OUTPUT);
    }

    // BLE setup
    NimBLEDevice::init("MimoESP32");

    // Set TX power for better range
    NimBLEDevice::setPower(ESP_PWR_LVL_P9);

    NimBLEScan *pScan = NimBLEDevice::getScan();
    pScan->setAdvertisedDeviceCallbacks(new ScanCallbacks());
    pScan->setActiveScan(true);
    pScan->setInterval(SCAN_INTERVAL);
    pScan->setWindow(SCAN_WINDOW);

    Serial.println("[BLE] Scanning for Mimo Monitor server...");
    pScan->start(SCAN_DURATION, false);
}

// ============== Main Loop ==============

unsigned long lastReconnectAttempt = 0;

void loop() {
    // Handle connection request
    if (doConnect) {
        doConnect = false;
        connectToServer();
    }

    // Handle re-scan request
    if (doScan) {
        unsigned long now = millis();
        if (now - lastReconnectAttempt > RECONNECT_DELAY) {
            lastReconnectAttempt = now;
            doScan = false;
            Serial.println("[BLE] Re-scanning...");
            NimBLEDevice::getScan()->start(SCAN_DURATION, false);
        }
    }

    // Update LED
    updateLed();

    // Yield for ESP32 housekeeping
    yield();
}
