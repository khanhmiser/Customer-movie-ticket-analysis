"""RAG: chia đoạn, tìm kiếm, chặn số bịa - chạy hoàn toàn offline (không gọi Gemini)."""

from types import SimpleNamespace

import pytest

from src import gemini, rag
from src.llm import LLMUnavailable


def test_chunk_markdown_keeps_heading_path_and_ignores_code_comments():
    text = ("# Tài liệu\n\n## 1. Cài đặt\nCài Anaconda rồi chạy lệnh dưới đây để cài thư viện.\n"
            "```bash\n# comment trong lệnh, không phải tiêu đề\npip install -r requirements.txt\n```\n"
            "### 1.1 Kiểm tra\nChạy pytest để chắc chắn mọi thứ hoạt động đúng như mong đợi.\n")
    chunks = rag.chunk_markdown(text, "docs/x.md", "X")
    assert [c.title for c in chunks] == ["1. Cài đặt", "1. Cài đặt › 1.1 Kiểm tra"]
    assert "# comment trong lệnh" in chunks[0].text


def test_long_section_is_split_without_losing_text():
    paras = [f"Đoạn số {i}: " + "nội dung " * 40 for i in range(8)]
    chunks = rag.chunk_markdown("## Dài\n" + "\n\n".join(paras), "a.md", "A")
    assert len(chunks) > 1 and all(len(c.text) <= rag.MAX_CHARS for c in chunks)
    assert sum(c.text.count("Đoạn số") for c in chunks) == 8


def test_collect_chunks_covers_docs_notebooks_and_briefs():
    sources = {c.source for c in rag.collect_chunks()}
    assert "docs/runbook.md" in sources
    assert any(s.startswith("notebooks/") for s in sources)


@pytest.fixture(scope="module")
def keyword_index():
    return rag.build_index(use_embeddings=False)


def test_keyword_search_finds_answer_document(keyword_index):
    """Không có API key vẫn tìm đúng tài liệu (TF-IDF) cho mọi câu trong bộ đánh giá."""
    rows = rag.eval_retrieval(keyword_index)
    assert rows and all(r["hit"] for r in rows)


def test_invented_number_is_blocked(keyword_index):
    fake = lambda q, hits: {"found": True, "answer": "Model đạt AUC 0.93 [1].", "citations": [1]}
    res = rag.answer(keyword_index, "AUC của model rủi ro thanh toán?", generator=fake)
    assert res["status"] == "blocked" and "0.93" in res["note"]


def test_supported_answer_passes_and_maps_citations(keyword_index):
    fake = lambda q, hits: {"found": True, "answer": "AUC 0.77 so với 0.75 của luật 1 biến [1].", "citations": [1, 99]}
    res = rag.answer(keyword_index, "AUC của model rủi ro thanh toán so với luật 1 biến?", generator=fake)
    assert res["status"] == "answered"
    assert [i for i, _ in res["sources"]] == [1]  # trích dẫn ngoài phạm vi bị bỏ


def test_without_gemini_falls_back_to_search_only(keyword_index):
    res = rag.answer(keyword_index, "Pipeline dừng vì dữ liệu lỗi thì làm gì?")
    assert res["status"] == "search_only" and res["hits"]
    with pytest.raises(LLMUnavailable):
        gemini.client()


class _FakeModels:
    """Giả lập Gemini: model 'busy' hết hạn mức, model khác trả lời bình thường."""
    def __init__(self):
        self.called = []

    def generate_content(self, model, contents, config):
        self.called.append(model)
        if model.startswith("busy"):
            raise gemini.ModelBusy("hết hạn mức gọi (429)")
        return SimpleNamespace(text='{"found": true, "answer": "ok [1]", "citations": [1]}')


def test_gemini_falls_back_to_next_model():
    """Dùng chung cho RAG và Text-to-SQL."""
    client = SimpleNamespace(models=_FakeModels())
    out = rag.generate("q", [], client=client, models=["busy-1", "busy-2", "good"])
    assert out["model"] == "good" and client.models.called == ["busy-1", "busy-2", "good"]
    with pytest.raises(LLMUnavailable, match="busy-1"):
        gemini.generate_json("s", "q", {}, models=["busy-1", "busy-2"], client_=SimpleNamespace(models=_FakeModels()))
