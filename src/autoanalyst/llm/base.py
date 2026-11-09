from typing import Any, Protocol

class LLMClient(Protocol):
    def complete_json(self, task: str, payload: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]: ...
