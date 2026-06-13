"""RAG MVP 数据模型测试。"""

from src.rag import RagManager


def test_rag_collection_document_chunk_search(tmp_path):
    db_path = tmp_path / "rag.db"
    rag = RagManager(str(db_path))

    collection_id = rag.create_collection("测试知识库", "说明")
    document_id = rag.add_document(collection_id, "guide.md", "text/markdown")
    chunk_id = rag.add_chunk(document_id, 0, "这是关于 VLM 图文问答助手的部署说明。")

    results = rag.keyword_search("部署")

    assert collection_id
    assert document_id
    assert chunk_id
    assert len(results) == 1
    assert results[0]["filename"] == "guide.md"


def test_rag_ingest_text_splits_and_searches(tmp_path):
    db_path = tmp_path / "rag.db"
    rag = RagManager(str(db_path))
    text = "部署说明 " * 220

    document_id, chunk_count = rag.ingest_text("默认知识库", "manual.pdf", text, "application/pdf")
    results = rag.keyword_search("部署说明", limit=3)

    assert document_id
    assert chunk_count > 1
    assert results
    assert all(r["filename"] == "manual.pdf" for r in results)


def test_rag_semantic_search_returns_scored_results(tmp_path):
    db_path = tmp_path / "rag.db"
    rag = RagManager(str(db_path))
    collection_id = rag.create_collection("默认知识库")
    doc_id = rag.add_document(collection_id, "deploy.md")
    rag.add_chunk(doc_id, 0, "这里介绍 Docker 部署和健康检查。")
    rag.add_chunk(doc_id, 1, "这里介绍图片颜色识别。")

    results = rag.semantic_search("部署健康检查", limit=1)

    assert len(results) == 1
    assert results[0]["score"] > 0
    assert "部署" in results[0]["content"]


def test_rag_get_or_create_collection_reuses_existing(tmp_path):
    db_path = tmp_path / "rag.db"
    rag = RagManager(str(db_path))

    first = rag.get_or_create_collection("默认知识库")
    second = rag.get_or_create_collection("默认知识库")

    assert first == second


def test_rag_list_documents_and_chunks(tmp_path):
    db_path = tmp_path / "rag.db"
    rag = RagManager(str(db_path))
    collection_id = rag.create_collection("默认知识库")
    doc_id = rag.add_document(collection_id, "manual.pdf", "application/pdf")
    rag.add_chunk(doc_id, 0, "第一段部署说明")
    rag.add_chunk(doc_id, 1, "第二段健康检查")

    documents = rag.list_documents("默认知识库")
    chunks = rag.list_chunks(doc_id)

    assert len(documents) == 1
    assert documents[0]["filename"] == "manual.pdf"
    assert documents[0]["chunk_count"] == 2
    assert [c["chunk_index"] for c in chunks] == [0, 1]


def test_rag_format_references():
    references = RagManager.format_references([
        {
            "filename": "manual.pdf",
            "chunk_index": 2,
            "score": 0.876,
            "content": "这是一个很长的引用内容" * 20,
        }
    ], max_excerpt_chars=30)

    assert "**引用来源**" in references
    assert "`manual.pdf` 第 2 段" in references
    assert "相似度 0.88" in references
    assert "..." in references


def test_rag_delete_document_removes_chunks(tmp_path):
    db_path = tmp_path / "rag.db"
    rag = RagManager(str(db_path))
    collection_id = rag.create_collection("默认知识库")
    doc_id = rag.add_document(collection_id, "manual.pdf")
    rag.add_chunk(doc_id, 0, "部署说明")

    assert rag.delete_document(doc_id) is True
    assert rag.list_documents("默认知识库") == []
    assert rag.list_chunks(doc_id) == []


def test_rag_clear_collection_removes_only_target_collection(tmp_path):
    db_path = tmp_path / "rag.db"
    rag = RagManager(str(db_path))
    first_collection = rag.create_collection("默认知识库")
    second_collection = rag.create_collection("其他知识库")
    first_doc = rag.add_document(first_collection, "a.pdf")
    second_doc = rag.add_document(second_collection, "b.pdf")
    rag.add_chunk(first_doc, 0, "默认知识库内容")
    rag.add_chunk(second_doc, 0, "其他知识库内容")

    removed = rag.clear_collection("默认知识库")

    assert removed == 1
    assert rag.list_documents("默认知识库") == []
    assert len(rag.list_documents("其他知识库")) == 1


def test_rag_document_owner_filtering(tmp_path):
    db_path = tmp_path / "rag.db"
    rag = RagManager(str(db_path))
    collection_id = rag.create_collection("默认知识库")
    user_a_doc = rag.add_document(collection_id, "a.pdf", owner_user_id="user-a")
    user_b_doc = rag.add_document(collection_id, "b.pdf", owner_user_id="user-b")
    rag.add_chunk(user_a_doc, 0, "用户A的部署说明")
    rag.add_chunk(user_b_doc, 0, "用户B的部署说明")

    docs = rag.list_documents("默认知识库", owner_user_id="user-a")
    search_results = rag.semantic_search("部署说明", owner_user_id="user-a")

    assert len(docs) == 1
    assert docs[0]["filename"] == "a.pdf"
    assert search_results
    assert all(r["owner_user_id"] == "user-a" for r in search_results)


def test_rag_delete_document_requires_matching_owner(tmp_path):
    db_path = tmp_path / "rag.db"
    rag = RagManager(str(db_path))
    collection_id = rag.create_collection("默认知识库")
    doc_id = rag.add_document(collection_id, "a.pdf", owner_user_id="user-a")
    rag.add_chunk(doc_id, 0, "用户A内容")

    assert rag.delete_document(doc_id, owner_user_id="user-b") is False
    assert rag.delete_document(doc_id, owner_user_id="user-a") is True


def test_rag_clear_collection_filters_owner(tmp_path):
    db_path = tmp_path / "rag.db"
    rag = RagManager(str(db_path))
    collection_id = rag.create_collection("默认知识库")
    user_a_doc = rag.add_document(collection_id, "a.pdf", owner_user_id="user-a")
    user_b_doc = rag.add_document(collection_id, "b.pdf", owner_user_id="user-b")
    rag.add_chunk(user_a_doc, 0, "用户A内容")
    rag.add_chunk(user_b_doc, 0, "用户B内容")

    removed = rag.clear_collection("默认知识库", owner_user_id="user-a")

    assert removed == 1
    docs = rag.list_documents("默认知识库")
    assert len(docs) == 1
    assert docs[0]["owner_user_id"] == "user-b"
