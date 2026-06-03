# nonebot-plugin-uptimekuma

通过 Uptime Kuma Push Monitor 主动上报 NoneBot 运行状态和每个适配器账号连接状态。

## 监控模型

建议在 Uptime Kuma 中创建：

- 1 个 `NoneBot Runtime` Push Monitor：监控 NoneBot 进程与事件循环是否仍在运行。
- 每个适配器账号 1 个 Push Monitor：单独监控该账号是否仍连接。

插件不会自动创建 Uptime Kuma 监控项；请在 Uptime Kuma 中创建 Push Monitor 后，将对应 Push URL 写入配置。

## 配置项

```env
UPTIMEKUMA_RUNTIME_PUSH_URL=https://kuma.example.com/api/push/runtime-token
UPTIMEKUMA_INTERVAL=30
UPTIMEKUMA_TIMEOUT=5
UPTIMEKUMA_STARTUP_GRACE=30
UPTIMEKUMA_DISCONNECT_GRACE=20
UPTIMEKUMA_SEND_DOWN_ON_SHUTDOWN=false

UPTIMEKUMA_BOT_PUSH_TARGETS='[
  {
    "adapter": "OneBot V11",
    "self_id": "123456",
    "push_url": "https://kuma.example.com/api/push/onebot-123456-token"
  },
  {
    "adapter": "Telegram",
    "self_id": "987654",
    "push_url": "https://kuma.example.com/api/push/telegram-987654-token"
  }
]'
```

## 上报内容

Runtime Monitor：

```text
status=up
msg=alive; bots=2; adapters=OneBot V11=1, Telegram=1
ping=<事件循环延迟毫秒>
```

Bot Monitor：

```text
status=up
msg=connected
ping=<事件循环延迟毫秒>
```

断开超过 `UPTIMEKUMA_DISCONNECT_GRACE` 后：

```text
status=down
msg=disconnected
ping=<事件循环延迟毫秒>
```

`ping` 使用 NoneBot 事件循环调度延迟，单位为毫秒。Uptime Kuma 会把它记录为该 heartbeat 的响应时间指标。
