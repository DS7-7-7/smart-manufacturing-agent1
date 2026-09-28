# -*- coding: utf-8 -*-
"""
predict_screw.py
================
train_screw.py 로 학습한 모델(screw_model.pth)로
새 나사 사진 한 장이 정상인지 불량인지 판정한다.

사용법:
    python predict_screw.py <이미지경로>
    python predict_screw.py <이미지경로> --device cpu
    python predict_screw.py <이미지경로> --device cuda
"""

import argparse
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

IMG_SIZE = 224


def pick_device(choice="auto"):
    if choice == "cpu":
        return torch.device("cpu")
    if choice == "cuda":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_model(device, path="screw_model.pth"):
    ckpt = torch.load(path, map_location=device)
    classes = ckpt["classes"]

    model = models.mobilenet_v2()          # 구조만 (가중치는 아래서 덮어씀)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, len(classes))
    model.load_state_dict(ckpt["state_dict"])
    model.to(device).eval()
    return model, classes


def predict(img_path, model, classes, device):
    tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406],
                             [0.229, 0.224, 0.225]),
    ])
    img = Image.open(img_path).convert("RGB")
    x = tf(img).unsqueeze(0).to(device)    # (1, 3, 224, 224)

    with torch.no_grad():
        probs = torch.softmax(model(x), dim=1)[0]

    pred_idx = int(probs.argmax())
    return classes[pred_idx], float(probs[pred_idx]), dict(zip(classes, probs.tolist()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="판정할 이미지 경로")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    args = ap.parse_args()

    device = pick_device(args.device)
    print(f"[장치] {device}")

    model, classes = load_model(device)
    label, conf, all_probs = predict(args.image, model, classes, device)

    verdict = "정상 OK" if label == "good" else "불량 NG"
    print(f"판정: {verdict}  (라벨={label}, 신뢰도={conf:.1%})")
    print("확률 분포: " + ", ".join(f"{k} {v:.1%}" for k, v in all_probs.items()))