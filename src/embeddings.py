"""Embedding Provider 抽象与本地轻量哈希向量实现。"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Embedding Provider 基类，后续可接入云端 embedding 或向量库。"""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """将文本转换为向量。"""


class HashEmbeddingProvider(EmbeddingProvider):
    """无外部依赖的哈希向量实现，适合 RAG MVP 和单元测试。

    该实现不是成熟语义 embedding，只用于提供可替换的向量检索链路。
    """

    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = max(16, dimensions)

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = self._tokenize(text)
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8", errors="ignore")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return self._normalize(vector)

    @staticmethod
    def cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        return sum(a * b for a, b in zip(left, right))

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        text = (text or "").lower()
        words = re.findall(r"[a-z0-9_]+", text)
        cjk = re.findall(r"[\u4e00-\u9fff]", text)
        cjk_bigrams = [a + b for a, b in zip(cjk, cjk[1:])]
        return words + cjk + cjk_bigrams

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]
