# 자율 에이전트 실습 (12장)

## 실습 개요

Qwen2.5 모델을 로컬 Ollama로 실행하고, ReAct 프레임워크로 자율 에이전트를 만들어
"이번 달 불량률이 3% 증가했다. 원인을 분석하고 대책을 세워라"라는 미션을
스스로 해결하게 만든다.

에이전트가 [생각 → MES/GraphRAG 검색 → 원인 분석 → 결론] 단계를 밟아가는 과정이
콘솔 로그로 눈에 보인다.

LLM 호출은 `llm_client` 모듈이 담당한다. 환경변수 `LLM_BACKEND` 하나로 백엔드를
바꿀 수 있고, 이 실습에서는 기본값인 **Ollama** 를 사용한다.

---

## 파일 구성

```
factory_agent_practice/
├── README.md              # 이 파일
├── requirements.txt       # 프로젝트 의존성 정의
├── llm_client.py          # 공용 LLM 클라이언트 (백엔드 추상화)
├── test_connection.py     # LLM 연결 테스트
├── tools.py               # 에이전트가 사용할 도구 정의
├── agent.py               # ReAct 에이전트 생성
└── run_mission.py         # 미션 실행 (메인 스크립트)
```

---

## 시스템 요구 사양

Ollama로 Qwen2.5를 돌리므로 요구 사양이 낮다.
GPU가 있으면 가속되지만, 없어도 CPU로 (느리게) 동작한다.

### 모델별 대략적 메모리 (GPU VRAM 기준)
- `qwen2.5:7b`  → VRAM 6~8GB 권장 (RTX 3060 12GB급이면 충분)
- `qwen2.5:14b` → VRAM 12~16GB 권장
- `qwen2.5:3b`  → 저사양/CPU 환경용 (단, ReAct 형식 준수가 불안정할 수 있음)

### 권장
- RAM 16GB 이상
- SSD 여유 공간 20GB 이상 (모델 파일 저장)

> 참고: ReAct 에이전트는 모델이 Thought/Action/Action Input 형식을 정확히
> 지켜야 안정적으로 동작한다. 가능하면 **7B 이상 instruct 모델**을 쓴다.

---

## 실행 순서

### 1. Ollama 설치 및 모델 준비

Ollama를 설치한다. (https://ollama.com/download)

설치 후 사용할 모델을 미리 받아둔다:
```bash
ollama pull qwen2.5:7b
```

받아둔 모델 목록 확인:
```bash
ollama list
```

여기 표시되는 태그(예: `qwen2.5:7b`)를 그대로 `OLLAMA_MODEL` 에 지정하면 된다.
Ollama 서버는 설치 시 자동으로 백그라운드에서 실행된다 (기본 포트 11434).

### 2. 파이썬 가상환경 및 의존성 설치

프로젝트 폴더에서 가상환경을 만들고 활성화한다.

Linux/Mac:
```bash
cd factory_agent_practice
python -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
cd factory_agent_practice
python -m venv .venv
.venv\Scripts\Activate.ps1
```

의존성을 설치한다:
```bash
pip install -r requirements.txt
```

`requirements.txt` 예시:
```
openai
langchain
langchain-openai
```

### 3. 연결 테스트

LLM과의 연결이 정상인지 확인한다.

```bash
OLLAMA_MODEL=qwen2.5:7b python test_connection.py
```

정상이면 모델이 자기소개를 반환한다.

> `LLM_BACKEND` 는 기본이 `ollama` 라 생략해도 된다.
> 모델명을 매번 붙이기 싫으면 셸 프로필이나 `.env` 에 `OLLAMA_MODEL` 을 넣어둔다.

Windows PowerShell에서는 환경변수 지정 방식이 다르다:
```powershell
$env:OLLAMA_MODEL="qwen2.5:7b"; python test_connection.py
```

### 4. 미션 실행

```bash
OLLAMA_MODEL=qwen2.5:7b python run_mission.py
```

에이전트가 미션을 받고 스스로 사고 과정을 로그로 출력한다.
Thought → Action → Observation 사이클을 여러 번 반복하며 결론에 도달한다.

---

## 백엔드 바꾸기 (선택)

코드는 그대로 두고 환경변수만 바꾸면 다른 LLM 백엔드로 전환된다.

```bash
# 기본: 로컬 Ollama
LLM_BACKEND=ollama OLLAMA_MODEL=qwen2.5:7b python run_mission.py

# LM Studio (로컬)
LLM_BACKEND=lmstudio python run_mission.py

# OpenAI API
LLM_BACKEND=gpt OPENAI_API_KEY=sk-... python run_mission.py
```

`test_connection.py`, `agent.py` 는 모두 `llm_client.backend_config()` 를 통해
같은 백엔드 설정을 공유하므로, 한 곳(`LLM_BACKEND`)만 바꾸면 전부 따라간다.

---

## 실행 예시 출력

```
============================================================
미션: 이번 달 불량률이 3% 증가했다. 원인을 분석하고 대책을 세워라.
============================================================

> Entering new AgentExecutor chain...

Thought: 이번 달 불량률이 3% 증가했다고 한다. 먼저 어느 라인에서
증가했는지 확인해야 한다.

Action: query_mes_data
Action Input: 이번 달 라인별 불량률

Observation: 이번 달 라인별 불량률 (지난달 대비):
- 라인 A: 2.1% → 2.3% (변화 미미)
- 라인 B: 1.8% → 5.2% (급증)
- 라인 C: 2.0% → 2.1% (변화 미미)

Thought: 라인 B의 불량률이 급증했다. 관련 설비를 조회한다.

... (계속) ...

Final Answer:
[원인 분석]
- 라인 B 불량률 급증 (1.8% → 5.2%)
- 추정 원인: 신규 공급업체 X사의 다이 표면 조도 미달
- 근거: 2024-03 동일 부품·동일 공급업체 유사 사례 존재

[대책 제안]
1. 즉시 조치: 다이 D-2201 표면 조도(Ra) 재측정
2. 단기 조치: X사에 검사 성적서 요구
3. 재발 방지: 신규 공급업체 부품 표준 검증 프로세스 정립

> Finished chain.
```

---

## 실전 배포로 확장하기

`tools.py`의 함수 내부만 실제 API 호출로 교체하면 나머지 코드는 그대로 쓴다.

- `query_mes_data` → 실제 MES REST API 또는 SDK 호출
- `graphrag_search` → 9장 GraphRAG 파이프라인(Neo4j + Cypher)에 연결
- `check_defect_type` → QMS(품질관리시스템)의 결함 분류 DB 조회

---

## 문제 해결

### 연결 실패 (Connection refused)
- Ollama 서버가 실행 중인지 확인: `ollama list` 가 정상 응답하는지 본다.
- 포트 확인: 기본은 `http://localhost:11434/v1` 이다.
  다른 포트면 `OLLAMA_BASE` 환경변수로 지정한다.

### `model not found`
`OLLAMA_MODEL` 태그가 실제 받아둔 모델과 일치하지 않는 경우다.
`ollama list` 로 정확한 태그를 확인해 그대로 넣는다.
필요하면 먼저 `ollama pull qwen2.5:7b` 로 받는다.

### 응답이 너무 느릴 때
- GPU가 인식되는지 확인한다. GPU 없이 CPU로만 돌면 느리다.
- 더 작은 모델로 낮춘다 (단, 3B 이하는 ReAct 형식 준수가 불안정).

### 모델 다운로드가 매우 느릴 때
- 네트워크 상태를 확인하고, 필요 시 시간을 두고 재시도한다
  (`ollama pull` 은 중단 지점부터 이어받는다).

### 에이전트가 무한 루프에 빠지거나 형식이 자주 깨질 때
- `agent.py`의 `max_iterations` 값을 낮춘다 (기본 10).
- 모델이 Thought/Action 형식을 못 지키는 경우가 잦으면 더 큰 instruct 모델
  (예: `qwen2.5:14b`)로 교체한다.