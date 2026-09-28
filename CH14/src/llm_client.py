# -*- coding: utf-8 -*-
"""
llm_client.py — 교재 공용 LLM 클라이언트
=========================================

교재의 모든 예제(CHxx)에서 import 해서 쓰는 단일 LLM 호출 모듈.

지원 백엔드 (환경변수 LLM_BACKEND 로 선택, 기본 ollama):
    gpt    : OpenAI API          (OPENAI_API_KEY 필요)
    ollama : 로컬 Ollama 서버     (설치만 되어 있으면 됨)

두 백엔드 모두 OpenAI 호환이라 openai SDK 하나로 처리한다.
→ 코드는 그대로 두고, 환경변수만 바꾸면 백엔드가 바뀐다.

설치:
    pip install openai

사용:
    from llm_client import chat

    # 1) 일반 텍스트
    print(chat("너는 친절한 비서다.", "안녕?"))

    # 2) JSON 강제 (dict 반환)
    data = chat('제품명과 수량을 JSON으로만 반환하라.',
                "로봇청소기 500개", as_json=True)

백엔드 전환 예:
    LLM_BACKEND=ollama OLLAMA_MODEL=qwen3:8b    python xx.py
    LLM_BACKEND=gpt    OPENAI_MODEL=gpt-4o-mini python xx.py
"""

from __future__ import annotations

import os
import json


# ---------------------------------------------------------------------------
# 백엔드별 설정
# ---------------------------------------------------------------------------
def _config(backend: str) -> dict:
    backend = backend.lower()
    if backend == "gpt":
        return {
            "base_url": "https://api.openai.com/v1",
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "api_key": os.environ.get("OPENAI_API_KEY", ""),
        }
    if backend == "ollama":
        return {
            "base_url": os.environ.get("OLLAMA_BASE", "http://localhost:11434/v1"),
            "model": os.environ.get("OLLAMA_MODEL", "qwen3:8b"),
            "api_key": "ollama",  # Ollama 는 키를 검증하지 않음
        }
    raise ValueError(f"알 수 없는 backend: {backend} (gpt | ollama)")


# 백엔드별로 client 를 한 번만 만들어 재사용
_clients: dict = {}


def _get(backend: str | None):
    backend = (backend or os.environ.get("LLM_BACKEND", "ollama")).lower()
    if backend not in _clients:
        from openai import OpenAI
        cfg = _config(backend)
        client = OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"] or "EMPTY")
        _clients[backend] = (client, cfg)
    return _clients[backend]


# ---------------------------------------------------------------------------
# 공개 함수: chat
# ---------------------------------------------------------------------------
def chat(
    system: str,
    user: str,
    *,
    as_json: bool = False,
    temperature: float = 0.0,
    max_tokens: int = 1000,
    backend: str | None = None,
) -> str | dict:
    """
    LLM 을 한 번 호출한다.

    Args:
        system     : 시스템 프롬프트
        user       : 사용자 입력
        as_json    : True 면 응답을 JSON(dict)으로 파싱해 반환
        temperature: 생성 온도 (기본 0 = 결정적)
        max_tokens : 최대 생성 토큰
        backend    : "gpt" | "ollama" (None 이면 LLM_BACKEND 환경변수 사용)

    Returns:
        as_json=False → str
        as_json=True  → dict  (파싱 실패 시 빈 dict {})
    """
    client, cfg = _get(backend)

    kwargs = dict(
        model=cfg["model"],
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if as_json:
        kwargs["response_format"] = {"type": "json_object"}

    # response_format 을 지원하지 않는 서버/모델이면 빼고 한 번 더 시도
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception:
        kwargs.pop("response_format", None)
        resp = client.chat.completions.create(**kwargs)

    text = (resp.choices[0].message.content or "").strip()

    if not as_json:
        return text

    # JSON 파싱 (```json 감싸기·앞뒤 잡텍스트 방어)
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):text.rfind("}") + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# 단독 실행 시: 간단 동작 확인
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"[LLM_BACKEND] {os.environ.get('LLM_BACKEND', 'ollama')}")
    print("-" * 40)
    print("[TEXT]", chat("너는 한 문장으로만 답한다.", "스마트 팩토리가 뭐야?"))
    print("[JSON]", chat(
        '제품명과 수량을 {"product":..,"qty":..} JSON 으로만 반환하라.',
        "로봇청소기 500개 주문",
        as_json=True,
    ))
