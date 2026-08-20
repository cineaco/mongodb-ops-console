import base64
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    MASTER_KEY: str
    JWT_SECRET: str
    JWT_ACCESS_TTL_MINUTES: int = 60
    JWT_REFRESH_TTL_DAYS: int = 7
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173"
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    EXPOSE_OPENAPI_DOCS: bool = True
    LOG_LEVEL: str = "INFO"

    # Poller
    POLLER_INTERVAL_SECONDS: int = 30
    POLLER_TIMEOUT_SECONDS: int = 10
    POLLER_ENABLED: bool = True

    # Metrics
    METRICS_RETENTION_DAYS: int = 7

    # Deployment
    PLAYBOOK_PATH: str = "/playbook"
    DEPLOY_TIMEOUT_SECONDS: int = 1800  # 30 minutes

    # Alerts
    ALERT_DEBOUNCE_MINUTES: int = 15
    SLACK_WEBHOOK_URL: str = ""
    SLACK_CHANNEL: str = ""
    ALERT_REPLICATION_LAG_WARNING: float = 5.0
    ALERT_REPLICATION_LAG_CRITICAL: float = 10.0
    ALERT_CONNECTIONS_WARNING: int = 500
    ALERT_CONNECTIONS_CRITICAL: int = 800
    ALERT_DISK_USAGE_WARNING: int = 70
    ALERT_DISK_USAGE_CRITICAL: int = 85
    ALERT_MEMORY_WARNING: int = 80
    ALERT_MEMORY_CRITICAL: int = 90
    ALERT_CACHE_DIRTY_WARNING: int = 20
    ALERT_MEMBER_DOWN_CRITICAL: int = 1

    @property
    def master_key_bytes(self) -> bytes:
        key = base64.b64decode(self.MASTER_KEY)
        if len(key) != 32:
            raise ValueError("MASTER_KEY must decode to exactly 32 bytes")
        return key

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
