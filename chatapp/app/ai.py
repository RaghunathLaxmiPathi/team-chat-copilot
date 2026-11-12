"""Connection to a language model for Copilot.

Providers:
- ollama: a model running on this computer (default). Chat text never leaves the machine.
- azure_openai: your organization's Azure OpenAI resource. Chat text IS sent to that resource, so use it only
  after a data-protection review (architecture note R-21). It needs CHATAPP_AI_ENDPOINT, CHATAPP_AI_API_KEY and
  CHATAPP_AI_MODEL (the deployment name).
- none: no model. Copilot falls back to its simple built-in answers.
"""
import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

log = logging.getLogger("chatapp.ai")


class AiError(Exception):
    """The model could not be reached or returned nothing usable."""


@dataclass
class AiRequest:
    system: str
    messages: list = field(default_factory=list)  # [{"role": "user" | "assistant", "content": str}]
    fallback: str = ""  # the simple built-in answer, used if the model cannot be reached


def _post(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (configured endpoint)
            return json.loads(response.read(2_000_000))
    except Exception as exc:
        raise AiError(f"{type(exc).__name__}") from None


class OllamaBackend:
    name = "ollama"

    def __init__(self, endpoint: str, model: str, timeout: float, max_tokens: int):
        self.endpoint = endpoint.rstrip("/")
        self.model, self.timeout, self.max_tokens = model, timeout, max_tokens
        host = urllib.parse.urlparse(self.endpoint).hostname or ""
        self.is_local = host in ("127.0.0.1", "localhost", "::1")

    def complete(self, req: AiRequest) -> str:
        body = _post(
            self.endpoint + "/api/chat",
            {"model": self.model, "stream": False, "keep_alive": "30m",  # keep the model loaded between replies
             "messages": [{"role": "system", "content": req.system}] + req.messages,
             "options": {"temperature": 0.4, "num_predict": self.max_tokens}},
            {}, self.timeout,
        )
        text = ((body.get("message") or {}).get("content") or "").strip()
        if not text:
            raise AiError("empty reply")
        return text


class AzureOpenAIBackend:
    name = "azure_openai"
    is_local = False

    def __init__(self, endpoint: str, model: str, api_key: str, timeout: float, max_tokens: int):
        self.endpoint = endpoint.rstrip("/")
        self.model, self.api_key, self.timeout, self.max_tokens = model, api_key, timeout, max_tokens

    def complete(self, req: AiRequest) -> str:
        body = _post(
            f"{self.endpoint}/openai/deployments/{urllib.parse.quote(self.model)}/chat/completions?api-version=2024-06-01",
            {"messages": [{"role": "system", "content": req.system}] + req.messages,
             "max_tokens": self.max_tokens, "temperature": 0.4},
            {"api-key": self.api_key}, self.timeout,
        )
        try:
            text = (body["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError):
            raise AiError("unexpected reply") from None
        if not text:
            raise AiError("empty reply")
        return text


def build_backend(settings):
    provider = (settings.ai_provider or "none").lower()
    if provider == "ollama":
        backend = OllamaBackend(settings.ai_endpoint, settings.ai_model, settings.ai_timeout_s, settings.ai_max_tokens)
    elif provider == "azure_openai":
        if not (settings.ai_endpoint.startswith("https://") and settings.ai_api_key and settings.ai_model):
            log.warning("ai_disabled", extra={"event": "ai_disabled", "code": "azure_openai needs an https endpoint, key and model"})
            return None
        backend = AzureOpenAIBackend(settings.ai_endpoint, settings.ai_model, settings.ai_api_key,
                                     settings.ai_timeout_s, settings.ai_max_tokens)
    else:
        return None
    log.info("ai_backend", extra={"event": "ai_backend", "code": f"{backend.name} local={backend.is_local}"})
    return backend
