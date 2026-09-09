import asyncio
import os
import sys

# Ensure backend root is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.config.settings import settings
from app.llm.service import get_llm_service
from app.llm.openrouter import OpenRouterLLMProvider


async def main():
    print(f"[OpenRouter Test] Initializing provider with model: {settings.LLM_MODEL or 'openrouter/free'}")
    
    if not settings.OPENROUTER_API_KEY:
        print("[Error] OPENROUTER_API_KEY is not set in .env")
        sys.exit(1)
        
    provider = OpenRouterLLMProvider()
    service = get_llm_service(provider=provider)
    
    print("[OpenRouter Test] Sending test request to OpenRouter API...")
    try:
        response = await service.chat("Respond with the exact words: LLM connection successful")
        print(f"[OpenRouter Test] Response received:\n{response.strip()}\n")
        print("LLM connection successful")
    except Exception as e:
        print(f"[Error] Failed to connect to OpenRouter: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
