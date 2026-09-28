# -*- coding: utf-8 -*-
"""
naive_rag.py  [9장] 일반 RAG
원천 문서를 그대로 벡터화 → 질문과 유사한 top-k 청크만 회수 → LLM이 답변.
임베더는 교체형: 기본 sentence-transformers, 없으면(오프라인) TF-IDF 자동 폴백.
"""
import os, glob

_HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(_HERE, "..", "corpus")
NAIVE_SYS = ("너는 제조 라인 엔지니어다. 아래 '문서 발췌'에 담긴 내용만 근거로 답하라. "
             "발췌에 없는 내용은 추측하지 말고 모른다고 하라.")


def load_chunks(corpus_dir=CORPUS_DIR):
    """문서 1개 = 청크 1개. (top-k로 '문서 일부만 회수'되는 상황을 만들기 위함)"""
    chunks = []
    for p in sorted(glob.glob(os.path.join(corpus_dir, "*.md"))):
        chunks.append((os.path.basename(p), open(p, encoding="utf-8").read()))
    return chunks


class Retriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.texts = [t for _, t in chunks]
        self._fit()

    def _fit(self):
        try:                                   # 1순위: 로컬 임베딩
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            self.mat = self.model.encode(self.texts, normalize_embeddings=True)
            self.backend = "sentence-transformers"
        except Exception:                      # 폴백: 오프라인 TF-IDF
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.model = TfidfVectorizer()
            self.mat = self.model.fit_transform(self.texts)
            self.backend = "tfidf(offline)"

    def search(self, query, k=2):
        if self.backend.startswith("sentence"):
            import numpy as np
            q = self.model.encode([query], normalize_embeddings=True)[0]
            sims = self.mat @ q
        else:
            from sklearn.metrics.pairwise import cosine_similarity
            sims = cosine_similarity(self.model.transform([query]), self.mat)[0]
        order = sims.argsort()[::-1][:k]
        return [(self.chunks[i][0], self.chunks[i][1], float(sims[i])) for i in order]


def answer(query, chat_fn, retriever, k=2):
    """chat_fn(system, user, **kw) -> str 콜백으로 답변 생성."""
    hits = retriever.search(query, k)
    ctx = "\n\n".join(f"[{src}]\n{txt}" for src, txt, _ in hits)
    resp = chat_fn(NAIVE_SYS, f"문서 발췌:\n{ctx}\n\n질문: {query}")
    return resp, hits


if __name__ == "__main__":
    r = Retriever(load_chunks())
    print("임베더:", r.backend)
    for src, _, s in r.search("에어컴프레서가 고장 나면 어디에 영향?", 2):
        print(f"  회수 {s:.3f}  {src}")