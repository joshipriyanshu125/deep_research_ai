"""
Day 14 — PDF Extractor
Extracts clean text and metadata (title, author, creation date, page count)
from PDF binary streams using pypdf.
"""
import io
import re
from typing import Dict, Any, Optional
from app.utils.logger import logger


class PDFExtractor:
    """
    Extracts text and document metadata from PDF files and byte streams.
    Never raises exceptions on corrupt or encrypted files.
    """

    def extract(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Extract text, title, author, and date from PDF bytes.
        """
        if not pdf_bytes or not isinstance(pdf_bytes, (bytes, bytearray)):
            return {
                "text": "",
                "title": "",
                "author": None,
                "date": None,
                "page_count": 0,
                "success": False,
                "is_pdf": True,
                "error": "Empty or invalid PDF byte stream",
            }

        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            
            # Check for encryption
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    logger.warning("PDF is encrypted and could not be decrypted with empty password.")
                    return {
                        "text": "",
                        "title": "",
                        "author": None,
                        "date": None,
                        "page_count": len(reader.pages) if reader.pages else 0,
                        "success": False,
                        "is_pdf": True,
                        "error": "Encrypted PDF file",
                    }

            page_texts = []
            for idx, page in enumerate(reader.pages):
                try:
                    p_text = page.extract_text()
                    if p_text:
                        page_texts.append(p_text.strip())
                except Exception as pe:
                    logger.warning(f"Error extracting page {idx} from PDF: {pe}")

            full_text = "\n\n".join(page_texts).strip()

            # Metadata extraction
            title = ""
            author = None
            date_str = None

            if reader.metadata:
                title = (reader.metadata.title or "").strip()
                author = reader.metadata.author
                raw_date = reader.metadata.creation_date
                if raw_date:
                    # pypdf returns datetime object or date string
                    if hasattr(raw_date, "strftime"):
                        date_str = raw_date.strftime("%Y-%m-%d")
                    else:
                        match = re.search(r"D:(\d{4})(\d{2})(\d{2})", str(raw_date))
                        if match:
                            date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                        else:
                            date_str = str(raw_date)[:10]

            return {
                "text": full_text,
                "title": title,
                "author": author,
                "date": date_str,
                "page_count": len(reader.pages),
                "success": bool(full_text),
                "is_pdf": True,
                "error": None if full_text else "No text found in PDF",
            }

        except Exception as e:
            logger.warning(f"Failed to parse PDF stream: {e}")
            return {
                "text": "",
                "title": "",
                "author": None,
                "date": None,
                "page_count": 0,
                "success": False,
                "is_pdf": True,
                "error": f"PDF parsing error: {e}",
            }


pdf_extractor = PDFExtractor()
