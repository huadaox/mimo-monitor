/*
 * mimo_hook.so - LD_PRELOAD 劫持库
 * 
 * 劫持 libc 的 write() 函数，当程序写入 stdout 时：
 * 1. 正常输出到终端
 * 2. 同时把内容发给 mimo monitor
 *
 * 编译：gcc -shared -fPIC -o mimo_hook.so mimo_hook.c -ldl
 * 使用：LD_PRELOAD=./mimo_hook.so claude "你的问题"
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <pthread.h>

// 原始 write 函数指针
static ssize_t (*original_write)(int fd, const void *buf, size_t count) = NULL;

// mimo monitor 地址
static const char *MIMO_HOST = "127.0.0.1";
static int MIMO_PORT = 9100;

// 状态关键词映射
typedef struct {
    const char *keyword;
    const char *status;
} StatusMapping;

static StatusMapping status_map[] = {
    {"Thinking", "thinking"},
    {"Reading", "running"},
    {"Writing", "running"},
    {"Executing", "running"},
    {"Calling", "running"},
    {"Waiting", "waiting"},
    {"Press Enter", "waiting"},
    {"Error", "error"},
    {NULL, NULL}
};

// 当前状态（避免重复上报）
static char current_state[32] = "idle";
static pthread_mutex_t state_mutex = PTHREAD_MUTEX_INITIALIZER;

// 发送 HTTP POST 请求
static void send_hook(const char *event, const char *detail) {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return;

    struct sockaddr_in server;
    server.sin_family = AF_INET;
    server.sin_port = htons(MIMO_PORT);
    inet_pton(AF_INET, MIMO_HOST, &server.sin_addr);

    if (connect(sock, (struct sockaddr *)&server, sizeof(server)) < 0) {
        close(sock);
        return;
    }

    // 构建 JSON
    char json[1024];
    snprintf(json, sizeof(json),
        "{\"tool\":\"claude-code\",\"event\":\"%s\",\"detail\":\"%s\"}",
        event, detail);

    // 构建 HTTP 请求
    char request[2048];
    snprintf(request, sizeof(request),
        "POST /api/hook HTTP/1.1\r\n"
        "Host: %s:%d\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %zu\r\n"
        "\r\n"
        "%s",
        MIMO_HOST, MIMO_PORT, strlen(json), json);

    send(sock, request, strlen(request), 0);
    close(sock);
}

// 检测状态关键词
static void detect_status(const char *buf, size_t count) {
    // 只处理 stdout (fd=1)
    // 转换为字符串（临时）
    char *str = malloc(count + 1);
    if (!str) return;
    memcpy(str, buf, count);
    str[count] = '\0';

    // 检查每个关键词
    for (int i = 0; status_map[i].keyword != NULL; i++) {
        if (strstr(str, status_map[i].keyword) != NULL) {
            pthread_mutex_lock(&state_mutex);
            
            // 状态变化时上报
            if (strcmp(current_state, status_map[i].status) != 0) {
                strcpy(current_state, status_map[i].status);
                
                // 异步发送，不阻塞主程序
                char detail[256];
                snprintf(detail, sizeof(detail), "TUI: %s", status_map[i].keyword);
                
                // 创建子进程发送请求
                pid_t pid = fork();
                if (pid == 0) {
                    send_hook("TUI_state", detail);
                    _exit(0);
                }
            }
            
            pthread_mutex_unlock(&state_mutex);
            break;
        }
    }

    free(str);
}

// 劫持 write 函数
ssize_t write(int fd, const void *buf, size_t count) {
    // 初始化原始函数
    if (!original_write) {
        original_write = dlsym(RTLD_NEXT, "write");
    }

    // 调用原始 write
    ssize_t result = original_write(fd, buf, count);

    // 只监控 stdout (fd=1)
    if (fd == 1 && result > 0) {
        detect_status(buf, result);
    }

    return result;
}

// 构造函数：初始化时调用
__attribute__((constructor))
static void init(void) {
    // 从环境变量读取配置
    const char *host = getenv("MIMO_HOST");
    if (host) MIMO_HOST = host;
    
    const char *port = getenv("MIMO_PORT");
    if (port) MIMO_PORT = atoi(port);
}
