import httpx
import pytest

from app.services import quick_answer_service as quick_answer_module
from app.services.quick_answer_service import QuickAnswerService, get_quick_answer_models


class FakeAsyncClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requested_urls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, **kwargs):
        self.requested_urls.append(url)
        return next(self.responses)


def response(status, payload):
    request = httpx.Request("POST", "https://generativelanguage.googleapis.com")
    return httpx.Response(status, json=payload, request=request)


def test_configured_model_is_first_and_fallbacks_are_deduplicated(monkeypatch):
    monkeypatch.setattr(quick_answer_module.settings, "GEMINI_MODEL", "gemini-1.5-flash")

    models = get_quick_answer_models()

    assert models[0] == "gemini-1.5-flash"
    assert len(models) == len(set(models))
    assert "gemini-2.5-flash" in models


@pytest.mark.asyncio
async def test_answer_falls_back_from_unavailable_model(monkeypatch):
    monkeypatch.setattr(quick_answer_module.settings, "GEMINI_MODEL", "gemini-1.5-flash")
    client = FakeAsyncClient([
        response(404, {"error": {"message": "model not found"}}),
        response(200, {"candidates": [{"content": {"parts": [{"text": "fallback answer"}]}}]}),
    ])
    monkeypatch.setattr(quick_answer_module.httpx, "AsyncClient", lambda **_: client)

    service = QuickAnswerService()
    service._api_key = "test-key"
    result = await service.answer("What is an electric vehicle?")

    assert result["answer"] == "fallback answer"
    assert result["model"] == "gemini-flash-lite-latest"
    assert client.requested_urls[0].endswith("/models/gemini-1.5-flash:generateContent")


@pytest.mark.asyncio
async def test_all_unavailable_models_return_safe_error(monkeypatch):
    monkeypatch.setattr(quick_answer_module.settings, "GEMINI_MODEL", "gemini-1.5-flash")
    client = FakeAsyncClient([
        response(404, {"error": {"message": "model not found"}})
        for _ in get_quick_answer_models()
    ])
    monkeypatch.setattr(quick_answer_module.httpx, "AsyncClient", lambda **_: client)

    service = QuickAnswerService()
    service._api_key = "test-key"

    with pytest.raises(RuntimeError, match="configured model") as exc_info:
        await service.answer("What happens when every model is unavailable?")

    assert "test-key" not in str(exc_info.value)
