"""Provider-agnostic JSON wrapper backed by an OpenAI-compatible chat API."""
import json
from typing import Any
from openai import OpenAI

class OpenAICompatibleClient:
    def __init__(self, api_key: str, model: str, base_url: str | None = None, temperature: float = 0):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model, self.temperature = model, temperature
        self.usage = {"prompt_tokens":0, "completion_tokens":0}

    def complete_json(self, task: str, payload: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
        prompt = f"Task: {task}\nReturn only valid JSON. Schema: {json.dumps(schema or {})}\nInput: {json.dumps(payload, default=str)}"
        response = self.client.chat.completions.create(model=self.model, temperature=self.temperature, response_format={"type":"json_object"}, messages=[{"role":"user", "content":prompt}])
        if response.usage:
            self.usage["prompt_tokens"] += response.usage.prompt_tokens
            self.usage["completion_tokens"] += response.usage.completion_tokens
        try: return json.loads(response.choices[0].message.content or "{}")
        except (json.JSONDecodeError, IndexError, TypeError) as exc: raise ValueError(f"LLM returned invalid JSON: {exc}") from exc
