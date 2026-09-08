# Bring your own model or API

Each host profile selects a provider. No provider keys are included in this repository, and provider keys stay on the companion, not on the handheld.

## Ollama, local or on your own server

```yaml
hosts:
  - id: local
    name: Local model
    ai_provider: ollama
    ai_url: http://127.0.0.1:11434
    ai_model: YOUR_INSTALLED_MODEL
```

Choose an exact name from `ollama list`. The existing default is Ollama, so older configurations remain compatible.

## OpenAI-compatible chat API

```yaml
hosts:
  - id: api
    name: My API model
    ai_provider: openai-compatible
    ai_url: https://YOUR_PROVIDER_HOST/v1
    ai_model: YOUR_PROVIDER_MODEL_ID
    ai_api_key_env: TDECK_MODEL_API_KEY
```

The companion appends `/chat/completions` to `ai_url`. The endpoint must support non-streaming chat completions with `model`, `messages`, and `max_tokens`, and return `choices[0].message.content` as text. An agent server can be used if it implements that contract; arbitrary proprietary agent APIs are not automatically supported. No tool execution or provider-specific conversation memory is added by this adapter. A local compatible server needing no authentication may omit `ai_api_key_env`.

Store your real key in a private file on the companion, for example `~/.config/tdeck-companion/provider.env`, containing `TDECK_MODEL_API_KEY=your_actual_key`. Set its permissions to 600. Do not paste it into an issue, commit, screenshot or host profile. Add an `EnvironmentFile=/home/YOUR_USER/.config/tdeck-companion/provider.env` line to the companion systemd unit's `[Service]` section, then reload and restart the service. The restricted system-service alternative needs a root-owned environment file accessible to systemd.

On the handheld, use the companion's URL and token, with host ID `api`. The companion token and the model-provider key are different credentials. Hosted model usage follows your provider's billing and data-processing terms.

The compatible adapter is verified with mocked HTTP tests; no third-party paid API or private agent endpoint was exercised for this release. Ollama was additionally tested against a real local model.
