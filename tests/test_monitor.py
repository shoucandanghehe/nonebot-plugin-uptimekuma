from anyio import sleep as wait
from httpx import AsyncClient, MockTransport, Request, Response
from nonebug import App
from pytest import MonkeyPatch, mark, raises


class StopMonitorError(Exception):
    pass


class FakeLogger:
    __slots__ = ('exceptions',)

    def __init__(self) -> None:
        self.exceptions: list[str] = []

    def exception(self, message: str) -> None:
        self.exceptions.append(message)


@mark.asyncio
async def test_send_heartbeat_sends_status_message_and_ping(app: App) -> None:
    assert app.provider is not None
    from nonebot_plugin_uptimekuma import monitor

    requests: list[Request] = []

    async def handler(request: Request) -> Response:
        requests.append(request)
        return Response(200, json={'ok': True})

    async with AsyncClient(transport=MockTransport(handler)) as client:
        await monitor.send_heartbeat(client, 'https://kuma.example.com/api/push/runtime', 'up', 'alive; bots=0', 0)

    assert len(requests) == 1
    query = dict(requests[0].url.params)
    assert query == {'status': 'up', 'msg': 'alive; bots=0', 'ping': '1'}


@mark.asyncio
async def test_send_heartbeat_logs_exception_on_failure(app: App, monkeypatch: MonkeyPatch) -> None:
    assert app.provider is not None
    from nonebot_plugin_uptimekuma import monitor

    logger = FakeLogger()

    async def handler(request: Request) -> Response:
        return Response(500, request=request)

    monkeypatch.setattr(monitor, 'logger', logger)

    async with AsyncClient(transport=MockTransport(handler)) as client:
        await monitor.send_heartbeat(client, 'https://kuma.example.com/api/push/secret-token', 'up', 'alive', 1)

    assert logger.exceptions == [
        'Failed to push Uptime Kuma heartbeat to https://kuma.example.com/api/push/secret-token: status_code=500'
    ]


@mark.asyncio
async def test_run_reports_runtime_and_configured_bot_targets(app: App, monkeypatch: MonkeyPatch) -> None:
    assert app.provider is not None
    from nonebot_plugin_uptimekuma import monitor
    from nonebot_plugin_uptimekuma.config import BotPushTarget, Config

    target = BotPushTarget(
        adapter='fake',
        self_id='1000',
        push_url='https://kuma.example.com/api/push/onebot-1000',
    )
    config = Config(
        uptimekuma_runtime_push_url='https://kuma.example.com/api/push/runtime',
        uptimekuma_bot_push_targets=[target],
        uptimekuma_startup_grace=0,
    )
    calls: list[tuple[str, str, str, int]] = []

    async def fake_send_heartbeat(
        client: AsyncClient,
        push_url: str,
        status: str,
        message: str,
        ping_ms: int,
    ) -> None:
        assert isinstance(client, AsyncClient)
        calls.append((push_url, status, message, ping_ms))

    async def stop_after_first_push(_delay: float) -> None:
        raise StopMonitorError

    monkeypatch.setattr(monitor, 'send_heartbeat', fake_send_heartbeat)
    monkeypatch.setattr(monitor, 'sleep', stop_after_first_push)

    async with app.test_api() as ctx:
        bot = ctx.create_bot(self_id='1000', auto_connect=False)
        monkeypatch.setattr(monitor, 'get_bots', lambda: {'1000': bot})
        with raises(StopMonitorError):
            await monitor.run(config)

    assert calls == [
        ('https://kuma.example.com/api/push/runtime', 'up', 'alive; bots=1; adapters=fake=1', calls[0][3]),
        (
            'https://kuma.example.com/api/push/onebot-1000',
            'up',
            'connected',
            calls[1][3],
        ),
    ]
    assert calls[0][3] >= 1
    assert calls[1][3] >= 1


@mark.asyncio
async def test_startup_grace_skips_missing_bot_target(app: App, monkeypatch: MonkeyPatch) -> None:
    assert app.provider is not None
    from nonebot_plugin_uptimekuma import monitor
    from nonebot_plugin_uptimekuma.config import BotPushTarget, Config

    target = BotPushTarget(
        adapter='fake',
        self_id='1000',
        push_url='https://kuma.example.com/api/push/onebot-1000',
    )
    config = Config(uptimekuma_bot_push_targets=[target], uptimekuma_startup_grace=30)
    calls: list[tuple[str, str, str, int]] = []

    async def fake_send_heartbeat(
        client: AsyncClient,
        push_url: str,
        status: str,
        message: str,
        ping_ms: int,
    ) -> None:
        assert isinstance(client, AsyncClient)
        calls.append((push_url, status, message, ping_ms))

    async def stop_after_first_push(_delay: float) -> None:
        raise StopMonitorError

    monkeypatch.setattr(monitor, 'send_heartbeat', fake_send_heartbeat)
    monkeypatch.setattr(monitor, 'sleep', stop_after_first_push)

    with raises(StopMonitorError):
        await monitor.run(config)

    assert calls == []


@mark.asyncio
async def test_bot_connection_hooks_report_configured_target(app: App, monkeypatch: MonkeyPatch) -> None:
    assert app.provider is not None
    from nonebot_plugin_uptimekuma import monitor
    from nonebot_plugin_uptimekuma.config import BotPushTarget, Config

    target = BotPushTarget(
        adapter='fake',
        self_id='1000',
        push_url='https://kuma.example.com/api/push/onebot-1000',
    )
    config = Config(uptimekuma_bot_push_targets=[target], uptimekuma_disconnect_grace=0)
    calls: list[tuple[str, str, str, int]] = []

    async def fake_send_heartbeat(
        client: AsyncClient,
        push_url: str,
        status: str,
        message: str,
        ping_ms: int,
    ) -> None:
        assert isinstance(client, AsyncClient)
        calls.append((push_url, status, message, ping_ms))

    monkeypatch.setattr(monitor, 'plugin_config', config)
    monkeypatch.setattr(monitor, 'send_heartbeat', fake_send_heartbeat)

    async with app.test_api() as ctx:
        ctx.create_bot(self_id='1000')
        await wait(0.01)
        assert calls == [('https://kuma.example.com/api/push/onebot-1000', 'up', 'connected', calls[0][3])]

    await wait(0.01)
    assert calls == [
        ('https://kuma.example.com/api/push/onebot-1000', 'up', 'connected', calls[0][3]),
        ('https://kuma.example.com/api/push/onebot-1000', 'down', 'disconnected', calls[1][3]),
    ]
    assert calls[0][3] >= 1
    assert calls[1][3] >= 1
