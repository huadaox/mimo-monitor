# Mimo TUI 监控 - 无感方案

**完全无感，用原命令启动，自动监控 TUI 状态**

## 原理

用 `LD_PRELOAD` 劫持 `write()` 函数：
- 程序写入 stdout 时，同时检查状态关键词
- 检测到 "Thinking"/"Reading"/"Writing" 等关键词时，自动 hook 上报
- 对程序完全透明，无性能影响

## 安装

```bash
cd ~/mimo/mimo_monitor/hooks
./install.sh
```

安装后，重新加载 shell：
```bash
source ~/.bashrc  # 或 source ~/.zshrc
```

## 使用

**完全无感，直接用原命令：**

```bash
# Claude Code（自动监控）
claude "你的问题"

# OpenCode（自动监控）
opencode

# Codex（自动监控）
codex
```

状态会自动上报到 mimo monitor，不需要任何额外操作。

## 状态映射

| TUI 显示 | 上报状态 |
|----------|----------|
| Thinking | thinking |
| Reading | running |
| Writing | running |
| Executing | running |
| Waiting | waiting |
| Error | error |

## 卸载

编辑 `~/.bashrc` 或 `~/.zshrc`，删除 mimo-hook.sh 相关行。

## 技术细节

### LD_PRELOAD 劫持

```c
// 劫持 write() 函数
ssize_t write(int fd, const void *buf, size_t count) {
    // 调用原始 write
    ssize_t result = original_write(fd, buf, count);
    
    // 监控 stdout
    if (fd == 1) {
        detect_status(buf, count);  // 检测状态关键词
    }
    
    return result;
}
```

### 优势

- ✅ 完全无感，用原命令
- ✅ 通用所有工具（claude/opencode/codex）
- ✅ 无性能影响
- ✅ 不需要修改程序代码

### 限制

- ⚠️ 只支持 Linux（LD_PRELOAD）
- ⚠️ 需要编译 gcc
- ⚠️ 依赖 TUI 输出包含状态关键词
