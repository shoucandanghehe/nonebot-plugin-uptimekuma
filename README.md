# nonebot-plugin-uptimekuma

通过 [Uptime Kuma](https://github.com/louislam/uptime-kuma) Push Monitor 监控 NoneBot 本身和每个 Bot 连接状态。

这个插件只做一件事：NoneBot 主动向 Uptime Kuma Push URL 上报心跳。它不会在 NoneBot 侧暴露 HTTP 健康检查接口，也不会自动创建 Uptime Kuma 监控项。

## 监控项怎么建

在 Uptime Kuma 里手动创建 Push 类型监控项：

1. 创建一个 `NoneBot Runtime`，用于判断 NoneBot 进程和事件循环是否还活着。
2. 每个 Bot 账号再创建一个独立监控项，例如：
   - `NoneBot / OneBot V11 / 123456`
   - `NoneBot / Telegram / xxx`

每个监控项都有自己的 Push URL，把这些 URL 写进 NoneBot 配置。

## 安装

```bash
nb plugin install nonebot-plugin-uptimekuma
```

或使用项目自己的包管理器安装：

```bash
uv add nonebot-plugin-uptimekuma
```

## 配置

```env
# 可选：NoneBot Runtime 监控项 Push URL
UPTIMEKUMA_RUNTIME_PUSH_URL=https://kuma.example.com/api/push/runtime-token

# 可选：每个 Bot 账号一个 Push URL
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

# 心跳间隔，单位秒
UPTIMEKUMA_INTERVAL=30

# 请求 Uptime Kuma 的超时时间，单位秒
UPTIMEKUMA_TIMEOUT=5

# NoneBot 启动后多少秒内不对缺失 Bot 上报 down
UPTIMEKUMA_STARTUP_GRACE=30

# Bot 断开后等待多少秒再上报 down，用于容忍短暂重连
UPTIMEKUMA_DISCONNECT_GRACE=20

# NoneBot 关闭时是否主动上报 down；默认 false，让 Uptime Kuma 自己因心跳超时判定 down
UPTIMEKUMA_SEND_DOWN_ON_SHUTDOWN=false
```

### 配置项说明

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `UPTIMEKUMA_RUNTIME_PUSH_URL` | `None` | Runtime Push Monitor URL；不配置则不监控 NoneBot Runtime。 |
| `UPTIMEKUMA_BOT_PUSH_TARGETS` | `[]` | Bot 账号 Push Monitor 列表。 |
| `UPTIMEKUMA_INTERVAL` | `30` | 周期心跳间隔，单位秒。 |
| `UPTIMEKUMA_TIMEOUT` | `5.0` | 请求 Uptime Kuma 超时时间，单位秒。 |
| `UPTIMEKUMA_STARTUP_GRACE` | `30` | 启动保护时间；保护期内缺失 Bot 不会上报 down。 |
| `UPTIMEKUMA_DISCONNECT_GRACE` | `20` | 断连保护时间；断开后仍未重连才上报 down。 |
| `UPTIMEKUMA_SEND_DOWN_ON_SHUTDOWN` | `false` | NoneBot 关闭时是否主动上报 down。 |

`adapter` 和 `self_id` 只用于在 NoneBot 本地匹配 Bot：

```python
(bot.type, bot.self_id) == (adapter, self_id)
```

它们不会出现在 Bot 监控项的 `msg` 中。Uptime Kuma 里每个 Bot 已经是独立监控项，监控项名称本身应该说明这是哪个账号。

## 上报内容

### Runtime Monitor

NoneBot 正常运行时周期上报：

```text
status=up
msg=alive; bots=2; adapters=OneBot V11=1, Telegram=1
ping=<事件循环延迟毫秒>
```

如果当前没有 Bot 在线：

```text
status=up
msg=alive; bots=0
ping=<事件循环延迟毫秒>
```

### Bot Monitor

Bot 在线：

```text
status=up
msg=connected
ping=<事件循环延迟毫秒>
```

Bot 断开且超过 `UPTIMEKUMA_DISCONNECT_GRACE`：

```text
status=down
msg=disconnected
ping=<事件循环延迟毫秒>
```

NoneBot 关闭且 `UPTIMEKUMA_SEND_DOWN_ON_SHUTDOWN=true`：

```text
status=down
msg=nonebot shutting down
ping=<事件循环延迟毫秒>
```

`ping` 使用 NoneBot 事件循环调度延迟，单位为毫秒。Uptime Kuma 会把它记录为该 heartbeat 的响应时间指标。

## 行为细节

- 零配置时插件只加载，不会启动后台心跳任务。
- 配置 Runtime URL 后，插件会在启动后立即开始周期上报 Runtime 心跳。
- 配置 Bot targets 后，插件会周期检查 `nonebot.get_bots()` 中的在线 Bot。
- Bot 连接时会立即向对应 Push URL 上报 `connected`。
- Bot 断开时会等待 `UPTIMEKUMA_DISCONNECT_GRACE`，等待后仍未在线才上报 `disconnected`。
- Push 请求失败会用 `logger.exception` 记录，便于 Sentry 等日志系统捕获异常。

## Uptime Kuma 建议

如果插件心跳间隔是 30 秒，Uptime Kuma 的 Push Monitor 心跳间隔建议设为 60 秒或 90 秒，避免偶发网络抖动直接误报。需要更快报警时再降低 Uptime Kuma 侧间隔或重试次数。
