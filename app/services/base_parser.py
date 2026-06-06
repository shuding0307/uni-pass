from abc import ABC, abstractmethod
import pdfplumber


class BasePdfParser(ABC):
    """PDF 파서 공통 추상 클래스. open_pdf/extract_text 공통 구현을 제공합니다."""

    def open_pdf(self, path: str):
        return pdfplumber.open(path)

    def extract_text(self, path: str) -> str:
        with self.open_pdf(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)

    @abstractmethod
    def parse(self, path: str, **kwargs):
        ...
