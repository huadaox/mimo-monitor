// mimo-monitor plugin for OpenCode
// Reports agent status to mimo_monitor via HTTP POST

import { exec } from "child_process";

const MIMO_MONITOR_URL = "http://localhost:9100/api/hook";

function report(event: string, status: string, detail: string, sessionID?: string) {
  const payload = JSON.stringify({
    tool: "opencode",
    event,
    status,
    detail,
    session_id: sessionID || "unknown",
  });
  // Use --noproxy to avoid proxy issues, run in background
  exec(`curl --noproxy localhost -sf -X POST -H "Content-Type: application/json" -d '${payload}' ${MIMO_MONITOR_URL} >/dev/null 2>&1 &`);
}

export default async function MimoMonitorPlugin(ctx: any) {
  return {
    // Before tool execution → thinking
    "tool.execute.before": async (input: any, output: any) => {
      const toolName = input.tool || "unknown";
      report("tool.execute.before", "thinking", `Executing: ${toolName}`, input.sessionID);
    },

    // After tool execution → running
    "tool.execute.after": async (input: any, output: any) => {
      const toolName = input.tool || "unknown";
      report("tool.execute.after", "running", `Completed: ${toolName}`, input.sessionID);
    },

    // Permission request → waiting
    "permission.ask": async (input: any, output: any) => {
      report("permission.ask", "waiting", "Waiting for permission", input.sessionID);
    },

    // Chat message → running
    "chat.message": async (input: any, output: any) => {
      report("chat.message", "running", "Processing message", input.sessionID);
    },

    // General events
    "event": async (input: any) => {
      const eventName = input.event?.type || "unknown";
      // Only report interesting events
      if (["session.create", "session.delete", "message.create"].includes(eventName)) {
        report(eventName, "running", `Event: ${eventName}`);
      }
    },
  };
}
