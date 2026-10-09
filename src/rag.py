"""Hỏi đáp trên tài liệu & báo cáo của project (RAG) bằng Gemini.

Luồng: tài liệu (docs/, README, data dictionary, phần chữ của notebook, bản tin tuần)
-> chia đoạn theo tiêu đề -> nhúng vector (Gemini embedding, có cache) + TF-IDF
-> tìm kết hợp 2 cách (Reciprocal Rank Fusion) -> Gemini trả lời CHỈ từ các đoạn tìm được, kèm trích dẫn [n]
-> kiểm tra số: số nào trong câu trả lời không có trong các đoạn trích -> chặn, chỉ hiện đoạn trích.

Không có key / GEMINI_MODE=off: vẫn tìm được bằng TF-IDF (không gọi API), chỉ không viết câu trả lời.

    python -m src.rag build                 # làm mới chỉ mục (chỉ nhúng đoạn mới / đã đổi)
    python -m src.rag ask "câu hỏi"
    python -m src.rag eval [--retrieval-only]
"""

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from src.briefs import SMALL_NUMBERS, numbers_in
from src import gemini
from src.config import DATA_DIR, EVAL_DIR, GEMINI_MODELS, RAG_EMBED_MODEL, REPORTS_DIR, ROOT
from src.llm import LLMUnavailable

RAG_DIR = DATA_DIR / "rag"
CACHE_PATH = RAG_DIR / "embeddings.npz"
EMBED_DIM = 768
MAX_CHARS = 1500  # đoạn dài hơn -> tách theo đoạn văn
TOP_K = 6

DOC_LABELS = {
    "README.md": "README (tổng quan project)",
    "docs/runbook.md": "Runbook vận hành",
    "docs/data_workflow.md": "Luồng dữ liệu & định nghĩa chỉ số",
    "docs/huong_dan_phong_ban.md": "Hướng dẫn cho phòng ban",
    "docs/ai_usage_log.md": "Nhật ký sử dụng AI",
    "data/marts/data_dictionary.md": "Từ điển dữ liệu",
    "CHANGELOG.md": "Lịch sử thay đổi",
}
DEPARTMENT_VI = {"leadership": "Ban lãnh đạo", "marketing": "Marketing", "customer_care": "CSKH",
                 "product_it": "Product / IT", "finance": "Tài chính"}


@dataclass
class Chunk:
    source: str   # đường dẫn tương đối, vd. docs/runbook.md
    label: str    # tên hiển thị của tài liệu
    title: str    # đường dẫn tiêu đề, vd. "4. Khi pipeline DỪNG vì dữ liệu lỗi"
    text: str

    @property
    def key(self):
        return hashlib.sha1(f"{self.source}\n{self.title}\n{self.text}".encode("utf-8")).hexdigest()

    @property
    def search_text(self):
        return f"{self.label} › {self.title}\n{self.text}"


# ------------------------------------------------------------------ Chia đoạn
HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")


def _split_long(text, max_chars=MAX_CHARS):
    """Tách đoạn quá dài theo đoạn văn (dòng trống); không cắt giữa bảng / đoạn văn."""
    if len(text) <= max_chars:
        return [text]
    parts, current = [], ""
    for para in re.split(r"\n\s*\n", text):
        if current and len(current) + len(para) + 2 > max_chars:
            parts.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        parts.append(current)
    return parts


def chunk_markdown(text, source, label):
    """Chia markdown theo tiêu đề (# .. ####); mỗi đoạn mang đường dẫn tiêu đề của nó.

    Dòng bắt đầu bằng # bên trong khối ``` (comment của lệnh bash) không được tính là tiêu đề.
    """
    chunks, path, lines, in_code = [], [], [], False

    def flush():
        body = "\n".join(lines).strip()
        if len(body) >= 40:  # bỏ đoạn chỉ có 1-2 chữ
            heads = [h for lv, h in path if lv > 1] or [h for _, h in path]
            title = " › ".join(heads) or label
            chunks.extend(Chunk(source, label, title, part) for part in _split_long(body))
        lines.clear()

    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            path = [(lv, h) for lv, h in path if lv < level] + [(level, m.group(2).strip())]
        else:
            lines.append(line)
    flush()
    return chunks


def _notebook_markdown(path):
    nb = json.loads(path.read_text(encoding="utf-8"))
    return "\n\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown")


def _source_paths(root=ROOT, reports_dir=REPORTS_DIR):
    docs = [root / rel for rel in DOC_LABELS if (root / rel).exists()]
    return docs + sorted((root / "notebooks").glob("0*.ipynb")) + sorted((reports_dir / "weekly").glob("*/brief_*.md"))


def source_fingerprint(root=ROOT, reports_dir=REPORTS_DIR):
    """Danh sách (file, thời điểm sửa) của mọi nguồn - đổi khi có bản tin mới hoặc tài liệu bị sửa."""
    return tuple((p.as_posix(), p.stat().st_mtime_ns) for p in _source_paths(root, reports_dir))


def collect_chunks(root=ROOT, reports_dir=REPORTS_DIR):
    chunks = []
    for rel, label in DOC_LABELS.items():
        p = root / rel
        if p.exists():
            chunks += chunk_markdown(p.read_text(encoding="utf-8"), rel, label)
    for p in sorted((root / "notebooks").glob("0*.ipynb")):
        label = f"Notebook {p.stem}"
        chunks += chunk_markdown(_notebook_markdown(p), f"notebooks/{p.name}", label)
    for p in sorted((reports_dir / "weekly").glob("*/brief_*.md")):
        week, dept = p.parent.name, p.stem.removeprefix("brief_")
        text = "\n".join(l for l in p.read_text(encoding="utf-8").splitlines() if not l.startswith("_Nguồn:"))
        label = f"Bản tin tuần {week} · {DEPARTMENT_VI.get(dept, dept)}"
        chunks += chunk_markdown(text, p.relative_to(root).as_posix(), label)
    return chunks


# ------------------------------------------------------------------ Gemini
def _normalize(m):
    m = np.asarray(m, dtype=np.float32)
    return m / np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-9, None)


def embed(texts, task_type, client=None, batch=50):
    """Vector đã chuẩn hóa (output_dimensionality < 3072 thì Gemini không tự chuẩn hóa)."""
    from google.genai import types
    client = client or gemini.client()
    config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBED_DIM,
                                      http_options=types.HttpOptions(timeout=gemini.TIMEOUT_MS))
    out = []
    for i in range(0, len(texts), batch):
        r = gemini.call(lambda: client.models.embed_content(model=RAG_EMBED_MODEL, contents=texts[i:i + batch], config=config))
        out += [e.values for e in r.embeddings]
    return _normalize(out)


# ------------------------------------------------------------------ Chỉ mục & tìm kiếm
class Index:
    def __init__(self, chunks, vectors=None):
        self.chunks = chunks
        self.vectors = vectors  # None = chỉ có TF-IDF
        # Từ + cụm 2 từ: tiếng Việt mỗi âm tiết là 1 "từ", cụm 2 âm tiết bắt được từ ghép ("thanh toán")
        self.tfidf = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, token_pattern=r"(?u)\b\w+\b")
        self.matrix = self.tfidf.fit_transform([c.search_text for c in chunks])

    @property
    def mode(self):
        return "vector + từ khóa" if self.vectors is not None else "từ khóa (TF-IDF)"

    def search(self, question, k=TOP_K, query_vector=None, client=None):
        """Trả về [(Chunk, điểm)] theo Reciprocal Rank Fusion của vector và TF-IDF."""
        lex = (self.matrix @ self.tfidf.transform([question]).T).toarray().ravel()
        rankings = [np.argsort(-lex)]
        if self.vectors is not None:
            if query_vector is None:
                query_vector = embed([question], "RETRIEVAL_QUERY", client=client)[0]
            rankings.append(np.argsort(-(self.vectors @ query_vector)))
        score = np.zeros(len(self.chunks))
        for order in rankings:
            score[order] += 1.0 / (60 + np.arange(1, len(order) + 1))
        best = np.argsort(-score)[:k]
        return [(self.chunks[i], float(score[i])) for i in best]


def build_index(chunks=None, use_embeddings=None, client=None, cache_path=CACHE_PATH):
    """Chỉ nhúng đoạn chưa có trong cache -> tài liệu đổi thì chỉ trả phí cho phần đổi."""
    chunks = chunks if chunks is not None else collect_chunks()
    use_embeddings = gemini.enabled() if use_embeddings is None else use_embeddings
    if not use_embeddings:
        return Index(chunks)
    cache = {}
    if cache_path.exists():
        data = np.load(cache_path)
        cache = dict(zip(data["keys"].tolist(), data["vectors"]))
    missing = [c for c in chunks if c.key not in cache]
    if missing:
        for c, v in zip(missing, embed([c.search_text for c in missing], "RETRIEVAL_DOCUMENT", client=client)):
            cache[c.key] = v
        keep = {c.key for c in chunks}  # bỏ vector của đoạn đã xóa khỏi tài liệu
        keys = [k for k in cache if k in keep]
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache_path, keys=np.array(keys), vectors=np.stack([cache[k] for k in keys]))
    return Index(chunks, np.stack([cache[c.key] for c in chunks]))


# ------------------------------------------------------------------ Trả lời
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["found", "answer", "citations"],
}

SYSTEM_PROMPT = """Bạn là trợ lý trả lời câu hỏi về hệ thống báo cáo vận hành của nền tảng bán vé xem phim online.
Chỉ dùng thông tin trong các ĐOẠN TRÍCH được cung cấp - không dùng kiến thức bên ngoài, không suy đoán.
- Trả lời bằng tiếng Việt, ngắn gọn, đi thẳng vào câu hỏi; dùng gạch đầu dòng khi có nhiều ý.
- Sau mỗi ý ghi nguồn dạng [1], [2] theo số thứ tự đoạn trích.
- Con số phải chép ĐÚNG như trong đoạn trích; không tự tính, không làm tròn, không đổi đơn vị.
- Đoạn trích tiếng Anh thì dịch ý sang tiếng Việt.
- Nếu các đoạn trích không đủ để trả lời: found = false và answer giải thích ngắn tài liệu thiếu gì.
- citations: số thứ tự các đoạn trích đã dùng."""

CITATION_RE = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")


def build_prompt(question, hits):
    blocks = [f"[{i}] ({c.label} › {c.title})\n{c.text}" for i, (c, _) in enumerate(hits, 1)]
    return "ĐOẠN TRÍCH:\n\n" + "\n\n---\n\n".join(blocks) + f"\n\nCÂU HỎI: {question}"


def unsupported_numbers(answer, hits):
    """Số trong câu trả lời không xuất hiện trong đoạn trích (bỏ qua số trích dẫn [n])."""
    allowed = set().union(*(numbers_in(c.search_text) for c, _ in hits)) | SMALL_NUMBERS
    used = numbers_in(CITATION_RE.sub("", answer))
    return sorted(n for n in used if n not in allowed and n.rstrip("%") not in allowed)


def generate(question, hits, client=None, models=GEMINI_MODELS):
    """Gemini trả lời từ các đoạn trích; kết quả kèm `model` đã trả lời (thử lần lượt `models`)."""
    return gemini.generate_json(SYSTEM_PROMPT, build_prompt(question, hits), ANSWER_SCHEMA, models=models, client_=client)


def answer(index, question, k=TOP_K, client=None, generator=None):
    """Trả về dict: status (answered | not_found | blocked | search_only), answer, sources, hits, note.

    generator(question, hits) -> {"found", "answer", "citations"}; mặc định gọi Gemini.
    """
    query_vector = None
    if index.vectors is not None:
        try:
            query_vector = embed([question], "RETRIEVAL_QUERY", client=client)[0]
        except LLMUnavailable:
            index = Index(index.chunks)  # không nhúng được câu hỏi -> tìm bằng từ khóa
    hits = index.search(question, k=k, query_vector=query_vector)
    out = {"question": question, "hits": hits, "answer": None, "sources": [], "note": "", "model": None}
    try:
        result = (generator or (lambda q, h: generate(q, h, client=client)))(question, hits)
    except LLMUnavailable as exc:
        return {**out, "status": "search_only", "note": f"Chưa dùng được Gemini ({exc}) - chỉ hiện đoạn tài liệu liên quan."}
    out["model"] = result.get("model")
    cited = sorted({i for i in result.get("citations", []) if 1 <= i <= len(hits)})
    out["sources"] = [(i, hits[i - 1][0]) for i in cited]
    if not result.get("found"):
        return {**out, "status": "not_found", "answer": result.get("answer", "")}
    bad = unsupported_numbers(result["answer"], hits)
    if bad:
        return {**out, "status": "blocked",
                "note": f"Câu trả lời có số không có trong tài liệu ({', '.join(bad)}) nên bị chặn - xem đoạn trích bên dưới."}
    return {**out, "status": "answered", "answer": result["answer"]}


# ------------------------------------------------------------------ Đánh giá
def load_eval(path=EVAL_DIR / "rag_eval.json"):
    return json.loads(path.read_text(encoding="utf-8"))


def eval_retrieval(index, questions=None, k=TOP_K, client=None):
    """Hit@k: có đoạn nào thuộc tài liệu chứa đáp án (`sources`) trong k đoạn tìm được (chỉ câu có đáp án)."""
    rows = []
    for q in questions or load_eval():
        if not q["sources"]:
            continue
        hits = index.search(q["question"], k=k, client=client)
        rank = next((i for i, (c, _) in enumerate(hits, 1) if c.source in q["sources"]), None)
        rows.append({"id": q["id"], "hit": rank is not None, "rank": rank})
    return rows


def eval_answers(index, questions=None, client=None):
    """Câu có đáp án: đúng khi trả lời được, có trích dẫn và chứa mọi cụm bắt buộc (`must_include`).
    Câu ngoài phạm vi (`sources` rỗng): đúng khi trả lời 'không có trong tài liệu'."""
    rows = []
    for q in questions or load_eval():
        res = answer(index, q["question"], client=client)
        text = (res["answer"] or "").lower()
        if q["sources"]:
            ok = res["status"] == "answered" and bool(res["sources"]) and all(s.lower() in text for s in q["must_include"])
        else:
            ok = res["status"] == "not_found"
        rows.append({"id": q["id"], "status": res["status"], "correct": ok, "answer": res["answer"], "note": res["note"]})
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    p_ask = sub.add_parser("ask")
    p_ask.add_argument("question")
    p_eval = sub.add_parser("eval")
    p_eval.add_argument("--retrieval-only", action="store_true")
    args = parser.parse_args()

    index = build_index()
    print(f"Chỉ mục: {len(index.chunks)} đoạn · tìm kiếm: {index.mode}")
    if args.cmd == "ask":
        res = answer(index, args.question)
        print(f"\n[{res['status']}] {res['note']}\n{res['answer'] or ''}\n")
        for i, c in res["sources"] or list(enumerate((c for c, _ in res["hits"]), 1)):
            print(f"  [{i}] {c.label} › {c.title}")
    elif args.cmd == "eval":
        ret = eval_retrieval(index)
        print(f"Tìm đúng tài liệu trong top {TOP_K}: {sum(r['hit'] for r in ret)}/{len(ret)}")
        for r in ret:
            print(f"  {r['id']}: {'hạng ' + str(r['rank']) if r['hit'] else 'TRƯỢT'}")
        if not args.retrieval_only:
            rows = eval_answers(index)
            done = [r for r in rows if r["status"] != "search_only"]  # search_only = API lỗi, không phải trả lời sai
            print(f"Trả lời đúng: {sum(r['correct'] for r in done)}/{len(done)} câu gọi được Gemini"
                  f" ({len(rows) - len(done)} câu lỗi API)")
            for r in rows:
                verdict = "LỖI API" if r["status"] == "search_only" else ("đúng" if r["correct"] else "SAI")
                print(f"  {r['id']}: {verdict} ({r['status']}) {r['note']}")
                if not r["correct"] and r["answer"]:
                    print("     " + r["answer"].replace("\n", "\n     "))


if __name__ == "__main__":
    main()
