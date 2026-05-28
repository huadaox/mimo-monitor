# Mimo Monitor - 系统托盘

在系统托盘显示 AI Agent 当前状态，图标颜色随状态变化。

## 状态颜色

| 状态 | 颜色 | 含义 |
|------|------|------|
| 🔵 蓝色 | thinking | AI 思考中 |
| 🟢 绿色 | running | 运行中 |
| 🟡 黄色 | idle | 空闲 |
| 🟠 橙色 | waiting | 等待用户 |
| 🔴 红色 | error | 出错 |
| ⚫ 灰色 | stopped | 离线 |

---

## Windows 使用（推荐）

Agent 跑在 WSL，托盘跑在 Windows，通过 API 连接。

### 方法 1：直接运行

```powershell
# 安装依赖
pip install pystray Pillow requests

# 运行
python tray_windows.py
```

### 方法 2：打包成 exe

```powershell
# 一键打包
build.bat

# 生成 dist/MimoMonitor.exe，双击运行
```

### 网络配置

默认连接 `http://localhost:9100`，如果连不上，设置环境变量：

```powershell
# 用 WSL IP（在 WSL 中运行 hostname -I 获取）
set MIMO_API=http://172.28.86.168:9100/api/status
set DASHBOARD_URL=http://172.28.86.168:9100

python tray_windows.py
```

---

## WSL / Linux / macOS 使用

```bash
# 安装依赖
pip install pystray Pillow requests

# 运行（需要 GUI 环境）
python tray.py
```

---

## 功能

- ✅ 托盘图标颜色随状态变化
- ✅ 鼠标悬停显示详细状态信息
- ✅ 左键双击打开 Dashboard
- ✅ 右键菜单：刷新 / 退出
- ✅ 每 2 秒自动轮询
- ✅ 服务器离线时显示灰色
- ✅ 支持自定义 API 地址

---

## 开机自启

### Windows

1. 按 `Win+R`，输入 `shell:startup`
2. 把 `MimoMonitor.exe` 快捷方式放进去

或创建 VBS 脚本静默启动：

```vbs
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "C:\path\to\MimoMonitor.exe", 0, False
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MIMO_API` | `http://localhost:9100/api/status` | API 地址 |
| `DASHBOARD_URL` | `http://localhost:9100` | Dashboard 地址 |
