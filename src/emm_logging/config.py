"""Configuration contract for the reusable logging module."""

from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingSettings(BaseSettings):
    """Env-driven logging configuration with safe defaults.

    All fields are populated from environment variables prefixed with ``LOG_``.
    Unknown ``LOG_*`` variables are ignored so consumers can layer their own
    settings without conflict.
    """

    model_config = SettingsConfigDict(env_prefix="LOG_", extra="ignore")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    console_format: Literal["json", "text"] = Field(default="text")
    service_name: str = Field(default="unknown-service")
    service_version: str = Field(default="0.0.0")
    seq_url: HttpUrl | None = Field(default=None)
    seq_api_key: str | None = Field(default=None)
    azure_connection_string: str | None = Field(default=None)
