# RAG 知识库检索问题排查记录

## 问题现象

用户上传 PDF 后，知识库 UI 显示存在文档记录，但模型回答时无法引用或读取该文档内容。

## 排查结论

本次排查确认：

- 知识库数据库路径正常：`data/sessions/sessions.db`
- 上传目录和临时目录权限正常：`data/uploads`、`data/temp_images`
- RAG 已启用：`ENABLE_RAG=true`
- 数据库表存在：`rag_collections`、`rag_documents`、`rag_chunks`
- 异常数据特征：`rag_documents` 有文档记录，但 `rag_chunks` 为 0，`embedding` 为 0

审计日志显示 PDF 文本解析成功，但 RAG 入库失败：

```text
parse_document success chars=1455
rag_ingest_document failed: 'utf-8' codec can't encode characters ... surrogates not allowed
```

## 根因

部分 PDF 文本抽取结果中包含非法 Unicode 代理字符（surrogate）。这些字符在后续流程中会导致：

- 本地 hash embedding 计算时 `token.encode("utf-8")` 失败
- SQLite 写入文本或 embedding 时编码失败
- 旧版入库流程先写入 `rag_documents`，后写入 `rag_chunks`，失败后留下“indexed 但 0 chunks”的不可检索脏文档

由于模型实际读取的是检索到的文本切片，而不是直接读取 PDF 文件路径，因此没有切片就不会有知识库上下文注入模型 prompt。

## 修复方案

已实施以下修复：

- 在 PDF 文本抽取后清洗非法 Unicode 字符：`ImageProcessor.sanitize_extracted_text()`
- 在 RAG 入库前再次清洗文本：`RagManager._sanitize_text()`
- embedding token 编码使用 `errors="ignore"`，避免异常字符中断索引
- `ingest_text()` 改为事务式写入，文档和切片一起成功或一起失败，避免半成功脏数据
- 新增 `cleanup_empty_documents()` 清理历史遗留的 0 切片文档
- 应用启动时自动清理当前用户下的无切片 RAG 文档

## 验证结果

已通过以下验证：

- `tests/test_rag.py` 新增非法 Unicode 入库测试
- `tests/test_rag.py` 新增 0 切片文档清理测试
- 小文本、大文本、含异常 Unicode 的 PDF 抽取文本均可生成切片并被检索
- 当前本地历史 0 切片文档已清理
- 质量门禁通过：`89 passed`
- 前端构建通过，依赖审计 0 漏洞
- 应用内 `_build_rag_context()` 可返回包含来源文件名的上下文和引用

## 后续注意

- 当前 UI 文件解析能力主要支持 PDF；Word、Excel、CSV、Markdown 还未接入上传解析链路。
- 扫描版 PDF 如果无法提取文本，会返回“未能从 PDF 中提取到文本”，需要后续接入 OCR。
- 如果知识库显示文档但无法检索，应优先检查：
  - `rag_documents` 是否有记录
  - `rag_chunks` 是否有对应切片
  - `rag_chunks.embedding` 是否非空
  - `audit_logs` 中是否存在 `rag_ingest_failed`
