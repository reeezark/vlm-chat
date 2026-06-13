"""Embedding Provider 测试。"""

from src.embeddings import HashEmbeddingProvider


def test_hash_embedding_is_normalized_and_stable():
    provider = HashEmbeddingProvider(dimensions=32)

    left = provider.embed("部署说明")
    right = provider.embed("部署说明")

    assert left == right
    assert len(left) == 32
    assert HashEmbeddingProvider.cosine_similarity(left, right) > 0.99


def test_hash_embedding_similarity_for_related_text():
    provider = HashEmbeddingProvider(dimensions=64)

    query = provider.embed("部署")
    related = provider.embed("这是部署说明文档")
    unrelated = provider.embed("图片颜色识别")

    assert HashEmbeddingProvider.cosine_similarity(query, related) > HashEmbeddingProvider.cosine_similarity(query, unrelated)
