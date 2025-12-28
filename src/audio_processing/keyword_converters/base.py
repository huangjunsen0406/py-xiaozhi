# -*- coding: utf-8 -*-
"""Abstract base class for keyword converters."""

from abc import ABC, abstractmethod


class KeywordConverter(ABC):
    @abstractmethod
    def convert(self, text: str) -> str:
        pass

    @abstractmethod
    def can_convert(self, text: str) -> bool:
        pass

    @property
    @abstractmethod
    def language(self) -> str:
        pass

    @property
    @abstractmethod
    def model_path(self) -> str:
        pass

    def to_keywords_file_content(self, text: str) -> str:
        return self.convert(text) + "\n"
