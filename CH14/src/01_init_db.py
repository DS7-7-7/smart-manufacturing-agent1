"""
01_init_db.py
=============
가상 ERP 데이터베이스(SQLite) 및 테이블 생성

03_erp_models.py 에 정의된 SQLAlchemy 모델을 읽어
실제 DB 파일(erp.db)과 11개 테이블을 만든다.

역할 분담
    03_erp_models.py  →  "무엇을" 저장할지 (테이블 구조 정의)
    01_init_db.py     →  "어디에" 저장할지 (실제 DB 파일 + 연결/세션 관리)

다른 파일에서는 아래를 import 해서 사용한다.
    from importlib import import_module
    init_db = import_module("01_init_db")
    with init_db.get_session() as session:
        ...
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from importlib import import_module

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# 파일명이 숫자로 시작해 일반 import가 안 되므로 importlib 사용
erp_models = import_module("03_erp_models")
Base = erp_models.Base


# ---------------------------------------------------------------------------
# DB 경로 및 엔진 설정
# ---------------------------------------------------------------------------
# 이 파일(src/)의 상위 폴더(CH14) 밑의 data 폴더에 erp.db 를 생성한다.
#   CH14/
#   ├── src/   ← 이 파일 위치
#   └── data/  ← erp.db 저장 위치
SRC_DIR = os.path.dirname(os.path.abspath(__file__))          # .../CH14/src
PROJECT_DIR = os.path.dirname(SRC_DIR)                        # .../CH14
DATA_DIR = os.path.join(PROJECT_DIR, "data")                  # .../CH14/data
os.makedirs(DATA_DIR, exist_ok=True)                          # data 폴더 없으면 생성

DB_PATH = os.path.join(DATA_DIR, "erp.db")
DB_URL = f"sqlite:///{DB_PATH}"

# echo=True 로 바꾸면 실행되는 SQL이 콘솔에 출력된다 (학습 시 유용).
engine = create_engine(DB_URL, echo=False, future=True)

# 세션 팩토리: 이 SessionLocal() 을 호출하면 새 세션이 만들어진다.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# ---------------------------------------------------------------------------
# 세션 헬퍼
# ---------------------------------------------------------------------------
@contextmanager
def get_session() -> Session:
    """
    with 문으로 안전하게 세션을 쓰기 위한 헬퍼.

        with get_session() as session:
            session.add(obj)
        # 블록을 정상 종료하면 자동 commit, 예외 발생 시 자동 rollback

    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 테이블 생성 / 초기화
# ---------------------------------------------------------------------------
def create_tables() -> None:
    """모델에 정의된 모든 테이블을 생성한다 (이미 있으면 건너뜀)."""
    Base.metadata.create_all(engine)


def drop_tables() -> None:
    """모든 테이블을 삭제한다 (실습 초기화용)."""
    Base.metadata.drop_all(engine)


def reset_database() -> None:
    """DB를 깨끗한 상태로 초기화한다 (전체 삭제 후 재생성)."""
    drop_tables()
    create_tables()


# ---------------------------------------------------------------------------
# 단독 실행 시: DB 파일과 테이블을 생성한다.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"DB 파일 경로: {DB_PATH}")
    reset_database()

    # 생성된 테이블 목록 확인
    from sqlalchemy import inspect
    tables = inspect(engine).get_table_names()
    print(f"생성된 테이블 수: {len(tables)}")
    for t in sorted(tables):
        print(f"  - {t}")
    print("ERP 데이터베이스 초기화 완료.")