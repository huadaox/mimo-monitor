# Mimo Monitor - 详细架构计划

## 项目目标
监控 AI Coding Agent（Claude Code / Codex / Cursor）的实时运行状态，通过局域网/蓝牙传输到嵌入式设备（ESP32等），在物理世界用LED/屏幕/蜂鸣器显示agent状态。

## 架构概览

```
┌─────────────────┐     hooks/stream-json      ┌──────────────────┐
│  Claude Code    │ ──────────────────────────> │                  │
│  (多个实例)      │     psutil fallback         │   Mimo Monitor   │
└─────────────────┘                              │   (FastAPI)      │
                                                 │                  │
┌─────────────────┐     process detection        │   - 状态聚合      │
│  Codex/Cursor   │ ──────────────────────────> │   - session管理   │
│  OpenCode       │                              │   - 事件总线      │
└─────────────────┘                              └────────┬─────────┘
                                                          │
                                        ┌─────────────────┼─────────────────┐
                                        │                 │                 │
                                        ▼                 ▼                 ▼
                                  ┌──────────┐     ┌──────────┐     ┌──────────┐
                                  │ WebSocket │     │ UDP广播   │     │ BLE GATT │
                                  │ Dashboard │     │ :9101    │     │ Service  │
                                  │ :9100     │     │          │     │          │
                                  └──────────┘     └──────────┘     └──────────┘
                                        │                 │                 │
                                        ▼                 ▼                 ▼
                                  ┌──────────┐     ┌──────────┐     ┌──────────┐
                                  │ 浏览器    │     │ ESP32    │     │ ESP32    │
                                  │ Dashboard │     │ WiFi     │     │ BLE      │
                                  └──────────┘     └──────────┘     └──────────┘
```

## Phase 1: Claude Code 深度集成

### 1.1 Hooks 集成
Claude Code 支持在特定事件时执行命令。我们利用 `Stop` 和 `PostToolUse` hooks：

```json
// .claude/settings.json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "curl -s -X POST http://localhost:9100/api/hook -H 'Content-Type: application/json' -d '{\"event\":\"stop\",\"session_id\":\"$CLAUDE_SESSION_ID\",\"detail\":\"response complete\"}'"
      }]
    }],
    "PostToolUse": [{
      "hooks": [{
        "type": "command",
        "command": "curl -s -X POST http://localhost:9100/api/hook -H 'Content-Type: application/json' -d '{\"event\":\"tool_use\",\"tool\":\"$CLAUDE_TOOL_NAME\",\"session_id\":\"$CLAUDE_SESSION_ID\"}'"
      }]
    }],
    "PreToolUse": [{
      "hooks": [{
        "type": "command",
        "command": "curl -s -X POST http://localhost:9100/api/hook -H 'Content-Type: application/json' -d '{\"event\":\"tool_start\",\"tool\":\"$CLAUDE_TOOL_NAME\",\"session_id\":\"$CLAUDE_SESSION_ID\"}'"
      }]
    }]
  }
}
```

### 1.2 Session 追踪
- 每个 Claude Code 实例有唯一 session_id
- 通过 psutil 检测进程 + hooks 接收事件 → 关联到具体 session
- 状态机：idle → thinking → tool_use → responding → idle

### 1.3 增强状态模型
```python
class AgentSession(BaseModel):
    session_id: str
    agent_type: str  # "claude-code" | "codex" | "cursor" | "opencode"
    pid: int | None
    status: AgentStatus  # idle|thinking|tool_use|responding|error|stopped
    current_tool: str | None  # 当前使用的工具名
    current_task: str | None  # 当前任务描述
    tokens_used: int
    tokens_limit: int
    uptime_seconds: float
    last_activity: float
    detail: str
```

## Phase 2: 传输层

### 2.1 LAN 传输 (UDP广播)
- 端口 9101，JSON格式广播
- 每2秒广播一次当前状态
- ESP32只需监听UDP端口即可接收
- 支持单播回复（设备注册后定向推送）

### 2.2 BLE GATT Service
- Service UUID: `0x1820` (自定义)
- Characteristics:
  - Status (Read/Notify): 当前所有agent状态
  - Command (Write): 设备->服务器的控制命令
- 依赖 `bleak` 库（Python BLE）

### 2.3 嵌入式设备协议
```json
{
  "v": 1,                    // 协议版本
  "ts": 1716800000,          // 时间戳
  "agents": [
    {
      "id": "claude-1",
      "type": "claude-code",
      "status": "thinking",   // idle|thinking|tool_use|responding|error|stopped
      "tool": "Read",         // 当前工具（可选）
      "task": "分析auth.py",  // 任务描述（可选）
      "tokens": 12500,        // 已用token
      "uptime": 3600          // 运行时长(秒)
    }
  ],
  "cmd": null                 // 控制命令（服务器->设备）
}
```

## Phase 3: Dashboard 增强
- 多session卡片并列显示
- 实时token消耗图表
- 事件时间线
- 设备连接管理（显示已连接的ESP32）

## 实现任务分解

### Task A: 核心重构 (models + detectors + api)
- 重构 models.py 支持多session
- 重构 detectors.py 增加session关联
- 新增 hooks API 端点
- 新增 session 管理器

### Task B: Claude Code hooks集成
- 创建 hooks 配置脚本
- 实现 hook 事件处理
- session_id 关联逻辑

### Task C: 传输层实现
- UDP广播服务
- BLE GATT服务
- 设备注册/心跳协议

### Task D: 嵌入式设备固件
- ESP32 Arduino/PlatformIO 固件
- WiFi UDP接收
- BLE接收
- LED/屏幕状态显示

### Task E: Dashboard重构
- 多session UI
- 事件时间线
- 设备管理面板

## 目录结构

```
~/mimo/
├── PLAN.md                  # 本文件
├── main.py                  # 入口
├── mimo_monitor/
│   ├── __init__.py
│   ├── models.py            # 数据模型
│   ├── detectors.py         # 进程检测
│   ├── session_manager.py   # Session管理器
│   ├── api.py               # FastAPI (REST + WS + Hooks)
│   ├── transmitters/
│   │   ├── __init__.py
│   │   ├── udp.py           # UDP广播
│   │   └── ble.py           # BLE GATT
│   └── static/
│       └── dashboard.html   # Web Dashboard
├── firmware/
│   ├── esp32_udp/           # ESP32 UDP固件
│   │   └── main.cpp
│   └── esp32_ble/           # ESP32 BLE固件
│       └── main.cpp
├── hooks_setup.py           # Claude Code hooks配置脚本
├── test_client.py
└── requirements.txt
```
