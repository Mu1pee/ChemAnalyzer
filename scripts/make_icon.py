"""Генерация иконки ChemAnalyzer (оригинальный рисунок: молекулярная сетка).

    python scripts/make_icon.py

Создаёт assets/icon.png (512x512) и assets/icon.ico (16–256 px).
Нужен Pillow:  pip install pillow
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets"
S = 1024  # рисуем крупно, затем уменьшаем — гладкие края


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # Фон: скруглённый квадрат с диагональным градиентом.
    grad = Image.new("RGBA", (S, S))
    px = grad.load()
    top, bottom = (14, 30, 54), (6, 14, 28)
    for y in range(S):
        for x in range(S):
            px[x, y] = (*lerp(top, bottom, (x + y) / (2 * S)), 255)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((24, 24, S - 24, S - 24), radius=210, fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    cx, cy, r = S // 2, S // 2 + 10, 300

    # Шестиугольник (бензольное кольцо) + «хвосты» заместителей.
    ring = [
        (cx + r * math.cos(math.radians(60 * i - 30)),
         cy + r * math.sin(math.radians(60 * i - 30)))
        for i in range(6)
    ]
    line = (90, 190, 255, 255)
    for i in range(6):
        a, b = ring[i], ring[(i + 1) % 6]
        d.line([a, b], fill=line, width=40)
    # Внутренняя «ароматическая» окружность.
    ir = r * 0.58
    d.ellipse((cx - ir, cy - ir, cx + ir, cy + ir), outline=(90, 190, 255, 140), width=22)

    tails = [(ring[0], (cx + r * 1.32, cy - r * 0.5)),
             (ring[3], (cx - r * 1.32, cy + r * 0.56))]
    for a, b in tails:
        d.line([a, b], fill=line, width=40)

    def node(p, rad, fill):
        d.ellipse((p[0] - rad, p[1] - rad, p[0] + rad, p[1] + rad), fill=fill)

    for p in ring:
        node(p, 46, (14, 30, 54, 255))
        node(p, 34, (120, 215, 255, 255))
    node(tails[0][1], 58, (255, 255, 255, 255))
    node(tails[0][1], 40, (80, 160, 235, 255))
    node(tails[1][1], 58, (255, 255, 255, 255))
    node(tails[1][1], 40, (80, 160, 235, 255))
    return img


def main() -> None:
    OUT.mkdir(exist_ok=True)
    big = draw()
    big.resize((512, 512), Image.LANCZOS).save(OUT / "icon.png")
    big.save(
        OUT / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("Создано:", OUT / "icon.png", OUT / "icon.ico")


if __name__ == "__main__":
    main()
