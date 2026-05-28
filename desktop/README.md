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

## 安装

```bash
cd ~/mimo/desktop
pip install -r requirements.txt
```

## 运行

```bash
# 先启动 mimo monitor 服务器
cd ~/mimo && python main.py &

# 再启动托盘
python desktop/tray.py
```

## 功能

- ✅ 托盘图标颜色随状态变化
- ✅ 鼠标悬停显示详细状态
- ✅ 右键菜单：打开 Dashboard / 刷新 / 退出
- ✅ 每 2 秒自动轮询
- ✅ 服务器离线时显示灰色

## 开机自启

### Windows
1. 按 `Win+R`，输入 `shell:startup`
2. 创建快捷方式：`pythonw C:\path\to\mimo\desktop\tray.py`

### macOS
创建 `~/Library/LaunchAgents/com.mimo.tray.plist`

### Linux
创建 `~/.config/systemd/user/mimo-tray.service`
