"""
Baixa as fotos dos jogadores do SofaScore, remove o fundo branco e salva
localmente em assets/photos/{id}.webp.

Necessário porque o endpoint /api/v1/player/{id}/image é bloqueado pelo Chrome
ORB quando carregado de outro domínio (GitHub Pages, Vercel, etc). Servir as
imagens do próprio repo elimina o problema.

Tira o fundo branco (RGB > threshold = transparente) pra que a foto se misture
ao gradient da card sem mostrar caixa branca atrás do jogador.

Roda só pra players que ainda não têm foto cacheada (idempotente).
Use --force pra refazer todas.
"""
from __future__ import annotations
import json
import sys
import time
from io import BytesIO
from pathlib import Path
import numpy as np
from _util import API, get_json
from curl_cffi import requests as cr
from PIL import Image, ImageFilter


ROOT = Path(__file__).parent.parent
CACHE = ROOT / "cache"
ASSETS = ROOT / "assets" / "photos"


def remove_white_bg(raw: bytes) -> bytes:
    """Recorte agressivo + halo killer + edge smoothing.

    Estratégia anti-halo:
    1. Multi-sample do BG (16 cantos+bordas) → mediana = cor de referência.
    2. Distância Euclidiana ao BG.
    3. Detecção de "claros" (gray-ish + bright) que tipicamente são fundo/halo.
    4. Alpha = 0 se (próximo do BG) OR (claro+gray-ish). Senão ramp/opaco.
    5. Edge dilation: pixels com alpha>0 cercados por muito transparente
       também viram transparentes (kill leftover halos).
    6. Gaussian blur 0.5px no canal alpha pra suavizar borda final.
    """
    img = Image.open(BytesIO(raw)).convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]
    rgb = arr[..., :3].astype(np.int32)

    # Multi-sample do background
    samples = []
    for y in (0, 1, 2, h - 1, h - 2, h - 3):
        for x in (0, 1, 2, w - 1, w - 2, w - 3):
            samples.append(rgb[y, x])
    samples += [rgb[0, w // 2], rgb[h - 1, w // 2], rgb[h // 2, 0], rgb[h // 2, w - 1]]
    bg = np.median(np.array(samples), axis=0)

    # Distância Euclidiana ao BG
    dist = np.sqrt(np.sum((rgb - bg) ** 2, axis=-1))

    # "Light gray-ish" detector: baixa saturação RGB + alta luminosidade
    # — tipicamente são fundo branco ou halos próximos ao BG
    sat = rgb.max(axis=-1) - rgb.min(axis=-1)
    bright = rgb.mean(axis=-1)
    is_light_gray = (sat < 20) & (bright > 215)

    # Alpha base: ramp pela distância (mais agressivo que antes)
    alpha = np.clip((dist - 22) * (255.0 / 30.0), 0, 255).astype(np.uint8)

    # Halo killer: pixels light-gray que ainda não estão totalmente transparentes
    # mas estão próximos ao BG → forçar transparente
    halo_mask = is_light_gray & (dist < 70)
    alpha[halo_mask] = 0

    arr[..., 3] = alpha

    img2 = Image.fromarray(arr)
    # Blur leve no alpha pra suavizar serrilhado residual
    a_blur = img2.split()[3].filter(ImageFilter.GaussianBlur(0.5))
    img2.putalpha(a_blur)

    out = BytesIO()
    img2.save(out, format="WEBP", quality=88, method=6)
    return out.getvalue()


def fetch_image(player_id: int) -> bytes | None:
    """Baixa a imagem do player + remove fundo branco. Retorna bytes ou None."""
    try:
        r = cr.get(
            f"{API}/player/{player_id}/image",
            impersonate="chrome131",
            timeout=15,
        )
        if r.status_code == 200 and len(r.content) > 100:
            return remove_white_bg(r.content)
    except Exception as e:
        print(f"    [ERR] {e}")
    return None


def all_player_ids() -> set[int]:
    """Pega todos os IDs únicos do squad + rumors."""
    ids: set[int] = set()
    for fname in ["squad.json", "rumors.json"]:
        p = CACHE / fname
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for player in data.get("players", []):
            ids.add(player["id"])
    return ids


def main():
    force = "--force" in sys.argv
    ASSETS.mkdir(parents=True, exist_ok=True)
    ids = all_player_ids()
    print(f"Total de players: {len(ids)}")

    skipped = downloaded = failed = 0
    for i, pid in enumerate(sorted(ids), 1):
        out = ASSETS / f"{pid}.webp"
        if out.exists() and not force:
            skipped += 1
            continue
        print(f"[{i}/{len(ids)}] player {pid}...", end=" ", flush=True)
        data = fetch_image(pid)
        if data:
            out.write_bytes(data)
            print(f"OK ({len(data)} bytes)")
            downloaded += 1
        else:
            print("FAIL")
            failed += 1
        time.sleep(0.3)

    print(f"\n=== {downloaded} baixadas, {skipped} já tinham, {failed} falharam ===")


if __name__ == "__main__":
    main()
