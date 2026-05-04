"""
Pega valor de mercado dos jogadores no Transfermarkt e salva em
cache/tm_values.json (sofascore_id -> {value_eur, value_label, fetched_at}).

Usa cache/tm_ids.json (criado pelo fetch_photos.py) pra mapear SofaScore ID -> TM ID.
Idempotente: só busca jogadores que ainda não tem valor cacheado.
Use --force pra refazer todos.
"""
from __future__ import annotations
import json
import re
import sys
import time
from pathlib import Path
from curl_cffi import requests as cr

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "cache"


def parse_value(text: str) -> tuple[int | None, str | None]:
    """Extrai valor de mercado da página HTML do TM. Retorna (euro_value, label)."""
    # Pattern 1: meta description "Market value: €70.00m"
    m = re.search(r"Market value:\s*€\s*([\d,.]+)\s*([mk]?)", text, re.IGNORECASE)
    if not m:
        # Pattern 2: data-header__market-value-wrapper
        m = re.search(
            r"data-header__market-value-wrapper[^>]*>.*?€</span>\s*([\d,.]+)\s*<span[^>]*>([mk]?)</span>",
            text, re.DOTALL,
        )
    if not m:
        return None, None
    num_str = m.group(1).replace(",", ".").strip(".")
    try:
        num = float(num_str)
    except ValueError:
        return None, None
    suffix = (m.group(2) or "").lower()
    if suffix == "m":
        euros = int(num * 1_000_000)
        label = f"€{num:.2f}M".replace(".00M", "M")
    elif suffix == "k":
        euros = int(num * 1_000)
        label = f"€{int(num)}K"
    else:
        euros = int(num)
        label = f"€{int(num):,}".replace(",", ".")
    return euros, label


def fetch_value(tm_id: str) -> tuple[int | None, str | None]:
    try:
        r = cr.get(
            f"https://www.transfermarkt.com/x/profil/spieler/{tm_id}",
            impersonate="chrome131",
            timeout=15,
        )
        if r.status_code != 200:
            return None, None
        return parse_value(r.text)
    except Exception as e:
        print(f"    [ERR] {e}")
        return None, None


def main():
    force = "--force" in sys.argv
    tm_ids_path = CACHE / "tm_ids.json"
    if not tm_ids_path.exists():
        print("[ERR] cache/tm_ids.json não existe — rode scrapers/fetch_photos.py primeiro")
        return 1

    tm_ids = json.loads(tm_ids_path.read_text(encoding="utf-8"))
    values_path = CACHE / "tm_values.json"
    values: dict[str, dict] = {}
    if values_path.exists() and not force:
        values = json.loads(values_path.read_text(encoding="utf-8"))

    skipped = updated = failed = 0
    for sofa_id, info in tm_ids.items():
        tm_id = info.get("tm_id")
        if not tm_id:
            continue
        if sofa_id in values and not force:
            skipped += 1
            continue
        print(f"  {info.get('name', sofa_id):30s} (tm={tm_id})...", end=" ", flush=True)
        euros, label = fetch_value(tm_id)
        if euros is not None:
            values[sofa_id] = {
                "value_eur": euros,
                "value_label": label,
                "fetched_at": time.strftime("%Y-%m-%d"),
            }
            print(f"OK {label}")
            updated += 1
        else:
            print("FAIL")
            failed += 1
        time.sleep(0.4)

    values_path.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== {updated} atualizados, {skipped} cacheados, {failed} falharam ===")


if __name__ == "__main__":
    sys.exit(main() or 0)
