from dataclasses import dataclass
from typing import Any, Callable
from autoanalyst.state.models import ToolResult

@dataclass
class Tool:
    name: str
    title: str
    description: str
    long_description: str
    parameters_json_schema: dict[str, Any]
    tags: list[str]
    capabilities: list[str]
    examples: list[str]
    risk_level: str
    output_type: str
    handler: Callable[[dict[str, Any]], ToolResult]

    def summary(self) -> dict[str, Any]:
        return {k:getattr(self,k) for k in ("name","title","description","long_description","parameters_json_schema","tags","capabilities","examples","risk_level","output_type")}
