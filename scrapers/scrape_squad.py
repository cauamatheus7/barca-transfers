"""
Coleta o elenco do FC Barcelona via SofaScore:
- Time principal (id 2817)
- Barcelona Atlètic / Barça B (id 24343)
- Emprestados (via endpoint de transferências)

Saída: cache/squad.json com lista de jogadores normalizada.
"""
from __future__ import annotations
import json
import time
from collections import Counter
from pathlib import Path
from _util import API, get_json, normalize_player

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "cache"

TEAMS = {
    "main":     {"id": 2817,  "label": "Barcelona"},
    "athletic": {"id": 24343, "label": "Barcelona Atlètic"},
}


def fetch_squad(team_id: int) -> list[dict]:
    data = get_json(f"{API}/team/{team_id}/players")
    return data.get("players", []) if data else []


def fetch_outgoing_loans(team_id: int) -> list[tuple[dict, dict]]:
    """Retorna [(raw_player, extras), ...] para players cedidos."""
    out: list[tuple[dict, dict]] = []
    try:
        data = get_json(f"{API}/team/{team_id}/transfers")
    except Exception as e:
        print(f"  [WARN] transfers endpoint: {e}")
        return out
    for t in (data or {}).get("transfersOut", []):
        is_loan = t.get("type") == "loan" or "Loan" in (t.get("transferType") or "")
        if not is_loan:
            continue
        p = t.get("player")
        if p:
            out.append((p, {
                "loan_to": (t.get("transferTo") or t.get("toTeam") or {}).get("name"),
                "loan_until": t.get("transferDate"),
            }))
    return out


def main():
    CACHE.mkdir(exist_ok=True)
    squad: list[dict] = []
    seen: set[int] = set()

    for source, team in TEAMS.items():
        print(f"\n[{source}] team {team['id']} ({team['label']})...")
        entries = fetch_squad(team["id"])
        print(f"  {len(entries)} jogadores")
        for e in entries:
            p = normalize_player(e.get("player"), source)
            if p and p["id"] not in seen:
                squad.append(p)
                seen.add(p["id"])
        time.sleep(0.5)

    print(f"\n[loans] outgoing loans do Barcelona principal...")
    loans = fetch_outgoing_loans(TEAMS["main"]["id"])
    print(f"  {len(loans)} emprestados encontrados")
    for raw, extras in loans:
        p = normalize_player(raw, "loan", **extras)
        if p and p["id"] not in seen:
            squad.append(p)
            seen.add(p["id"])

    out = CACHE / "squad.json"
    out.write_text(
        json.dumps({"team": "FC Barcelona", "players": squad},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    by_pos = Counter(p["position"] for p in squad)
    by_source = Counter(p["source"] for p in squad)
    print(f"\n=== Salvo em {out.name}: {len(squad)} jogadores ===")
    print(f"  por posição (G/D/M/F): {dict(by_pos)}")
    print(f"  por fonte:             {dict(by_source)}")


if __name__ == "__main__":
    main()
