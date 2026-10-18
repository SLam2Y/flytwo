from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    BOT_TOKEN: str | None = None
    API_URL: str | None = None
    BOT_SECRET: str | None = None
    TG_SECRET: str | None = None
    WEBAPP_URL: str = 'https://blueflyingpanda.github.io/fly2/'

    DB_USER: str | None = None
    DB_PASS: str | None = None
    DB_HOST: str | None = None
    DB_PORT: str | None = None
    DB_NAME: str | None = None

    REDIS_PASS: str | None = None
    REDIS_HOST: str | None = None
    REDIS_PORT: str | None = None
    REDIS_TTL: int | None = None

    JWT_SECRET: str | None = None
    JWT_ACCESS_TOKEN_EXPIRE: int | None = None

    CORS_ORIGINS: list[str] = ['*']
    DEBUG: bool = False

    # MCP server (HTTP proxy in front of the API)
    MCP_API_BASE: str = 'http://bot:8080'  # internal URL of the FastAPI service
    MCP_HOST: str = '0.0.0.0'
    MCP_PORT: int = 8765
    MCP_PATH: str = '/mcp/'
    # Hostnames allowed in the Host header (DNS-rebinding guard). Defaults to '*' (allow
    # any) since the server only sits behind the trusted reverse proxy; narrow to specific
    # domain(s) via the MCP_ALLOWED_HOSTS env var to re-enable the guard.
    MCP_ALLOWED_HOSTS: list[str] = ['*']

    @field_validator('CORS_ORIGINS', 'MCP_ALLOWED_HOSTS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [item.strip() for item in v.split(',') if item.strip()]
        return v


_settings = Settings()

BOT_TOKEN = _settings.BOT_TOKEN
API_URL = _settings.API_URL
BOT_SECRET = _settings.BOT_SECRET
TG_SECRET = _settings.TG_SECRET
WEBAPP_URL = _settings.WEBAPP_URL

DB_USER = _settings.DB_USER
DB_PASS = _settings.DB_PASS
DB_HOST = _settings.DB_HOST
DB_PORT = _settings.DB_PORT
DB_NAME = _settings.DB_NAME

REDIS_PASS = _settings.REDIS_PASS
REDIS_HOST = _settings.REDIS_HOST
REDIS_PORT = _settings.REDIS_PORT
REDIS_TTL = _settings.REDIS_TTL

JWT_SECRET = _settings.JWT_SECRET
JWT_ACCESS_TOKEN_EXPIRE = _settings.JWT_ACCESS_TOKEN_EXPIRE

CORS_ORIGINS = _settings.CORS_ORIGINS
DEBUG = _settings.DEBUG

MCP_API_BASE = _settings.MCP_API_BASE
MCP_HOST = _settings.MCP_HOST
MCP_PORT = _settings.MCP_PORT
MCP_PATH = _settings.MCP_PATH
MCP_ALLOWED_HOSTS = _settings.MCP_ALLOWED_HOSTS
