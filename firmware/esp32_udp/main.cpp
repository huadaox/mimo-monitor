/*
 * Mimo Monitor - ESP32 WiFi UDP Firmware
 *
 * Listens for UDP broadcasts on port 9101 from the Mimo Monitor server.
 * Displays AI agent status on an NeoPixel LED (or built-in LED fallback).
 *
 * Protocol (JSON over UDP):
 *   {"v":1,"ts":...,"agents":[{"id":"...","status":"...","tool":"..."}]}
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
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>

// ============== Configuration ==============
// Edit these before flashing!
const char *WIFI_SSID = "YOUR_WIFI_SSID";
const char *WIFI_PASS = "YOUR_WIFI_PASSWORD";

const uint16_t UDP_PORT = 9101;
const uint8_t LED_PIN = 48;       // Built-in NeoPixel on most ESP32-S3 boards; change as needed
const uint8_t NUM_PIXELS = 1;     // Number of NeoPixels
const bool USE_NEOPIXEL = true;   // Set false to use a plain LED on LED_PIN

// Fallback plain LED pin (when USE_NEOPIXEL = false)
const uint8_t PLAIN_LED_PIN = 2;

// ============== Globals ==============
WiFiUDP udp;
Adafruit_NeoPixel strip(NUM_PIXELS, LED_PIN, NEO_GRB + NEO_KHZ800);

// Agent state (we track the "most interesting" agent)
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
unsigned long lastPacketTime = 0;
const unsigned long STALE_TIMEOUT = 15000;  // 15s no packet → stopped

// ============== LED Helpers ==============

void setPixelColor(uint8_t r, uint8_t g, uint8_t b) {
    if (USE_NEOPIXEL) {
        strip.setPixelColor(0, strip.Color(r, g, b));
        strip.show();
    } else {
        // For plain LED, use brightness as PWM
        int brightness = (r + g + b) / 3;
        analogWrite(PLAIN_LED_PIN, brightness);
    }
}

void ledOff() {
    setPixelColor(0, 0, 0);
}

// Breathing effect: smooth sine wave
uint8_t breathe(unsigned long ms, uint16_t periodMs = 2000) {
    float phase = (float)(ms % periodMs) / periodMs * 2.0 * PI;
    return (uint8_t)((sinf(phase - PI / 2.0) + 1.0) / 2.0 * 255);
}

void updateLed() {
    unsigned long now = millis();

    // Check for stale data
    if (lastPacketTime > 0 && (now - lastPacketTime > STALE_TIMEOUT)) {
        currentState = STATE_STOPPED;
    }

    switch (currentState) {
        case STATE_STOPPED:
            ledOff();
            break;

        case STATE_IDLE:
            // Yellow solid
            setPixelColor(255, 193, 7);
            break;

        case STATE_RUNNING: {
            // Green breathing
            uint8_t b = breathe(now, 2000);
            setPixelColor(0, b, 0);
            break;
        }

        case STATE_THINKING: {
            // Blue blink (500ms on/off)
            bool on = (now / 500) % 2 == 0;
            setPixelColor(0, 0, on ? 255 : 0);
            break;
        }

        case STATE_WAITING: {
            // Orange pulse (slower)
            uint8_t b = breathe(now, 3000);
            setPixelColor(255, b / 2, 0);
            break;
        }

        case STATE_ERROR: {
            // Red fast flash (200ms)
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

// Priority: error > thinking > running > waiting > idle > stopped
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

// ============== UDP Packet Processing ==============

void processPacket(const uint8_t *data, size_t len) {
    // Ensure null-terminated
    char buf[1024];
    size_t copyLen = min(len, sizeof(buf) - 1);
    memcpy(buf, data, copyLen);
    buf[copyLen] = '\0';

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
        Serial.println("[WARN] No agents array in packet");
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

    // Update state
    currentState = bestState;
    currentAgentId = bestId;
    currentTool = bestTool;
    lastPacketTime = millis();

    // Serial debug output
    Serial.printf("[STATE] %s | agent=%s tool=%s | agents=%d\n",
                  stateToString(currentState),
                  currentAgentId.c_str(),
                  currentTool.c_str(),
                  (int)agents.size());
}

// ============== Setup ==============

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n=== Mimo Monitor - ESP32 UDP ===");

    // LED setup
    if (USE_NEOPIXEL) {
        strip.begin();
        strip.setBrightness(40);  // 0-255, keep it eye-friendly
        strip.show();
    } else {
        pinMode(PLAIN_LED_PIN, OUTPUT);
    }

    // WiFi connect
    Serial.printf("[WIFI] Connecting to %s", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(500);
        Serial.print(".");
        attempts++;
        // Blink LED while connecting
        if (attempts % 2 == 0) setPixelColor(0, 0, 50);
        else ledOff();
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WIFI] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
        Serial.printf("[UDP] Listening on port %d\n", UDP_PORT);
        udp.begin(UDP_PORT);
        // Green flash to confirm
        setPixelColor(0, 255, 0);
        delay(500);
    } else {
        Serial.println("\n[WIFI] Connection failed! Running in offline mode.");
        // Red flash to indicate error
        setPixelColor(255, 0, 0);
        delay(2000);
    }
}

// ============== Main Loop ==============

unsigned long lastWifiCheck = 0;

void loop() {
    // Check for UDP packets
    int packetSize = udp.parsePacket();
    if (packetSize > 0) {
        uint8_t buf[1024];
        int len = udp.read(buf, sizeof(buf));
        if (len > 0) {
            processPacket(buf, len);
        }
    }

    // Update LED
    updateLed();

    // Reconnect WiFi if lost (check every 10s)
    unsigned long now = millis();
    if (now - lastWifiCheck > 10000) {
        lastWifiCheck = now;
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("[WIFI] Connection lost, reconnecting...");
            WiFi.reconnect();
        }
    }

    // Small yield for ESP32 housekeeping
    yield();
}
