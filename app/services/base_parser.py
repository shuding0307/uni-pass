from abc import ABC, abstractmethod
from typing import Any, Iterable

import pdfplumber


class BasePdfParser(ABC):
    """PDF 파서 공통 추상 클래스. open_pdf/extract_text 공통 구현을 제공합니다."""

    def open_pdf(self, path: str):
        return pdfplumber.open(path)

    def extract_text(self, path: str) -> str:
        with self.open_pdf(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)

    def iter_pages(self, path: str) -> Iterable[Any]:
        with self.open_pdf(path) as pdf:
            yield from pdf.pages

    def extract_tables(self, path: str) -> list:
        tables = []
        with self.open_pdf(path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    tables.append(table)
        return tables

    def extract_words(self, path: str) -> list:
        words = []
        with self.open_pdf(path) as pdf:
            for page in pdf.pages:
                words.extend(page.extract_words())
        return words

    @abstractmethod
    def parse(self, path: str, **kwargs):
        ...
