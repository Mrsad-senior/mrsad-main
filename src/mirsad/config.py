"""Runtime settings, read from environment variables prefixed ``MIRSAD_`` or a ``.env`` file."""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MIRSAD_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8700
    data_dir: Path = Path(".mirsad")
    database_url: str = ""  # default: sqlite file inside data_dir
    policy_path: Path = PROJECT_DIR / "configs" / "policies" / "default.yaml"
    upstreams_path: Path = PROJECT_DIR / "configs" / "upstreams.yaml"
    detector_model_dir: Path = PACKAGE_DIR / "detector" / "model"

    secret_key: str = ""  # JWT signing + audit HMAC; generated and persisted in data_dir if empty
    token_ttl_hours: int = 12
    approval_timeout_s: float = 120.0
    max_result_chars: int = 200_000
    audit_payload_max_chars: int = 20_000

    enable_demo: bool = False
    llm_base_url: str = "http://127.0.0.1:11434/v1"  # upstream for the OpenAI-compatible proxy / demo agent
    llm_model: str = "qwen2.5:7b"
    llm_api_key: str = "ollama"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:security@najd-trading.example"
    log_level: str = "INFO"

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'mirsad.db').resolve()}"

    def resolved_secret_key(self) -> str:
        """Return the configured secret or a persisted random one (file mode 0600)."""
        if self.secret_key:
            return self.secret_key
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / "secret.key"
        if path.exists():
            return path.read_text().strip()
        key = secrets.token_urlsafe(48)
        path.write_text(key)
        path.chmod(0o600)
        return key


@lru_cache
def get_settings() -> Settings:
    return Settings()
