"""
Mimo Monitor - Windows 系统托盘

在 Windows 系统托盘显示 AI Agent 状态。
连接 WSL 中运行的 mimo monitor 服务器。

使用方法：
  1. 先在 WSL 启动服务器：cd ~/mimo && python main.py
  2. 在 Windows 运行：python tray.py
  3. 或打包成 exe：pyinstaller --onefile --windowed tray.py
"""

import sys
import os
import time
import threading
import webbrowser
from pathlib import Path

# 尝试导入，失败则提示安装
try:
    import requests
    from PIL import Image, ImageDraw
    import pystray
    from pystray import MenuItem, Icon
except ImportError:
    print("请先安装依赖：pip install pystray Pillow requests")
    input("按回车退出...")
    sys.exit(1)


# ============== 配置 ==============
# WSL 中的 mimo monitor 地址
# 方案1: localhost (WSL2 默认支持)
# 方案2: WSL IP (如果 localhost 不行)
MIMO_API = os.environ.get("MIMO_API", "http://localhost:9100/api/status")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:9100")
POLL_INTERVAL = 2  # 秒


# 状态颜色映射
STATUS_COLORS = {
    "thinking": (0, 120, 255),    # 蓝
    "running": (0, 200, 80),      # 绿
    "idle": (255, 193, 7),        # 黄
    "waiting": (255, 140, 0),     # 橙
    "error": (255, 0, 0),         # 红
    "stopped": (128, 128, 128),   # 灰
}

# 状态中文名
STATUS_NAMES = {
    "thinking": "思考中",
    "running": "运行中",
    "idle": "空闲",
    "waiting": "等待中",
    "error": "出错了",
    "stopped": "已停止",
}

# 状态图标符号
STATUS_ICONS = {
    "thinking": "💡",
    "running": "⚡",
    "idle": "😴",
    "waiting": "⏳",
    "error": "❌",
    "stopped": "⚫",
}


def create_icon_image(color: tuple, size: int = 64) -> Image.Image:
    """创建圆形托盘图标"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 外圈
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color + (255,),
        outline=(255, 255, 255, 100),
        width=2,
    )

    # 内圈高光
    highlight_margin = 12
    draw.ellipse(
        [highlight_margin, highlight_margin, size // 2, size // 2],
        fill=(255, 255, 255, 60),
    )

    return img


def get_status() -> dict:
    """从 mimo monitor 获取状态"""
    try:
        resp = requests.get(MIMO_API, timeout=3)
        tools = resp.json()
        if not tools:
            return {"status": "stopped", "name": "", "detail": ""}

        # 取最高优先级
        priority = {"error": 5, "thinking": 4, "running": 3, "waiting": 2, "idle": 1, "stopped": 0}
        best = max(tools, key=lambda t: priority.get(t.get("status", "stopped"), 0))
        return best
    except requests.exceptions.ConnectionError:
        return {"status": "stopped", "name": "", "detail": "无法连接服务器"}
    except Exception as e:
        return {"status": "stopped", "name": "", "detail": str(e)}


class MimoTray:
    def __init__(self):
        self.icon = None
        self.current_status = "stopped"
        self.running = True

    def create_icon(self):
        """创建托盘图标"""
        img = create_icon_image(STATUS_COLORS["stopped"])
        menu = pystray.Menu(
            MenuItem("打开 Dashboard", self.open_dashboard, default=True),
            MenuItem("刷新状态", self.refresh),
            pystray.Menu.SEPARATOR,
            MenuItem("API 地址: " + MIMO_API, None, enabled=False),
            pystray.Menu.SEPARATOR,
            MenuItem("退出", self.quit),
        )
        self.icon = Icon("MimoMonitor", img, "Mimo Monitor: 初始化中...", menu)

    def update_icon(self, status_data: dict):
        """更新图标状态"""
        status = status_data.get("status", "stopped")
        tool = status_data.get("name", "")
        detail = status_data.get("detail", "")

        # 状态没变就不更新
        if status == self.current_status and tool == getattr(self, '_last_tool', ''):
            return

        self.current_status = status
        self._last_tool = tool
        color = STATUS_COLORS.get(status, STATUS_COLORS["stopped"])
        img = create_icon_image(color)

        # 构建提示文字
        status_name = STATUS_NAMES.get(status, status)
        icon_symbol = STATUS_ICONS.get(status, "")
        tooltip = f"{icon_symbol} Mimo Monitor\n状态: {status_name}"
        if tool:
            tooltip += f"\n工具: {tool}"
        if detail:
            tooltip += f"\n{detail}"

        self.icon.icon = img
        self.icon.title = tooltip

    def poll_loop(self):
        """轮询状态更新"""
        while self.running:
            try:
                status_data = get_status()
                self.update_icon(status_data)
            except Exception:
                pass
            time.sleep(POLL_INTERVAL)

    def open_dashboard(self, icon, item):
        """打开 Web Dashboard"""
        webbrowser.open(DASHBOARD_URL)

    def refresh(self, icon, item):
        """手动刷新"""
        status_data = get_status()
        self.update_icon(status_data)

    def quit(self, icon, item):
        """退出"""
        self.running = False
        icon.stop()

    def run(self):
        """运行"""
        self.create_icon()

        # 启动轮询线程
        poll_thread = threading.Thread(target=self.poll_loop, daemon=True)
        poll_thread.start()

        # 运行托盘（阻塞）
        self.icon.run()


def main():
    print("=" * 50)
    print("Mimo Monitor - Windows 托盘")
    print("=" * 50)
    print(f"API 地址: {MIMO_API}")
    print(f"Dashboard: {DASHBOARD_URL}")
    print("=" * 50)
    print()
    print("提示：")
    print("  - 确保 WSL 中的 mimo monitor 已启动")
    print("  - 鼠标悬停查看状态")
    print("  - 左键双击打开 Dashboard")
    print("  - 右键查看菜单")
    print()

    # 测试连接
    print("正在连接服务器...", end=" ")
    try:
        resp = requests.get(MIMO_API, timeout=5)
        print(f"✅ 成功 (状态码: {resp.status_code})")
    except Exception as e:
        print(f"❌ 失败: {e}")
        print()
        print("请确保：")
        print("  1. WSL 中已启动 mimo monitor: cd ~/mimo && python main.py")
        print("  2. 服务器监听在 0.0.0.0:9100")
        print()
        input("按回车继续尝试运行（托盘会持续重试连接）...")

    print()
    print("启动托盘图标...")

    tray = MimoTray()
    tray.run()


if __name__ == "__main__":
    main()
