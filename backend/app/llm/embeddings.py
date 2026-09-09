import numpy as np
from typing import List, Optional
from app.config.settings import settings
from app.utils.logger import logger
import httpx


class EmbeddingService:
    def __init__(self, api_key: Optional[str] = None, model: str = settings.EMBEDDING_MODEL):
        self.api_key = api_key or settings.OPENAI_API_KEY or settings.OPENROUTER_API_KEY
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1" if (settings.OPENROUTER_API_KEY and not settings.OPENAI_API_KEY) else "https://api.openai.com/v1"

    async def get_embedding(self, text: str) -> List[float]:
        if not self.api_key:
            # Generate deterministic pseudo-embedding for testing / fallback
            np.random.seed(abs(hash(text)) % (2**32))
            vec = np.random.randn(384).astype(np.float32)
            norm = np.linalg.norm(vec)
            return (vec / (norm + 1e-9)).tolist()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"input": text, "model": self.model}
                )
                if res.status_code == 200:
                    return res.json()["data"][0]["embedding"]
        except Exception as e:
            logger.warning(f"Embedding request failed: {e}. Using deterministic vector.")

        np.random.seed(abs(hash(text)) % (2**32))
        vec = np.random.randn(384).astype(np.float32)
        norm = np.linalg.norm(vec)
        return (vec / (norm + 1e-9)).tolist()


embedding_service = EmbeddingService()
