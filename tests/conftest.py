from nonebot import load_plugin
from nonebug import NONEBOT_INIT_KWARGS
from pytest import Config, fixture


def pytest_configure(config: Config) -> None:
    config.stash[NONEBOT_INIT_KWARGS] = {'driver': '~none'}


@fixture(scope='session', autouse=True)
async def after_nonebot_init(after_nonebot_init: None) -> None:
    assert after_nonebot_init is None
    load_plugin('nonebot_plugin_uptimekuma')
