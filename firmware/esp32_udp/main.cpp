/*
 * Mimo Monitor - ESP32 WiFi UDP Firmware (v2 - Servo Robot Head)
 *
 * Listens for UDP broadcasts on port 9101 from the Mimo Monitor server.
 * Controls:
 *   - 2x SG90 servo motors (yaw=左右, pitch=上下) for head movement
 *   - NeoPixel LED for eyes
 *
 * Protocol (JSON over UDP):
 *   {"v":1,"ts":...,"agents":[{"id":"...","status":"...","tool":"..."}]}
 *
 * Status -> Head behavior:
 *   thinking  = 偏头(疑惑) + 蓝色眼睛
 *   running   = 点头(干活) + 绿色呼吸眼
 *   idle      = 左右慢摇(发呆) + 黄色眼睛
 *   waiting   = 快速摇头(催促) + 橙色眼睛
 *   error     = 疯狂摇头 + 红色快闪眼
 *   stopped   = 低头(睡觉) + 眼睛熄灭
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <ESP32Servo.h>

// ============== Configuration ==============
// WiFi - EDIT THESE BEFORE FLASHING!
const char *WIFI_SSID = "YOUR_WIFI_SSID";
const char *WIFI_PASS = "YOUR_WIFI_PASSWORD";

// Network
const uint16_t UDP_PORT = 9101;

// LED (eyes)
const uint8_t LED_PIN = 48;       // Built-in NeoPixel on ESP32-S3
const uint8_t NUM_PIXELS = 1;
const bool USE_NEOPIXEL = true;

// Servos
const uint8_t YAW_PIN = 13;      // 左右转头
const uint8_t PITCH_PIN = 14;    // 上下点头
const int SERVO_SPEED = 15;      // 每循环移动的最大角度（越小越平滑）

// Servo angle limits (adjust based on your physical build)
const int YAW_MIN = 0;
const int YAW_MAX = 180;
const int YAW_CENTER = 90;

const int PITCH_MIN = 45;
const int PITCH_MAX = 135;
const int PITCH_CENTER = 90;

// ============== Globals ==============
WiFiUDP udp;
Adafruit_NeoPixel strip(NUM_PIXELS, LED_PIN, NEO_GRB + NEO_KHZ800);

Servo yawServo;
Servo pitchServo;

// Current & target positions
int yawCurrent = YAW_CENTER;
int pitchCurrent = PITCH_CENTER;
int yawTarget = YAW_CENTER;
int pitchTarget = PITCH_CENTER;

// Animation state
unsigned long lastAnimUpdate = 0;
int animPhase = 0;
unsigned long animStepTime = 0;

// Agent state
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
    }
}

void ledOff() {
    setPixelColor(0, 0, 0);
}

uint8_t breathe(unsigned long ms, uint16_t periodMs = 2000) {
    float phase = (float)(ms % periodMs) / periodMs * 2.0 * PI;
    return (uint8_t)((sinf(phase - PI / 2.0) + 1.0) / 2.0 * 255);
}

// ============== Servo Helpers ==============

void moveServos() {
    unsigned long now = millis();
    if (now - lastAnimUpdate < 20) return;  // 50fps
    lastAnimUpdate = now;

    // Smooth movement: move towards target by max SERVO_SPEED
    int dy = yawTarget - yawCurrent;
    int dp = pitchTarget - pitchCurrent;

    if (abs(dy) > SERVO_SPEED) yawCurrent += (dy > 0) ? SERVO_SPEED : -SERVO_SPEED;
    else yawCurrent = yawTarget;

    if (abs(dp) > SERVO_SPEED) pitchCurrent += (dp > 0) ? SERVO_SPEED : -SERVO_SPEED;
    else pitchCurrent = pitchTarget;

    yawServo.write(yawCurrent);
    pitchServo.write(pitchCurrent);
}

// ============== Animations ==============

// 每个状态有不同的头部动画模式
void updateAnimation() {
    unsigned long now = millis();

    // Check stale
    if (lastPacketTime > 0 && (now - lastPacketTime > STALE_TIMEOUT)) {
        currentState = STATE_STOPPED;
    }

    switch (currentState) {
        case STATE_STOPPED: {
            // 低头睡觉
            yawTarget = YAW_CENTER;
            pitchTarget = PITCH_MIN + 10;
            ledOff();
            break;
        }

        case STATE_IDLE: {
            // 左右慢摇发呆
            int swing = 25;
            float phase = (float)(now % 4000) / 4000.0 * 2.0 * PI;
            yawTarget = YAW_CENTER + (int)(sinf(phase) * swing);
            pitchTarget = PITCH_CENTER;
            setPixelColor(255, 193, 7);  // 黄色
            break;
        }

        case STATE_RUNNING: {
            // 点头干活
            int nod = 15;
            float phase = (float)(now % 1200) / 1200.0 * 2.0 * PI;
            yawTarget = YAW_CENTER;
            pitchTarget = PITCH_CENTER + (int)(sinf(phase) * nod);
            uint8_t b = breathe(now, 2000);
            setPixelColor(0, b, 0);  // 绿色呼吸
            break;
        }

        case STATE_THINKING: {
            // 歪头疑惑 (偏左)
            yawTarget = YAW_CENTER - 20;
            pitchTarget = PITCH_CENTER + 10;
            // 蓝色眼睛缓慢呼吸
            uint8_t b = breathe(now, 3000);
            setPixelColor(0, 0, b);
            break;
        }

        case STATE_WAITING: {
            // 快速摇头催促
            int shake = 20;
            float phase = (float)(now % 400) / 400.0 * 2.0 * PI;
            yawTarget = YAW_CENTER + (int)(sinf(phase) * shake);
            pitchTarget = PITCH_CENTER;
            setPixelColor(255, 140, 0);  // 橙色
            break;
        }

        case STATE_ERROR: {
            // 疯狂摇头
            int shake = 30;
            float phase = (float)(now % 200) / 200.0 * 2.0 * PI;
            yawTarget = YAW_CENTER + (int)(sinf(phase) * shake);
            pitchTarget = PITCH_CENTER - 10;  // 微微抬头（惊恐）
            // 红色快闪
            bool on = (now / 150) % 2 == 0;
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

// ============== UDP Packet Processing ==============

void processPacket(const uint8_t *data, size_t len) {
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
    lastPacketTime = millis();

    Serial.printf("[STATE] %s | agent=%s tool=%s\n",
                  stateToString(currentState),
                  currentAgentId.c_str(),
                  currentTool.c_str());
}

// ============== Setup ==============

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n=== Mimo Monitor - Robot Head v2 ===");

    // LED setup
    if (USE_NEOPIXEL) {
        strip.begin();
        strip.setBrightness(40);
        strip.show();
    }

    // Servo setup
    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);
    yawServo.setPeriodHertz(50);
    pitchServo.setPeriodHertz(50);
    yawServo.attach(YAW_PIN, 500, 2400);
    pitchServo.attach(PITCH_PIN, 500, 2400);

    // Initial position: center
    yawServo.write(YAW_CENTER);
    pitchServo.write(PITCH_CENTER);
    yawCurrent = YAW_CENTER;
    pitchCurrent = PITCH_CENTER;

    Serial.printf("[SERVO] Yaw on GPIO %d, Pitch on GPIO %d\n", YAW_PIN, PITCH_PIN);

    // WiFi connect
    Serial.printf("[WIFI] Connecting to %s", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(500);
        Serial.print(".");
        attempts++;
        // Blink while connecting
        if (attempts % 2 == 0) setPixelColor(0, 0, 50);
        else ledOff();
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WIFI] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
        Serial.printf("[UDP] Listening on port %d\n", UDP_PORT);
        udp.begin(UDP_PORT);
        // Happy boot animation: nod once
        yawServo.write(YAW_CENTER - 20);
        delay(200);
        yawServo.write(YAW_CENTER + 20);
        delay(200);
        yawServo.write(YAW_CENTER);
        setPixelColor(0, 255, 0);
        delay(500);
    } else {
        Serial.println("\n[WIFI] Connection failed! Running in offline mode.");
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

    // Update animation & move servos
    updateAnimation();
    moveServos();

    // Reconnect WiFi if lost
    unsigned long now = millis();
    if (now - lastWifiCheck > 10000) {
        lastWifiCheck = now;
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("[WIFI] Connection lost, reconnecting...");
            WiFi.reconnect();
        }
    }

    yield();
}
