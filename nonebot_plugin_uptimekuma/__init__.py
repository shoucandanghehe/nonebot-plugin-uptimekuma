from nonebot.plugin import PluginMetadata

from . import monitor as monitor
from .config import Config

__plugin_meta__ = PluginMetadata(
    name='Uptime Kuma',
    description='通过 Uptime Kuma Push Monitor 监控 NoneBot 运行状态和每个适配器账号连接状态',
    usage='配置 UPTIMEKUMA_RUNTIME_PUSH_URL 与 UPTIMEKUMA_BOT_PUSH_TARGETS 后自动上报心跳',
    type='application',
    homepage='https://github.com/scdhh/nonebot-plugin-uptimekuma',
    config=Config,
    supported_adapters=None,
)
