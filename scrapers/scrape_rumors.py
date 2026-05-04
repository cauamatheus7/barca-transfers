"""
Compila lista de jogadores especulados para o Barcelona, resolvendo IDs no SofaScore.

A lista de nomes vem da pesquisa via WebSearch + edição manual.
Para refresh: edite RUMORS abaixo e re-rode.

Saída: cache/rumors.json com lista de jogadores normalizada.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from urllib.parse import quote
from _util import API, get_json, normalize_player

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "cache"

# Lista compilada via WebSearch (maio 2026, janela de verão 2026).
# Estrutura: nome para busca, dica de time (substring p/ desambiguar — opcional),
# posição-alvo, contexto/notas.
RUMORS = [
    # Atacantes (centroavantes)
    {"search": "Julian Alvarez",      "team_hint": "Atlético",         "target_pos": "ST",  "note": "Atlético Madrid · prioridade #1, ~€100M"},
    {"search": "Joao Pedro",          "team_hint": "Chelsea",          "target_pos": "ST",  "note": "Chelsea · backup confirmado"},
    {"search": "Dusan Vlahovic",      "team_hint": "Juventus",         "target_pos": "ST",  "note": "Juventus · opção como agente livre 2026"},

    # Pontas-esquerda
    {"search": "Marcus Rashford",     "team_hint": "Barcelona",        "target_pos": "LW",  "note": "Man United · já está emprestado, querem efetivar"},
    {"search": "Rafael Leao",         "team_hint": "Milan",            "target_pos": "LW",  "note": "AC Milan · interesse de Laporta"},
    {"search": "Andreas Schjelderup", "team_hint": "Benfica",          "target_pos": "LW",  "note": "Benfica · alternativa jovem"},
    {"search": "Abde Ezzalzouli",     "team_hint": "Betis",            "target_pos": "LW",  "note": "Real Betis · alternativa"},
    {"search": "Jan Virgili",         "team_hint": "Mallorca",         "target_pos": "LW",  "note": "Mallorca · alternativa jovem"},

    # Zagueiros
    {"search": "Alessandro Bastoni",  "team_hint": "Inter",            "target_pos": "CB",  "note": "Inter · prioridade #1 zaga, valor €70M"},
    {"search": "Jon Martin",          "team_hint": "Real Sociedad",    "target_pos": "CB",  "note": "Real Sociedad · backup"},
    {"search": "Jhon Lucumi",         "team_hint": "Bologna",          "target_pos": "CB",  "note": "Bologna · backup"},
    {"search": "Goncalo Inacio",      "team_hint": "Sporting",         "target_pos": "CB",  "note": "Sporting CP"},
    {"search": "Murillo",             "team_hint": "Nottingham",       "target_pos": "CB",  "note": "Nottingham Forest"},
    {"search": "Nico Schlotterbeck",  "team_hint": "Dortmund",         "target_pos": "CB",  "note": "Borussia Dortmund"},
    {"search": "Marc Guehi",          "team_hint": "",                 "target_pos": "CB",  "note": "Crystal Palace / Man City — recém-transferido"},

    # Goleiro
    {"search": "Alex Remiro",         "team_hint": "Real Sociedad",    "target_pos": "GK",  "note": "Real Sociedad · objetivo para o gol"},
]


def search_player(name: str, team_hint: str = "") -> dict | None:
    """Busca o melhor match. Se team_hint bater (substring no nome do time), prefere."""
    try:
        data = get_json(f"{API}/search/players/{quote(name)}")
    except Exception as e:
        print(f"  [ERR] search {name}: {e}")
        return None
    players = (data or {}).get("players", [])
    if not players:
        return None
    if team_hint:
        for p in players:
            team_name = (p.get("team") or {}).get("name", "")
            if team_hint.lower() in team_name.lower():
                return p
    return players[0]


def main():
    CACHE.mkdir(exist_ok=True)
    rumors: list[dict] = []
    not_found: list[str] = []

    print(f"Resolvendo {len(RUMORS)} nomes no SofaScore...\n")
    for r in RUMORS:
        print(f"  {r['search']:35s} ", end="")
        result = search_player(r["search"], r.get("team_hint", ""))
        if result:
            team = result.get("team") or {}
            p = normalize_player(
                result, "rumor",
                position_target=r["target_pos"],
                note=r["note"],
                current_team=team.get("name"),
                current_team_id=team.get("id"),
            )
            rumors.append(p)
            print(f"OK -> {p['name']} ({p['current_team']}, pos={p['position']})")
        else:
            not_found.append(r["search"])
            print("NÃO ENCONTRADO")
        time.sleep(0.4)

    out = CACHE / "rumors.json"
    out.write_text(
        json.dumps({"updated": time.strftime("%Y-%m-%d"), "players": rumors},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n=== {len(rumors)} resolvidos · {len(not_found)} não encontrados ===")
    if not_found:
        print(f"Nao encontrados: {not_found}")
    print(f"Salvo em {out}")


if __name__ == "__main__":
    main()
