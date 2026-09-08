import json
import httpx
import pytest
from tdeck_companion.ai import chat_host
from tdeck_companion.config import HostProfile

@pytest.mark.asyncio
async def test_compatible_api_uses_server_environment(monkeypatch):
    monkeypatch.setenv('TEST_PROVIDER_KEY','test-placeholder-not-a-real-key')
    seen=[]
    def respond(request):
        seen.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':'reply'}}]})
    real=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(respond),**kw))
    h=HostProfile(id='api',name='API',ai_provider='openai-compatible',ai_url='https://example.invalid/v1',ai_model='chosen-model',ai_api_key_env='TEST_PROVIDER_KEY')
    assert await chat_host(h,'hello')=='reply'
    assert str(seen[0].url)=='https://example.invalid/v1/chat/completions'
    assert seen[0].headers['authorization']=='Bearer test-placeholder-not-a-real-key'
    assert json.loads(seen[0].content)['model']=='chosen-model'
    assert 'api_key' not in json.loads(seen[0].content)

@pytest.mark.asyncio
async def test_missing_credential_fails_without_network(monkeypatch):
    monkeypatch.delenv('TEST_PROVIDER_KEY',raising=False)
    h=HostProfile(id='api',name='API',ai_provider='openai-compatible',ai_api_key_env='TEST_PROVIDER_KEY')
    with pytest.raises(RuntimeError,match='environment variable is missing'):
        await chat_host(h,'hello')
