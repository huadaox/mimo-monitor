# Mimo Monitor

AI 编程助手物理状态监控工具。实时监控 Claude Code / OpenCode / Codex 的运行状态，通过 ESP32 驱动一个可爱的小机器人头部，用动作和眼神表达 AI 的当前状态。

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![ESP32](https://img.shields.io/badge/ESP32-S3-orange)

## 效果预览

```
AI在思考         AI在干活         AI在等你         AI出错了
   ╭──╮           ╭──╮           ╭──╮           ╭──╮
   │🔵│ ←歪头    │🟢│ ←点头    │🟠│ ←摇头    │🔴│ ←疯狂摇头
   ╰──╯           ╰──╯           ╰──╯           ╰──╯
  "嗯？"         "好的好的"      "快回我呀"      "啊啊啊！"
```

## 架构

```
┌─────────────────────────────────────────────┐
│  Claude Code / OpenCode / Codex             │
│  (Hook → HTTP POST)                         │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Mimo Monitor Server (Python/FastAPI)       │
│  - 接收 Hook 事件                           │
│  - 状态合并 & 优先级排序                     │
│  - UDP 广播 (每2秒)                         │
│  - BLE GATT 服务                            │
│  - Web Dashboard                            │
└──────────────┬──────────────────────────────┘
               │ UDP :9101
               ▼
┌─────────────────────────────────────────────┐
│  ESP32-S3 机器人头                          │
│  - 2x SG90 舵机 (yaw/pitch)                │
│  - NeoPixel LED 眼睛                        │
│  - 状态→动作映射                            │
└─────────────────────────────────────────────┘
```

## 快速开始

### 1. 启动服务器

```bash
cd ~/mimo
pip install -r requirements.txt
python main.py
```

服务器启动后：
- API: http://localhost:9100
- Dashboard: http://localhost:9100/
- UDP 广播: 端口 9101

### 2. 安装 Hooks

```bash
# Claude Code
bash mimo_monitor/hooks/claude_code/setup.sh

# OpenCode
bash mimo_monitor/hooks/opencode/setup.sh

# Codex
bash mimo_monitor/hooks/codex/setup.sh

# 全部安装
bash mimo_monitor/hooks/install.sh --all
```

### 3. 烧录 ESP32 固件

```bash
cd firmware/esp32_udp

# 修改 WiFi 配置
vim main.cpp  # 编辑 WIFI_SSID 和 WIFI_PASS

# 编译烧录
pio run --target upload
```

## 状态映射

| 状态 | 触发条件 | 头部动作 | 眼睛 |
|------|----------|----------|------|
| `thinking` | AI 开始处理 | 歪头 | 🔵 蓝 |
| `running` | 工具执行中 | 点头 | 🟢 绿 |
| `idle` | 等待输入 | 慢摇 | 🟡 黄 |
| `waiting` | 等待用户确认 | 快摇头 | 🟠 橙 |
| `error` | 出错 | 疯狂摇头 | 🔴 红 |
| `stopped` | 离线 | 低头 | ⚫ 灭 |

## API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取所有工具状态 |
| `/api/status/{name}` | GET | 获取单个工具状态 |
| `/api/hook` | POST | 接收 Hook 事件 |
| `/api/hook/log` | GET | Hook 事件日志 |
| `/api/health` | GET | 健康检查 |
| `/ws` | WebSocket | 实时状态推送 |

## 硬件清单

| 部件 | 型号 | 价格 |
|------|------|------|
| 开发板 | ESP32-S3-DevKitC-N16R8 | ~¥32 |
| 舵机 | SG90 180度 ×2 | ~¥6 |
| 杜邦线 | 母对母 10cm | ~¥4 |
| 头壳 | 3D打印 | ~¥15 |

**总成本：~¥57**

## 项目结构

```
mimo/
├── main.py                          # 服务器入口
├── mimo_monitor/
│   ├── api.py                       # FastAPI 服务
│   ├── models.py                    # 数据模型
│   ├── detectors.py                 # 进程检测
│   ├── hooks/
│   │   ├── claude_code/             # Claude Code hooks
│   │   ├── opencode/                # OpenCode 插件
│   │   ├── codex/                   # Codex wrapper
│   │   └── install.sh               # 统一安装脚本
│   └── transmitters/
│       ├── udp.py                   # UDP 广播
│       └── ble.py                   # BLE GATT
├── firmware/
│   ├── esp32_udp/                   # ESP32 WiFi 固件
│   │   ├── main.cpp                 # 主程序
│   │   └── platformio.ini           # PlatformIO 配置
│   └── README.md                    # 固件文档
└── static/
    └── dashboard.html               # Web 仪表盘
```

## License

MIT
