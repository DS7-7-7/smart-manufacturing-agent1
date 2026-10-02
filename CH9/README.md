A설비가 고장 나면 후속 공정 중 어디에 연쇄 타격(도미노 효과)이 올까?"라는 복잡한 질문을 던져보고, 
일반 RAG와 GraphRAG의 답변 품질을 비교해 보며 GraphRAG의 똑똑함을 체감하기


## [실습] 설비 고장에 따른 공정 연쇄 영향 분석 — RAG vs GraphRAG

### 1. 실습 목표
- "A설비가 고장 나면 후속 공정 중 어디에 연쇄 타격(도미노 효과)이 올까?"와 같은 **멀티홉 질의**를 수행한다.
- 일반 RAG와 GraphRAG의 검색 및 답변 결과를 비교한다.
- 설비–공정–제품 간 **관계 구조를 활용하는 GraphRAG의 장점**을 확인한다.

### 2. 실습 시나리오
> 생산라인에서 A설비가 고장 났다고 가정한다.  
> A설비가 담당하는 공정부터 후속 공정, 최종 제품까지 영향을 추적한다.

**예시 관계**
```text
A설비
 └─ 담당 → 가공공정 1
             └─ 선행 → 조립공정 2
                         └─ 선행 → 검사공정 3
                                     └─ 생산 → 제품 B

                                     ch13_domino_rag/
├── data/
│   ├── manufacturing_process.md
│   ├── equipment.md
│   └── relations.md
│
├── src/
│   ├── document_loader.py
│   ├── vector_store.py
│   ├── knowledge_graph.py
│   ├── rag.py
│   ├── graph_rag.py
│   ├── llm.py
│   └── main.py
│
├── requirements.txt
└── README.md