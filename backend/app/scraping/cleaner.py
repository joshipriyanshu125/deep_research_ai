import re
from bs4 import BeautifulSoup


class HTMLCleaner:
    def clean(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        
        soup = BeautifulSoup(raw_html, "html.parser")
        
        # Remove unwanted script, style, nav, footer tags
        for element in soup(["script", "style", "nav", "footer", "aside", "header", "form", "noscript", "svg"]):
            element.decompose()
            
        text = soup.get_text(separator="\n")
        # Collapse multi-newlines and leading/trailing whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)
        return re.sub(r"\n{3,}", "\n\n", cleaned)


html_cleaner = HTMLCleaner()
