# -*- coding: utf-8 -*-
"""BPE converter for English wake words."""

import re
from pathlib import Path
from typing import Dict, List, Optional

from .base import KeywordConverter


class BpeConverter(KeywordConverter):

    def __init__(self, tokens_path: Optional[str] = None):
        self._tokens_path = tokens_path
        self._token_to_id: Optional[Dict[str, int]] = None

    def _get_tokens_path(self) -> Path:
        if self._tokens_path:
            return Path(self._tokens_path)

        # Default path: models/en/tokens.txt
        from src.utils.resource_finder import get_app_root
        return get_app_root() / "models" / "en" / "tokens.txt"

    def _load_tokens(self):
        """Load tokens from tokens.txt file."""
        if self._token_to_id is not None:
            return

        tokens_path = self._get_tokens_path()
        if not tokens_path.exists():
            raise FileNotFoundError(f"BPE tokens file not found: {tokens_path}")

        self._token_to_id = {}

        with open(tokens_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    token = parts[0]
                    token_id = int(parts[-1])
                    self._token_to_id[token] = token_id

    @property
    def language(self) -> str:
        return "en"

    @property
    def model_path(self) -> str:
        return "models/en"

    def can_convert(self, text: str) -> bool:
        chinese_pattern = re.compile(r"[\u4e00-\u9fff]")
        has_chinese = bool(chinese_pattern.search(text))
        has_letters = bool(re.search(r"[a-zA-Z]", text))
        return not has_chinese and has_letters

    def _greedy_tokenize(self, text: str) -> List[str]:
        tokens = []
        i = 0

        while i < len(text):
            matched = False

            max_len = min(20, len(text) - i)
            for length in range(max_len, 0, -1):
                substr = text[i:i + length]

                if substr in self._token_to_id:
                    tokens.append(substr)
                    i += length
                    matched = True
                    break

            if not matched:
                char = text[i]
                if char in self._token_to_id:
                    tokens.append(char)
                else:
                    tokens.append("<unk>")
                i += 1

        return tokens

    def convert(self, text: str) -> str:
        self._load_tokens()

        normalized = text.strip().upper()
        words = normalized.split()

        processed_words = [f"▁{word}" for word in words]

        all_tokens = []
        for word in processed_words:
            tokens = self._greedy_tokenize(word)
            all_tokens.extend(tokens)

        bpe_str = " ".join(all_tokens)
        return f"{bpe_str} @{normalized}"
