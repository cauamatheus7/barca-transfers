"""
Coleta stats agregadas (temporada 25/26) para todos os jogadores em
data/squad.json + data/rumors.json. Suporta multi-liga.

Estratégia para cada jogador:
1. GET /player/{id}/statistics/seasons - lista de torneios e temporadas que jogou
2. Escolhe a "liga doméstica" preferencial em 25/26 (ranking de ligas conhecidas)
3. GET /player/{id}/unique-tournament/{utid}/season/{seasonId}/statistics/overall
4. Salva em data/stats.json mapeando player_id -> stats

Cache opcional: se data/stats.json já existir, mantém os jogadores que já têm stats
e só busca os faltantes (passe --force pra refazer tudo).
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path
from _util import API, get_json

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "cache"

# Ranking de ligas "domésticas" preferenciais para detectar a liga principal do jogador
# Ordem importa: liga mais alta na lista = preferência
LEAGUE_PRIORITY = [
    "LaLiga",
    "Premier League",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Primeira Liga",
    "Eredivisie",
    "LaLiga 2",
    "Primera Federación",
    "Championship",
    "Liga Profesional Argentina",
    "Saudi Pro League",
]

CURRENT_SEASON_YEAR = "25/26"


def safe_get_json(url: str) -> dict | None:
    """Wraps _util.get_json com tolerância a erros (loga e retorna None)."""
    try:
        return get_json(url)
    except Exception as e:
        print(f"    [ERR] {e}")
        return None


def find_main_league_season(seasons_data: dict) -> tuple[int, int, str] | None:
    """Retorna (utid, season_id, league_name) da liga doméstica preferencial em 25/26."""
    if not seasons_data:
        return None
    tournaments = seasons_data.get("uniqueTournamentSeasons", [])

    # Mapear nome da liga -> (utid, season_id)
    available_25_26: dict[str, tuple[int, int]] = {}
    for t in tournaments:
        ut = t.get("uniqueTournament", {})
        name = ut.get("name", "")
        utid = ut.get("id")
        for s in t.get("seasons", []):
            if s.get("year") == CURRENT_SEASON_YEAR:
                available_25_26[name] = (utid, s["id"])
                break

    # Tentar pela ordem de prioridade
    for league in LEAGUE_PRIORITY:
        if league in available_25_26:
            utid, sid = available_25_26[league]
            return utid, sid, league

    # Se não tem nenhuma da lista, tenta primeira liga 25/26 que não seja seleção
    for name, (utid, sid) in available_25_26.items():
        if "World Cup" not in name and "EURO" not in name and "Nations" not in name:
            return utid, sid, name

    return None


def fetch_overall_stats(player_id: int, utid: int, sid: int) -> dict | None:
    data = safe_get_json(f"{API}/player/{player_id}/unique-tournament/{utid}/season/{sid}/statistics/overall")
    if not data:
        return None
    # B7: nunca retorna o wrapper inteiro — exige a chave 'statistics' propriamente
    stats = data.get("statistics")
    return stats if stats else None


def load_players() -> list[dict]:
    """Junta squad + rumors numa lista única."""
    out = []
    squad = json.loads((CACHE / "squad.json").read_text(encoding="utf-8"))
    out.extend(squad["players"])
    rumors = json.loads((CACHE / "rumors.json").read_text(encoding="utf-8"))
    out.extend(rumors["players"])
    return out


def main():
    force = "--force" in sys.argv
    CACHE.mkdir(exist_ok=True)
    players = load_players()
    print(f"Total de jogadores: {len(players)}")

    out_path = CACHE / "stats.json"
    existing: dict[str, dict] = {}
    if out_path.exists() and not force:
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        print(f"Cache existente: {len(existing)} jogadores. Use --force pra refazer tudo.")

    skipped = updated = empty = 0
    for i, p in enumerate(players, 1):
        pid = str(p["id"])
        # B1: skip se já tentou (independente do resultado), a não ser que --force
        if pid in existing and not force:
            skipped += 1
            continue

        print(f"[{i}/{len(players)}] {p['name']:30s} (id {pid})...", end=" ", flush=True)
        seasons = safe_get_json(f"{API}/player/{pid}/statistics/seasons")
        time.sleep(0.4)
        choice = find_main_league_season(seasons or {})
        if not choice:
            print("nenhuma liga 25/26")
            existing[pid] = {"player_id": p["id"], "name": p["name"], "league": None, "stats": None}
            empty += 1
            continue

        utid, sid, league = choice
        stats = fetch_overall_stats(p["id"], utid, sid)
        time.sleep(0.4)
        if not stats:
            print(f"sem stats em {league}")
            existing[pid] = {"player_id": p["id"], "name": p["name"], "league": league, "stats": None}
            empty += 1
            continue

        appearances = stats.get("appearances", 0) or 0
        rating = stats.get("rating")
        print(f"OK {league} - {appearances} apps, rating {rating}")
        existing[pid] = {
            "player_id": p["id"],
            "name": p["name"],
            "league": league,
            "season_year": CURRENT_SEASON_YEAR,
            "tournament_id": utid,
            "season_id": sid,
            "stats": stats,
        }
        updated += 1

        # Salvar a cada 10 jogadores pra não perder progresso
        if updated % 10 == 0:
            out_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    out_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== Salvo em {out_path.name} ===")
    print(f"  skipped (cache): {skipped}")
    print(f"  atualizados:     {updated}")
    print(f"  sem dados:       {empty}")
    print(f"  total no arquivo: {len(existing)}")


if __name__ == "__main__":
    main()
