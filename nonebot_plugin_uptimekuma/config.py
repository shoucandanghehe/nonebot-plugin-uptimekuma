from pydantic import BaseModel, Field


class BotPushTarget(BaseModel):
    adapter: str = Field(min_length=1)
    self_id: str = Field(min_length=1)
    push_url: str = Field(min_length=1)


class Config(BaseModel):
    uptimekuma_runtime_push_url: str | None = None
    uptimekuma_bot_push_targets: list[BotPushTarget] = Field(default_factory=list)
    uptimekuma_interval: int = Field(default=30, ge=1)
    uptimekuma_timeout: float = Field(default=5.0, gt=0)
    uptimekuma_startup_grace: int = Field(default=30, ge=0)
    uptimekuma_disconnect_grace: int = Field(default=20, ge=0)
    uptimekuma_send_down_on_shutdown: bool = False
