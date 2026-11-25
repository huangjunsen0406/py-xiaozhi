# -*- coding: utf-8 -*-
"""Abstract base class for keyword converters."""

from abc import ABC, abstractmethod


class KeywordConverter(ABC):
    @abstractmethod
    def convert(self, text: str) -> str:
        pass

    @property
    @abstractmethod
    def model_path(self) -> str:
        pass
