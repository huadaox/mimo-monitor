import { definePlugin } from "@opencode-ai/plugin";
import { exec } from "child_process";

const MIMO_MONITOR_URL = "http://localhost:9100/api/hook";

function report(tool: string, event: string, status: string, detail: string) {
  const payload = JSON.stringify({
    tool,
    event,
    status,
    detail,
    session_id: `opencode-${Date.now()}`,
  });

  exec(`curl -s -X POST -H "Content-Type: application/json" -d '${payload.replace(/'/g, "'\\''")}' ${MIMO_MONITOR_URL}`, (err) => {
    if (err) console.error("[mimo-monitor] Failed to report:", err.message);
  });
}

export default definePlugin({
  name: "mimo-monitor",
  description: "Reports agent status to mimo_monitor for real-time monitoring",

  hooks: {
    // Tool execution starts → thinking
    "tool.execute.before": (ctx: any) => {
      const toolName = ctx.tool?.name || "unknown";
      report("opencode", "tool.execute.before", "thinking", `Executing tool: ${toolName}`);
    },

    // Tool execution finishes → running
    "tool.execute.after": (ctx: any) => {
      const toolName = ctx.tool?.name || "unknown";
      report("opencode", "tool.execute.after", "running", `Completed tool: ${toolName}`);
    },

    // Permission request → waiting
    "permission.ask": (ctx: any) => {
      const permType = ctx.permission?.type || "unknown";
      report("opencode", "permission.ask", "waiting", `Waiting for permission: ${permType}`);
    },

    // Chat message received → running
    "chat.message": (ctx: any) => {
      report("opencode", "chat.message", "running", "Processing chat message");
    },
  },
});
