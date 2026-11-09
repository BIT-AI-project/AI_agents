"""Application configuration loaded from environment and YAML."""
from pathlib import Path
from typing import Any, Literal
import os
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]

class AppConfig(BaseModel):
    dataset_path: Path = ROOT / "data" / "online_retail.sqlite"
    output_dir: Path = ROOT / "output"
    workflow_mode: str = "plan_with_review_and_retrieval"
    planning_enabled: bool = True
    output_review_enabled: bool = True
    tool_retrieval_enabled: bool = True
    top_k_tools: int = 4
    max_total_steps: int = 20
    max_retries_per_plan_step: int = 2
    max_consecutive_identical_tool_calls: int = 3
    python_timeout_seconds: int = 60
    max_sql_rows: int = 5000
    max_schema_sample_rows: int = 5
    llm_provider: Literal["fake", "openai", "anthropic", "opencode"] = "fake"
    llm_model: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.0
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    anthropic_structured_outputs: bool | None = None
    opencode_base_url: str = "http://localhost:4096"
    opencode_token: str | None = None
    opencode_model: str | None = None
    opencode_timeout_seconds: int = 120

    @classmethod
    def load(cls, path: str | Path | None = None) -> "AppConfig":
        load_dotenv()
        values: dict[str, Any] = {}
        if path:
            with Path(path).open(encoding="utf-8") as stream:
                values.update(yaml.safe_load(stream) or {})
        mapping = {
            "AUTOANALYST_DATASET":"dataset_path", "AUTOANALYST_OUTPUT":"output_dir",
            "OPENAI_API_KEY":"openai_api_key", "OPENAI_BASE_URL":"openai_base_url", "OPENAI_MODEL":"openai_model",
            "ANTHROPIC_API_KEY":"anthropic_api_key", "ANTHROPIC_BASE_URL":"anthropic_base_url", "ANTHROPIC_MODEL":"anthropic_model", "ANTHROPIC_STRUCTURED_OUTPUTS":"anthropic_structured_outputs",
            "OPENCODE_BASE_URL":"opencode_base_url", "OPENCODE_TOKEN":"opencode_token", "OPENCODE_MODEL":"opencode_model",
            "AUTOANALYST_LLM_MODEL":"llm_model", "AUTOANALYST_LLM_TEMPERATURE":"llm_temperature",
        }
        provider=os.getenv("AUTOANALYST_LLM_PROVIDER") or os.getenv("AUTOANALYST_LLM")
        if provider: values["llm_provider"]=provider
        for env, key in mapping.items():
            if os.getenv(env): values[key] = os.environ[env]
        for key in ("dataset_path", "output_dir"):
            if key in values:
                p = Path(values[key]); values[key] = p if p.is_absolute() else ROOT / p
        return cls(**values)

    def with_mode(self, mode: str) -> "AppConfig":
        flags = {"react_baseline":(False,False,False), "plan_only":(True,False,False), "plan_with_review":(True,True,False), "plan_with_review_and_retrieval":(True,True,True)}
        if mode not in flags: raise ValueError(f"Unknown workflow mode: {mode}")
        plan, review, retrieval = flags[mode]
        return self.model_copy(update={"workflow_mode":mode, "planning_enabled":plan, "output_review_enabled":review, "tool_retrieval_enabled":retrieval})
