"""
Mimo Monitor - 系统托盘状态指示器

在系统托盘显示 AI Agent 当前状态，图标颜色随状态变化。
支持 Windows / macOS / Linux。

依赖：pip install pystray pillow requests
"""

import sys
import time
import threading
import requests
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem, Icon

# ============== 配置 ==============
MIMO_API = "http://localhost:9100/api/status"
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
            return {"status": "stopped", "tool": "", "detail": ""}

        # 取最高优先级
        priority = {"error": 5, "thinking": 4, "running": 3, "waiting": 2, "idle": 1, "stopped": 0}
        best = max(tools, key=lambda t: priority.get(t.get("status", "stopped"), 0))
        return best
    except Exception:
        return {"status": "stopped", "tool": "", "detail": "无法连接服务器"}


class MimoTray:
    def __init__(self):
        self.icon = None
        self.current_status = "stopped"
        self.running = True

    def create_icon(self):
        """创建托盘图标"""
        img = create_icon_image(STATUS_COLORS["stopped"])
        menu = Menu(
            MenuItem("打开 Dashboard", self.open_dashboard),
            MenuItem("刷新状态", self.refresh),
            MenuItem("退出", self.quit),
        )
        self.icon = Icon("MimoMonitor", img, "Mimo Monitor: 初始化中...", menu)

    def update_icon(self, status_data: dict):
        """更新图标状态"""
        status = status_data.get("status", "stopped")
        tool = status_data.get("name", "")
        detail = status_data.get("detail", "")

        if status == self.current_status:
            return

        self.current_status = status
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
        import webbrowser
        webbrowser.open("http://localhost:9100")

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
    tray = MimoTray()
    tray.run()


if __name__ == "__main__":
    main()
