"""Environment-driven settings. Missing provider credentials never crash the app: the mock providers are used."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/rpg.db"))
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    image_provider: str = field(default_factory=lambda: os.getenv("IMAGE_PROVIDER", "placeholder"))
    hf_token: str = field(default_factory=lambda: os.getenv("HF_TOKEN", ""))
    flux_model: str = field(default_factory=lambda: os.getenv("FLUX_MODEL", "black-forest-labs/FLUX.1-schnell"))
    asset_dir: str = field(default_factory=lambda: os.getenv("ASSET_DIR", "./data/assets"))
    cors_origins: list[str] = field(default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","))
    max_input_chars: int = field(default_factory=lambda: _int("MAX_INPUT_CHARS", 300))
    rate_action_per_min: int = field(default_factory=lambda: _int("RATE_ACTION_PER_MIN", 120))
    rate_generate_per_min: int = field(default_factory=lambda: _int("RATE_GENERATE_PER_MIN", 20))
    rate_asset_per_min: int = field(default_factory=lambda: _int("RATE_ASSET_PER_MIN", 30))
    max_campaigns_per_user: int = field(default_factory=lambda: _int("MAX_CAMPAIGNS_PER_USER", 25))

    def provider_status(self) -> dict:
        return {
            "llm": "openai-compatible" if self.llm_api_key else "mock",
            "llm_message": None if self.llm_api_key else "LLM_API_KEY is not set. Using the built-in deterministic Game Master (set LLM_API_KEY in .env to enable an LLM).",
            "image": self.image_provider if (self.image_provider != "huggingface" or self.hf_token) else "placeholder",
            "image_message": None if (self.image_provider != "huggingface" or self.hf_token) else "HF_TOKEN is not set. Using placeholder artwork.",
        }
