import argparse
from pathlib import Path

import torch
import torch.nn as nn
from torchvision import datasets, models, transforms
from torch.utils.data import DataLoader

DATA = Path(".../CH5/data/screw_2class")
IMG_SIZE = 224


def pick_device(choice="auto"):
    if choice == "cpu":
        return torch.device("cpu")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


# 저장된 모델(screw_model.pth) 불러오기
def load_model(device, path="screw_model.pth"):
    ckpt = torch.load(path, map_location=device)
    classes = ckpt["classes"]
    model = models.mobilenet_v2()                       # 구조만 만들고
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, len(classes))
    model.load_state_dict(ckpt["state_dict"])           # 학습된 가중치를 덮어씀
    model.to(device).eval()
    return model, classes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    args = ap.parse_args()

    device = pick_device(args.device)
    print(f"[장치] {device}")

    model, classes = load_model(device)

    tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    # ImageFolder: 이미지와 정답 라벨을 함께 제공
    test_ds = datasets.ImageFolder(DATA / "test", transform=tf)
    loader = DataLoader(test_ds, batch_size=1, shuffle=False)

    print(f"[클래스] {classes}\n")
    print(f"{'파일':<28}{'정답':<12}{'예측':<12}{'결과'}")
    print("-" * 60)

    correct, total = 0, 0
    with torch.no_grad():
        for i, (x, y) in enumerate(loader):
            x = x.to(device)
            pred = int(model(x).argmax(1).item())        # 모델의 예측
            true = int(y.item())                         # 실제 정답
            fname = Path(test_ds.samples[i][0]).name
            ok = (pred == true)                          # 맞았는지 비교
            correct += ok
            total += 1
            mark = "O 맞음" if ok else "X 틀림"
            print(f"{fname:<28}{classes[true]:<12}{classes[pred]:<12}{mark}")

    print("-" * 60)
    print(f"정확도: {correct}/{total} = {correct/total:.1%}")


if __name__ == "__main__":
    main()