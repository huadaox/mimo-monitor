// Mimo Monitor - OpenCode 插件
//
// 通过 OpenCode 的插件系统写入状态文件。
// 安装: bash plugins/install.sh opencode
//
// OpenCode 事件 → 状态映射:
//   tool.execute.before → working
//   tool.execute.after  → working
//   permission.ask      → waiting
//   chat.message        → working

import { writeFileSync, mkdirSync, renameSync } from "fs";
import { join } from "path";
import { homedir } from "os";
import { execSync } from "child_process";

const STATE_DIR = join(homedir(), ".agent-state");
const TOOL = "opencode";

function writeState(state: string, detail: string = "") {
  try {
    mkdirSync(STATE_DIR, { recursive: true });
    const ts = Date.now() / 1000;
    const data = JSON.stringify({ state, detail, ts });
    const tmp = join(STATE_DIR, `${TOOL}.tmp`);
    const dst = join(STATE_DIR, `${TOOL}.json`);
    writeFileSync(tmp, data);
    renameSync(tmp, dst);
  } catch (e) {
    // 静默失败，不影响主程序
  }
}

export default async function MimoMonitorPlugin(ctx: any) {
  return {
    "tool.execute.before": async (input: any) => {
      const toolName = input?.tool || "unknown";
      writeState("working", `Tool: ${toolName}`);
    },

    "tool.execute.after": async (input: any) => {
      const toolName = input?.tool || "unknown";
      writeState("working", `Done: ${toolName}`);
    },

    "permission.ask": async () => {
      writeState("waiting", "Waiting for permission");
    },

    "chat.message": async () => {
      writeState("working", "Processing message");
    },

    "session.create": async () => {
      writeState("working", "Session started");
    },

    "session.delete": async () => {
      writeState("idle", "Session ended");
    },
  };
}
