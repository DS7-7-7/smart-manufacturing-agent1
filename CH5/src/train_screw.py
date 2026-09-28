# -*- coding: utf-8 -*-
"""
train_screw.py
==============
MobileNetV2 전이학습으로 '정상 나사 / 불량 나사'를 분류한다.

* 데이터 준비는 build_dataset.py 가 먼저 담당한다.
  이 파일은 재구성된 screw_2class/ 폴더를 읽어 '학습'만 한다.

  실행 순서:
      python build_dataset.py              # (1회) 데이터 재구성
      python train_screw.py                # 자동 (GPU 있으면 GPU, 없으면 CPU)
      python train_screw.py --device cpu   # CPU 강제
      python train_screw.py --device cuda  # GPU 강제
"""

import argparse
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms

# ===========================================================================
# 설정 (build_dataset.py 의 DST 와 같은 경로여야 함)
# ===========================================================================
DATA = Path("/home/a202192012/5.Agent_System/프로젝트/스마트제조_AI_Agent_교제코드/CH5/data/screw_2class")

IMG_SIZE = 224
BATCH_SIZE = 8
EPOCHS = 8

torch.manual_seed(42)


# ===========================================================================
# 장치 선택 (CPU / GPU)
# ===========================================================================
def pick_device(choice: str = "auto") -> torch.device:
    """
    choice: 'auto' | 'cpu' | 'cuda'
      auto : GPU가 있으면 GPU, 없으면 CPU
      cuda : GPU 강제 (없으면 경고 후 CPU로 대체)
      cpu  : CPU 강제
    """
    if choice == "cpu":
        return torch.device("cpu")
    if choice == "cuda":
        if torch.cuda.is_available():
            return torch.device("cuda")
        print("[경고] GPU(cuda)를 쓸 수 없어 CPU로 대체합니다.")
        return torch.device("cpu")
    # auto
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ===========================================================================
# (1) 데이터 로딩
# ===========================================================================
def make_loaders():
    normalize = transforms.Normalize([0.485, 0.456, 0.406],
                                     [0.229, 0.224, 0.225])   # ImageNet 기준
    train_tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ToTensor(),
        normalize,
    ])
    test_tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        normalize,
    ])

    if not (DATA / "train").exists():
        raise FileNotFoundError(
            f"{DATA} 가 없습니다. 먼저 'python build_dataset.py' 를 실행하세요.")

    train_ds = datasets.ImageFolder(DATA / "train", transform=train_tf)
    test_ds = datasets.ImageFolder(DATA / "test", transform=test_tf)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False)
    return train_loader, test_loader, train_ds.classes


# ===========================================================================
# (2) MobileNetV2 전이학습 모델
# ===========================================================================
def build_model(num_classes=2):
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
    for p in model.features.parameters():   # 특징 추출부 freeze
        p.requires_grad = False
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, num_classes)  # 분류층만 교체
    return model


# ===========================================================================
# 학습 / 평가 (device 로 데이터도 이동)
# ===========================================================================
def run_epoch(model, loader, loss_fn, device, optimizer=None):
    train = optimizer is not None
    model.train() if train else model.eval()
    total, correct, loss_sum = 0, 0, 0.0
    with torch.set_grad_enabled(train):
        for x, y in loader:
            x, y = x.to(device), y.to(device)      # 데이터를 같은 장치로
            if train:
                optimizer.zero_grad()
            out = model(x)
            loss = loss_fn(out, y)
            if train:
                loss.backward()
                optimizer.step()
            loss_sum += loss.item() * x.size(0)
            correct += (out.argmax(1) == y).sum().item()
            total += x.size(0)
    return loss_sum / total, correct / total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"],
                    help="학습 장치 (auto=자동감지, cpu, cuda)")
    args = ap.parse_args()

    device = pick_device(args.device)
    print(f"[장치] {device}")

    train_loader, test_loader, classes = make_loaders()
    print(f"[클래스] {classes}")          # ['defective', 'good']

    model = build_model(len(classes)).to(device)   # 모델을 장치로
    loss_fn = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.classifier.parameters(), lr=1e-3)

    for epoch in range(1, EPOCHS + 1):
        tr_loss, tr_acc = run_epoch(model, train_loader, loss_fn, device, optimizer)
        te_loss, te_acc = run_epoch(model, test_loader, loss_fn, device)
        print(f"[epoch {epoch}/{EPOCHS}] train acc {tr_acc:.2f} . test acc {te_acc:.2f}")

    torch.save({"state_dict": model.state_dict(), "classes": classes},
               "screw_model.pth")
    print("[저장] screw_model.pth")


if __name__ == "__main__":
    main()