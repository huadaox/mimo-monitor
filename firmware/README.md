# Mimo Monitor - ESP32 Firmware

ESP32 固件，用于将 AI Agent 运行状态通过 LED 可视化显示。
提供两种连接方案：**WiFi UDP** 和 **BLE（蓝牙低功耗）**。

---

## 状态 → LED 颜色映射

| 状态 | LED 效果 | 颜色 |
|------|----------|------|
| `thinking` | 蓝色闪烁（500ms） | 🔵 Blue |
| `running` | 绿色呼吸灯 | 🟢 Green |
| `idle` | 黄色常亮 | 🟡 Yellow |
| `waiting` | 橙色慢闪 | 🟠 Orange |
| `error` | 红色快闪（200ms） | 🔴 Red |
| `stopped` | 熄灭 | ⚫ Off |

---

## 方案一：WiFi UDP（推荐）

### 原理
Mimo Monitor 服务器每2秒在 UDP 端口 9101 广播状态 JSON，ESP32 监听并解析。

### 接线

```
ESP32 开发板        NeoPixel LED
─────────────       ─────────────
GPIO 48  ─────────→  DIN
3.3V     ─────────→  VCC
GND      ─────────→  GND
```

> 📝 如果使用 ESP32-S3 开发板（如 ESP32-S3-DevKitC），GPIO 48 通常是板载 NeoPixel 的引脚，无需外接 LED。
> 对于普通 LED：GPIO 2 → LED 正极 → 220Ω 电阻 → GND

### 编译烧录

```bash
# 1. 安装 PlatformIO CLI (如果没有)
pip install platformio

# 2. 进入固件目录
cd ~/mimo/firmware/esp32_udp

# 3. 修改 WiFi 配置（编辑 main.cpp 头部）
#    const char *WIFI_SSID = "YOUR_WIFI_SSID";
#    const char *WIFI_PASS = "YOUR_WIFI_PASSWORD";

# 4. 编译
pio run

# 5. 烧录（连接 USB）
pio run --target upload

# 6. 查看串口调试输出
pio device monitor
```

### 平台IO 配置
- 板子：`esp32dev`（通用 ESP32）
- 依赖库：ArduinoJson v7+, Adafruit NeoPixel
- 端口：UDP 9101

---

## 方案二：BLE（蓝牙低功耗）

### 原理
ESP32 扫描局域网 BLE 设备，找到 Mimo Monitor 的 GATT Service（UUID 0x1820），订阅 Status 特征（UUID 0x2B01）的 Notify。

### 接线
与 UDP 方案完全相同（LED 接线不变）。

### 编译烧录

```bash
# 1. 进入固件目录
cd ~/mimo/firmware/esp32_ble

# 2. 编译
pio run

# 3. 烧录
pio run --target upload

# 4. 查看串口调试输出
pio device monitor
```

### 平台IO 配置
- 依赖库：ArduinoJson v7+, Adafruit NeoPixel, NimBLE-Arduino
- BLE UUID：
  - Service: `0x1820`
  - Status Char: `0x2B01`（Read + Notify）

---

## 选择哪种方案？

| 特性 | WiFi UDP | BLE |
|------|----------|-----|
| 范围 | 同一局域网（~50m） | ~10-30m |
| 延迟 | ~2秒（广播间隔） | 即时（Notify） |
| 配置 | 需要 WiFi 密码 | 零配置（自动扫描） |
| 功耗 | 较高 | 低 |
| 多设备 | 天然支持（广播） | 每个设备独立连接 |
| 穿墙 | 好 | 差 |

**建议**：如果设备固定在桌面使用，选 WiFi UDP（稳定可靠）。
如果需要便携或多个独立小灯，选 BLE。

---

## 自定义

### 更换 LED 引脚
编辑 `main.cpp` 中的：
```cpp
const uint8_t LED_PIN = 48;       // 改为你的引脚
const bool USE_NEOPIXEL = true;   // false = 普通LED
```

### 使用普通 LED（非 NeoPixel）
```cpp
const bool USE_NEOPIXEL = false;
const uint8_t PLAIN_LED_PIN = 2;  // GPIO 2（大多数板载LED）
```

### 多个 NeoPixel
```cpp
const uint8_t NUM_PIXELS = 8;     // LED 灯带数量
```

---

## 故障排查

1. **WiFi 连接失败**：检查 SSID/密码，确认 ESP32 在路由器信号范围内
2. **收不到 UDP 包**：确认 Mimo Monitor 服务器已启动 UDP 广播功能
3. **BLE 扫描不到**：确认服务器端 BLE GATT 服务已启用，距离不超过 10m
4. **LED 不亮**：检查接线，确认 GPIO 引脚正确
5. **串口无输出**：确认 `monitor_speed = 115200`

---

## 协议格式

服务器发送的 JSON 格式：

```json
{
  "v": 1,
  "ts": 1716800000,
  "agents": [
    {
      "id": "claude-1",
      "type": "claude-code",
      "status": "thinking",
      "tool": "Read",
      "task": "分析 auth.py",
      "tokens": 12500,
      "uptime": 3600
    }
  ]
}
```

ESP32 优先显示最高优先级状态（error > thinking > running > waiting > idle > stopped）。
