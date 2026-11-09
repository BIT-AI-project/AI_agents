"""Anthropic Messages API client with JSON-schema-constrained outputs."""
import copy
import json
import re
from typing import Any
from anthropic import Anthropic

def _anthropic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Pydantic JSON Schema to Anthropic's strict-output subset.

    Dynamic maps are constrained to empty objects. AutoAnalyst already supplies
    deterministic tool arguments and uses these maps as optional LLM metadata.
    """
    result=copy.deepcopy(schema)
    result.pop("$schema",None)
    def visit(node):
        if isinstance(node,dict):
            node.pop("title",None)
            node.pop("default",None)
            node.pop("examples",None)
            if node.get("type")=="object":
                properties=node.get("properties")
                if properties is not None:
                    node["required"]=list(properties)
                node["additionalProperties"]=False
            for value in list(node.values()): visit(value)
        elif isinstance(node,list):
            for value in node: visit(value)
    visit(result)
    return result

class AnthropicJSONClient:
    """Provider implementation for Claude's native Messages API."""
    def __init__(self,api_key: str,model: str,base_url: str|None=None,max_tokens: int=4096,structured_outputs: bool=True):
        options={"api_key":api_key}
        if base_url: options["base_url"]=base_url
        self.client=Anthropic(**options)
        self.model=model
        self.max_tokens=max_tokens
        self.structured_outputs=structured_outputs
        self.usage={"prompt_tokens":0,"completion_tokens":0}

    def complete_json(self,task: str,payload: dict[str,Any],schema: dict[str,Any]|None=None)->dict[str,Any]:
        schema=schema or {"type":"object","properties":{},"required":[],"additionalProperties":False}
        prompt=(f"Task: {task}\nReturn one JSON object matching the requested schema. "
                f"If a metadata or arguments object has no declared properties, return {{}} for it.\n"
                f"JSON schema: {json.dumps(_anthropic_schema(schema))}\n"
                f"Input: {json.dumps(payload,default=str)}")
        params={"model":self.model,"max_tokens":self.max_tokens,
                "messages":[{"role":"user","content":prompt}]}
        if self.structured_outputs:
            params["output_config"]={"format":{"type":"json_schema","schema":_anthropic_schema(schema)}}
        response=self.client.messages.create(**params)
        text="".join(block.text for block in response.content if getattr(block,"type",None)=="text")
        self.usage["prompt_tokens"]+=response.usage.input_tokens
        self.usage["completion_tokens"]+=response.usage.output_tokens
        if not text.strip():
            block_types=[getattr(block,"type","unknown") for block in response.content]
            raise ValueError(f"Anthropic returned no text block for {task} (stop_reason={response.stop_reason!r}, content_types={block_types})")
        candidates=[text.strip()]
        fenced=re.search(r"```(?:json)?\s*(.*?)```",text,re.S|re.I)
        if fenced: candidates.append(fenced.group(1).strip())
        start,end=text.find("{"),text.rfind("}")
        if start>=0 and end>start: candidates.append(text[start:end+1])
        last_error=None
        for candidate in candidates:
            try: return json.loads(candidate)
            except json.JSONDecodeError as exc: last_error=exc
        preview=text.strip().replace("\n"," ")[:180]
        raise ValueError(f"Anthropic returned non-JSON text for {task} (stop_reason={response.stop_reason!r}, preview={preview!r}; {last_error})") from last_error
