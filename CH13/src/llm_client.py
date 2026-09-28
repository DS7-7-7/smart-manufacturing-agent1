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

Qwen3 thinking(추론) 제어:
    - Qwen3 계열은 기본적으로 <think>...</think> 를 생성해 응답이 느려지고
      작은 max_tokens 에서는 답(content)이 비어버린다.
    - 공식 문서 기준, thinking 을 끄는 hard switch 는
      chat_template_kwargs={"enable_thinking": False} 이다.
      (프롬프트의 /no_think 는 soft switch 라 <think> 블록이 남아 효과가 약하다.)
    - 이 모듈은 ollama 백엔드에서 기본으로 thinking 을 끈다.
      켜고 싶으면:  OLLAMA_THINK=1 python xx.py
    - thinking 이 없는 모델(qwen2.5 계열)에는 이 옵션이 무해하게 무시된다.

설치:
    pip install openai
"""

from __future__ import annotations

import os
import json
from typing import Dict, List, Union


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


def _resolve_backend(backend: str | None) -> str:
    return (backend or os.environ.get("LLM_BACKEND", "ollama")).lower()


def _get(backend: str | None):
    backend = _resolve_backend(backend)
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
    user: Union[str, List[Dict[str, str]]],
    *,
    as_json: bool = False,
    temperature: float | None = None,
    max_tokens: int = 1000,
    backend: str | None = None,
) -> Union[str, dict]:
    """
    LLM 을 한 번 호출한다.

    Args:
        system     : 시스템 프롬프트
        user       : 사용자 입력.
                     - str        → 단일 턴 유저 메시지로 처리
                     - list[dict] → 멀티턴 메시지 리스트 그대로 사용
        as_json    : True 면 응답을 JSON(dict)으로 파싱해 반환
        temperature: 생성 온도. None 이면 백엔드별 권장값 자동 적용
                     (Qwen3 non-thinking 권장 0.7; greedy(0)은 무한반복 위험이 있어 피함)
        max_tokens : 최대 생성 토큰
        backend    : "gpt" | "ollama" (None 이면 LLM_BACKEND 환경변수 사용)

    Returns:
        as_json=False → str
        as_json=True  → dict  (파싱 실패 시 빈 dict {})
    """
    backend = _resolve_backend(backend)
    client, cfg = _get(backend)

    # 온도 기본값: 지정 안 하면 0.7 (Qwen3 non-thinking 권장, greedy 무한반복 회피)
    if temperature is None:
        temperature = 0.7

    # user 가 문자열이면 단일 유저 메시지로, 리스트면 그대로 사용 (멀티턴)
    if isinstance(user, str):
        user_messages = [{"role": "user", "content": user}]
    else:
        user_messages = list(user)

    kwargs = dict(
        model=cfg["model"],
        messages=[{"role": "system", "content": system}] + user_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if as_json:
        kwargs["response_format"] = {"type": "json_object"}

    # Qwen3 thinking hard switch:
    #   chat_template_kwargs={"enable_thinking": False} 를 넘겨 thinking 을 끈다.
    #   (Ollama OpenAI 호환 경로는 extra_body 로 전달)
    if backend == "ollama":
        think_on = os.environ.get("OLLAMA_THINK", "0") == "1"
        kwargs["extra_body"] = {
            "chat_template_kwargs": {"enable_thinking": think_on}
        }

    # 지원하지 않는 옵션(extra_body / response_format)은 하나씩 떼고 재시도한다.
    for _ in range(3):
        try:
            resp = client.chat.completions.create(**kwargs)
            break
        except Exception:
            if "extra_body" in kwargs:
                kwargs.pop("extra_body")
                continue
            if "response_format" in kwargs:
                kwargs.pop("response_format")
                continue
            raise
    else:
        return {} if as_json else ""

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
    print("[TEXT]", chat("너는 한 문장으로만 답한다.", "스마트 팩토리가 뭐야?", max_tokens=100))
    print("[JSON]", chat(
        '제품명과 수량을 {"product":..,"qty":..} JSON 으로만 반환하라.',
        "로봇청소기 500개 주문",
        as_json=True,
    ))