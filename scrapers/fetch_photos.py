"""
Baixa fotos dos jogadores usando Transfermarkt (600×600) como fonte primária e
SofaScore (150×150) como fallback. Salva localmente em assets/photos/{id}.webp.

Por que TM em vez de SofaScore:
  - SofaScore retorna 150×150 webp (~3-4KB) — pixela quando ampliado pra cards 320px
  - Transfermarkt retorna 600×600 jpg/png (~15-30KB) — qualidade muito maior

Por que cachear local em vez de hot-link:
  - Chrome ORB bloqueia /api/v1/* da SofaScore cross-origin
  - TM tem hotlink protection (Referer check) na CDN — também bloqueia external
  Servir do próprio repo elimina ambos os problemas.

Cache de TM IDs em cache/tm_ids.json: pra não re-pesquisar TM toda vez.
Roda só pra players sem foto (idempotente). Use --force pra refazer todas.
"""
from __future__ import annotations
import json
import re
import sys
import time
from pathlib import Path
from _util import API, get_json
from curl_cffi import requests as cr

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "cache"
ASSETS = ROOT / "assets" / "photos"
TM_IDS_FILE = CACHE / "tm_ids.json"


def load_tm_ids() -> dict[str, dict]:
    if TM_IDS_FILE.exists():
        return json.loads(TM_IDS_FILE.read_text(encoding="utf-8"))
    return {}


def save_tm_ids(d: dict) -> None:
    TM_IDS_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def find_transfermarkt_photo(name: str) -> tuple[str | None, str | None]:
    """Busca jogador no TM por nome, retorna (tm_id, photo_url_big) ou (None, None).
    photo_url já vem na variante 'big' (600×600)."""
    try:
        url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={name.replace(' ', '+')}"
        r = cr.get(url, impersonate="chrome131", timeout=15)
        if r.status_code != 200:
            return None, None
        m = re.search(r"/profil/spieler/(\d+)", r.text)
        if not m:
            return None, None
        tm_id = m.group(1)
        profile = cr.get(
            f"https://www.transfermarkt.com/x/profil/spieler/{tm_id}",
            impersonate="chrome131",
            timeout=15,
        )
        img_match = re.search(
            r'(https://img\.a\.transfermarkt\.technology/portrait/[^"\s]+\.(?:jpg|png|webp))',
            profile.text,
        )
        if not img_match:
            return tm_id, None
        url = img_match.group(1)
        # Forçar variante "big" (600×600) — substitui /medium/ ou /header/ na URL
        url_big = url.replace("/medium/", "/big/").replace("/header/", "/big/")
        return tm_id, url_big
    except Exception as e:
        print(f"    [TM ERR] {e}")
        return None, None


def fetch_sofascore(player_id: int) -> bytes | None:
    try:
        r = cr.get(f"{API}/player/{player_id}/image", impersonate="chrome131", timeout=15)
        if r.status_code == 200 and len(r.content) > 100:
            return r.content
    except Exception as e:
        print(f"    [SS ERR] {e}")
    return None


def fetch_image(player: dict, tm_cache: dict) -> tuple[bytes | None, str]:
    """Tenta TM primeiro, fallback SofaScore. Retorna (bytes, origem)."""
    name = player.get("name", "")
    pid_str = str(player["id"])

    # Cache de TM IDs
    cached = tm_cache.get(pid_str)
    tm_url = None
    if cached:
        tm_url = cached.get("photo_url")
    elif name:
        tm_id, tm_url = find_transfermarkt_photo(name)
        tm_cache[pid_str] = {"name": name, "tm_id": tm_id, "photo_url": tm_url}
        time.sleep(0.5)  # respeito ao TM

    if tm_url:
        try:
            r = cr.get(tm_url, impersonate="chrome131", timeout=15)
            if r.status_code == 200 and len(r.content) > 1000:
                return r.content, "TM"
        except Exception as e:
            print(f"    [TM dl ERR] {e}")

    data = fetch_sofascore(player["id"])
    if data:
        return data, "SS"
    return None, "FAIL"


def all_players() -> list[dict]:
    out: list[dict] = []
    seen: set[int] = set()
    for fname in ["squad.json", "rumors.json"]:
        p = CACHE / fname
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for player in data.get("players", []):
            if player["id"] not in seen:
                out.append(player)
                seen.add(player["id"])
    return out


def main():
    force = "--force" in sys.argv
    ASSETS.mkdir(parents=True, exist_ok=True)
    players = all_players()
    print(f"Total: {len(players)} players")
    tm_cache = load_tm_ids()

    skipped = downloaded = failed = 0
    by_origin = {"TM": 0, "SS": 0, "FAIL": 0}

    for i, p in enumerate(players, 1):
        pid = p["id"]
        out = ASSETS / f"{pid}.webp"
        if out.exists() and not force:
            skipped += 1
            continue
        print(f"[{i}/{len(players)}] {p.get('name', pid):30s}...", end=" ", flush=True)
        data, origin = fetch_image(p, tm_cache)
        by_origin[origin] = by_origin.get(origin, 0) + 1
        if data:
            out.write_bytes(data)
            print(f"OK ({origin}, {len(data)} bytes)")
            downloaded += 1
        else:
            print("FAIL")
            failed += 1
        if i % 5 == 0:
            save_tm_ids(tm_cache)
        time.sleep(0.3)

    save_tm_ids(tm_cache)
    print(f"\n=== {downloaded} baixadas, {skipped} já tinham, {failed} falharam ===")
    print(f"  por fonte: {by_origin}")


if __name__ == "__main__":
    main()
