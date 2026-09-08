from typing import List, Dict, Any


class TextChunker:
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not text:
            return []
            
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + self.chunk_size
            chunk_content = text[start:end]
            
            # Find closest sentence break if not at the very end
            if end < text_len:
                last_period = chunk_content.rfind(". ")
                if last_period != -1 and last_period > self.chunk_size // 2:
                    end = start + last_period + 1
                    chunk_content = text[start:end]
            
            chunks.append({
                "content": chunk_content.strip(),
                "metadata": metadata or {},
                "start_idx": start,
                "end_idx": end
            })
            
            start = end - self.overlap
            if start < 0 or start >= text_len:
                break
                
        return chunks


text_chunker = TextChunker()
