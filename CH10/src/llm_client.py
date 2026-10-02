# -*- coding: utf-8 -*-
"""
llm_client.py — 교재 공용 LLM 클라이언트
=========================================

교재의 모든 예제(extract.py 등)에서 import 해서 쓰는 단일 LLM 호출 모듈.

지원 백엔드 (환경변수 LLM_BACKEND 로 선택, 기본 ollama):
    gpt      : OpenAI API          (OPENAI_API_KEY 필요)
    ollama   : 로컬 Ollama 서버     (설치만 되어 있으면 됨)
    lmstudio : 로컬 LM Studio 서버
    vllm     : 로컬 vLLM 서버
    sglang   : 로컬 SGLang 서버

모든 백엔드가 OpenAI 호환 /v1/chat/completions 규격이라 openai SDK 하나로 처리한다.
→ 코드는 그대로 두고, 환경변수(LLM_BACKEND)만 바꾸면 백엔드가 바뀐다.

모델 자동탐색(auto):
    - 로컬 서버(sglang/vllm/lmstudio)는 model 을 "auto" 로 두면
      /v1/models 에 물어 첫 모델 id 를 자동으로 쓴다.
    - 즉 base_url 만 맞으면 모델명을 몰라도 굴러간다.

Qwen3 thinking(추론) 제어:
    - Qwen3 계열은 기본적으로 <think>...</think> 를 생성해 응답이 느려지고
      작은 max_tokens 에서는 답(content)이 비어버린다.
    - 공식 문서 기준, thinking 을 끄는 hard switch 는
      chat_template_kwargs={"enable_thinking": False} 이다.
      (프롬프트의 /no_think 는 soft switch 라 <think> 블록이 남아 효과가 약하다.)
    - 이 모듈은 로컬 백엔드(gpt 제외)에서 기본으로 thinking 을 끈다.
      켜고 싶으면:  OLLAMA_THINK=1 python xx.py
    - thinking 이 없는 모델(qwen2.5 계열)에는 이 옵션이 무해하게 무시된다.

보안 메모:
    API 키 '값'은 이 파일에 저장하지 않는다. 환경변수(OPENAI_API_KEY 등)에서 읽는다.
    로컬 서버는 키가 필요 없으므로 더미값이 들어간다.

설치:
    pip install openai
"""

from __future__ import annotations

import os
import re
import json
from typing import Dict, List, Union


# ---------------------------------------------------------------------------
# 백엔드별 설정
# ---------------------------------------------------------------------------
def _config(backend: str) -> dict:
    backend = backend.lower()
    if backend in ("gpt", "openai"):
        return {
            "base_url": os.environ.get("OPENAI_BASE", "https://api.openai.com/v1"),
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "api_key": os.environ.get("OPENAI_API_KEY", ""),
            "local": False,
        }
    if backend == "ollama":
        return {
            "base_url": os.environ.get("OLLAMA_BASE", "http://localhost:11434/v1"),
            "model": os.environ.get("OLLAMA_MODEL", "qwen3:8b"),
            "api_key": "ollama",  # Ollama 는 키를 검증하지 않음
            "local": True,
        }
    if backend == "lmstudio":
        return {
            "base_url": os.environ.get("LMSTUDIO_BASE", "http://localhost:1234/v1"),
            "model": os.environ.get("LMSTUDIO_MODEL", "auto"),
            "api_key": "lmstudio",
            "local": True,
        }
    if backend == "vllm":
        return {
            "base_url": os.environ.get("VLLM_BASE", "http://localhost:8000/v1"),
            "model": os.environ.get("VLLM_MODEL", "auto"),
            "api_key": "vllm",
            "local": True,
        }
    if backend == "sglang":
        return {
            "base_url": os.environ.get("SGLANG_BASE", "http://localhost:8000/v1"),
            "model": os.environ.get("SGLANG_MODEL", "auto"),
            "api_key": "sglang",
            "local": True,
        }
    raise ValueError(
        f"알 수 없는 backend: {backend} (gpt | ollama | lmstudio | vllm | sglang)"
    )


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


def _model_id(client, cfg: dict) -> str:
    """
    사용할 모델 id 결정.
    cfg["model"] 이 'auto'/빈값이면 서버(/v1/models)에 물어 첫 모델을 쓴다.
    (SGLang/vLLM 은 보통 --model-path 경로가 그대로 모델 id 가 된다.)
    결과는 cfg 에 캐시해 매 호출마다 조회하지 않는다.
    """
    if cfg.get("_resolved_model"):
        return cfg["_resolved_model"]
    m = (cfg.get("model") or "").strip()
    if not m or m.lower() == "auto":
        ids = [x.id for x in client.models.list().data]
        if not ids:
            raise RuntimeError("서버에 서빙 중인 모델이 없습니다.")
        m = ids[0]
    cfg["_resolved_model"] = m
    return m


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
        temperature: 생성 온도. None 이면 자동
                     (추출 작업은 재현성을 위해 0.0 을 기본으로 쓴다)
        max_tokens : 최대 생성 토큰
        backend    : "gpt" | "ollama" | "lmstudio" | "vllm" | "sglang"
                     (None 이면 LLM_BACKEND 환경변수 사용)

    Returns:
        as_json=False → str
        as_json=True  → dict  (파싱 실패 시 빈 dict {})
    """
    backend = _resolve_backend(backend)
    client, cfg = _get(backend)

    # 온도 기본값: 추출 재현성을 위해 0.0
    if temperature is None:
        temperature = 0.0

    # user 가 문자열이면 단일 유저 메시지로, 리스트면 그대로 사용 (멀티턴)
    if isinstance(user, str):
        user_messages = [{"role": "user", "content": user}]
    else:
        user_messages = list(user)

    kwargs = dict(
        model=_model_id(client, cfg),
        messages=[{"role": "system", "content": system}] + user_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if as_json:
        kwargs["response_format"] = {"type": "json_object"}

    # Qwen3 thinking hard switch:
    #   chat_template_kwargs={"enable_thinking": False} 를 넘겨 thinking 을 끈다.
    #   (OpenAI 호환 경로는 extra_body 로 전달) — 로컬 백엔드에서만 시도.
    if cfg.get("local"):
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

    return _loads_lenient(text)


def extract_json(
    system: str,
    user: Union[str, List[Dict[str, str]]],
    *,
    backend: str | None = None,
) -> Union[dict, list]:
    """chat(as_json=True) 의 별칭. 표면적으로 dict/list 를 돌려준다."""
    return chat(system, user, as_json=True, backend=backend)


# ---------------------------------------------------------------------------
# JSON 파서 (```json``` 코드펜스·<think> 블록·앞뒤 잡텍스트 방어)
# ---------------------------------------------------------------------------
def _loads_lenient(text: str):
    text = (text or "").strip()
    if not text:
        return {}
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)  # 추론흔적 제거
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 가장 바깥 { } 또는 [ ] 덩어리를 잡아본다
        m = re.search(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                return {}
        return {}


# ---------------------------------------------------------------------------
# 편의 함수: 연결 확인 / 모델 목록
# ---------------------------------------------------------------------------
def list_models(backend: str | None = None) -> list[str]:
    """서버가 서빙 중인 모델 id 목록 (/v1/models)."""
    client, _ = _get(backend)
    return [m.id for m in client.models.list().data]


def ping(backend: str | None = None) -> str:
    return chat("You are a health check.", "Reply with exactly: OK", backend=backend)


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