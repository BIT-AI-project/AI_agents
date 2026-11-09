"""OpenCode V2 server provider using its stateless text-generation API."""
import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

class OpenCodeJSONClient:
    """Adapter for OpenCode's experimental ``/api/experimental/generate/text`` route.

    ``model`` can be ``providerID/modelID``. When omitted, OpenCode's server-side
    default model is used. The endpoint does not expose token usage or sampling
    controls, so those metrics are unavailable for this provider.
    """
    def __init__(self,base_url: str="http://localhost:4096",token: str|None=None,model: str|None=None,timeout: int=120):
        self.base_url=base_url.rstrip("/")
        self.token=token
        self.model=model
        self.timeout=timeout
        self.usage: dict[str,int]={}

    def complete_json(self,task: str,payload: dict[str,Any],schema: dict[str,Any]|None=None)->dict[str,Any]:
        output_schema=schema or {"type":"object"}
        prompt=(f"Task: {task}\nReturn only one valid JSON object matching this JSON Schema:\n"
                f"{json.dumps(output_schema)}\nInput:\n{json.dumps(payload,default=str)}")
        body={"prompt":prompt}
        if self.model:
            if "/" not in self.model:
                raise ValueError("OPENCODE_MODEL must be providerID/modelID, for example anthropic/claude-sonnet-4-5")
            provider_id,model_id=self.model.split("/",1)
            body["model"]={"providerID":provider_id,"id":model_id}
        headers={"Content-Type":"application/json","Accept":"application/json"}
        if self.token: headers["Authorization"]=f"Bearer {self.token}"
        request=Request(self.base_url+"/api/experimental/generate/text",data=json.dumps(body).encode("utf-8"),headers=headers,method="POST")
        try:
            with urlopen(request,timeout=self.timeout) as response:
                result=json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail=exc.read().decode("utf-8",errors="replace")[:1000]
            raise RuntimeError(f"OpenCode API returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Could not connect to OpenCode at {self.base_url}: {exc.reason}") from exc
        text=((result.get("data") or {}).get("text") or "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            fenced=re.search(r"```(?:json)?\s*(.*?)```",text,re.S|re.I)
            if fenced:
                try: return json.loads(fenced.group(1).strip())
                except json.JSONDecodeError: pass
            raise ValueError(f"OpenCode returned invalid JSON for {task}: {exc}") from exc
