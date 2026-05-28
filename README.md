# Mimo Monitor

AI 编程助手物理状态监控工具。实时监控 Claude Code / OpenCode / Codex / Cursor 的运行状态，通过 ESP32 驱动一个可爱的小机器人头部，用动作和眼神表达 AI 的当前状态。

## 工具支持

| 工具 | 插件（精确状态） | 进程检测（回退） | 状态精度 |
|------|:---:|:---:|------|
| **Claude Code** | ✅ `claude_code.sh` | ✅ | working / waiting / idle / stopped |
| **Codex** | ✅ `codex.sh` | ✅ | working / idle / stopped（无细粒度 hook） |
| **OpenCode** | ✅ `opencode.ts` | ✅ | working / waiting / idle / stopped |
| **Cursor** | ❌ 无插件 | ✅ | idle / stopped（仅进程检测） |

插件通过写 `~/.agent-state/{tool}.json` 上报状态，进程检测作为回退。没有插件的工具只能检测进程是否存在。

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![ESP32](https://img.shields.io/badge/ESP32-S3-orange)

## 架构

```
┌─────────────────────────────────────────────┐
│  Claude Code / OpenCode / Codex / Cursor    │
│  插件写入 ~/.agent-state/{tool}.json        │
└──────────────┬──────────────────────────────┘
               │ 文件系统 (原子写入)
               ▼
┌─────────────────────────────────────────────┐
│  Mimo Monitor Server (Python/FastAPI)       │
│  - watcher 监控状态目录                      │
│  - 进程检测回退                              │
│  - UDP 广播 (每2秒)                          │
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

## 核心设计：通用状态文件协议

所有工具的插件通过写文件上报状态，服务端通过读文件获取状态。

```
~/.agent-state/{tool}.json
```

```json
{"state":"working","detail":"Tool: Bash","ts":1716800000.123}
```

**优势**：
- 零依赖：插件只需 `echo` + `mv`，不需要 curl/python/node
- 可靠：文件系统是操作系统级的，不依赖网络
- 通用：任何工具都能用一行 shell 写状态
- 原子写入：rename 是原子操作，不会读到半写状态
- 可调试：`cat ~/.agent-state/*.json` 直接看状态

## 状态定义

| 状态 | 含义 | 硬件动作 |
|------|------|----------|
| `working` | 工具正在执行 | 点头，绿灯 |
| `waiting` | 等待用户 | 快摇头，橙灯 |
| `idle` | 空闲 | 慢摇，黄灯 |
| `stopped` | 离线 | 低头，灭灯 |

## 快速开始

### 1. 安装插件

```bash
# 安装所有插件
bash mimo_monitor/plugins/install.sh

# 或单独安装
bash mimo_monitor/plugins/install.sh claude-code
bash mimo_monitor/plugins/install.sh codex
bash mimo_monitor/plugins/install.sh opencode
```

### 2. 启动服务器

```bash
cd ~/mimo
.venv/bin/python main.py
```

### 3. 验证

```bash
# 直接查看状态文件
cat ~/.agent-state/*.json

# API
curl http://localhost:9100/api/status

# Dashboard
open http://localhost:9100/
```

## 添加新工具支持

只需要做一件事：让工具写状态文件。

```bash
# 最简实现（一行 shell）
mkdir -p ~/.agent-state
echo '{"state":"working","detail":"...","ts":'$(date +%s)'}' > ~/.agent-state/my-tool.json
```

然后在 `detectors.py` 的 `scan_tools()` 里加上新工具的进程检测即可。

### 待贡献：Cursor 插件

Cursor 目前只有进程检测，无法获取精确状态。如果 Cursor 支持类似的 hook/extension 机制，欢迎贡献插件。

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取所有工具状态 |
| `/api/status/{name}` | GET | 获取单个工具状态 |
| `/api/hook` | POST | 接收 Hook 事件（向后兼容） |
| `/api/log` | GET | 事件日志 |
| `/api/health` | GET | 健康检查 |
| `/ws` | WebSocket | 实时状态推送 |

## 项目结构

```
mimo/
├── main.py                          # 服务器入口
├── mimo_monitor/
│   ├── protocol.py                  # 状态文件协议（核心）
│   ├── watcher.py                   # 文件系统监控
│   ├── models.py                    # 数据模型
│   ├── api.py                       # FastAPI 服务
│   ├── detectors.py                 # 进程检测（回退）
│   ├── plugins/                     # 各工具插件
│   │   ├── claude_code.sh           # Claude Code hook
│   │   ├── codex.sh                 # Codex wrapper
│   │   ├── opencode.ts              # OpenCode 插件
│   │   └── install.sh               # 统一安装
│   └── transmitters/
│       ├── udp.py                   # UDP 广播
│       └── ble.py                   # BLE GATT
├── firmware/
│   └── esp32_udp/                   # ESP32 固件
└── static/
    └── dashboard.html               # Web 仪表盘
```

## License

MIT
