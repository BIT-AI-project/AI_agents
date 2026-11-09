from types import SimpleNamespace
import pytest
from autoanalyst.cli import make_llm
from autoanalyst.config import AppConfig
from autoanalyst.llm.anthropic_client import AnthropicJSONClient
from autoanalyst.llm.fake_client import FakeLLM
from autoanalyst.llm.openai_client import OpenAICompatibleClient
from autoanalyst.llm.opencode_client import OpenCodeJSONClient

def test_provider_selected_from_environment(monkeypatch):
    monkeypatch.setenv("AUTOANALYST_LLM_PROVIDER","anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY","test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL","claude-test-model")
    config=AppConfig.load()
    client=make_llm(config)
    assert isinstance(client,AnthropicJSONClient)
    assert client.model=="claude-test-model"
    assert client.structured_outputs is True

def test_fake_provider_stays_offline():
    assert isinstance(make_llm(AppConfig(llm_provider="fake")),FakeLLM)

def test_provider_requires_matching_secret():
    with pytest.raises(ValueError,match="OPENAI_API_KEY"):
        make_llm(AppConfig(llm_provider="openai",openai_api_key=None))
    with pytest.raises(ValueError,match="ANTHROPIC_API_KEY"):
        make_llm(AppConfig(llm_provider="anthropic",anthropic_api_key=None))

def test_anthropic_structured_json_and_usage():
    calls={}
    def create(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text",text='{"answer":"ok"}')],usage=SimpleNamespace(input_tokens=12,output_tokens=4))
    client=AnthropicJSONClient.__new__(AnthropicJSONClient)
    client.client=SimpleNamespace(messages=SimpleNamespace(create=create))
    client.model="claude-test"; client.max_tokens=1024; client.structured_outputs=True; client.usage={"prompt_tokens":0,"completion_tokens":0}
    result=client.complete_json("test",{"query":"hello"},{"type":"object","properties":{"answer":{"type":"string"}},"required":["answer"]})
    assert result=={"answer":"ok"}
    assert calls["output_config"]["format"]["type"]=="json_schema"
    assert calls["output_config"]["format"]["schema"]["additionalProperties"] is False
    assert "temperature" not in calls
    assert client.usage=={"prompt_tokens":12,"completion_tokens":4}

def test_anthropic_empty_response_has_actionable_error():
    client=AnthropicJSONClient.__new__(AnthropicJSONClient)
    client.client=SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs:SimpleNamespace(content=[],usage=SimpleNamespace(input_tokens=4,output_tokens=0),stop_reason="end_turn")))
    client.model="claude-test"; client.max_tokens=128; client.structured_outputs=True; client.usage={"prompt_tokens":0,"completion_tokens":0}
    with pytest.raises(ValueError,match="no text block.*stop_reason='end_turn'"):
        client.complete_json("test",{}, {"type":"object","properties":{}})

def test_anthropic_compatible_non_claude_uses_prompt_json_mode():
    calls={}
    def create(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text",text='{"ok":true}')],usage=SimpleNamespace(input_tokens=5,output_tokens=2))
    client=AnthropicJSONClient.__new__(AnthropicJSONClient)
    client.client=SimpleNamespace(messages=SimpleNamespace(create=create))
    client.model="gemma-e4b-agent:latest"; client.max_tokens=128; client.structured_outputs=False; client.usage={"prompt_tokens":0,"completion_tokens":0}
    result=client.complete_json("test",{}, {"type":"object","properties":{"ok":{"type":"boolean"}}})
    assert result=={"ok":True}
    assert "output_config" not in calls

    client=make_llm(AppConfig(llm_provider="anthropic",anthropic_api_key="test-key",anthropic_model="gemma-e4b-agent:latest"))
    assert isinstance(client,AnthropicJSONClient)
    assert client.structured_outputs is False

def test_openai_client_selected_with_config():
    client=make_llm(AppConfig(llm_provider="openai",openai_api_key="test-key",openai_model="gpt-test"))
    assert isinstance(client,OpenAICompatibleClient)
    assert client.model=="gpt-test"

def test_opencode_provider_selected_with_config(monkeypatch):
    monkeypatch.setenv("AUTOANALYST_LLM_PROVIDER","opencode")
    monkeypatch.setenv("OPENCODE_BASE_URL","http://opencode.test:4096/")
    monkeypatch.setenv("OPENCODE_TOKEN","server-token")
    monkeypatch.setenv("OPENCODE_MODEL","anthropic/claude-test")
    client=make_llm(AppConfig.load())
    assert isinstance(client,OpenCodeJSONClient)
    assert client.base_url=="http://opencode.test:4096"
    assert client.model=="anthropic/claude-test"

def test_opencode_stateless_generation_request(monkeypatch):
    import autoanalyst.llm.opencode_client as module
    captured={}
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self): return b'{"data":{"text":"{\\"answer\\":\\"ok\\"}"}}'
    def fake_urlopen(request,timeout):
        captured["url"]=request.full_url; captured["headers"]=request.headers
        captured["body"]=__import__("json").loads(request.data); captured["timeout"]=timeout
        return Response()
    monkeypatch.setattr(module,"urlopen",fake_urlopen)
    client=OpenCodeJSONClient("http://opencode.test:4096","server-token","provider/model",7)
    assert client.complete_json("test",{"value":1},{"type":"object"})=={"answer":"ok"}
    assert captured["url"]=="http://opencode.test:4096/api/experimental/generate/text"
    assert captured["headers"]["Authorization"]=="Bearer server-token"
    assert captured["body"]["model"]=={"providerID":"provider","id":"model"}
    assert captured["timeout"]==7
