"""Configuration for ThoughtOS server.

Reads from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from .paths import database_path


@dataclass
class LLMConfig:
    """Configuration for a specific LLM provider."""
    provider: str = "ollama"  # ollama, gemini, openai
    model: str = "llama3.2:3b"
    base_url: str = "http://127.0.0.1:11434"
    api_key: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 2048


@dataclass
class ExtractionConfig:
    """Configuration for the entity extraction pipeline."""
    # Stage control
    enable_rule_engine: bool = True
    enable_llm_extraction: bool = True
    enable_rule_generation: bool = False  # LLM proposes rules from patterns

    # Deduplication
    fuzzy_threshold: float = 0.85  # 0-1, for fuzzy entity matching
    enable_llm_dedup: bool = True

    # LLM used for extraction (rule generation can use a different one)
    extraction_llm: LLMConfig = field(default_factory=LLMConfig)

    # Separate LLM for rule generation (often a smarter model)
    rule_gen_llm: LLMConfig = field(
        default_factory=lambda: LLMConfig(model="llama3.2:3b")
    )


@dataclass
class Config:
    """Top-level ThoughtOS configuration."""
    db_path: str = field(default_factory=database_path)
    host: str = "0.0.0.0"
    port: int = 8000
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)


def load_config() -> Config:
    """Load configuration from environment variables."""
    config = Config()

    # Server
    config.host = os.getenv("THOUGHTOS_HOST", "0.0.0.0")
    config.port = int(os.getenv("THOUGHTOS_PORT", "8000"))
    config.db_path = database_path()

    # Extraction LLM
    ext = config.extraction
    ext.enable_llm_extraction = os.getenv("THOUGHTOS_LLM_ENABLED", "1") != "0"
    ext.enable_rule_generation = os.getenv("THOUGHTOS_RULE_GEN_ENABLED", "0") == "1"
    ext.extraction_llm.provider = os.getenv("THOUGHTOS_LLM_PROVIDER", "ollama")
    ext.extraction_llm.model = os.getenv(
        "THOUGHTOS_LLM_MODEL", "llama3.2:3b"
    )
    ext.extraction_llm.base_url = os.getenv(
        "THOUGHTOS_LLM_BASE_URL", "http://127.0.0.1:11434"
    )
    ext.extraction_llm.api_key = os.getenv("THOUGHTOS_LLM_API_KEY")

    # Rule generation LLM (can be different)
    ext.rule_gen_llm.provider = os.getenv(
        "THOUGHTOS_RULE_LLM_PROVIDER",
        ext.extraction_llm.provider,
    )
    ext.rule_gen_llm.model = os.getenv(
        "THOUGHTOS_RULE_LLM_MODEL",
        ext.extraction_llm.model,
    )
    ext.rule_gen_llm.base_url = os.getenv(
        "THOUGHTOS_RULE_LLM_BASE_URL",
        ext.extraction_llm.base_url,
    )
    ext.rule_gen_llm.api_key = os.getenv(
        "THOUGHTOS_RULE_LLM_API_KEY",
        ext.extraction_llm.api_key,
    )

    return config
