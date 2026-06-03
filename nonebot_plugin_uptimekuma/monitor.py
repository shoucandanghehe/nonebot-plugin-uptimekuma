from time import monotonic, perf_counter

from anyio import CancelScope, create_task_group, sleep
from anyio.lowlevel import checkpoint
from httpx import AsyncClient, HTTPError, HTTPStatusError
from nonebot import get_bots, get_driver, get_plugin_config, logger
from nonebot.adapters import Bot

from .config import Config

plugin_config = get_plugin_config(Config)
driver = get_driver()


@driver.on_startup
async def start_monitor() -> None:
    if plugin_config.uptimekuma_runtime_push_url or plugin_config.uptimekuma_bot_push_targets:
        driver.task_group.start_soon(run, plugin_config)


async def measure_event_loop_lag_ms() -> int:
    started_at = perf_counter()
    await checkpoint()
    lag_ms = round((perf_counter() - started_at) * 1000)
    return max(1, lag_ms)


async def run(config: Config) -> None:  # noqa: C901, PLR0912
    if not (config.uptimekuma_runtime_push_url or config.uptimekuma_bot_push_targets):
        return

    started_at = monotonic()
    async with AsyncClient(timeout=config.uptimekuma_timeout) as client:
        try:
            while True:
                lag_ms = await measure_event_loop_lag_ms()
                bots = get_bots()
                connected = {(bot.type, bot.self_id) for bot in bots.values()}

                async with create_task_group() as task_group:
                    if config.uptimekuma_runtime_push_url:
                        if bots:
                            counts: dict[str, int] = {}
                            for bot in bots.values():
                                counts[bot.type] = counts.get(bot.type, 0) + 1
                            adapters = ', '.join(f'{adapter}={count}' for adapter, count in sorted(counts.items()))
                            message = f'alive; bots={len(bots)}; adapters={adapters}'
                        else:
                            message = 'alive; bots=0'

                        task_group.start_soon(
                            send_heartbeat,
                            client,
                            config.uptimekuma_runtime_push_url,
                            'up',
                            message,
                            lag_ms,
                        )

                    for target in config.uptimekuma_bot_push_targets:
                        key = (target.adapter, target.self_id)
                        if key in connected:
                            status = 'up'
                            state = 'connected'
                        elif monotonic() - started_at < config.uptimekuma_startup_grace:
                            continue
                        else:
                            status = 'down'
                            state = 'disconnected'

                        task_group.start_soon(
                            send_heartbeat,
                            client,
                            target.push_url,
                            status,
                            state,
                            lag_ms,
                        )

                await sleep(config.uptimekuma_interval)
        finally:
            if config.uptimekuma_send_down_on_shutdown:
                with CancelScope(shield=True):
                    lag_ms = await measure_event_loop_lag_ms()
                    async with create_task_group() as task_group:
                        if config.uptimekuma_runtime_push_url:
                            task_group.start_soon(
                                send_heartbeat,
                                client,
                                config.uptimekuma_runtime_push_url,
                                'down',
                                'nonebot shutting down',
                                lag_ms,
                            )

                        for target in config.uptimekuma_bot_push_targets:
                            task_group.start_soon(
                                send_heartbeat,
                                client,
                                target.push_url,
                                'down',
                                'nonebot shutting down',
                                lag_ms,
                            )


@driver.on_bot_connect
async def report_bot_connected(bot: Bot) -> None:
    for target in plugin_config.uptimekuma_bot_push_targets:
        if (target.adapter, target.self_id) != (bot.type, bot.self_id):
            continue

        async with AsyncClient(timeout=plugin_config.uptimekuma_timeout) as client:
            await send_heartbeat(
                client,
                target.push_url,
                'up',
                'connected',
                await measure_event_loop_lag_ms(),
            )
        return


@driver.on_bot_disconnect
async def report_bot_disconnected(bot: Bot) -> None:
    for target in plugin_config.uptimekuma_bot_push_targets:
        if (target.adapter, target.self_id) != (bot.type, bot.self_id):
            continue

        if plugin_config.uptimekuma_disconnect_grace > 0:
            await sleep(plugin_config.uptimekuma_disconnect_grace)

        if (target.adapter, target.self_id) in {(bot.type, bot.self_id) for bot in get_bots().values()}:
            return

        async with AsyncClient(timeout=plugin_config.uptimekuma_timeout) as client:
            await send_heartbeat(
                client,
                target.push_url,
                'down',
                'disconnected',
                await measure_event_loop_lag_ms(),
            )
        return


async def send_heartbeat(client: AsyncClient, push_url: str, status: str, message: str, ping_ms: int) -> None:
    try:
        response = await client.get(
            push_url,
            params={
                'status': status,
                'msg': message,
                'ping': max(1, ping_ms),
            },
        )
        response.raise_for_status()
    except HTTPStatusError as exception:
        logger.exception(
            f'Failed to push Uptime Kuma heartbeat to {push_url}: status_code={exception.response.status_code}'
        )
    except HTTPError:
        logger.exception(f'Failed to push Uptime Kuma heartbeat to {push_url}')
