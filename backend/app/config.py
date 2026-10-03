"""Configuration loaded from environment variables.

Settings are computed lazily so importing this module doesn't require
CHAT_API_KEY to be present. The key is only checked when get_settings()
is actually called by rag_chain.ask() (or by tests).
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()


@dataclass(frozen=True)
class Settings:
    chat_api_key: str
    llm_model: str


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings(
            chat_api_key=os.environ["CHAT_API_KEY"],
            llm_model=os.environ.get("LLM_MODEL", "openai/gpt-oss-20b"),
        )
    return _settings
