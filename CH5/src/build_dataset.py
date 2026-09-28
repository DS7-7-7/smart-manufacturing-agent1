# -*- coding: utf-8 -*-
"""
build_dataset.py
================
원본 MVTec screw 데이터를 '정상/불량' 분류 학습용으로 재구성한다.
(데이터 준비 전용 — 한 번만 실행하면 된다. 학습은 train_screw.py)

데이터 구성 (각 클래스 20장, 파일 번호로 고정 분할):
    정상(good)      : test/good        의 000~019
    불량(defective) : test/scratch_head 의 000~019
      -> 000~014 (15장) = train,  015~019 (5장) = test

결과:
  screw_2class/
  |- train/{good, defective}   각 15장
  |- test/ {good, defective}   각 5장
"""

import re
import shutil
from pathlib import Path

# ===========================================================================
# 설정 (경로만 본인 환경에 맞게 바꾸면 됨)
# ===========================================================================
SRC = Path("/home/a202192012/5.Agent_System/프로젝트/스마트제조_AI_Agent_교제코드/CH5/data/screw")   # 원본 데이터
DST = Path("/home/a202192012/5.Agent_System/프로젝트/스마트제조_AI_Agent_교제코드/CH5/data/screw_2class")    # 재구성 저장 위치

GOOD_DIR = SRC / "test" / "good"            # 정상 이미지 폴더
DEFECT_DIR = SRC / "test" / "scratch_head"  # 불량 이미지 폴더 (하나만 사용)

TRAIN_MAX = 14      # 번호 0~14 -> train (15장)
TEST_MAX = 19       # 번호 15~19 -> test (5장), 20번 이상은 사용 안 함


def _file_num(path: Path) -> int:
    """'032.png' -> 32"""
    m = re.search(r"(\d+)", path.stem)
    return int(m.group(1)) if m else -1


def build_dataset():
    if DST.exists():
        shutil.rmtree(DST)     # 반복 실행 시 깨끗이 다시 생성

    sources = {"good": GOOD_DIR, "defective": DEFECT_DIR}
    counts = {"train": {}, "test": {}}

    for label, folder in sources.items():
        imgs = sorted(p for p in folder.iterdir()
                      if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"))
        for src in imgs:
            n = _file_num(src)
            if n <= TRAIN_MAX:
                split = "train"
            elif n <= TEST_MAX:
                split = "test"
            else:
                continue        # 20번 이상은 버림
            out_dir = DST / split / label
            out_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, out_dir / src.name)
            counts[split][label] = counts[split].get(label, 0) + 1

    print(f"[재구성] train {counts['train']}, test {counts['test']}")
    print(f"          -> {DST}")


if __name__ == "__main__":
    build_dataset()