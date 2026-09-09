import pytest
import asyncio
from app.llm.service import LLMService, get_llm_service, llm_service
from app.llm.provider import MockLLMProvider


@pytest.mark.asyncio
async def test_llm_service_generate():
    service = LLMService(provider=MockLLMProvider())
    res = await service.generate("test prompt")
    assert isinstance(res, str)
    assert len(res) > 0


@pytest.mark.asyncio
async def test_llm_service_chat():
    service = LLMService(provider=MockLLMProvider())
    res = await service.chat("hello world")
    assert isinstance(res, str)
    assert len(res) > 0


@pytest.mark.asyncio
async def test_llm_service_summarize():
    service = LLMService(provider=MockLLMProvider())
    res = await service.summarize("This is a long text about artificial intelligence and research.")
    assert isinstance(res, str)
    assert len(res) > 0


@pytest.mark.asyncio
async def test_llm_service_extract():
    service = LLMService(provider=MockLLMProvider())
    res = await service.extract("Sample text for entity extraction", schema_description="{'entities': list}")
    assert isinstance(res, str)
    assert "{" in res or "[" in res


@pytest.mark.asyncio
async def test_llm_service_classify():
    service = LLMService(provider=MockLLMProvider())
    res = await service.classify("This is a paper about neural networks", categories=["academic", "web", "market"])
    assert isinstance(res, str)
    assert "{" in res or "[" in res


@pytest.mark.asyncio
async def test_llm_service_generate_parsed_json():
    service = LLMService(provider=MockLLMProvider())
    res = await service.generate_parsed_json("decompose query into sub-questions")
    assert isinstance(res, (dict, list))


def test_llm_service_singleton():
    assert llm_service is not None
    assert isinstance(llm_service, LLMService)
    assert repr(llm_service).startswith("<LLMService")
