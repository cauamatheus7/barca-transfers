"""
Gera assets/og-image.png (1200×630) — imagem usada como preview Open Graph
quando o link é compartilhado no WhatsApp/Twitter/Discord/etc.

Usa fontes do sistema (Times pra serif, Arial pra sans) — não precisa de fontes
customizadas. Visual minimalista combinando com o tema do site.

Roda uma vez, comita o png. Não precisa rerodar a menos que mude branding.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).parent.parent
OUT = ROOT / "assets" / "og-image.png"

W, H = 1200, 630
INK = (12, 14, 28)         # --ink
INK_DEEP = (6, 8, 15)
PAPER = (240, 232, 214)    # --paper
SILVER = (212, 216, 224)   # --silver
GOLD = (245, 197, 18)      # --gold
GRENAT = (179, 22, 58)     # --grenat
BLUE = (26, 79, 175)       # --blue
MIST = (107, 115, 136)     # --mist


def find_font(names: list[str], size: int) -> ImageFont.ImageFont:
    """Tenta carregar a primeira font do sistema que existir."""
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def draw_shield(draw: ImageDraw.ImageDraw, cx: int, cy: int, w: int, h: int, color: tuple, alpha: int = 60):
    """Desenha um brasão hatched no estilo da masthead."""
    # Outline
    points = [
        (cx, cy - h // 2),
        (cx + w // 2, cy - h // 2 + h * 0.14),
        (cx + w // 2, cy + h * 0.04),
        (cx, cy + h // 2),
        (cx - w // 2, cy + h * 0.04),
        (cx - w // 2, cy - h // 2 + h * 0.14),
    ]
    line_color = (*color, alpha)
    draw.polygon(points, outline=line_color, width=3)
    # Cross lines
    draw.line([(cx, cy - h // 2 + h * 0.1), (cx, cy + h * 0.45)],
              fill=line_color, width=2)
    draw.line([(cx - w // 2 + 8, cy), (cx + w // 2 - 8, cy)],
              fill=line_color, width=2)


def main():
    img = Image.new("RGB", (W, H), INK)
    draw = ImageDraw.Draw(img, "RGBA")

    # Gradient: azul Barça superior → grená inferior, sutil
    for y in range(H):
        ratio = y / H
        r = int(INK[0] * (1 - 0.3 * ratio) + GRENAT[0] * 0.04 * ratio)
        g = int(INK[1] * (1 - 0.2 * ratio))
        b = int(INK[2] * (1 - 0.1 * ratio) + BLUE[2] * 0.04 * (1 - ratio))
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Stripe Barça no topo (6px)
    half = W // 2
    draw.rectangle([(0, 0), (half, 6)], fill=BLUE)
    draw.rectangle([(half, 0), (W, 6)], fill=GRENAT)

    # Brasão watermark à direita
    draw_shield(draw, cx=int(W * 0.78), cy=int(H * 0.5), w=380, h=460, color=PAPER, alpha=24)

    # Carregar fontes (com fallback)
    title_font = find_font([
        "C:/Windows/Fonts/timesi.ttf",      # Times Italic
        "C:/Windows/Fonts/times.ttf",
        "/System/Library/Fonts/Times.ttc",
    ], 130)
    bold_font = find_font([
        "C:/Windows/Fonts/timesbd.ttf",     # Times Bold
        "C:/Windows/Fonts/times.ttf",
    ], 130)
    kicker_font = find_font([
        "C:/Windows/Fonts/consola.ttf",     # Consolas
        "C:/Windows/Fonts/arial.ttf",
    ], 22)
    sub_font = find_font([
        "C:/Windows/Fonts/arial.ttf",
    ], 26)

    # Kicker "MERCADO · JANELA 2026"
    draw.text((80, 100), "MERCADO  ·  JANELA 2026  ·  EDIÇÃO DIÁRIA",
              font=kicker_font, fill=GOLD)

    # Título (italic display)
    draw.text((78, 175), "Transfer", font=title_font, fill=PAPER)
    draw.text((78, 305), "Desk", font=bold_font, fill=SILVER)

    # FCB. depois de Desk (na mesma linha)
    desk_w = bold_font.getlength("Desk")
    draw.text((78 + desk_w + 24, 305), "FCB.", font=title_font, fill=PAPER)

    # Subtitle
    draw.text((80, 470),
              "Centro de monitoramento de rumores do FC Barcelona",
              font=sub_font, fill=SILVER)
    draw.text((80, 510),
              "Atualizado a cada hora · Romano · Moretto · Romero · Juanmartí",
              font=sub_font, fill=MIST)

    # Tagline neutra no canto inferior (sem URL pessoal)
    url_font = find_font(["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/arial.ttf"], 18)
    draw.text((80, 568), "Janela de transferências · 2026",
              font=url_font, fill=MIST)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"OK -> {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
