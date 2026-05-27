# Mimo Monitor - ESP32 Robot Head Firmware

ESP32 固件，用于将 AI Agent 运行状态通过机器人头部动作和 LED 眼睛可视化显示。

---

## 状态 → 动作映射

| 状态 | 头部动作 | 眼睛颜色 | 描述 |
|------|----------|----------|------|
| `thinking` | 歪头（偏左） | 🔵 蓝色呼吸 | 疑惑：嗯？让我想想... |
| `running` | 点头 | 🟢 绿色呼吸 | 干活中：好的好的 |
| `idle` | 左右慢摇 | 🟡 黄色 | 发呆：在呢在呢 |
| `waiting` | 快速摇头 | 🟠 橙色 | 催促：快回我呀 |
| `error` | 疯狂摇头 | 🔴 红色快闪 | 惊恐：出大事了！ |
| `stopped` | 低头 | ⚫ 熄灭 | 睡觉：zzZ... |

---

## 硬件清单

| 部件 | 型号 | 数量 | 价格 |
|------|------|------|------|
| 开发板 | ESP32-S3-DevKitC-N16R8 | 1 | ~¥32 |
| 舵机 | SG90 180度 | 2 | ~¥6 |
| 杜邦线 | 母对母 10cm | 若干 | ~¥4 |
| 头壳 | 3D打印 | 1 | ~¥15 |

---

## 接线

```
ESP32-S3 开发板            舵机
───────────────            ──────
GPIO 13  ────(橙线)────→  Yaw舵机（左右）信号线
GPIO 14  ────(橙线)────→  Pitch舵机（上下）信号线
5V       ────(红线)────→  两个舵机的红线（并联）
GND      ────(棕线)────→  两个舵机的棕线（并联）
GPIO 48  ─────────────→  NeoPixel LED（板载，无需接线）
```

### 接线图

```
         ┌─────────────────────┐
         │   ESP32-S3-DevKitC  │
         │                     │
         │  GPIO 13 ─────────────────── Servo Yaw (橙)
         │  GPIO 14 ─────────────────── Servo Pitch (橙)
         │  5V ──────────────────────── Servo 红线 (并联)
         │  GND ─────────────────────── Servo 棕线 (并联)
         │  GPIO 48 ─ NeoPixel (板载)  │
         │                     │
         │  [USB-C]            │
         └─────────────────────┘
```

---

## 机械结构

### 简易云台方案

```
        ┌──────────┐
        │   头壳   │  ← 3D打印，安装在Pitch舵机臂上
        │  ●    ●  │  ← LED眼睛
        └────┬─────┘
             │
        ┌────┴─────┐
        │ Pitch舵机 │  ← 控制上下点头
        └────┬─────┘
             │
        ┌────┴─────┐
        │ Yaw舵机  │  ← 控制左右转头
        └────┬─────┘
             │
        ┌────┴─────┐
        │   底座   │  ← 可以用亚克力/3D打印/木板
        └──────────┘
```

### 舵机安装

1. **Yaw舵机**：固定在底座上，输出轴朝上
2. **Yaw转接件**：装在Yaw舵机输出轴上，水平伸出
3. **Pitch舵机**：固定在Yaw转接件的另一端，输出轴朝前
4. **Pitch转接件**：装在Pitch舵机输出轴上，垂直伸出
5. **头壳**：固定在Pitch转接件上

---

## 编译烧录

```bash
# 1. 安装 PlatformIO CLI
pip install platformio

# 2. 进入固件目录
cd ~/mimo/firmware/esp32_udp

# 3. 修改 WiFi 配置
#    编辑 main.cpp 头部:
#    const char *WIFI_SSID = "你的WiFi名";
#    const char *WIFI_PASS = "你的WiFi密码";

# 4. 编译
pio run

# 5. 烧录（USB连接开发板）
pio run --target upload

# 6. 查看串口调试
pio device monitor
```

---

## 串口调试输出

正常启动后会看到：

```
=== Mimo Monitor - Robot Head v2 ===
[SERVO] Yaw on GPIO 13, Pitch on GPIO 14
[WIFI] Connecting to MyWiFi......
[WIFI] Connected! IP: 192.168.1.100
[UDP] Listening on port 9101
[STATE] THINKING | agent=claude-code tool=Read
[STATE] RUNNING | agent=claude-code tool=Bash
[STATE] IDLE | agent=claude-code tool=
```

---

## 自定义

### 调整舵机角度范围

编辑 `main.cpp` 中的常量：

```cpp
// Yaw（左右）角度范围
const int YAW_MIN = 0;
const int YAW_MAX = 180;
const int YAW_CENTER = 90;

// Pitch（上下）角度范围
const int PITCH_MIN = 45;
const int PITCH_MAX = 135;
const int PITCH_CENTER = 90;
```

### 调整动作幅度

```cpp
// 发呆时左右摇摆幅度
int swing = 25;  // 增大 = 摇得更厉害

// 干活时点头幅度
int nod = 15;
```

### 调整运动平滑度

```cpp
const int SERVO_SPEED = 15;  // 每帧最大移动角度
// 减小 → 动作更慢更平滑
// 增大 → 动作更快更生硬
```

---

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| 舵机抖动 | 供电不足 | 用外部5V电源给舵机供电 |
| 舵机不转 | 接线错误 | 检查信号线是否接对GPIO |
| 头往反方向转 | 舵机安装方向反了 | 修改 `YAW_MIN/MAX` 或物理翻转舵机 |
| 收不到UDP包 | WiFi连接失败 | 检查SSID/密码 |
| LED不亮 | GPIO引脚错误 | 确认是GPIO 48（S3板载） |

---

## 外部供电方案（可选）

如果舵机抖动严重，说明USB供电不足。用外部5V电源：

```
外部5V电源 ──┬── 5V ──→ 舵机红线
             └── GND ─→ 舵机棕线 ──┬── GND ──→ ESP32 GND
                                   │
ESP32 GPIO 13/14 ──(橙线)──→ 舵机信号线
```

> ⚠️ 外部电源和ESP32必须共地（GND连在一起）
