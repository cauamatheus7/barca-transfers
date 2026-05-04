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
from _util import API, get_json
from curl_cffi import requests as cr
from PIL import Image

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "cache"
ASSETS = ROOT / "assets" / "photos"

WHITE_THRESHOLD = 240  # RGB acima disso vira transparente


def remove_white_bg(raw: bytes) -> bytes:
    """Carrega webp/png/jpeg e troca fundo branco por transparente. Salva como webp."""
    img = Image.open(BytesIO(raw)).convert("RGBA")
    pixels = list(img.getdata())
    new_pixels = []
    for r, g, b, a in pixels:
        if r >= WHITE_THRESHOLD and g >= WHITE_THRESHOLD and b >= WHITE_THRESHOLD:
            new_pixels.append((r, g, b, 0))
        else:
            new_pixels.append((r, g, b, a))
    img.putdata(new_pixels)
    out = BytesIO()
    img.save(out, format="WEBP", quality=85)
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
