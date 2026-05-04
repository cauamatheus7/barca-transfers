"""
Gera duas páginas HTML estáticas a partir do cache:

  - index.html       — feed de notícias estilo OneFootball (página inicial)
  - comparador.html  — picker visual com fotos + comparação de stats

Lê squad.json + rumors.json + stats.json + news.json.
Cada página tem o mesmo masthead/ticker/footer (componentes compartilhados);
diferem apenas no body e no script específico da página.

Fotos dos jogadores vêm da CDN pública do SofaScore via tag <img>.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from position_config import (
    REFINED_POSITIONS, REFINED_TO_UI_GROUP, POSITION_GROUPS_UI, STATS_BY_POSITION,
)

ROOT = Path(__file__).parent
CACHE = ROOT / "cache"

# L3: tabela única para metadata de cada origem do jogador.
SOURCES = {
    "rumor":    {"order": 0, "label_short": "Especulado",       "label_long": "ESPECULADOS",      "default_team": "Time não informado"},
    "main":     {"order": 1, "label_short": "Elenco principal", "label_long": "ELENCO PRINCIPAL", "default_team": "FC Barcelona"},
    "athletic": {"order": 2, "label_short": "Barça Atlètic",    "label_long": "BARÇA ATLÈTIC",    "default_team": "Barça Atlètic"},
    "loan":     {"order": 3, "label_short": "Emprestado",       "label_long": "EMPRESTADOS",      "default_team": "Emprestado"},
}


def get_age(date_of_birth) -> int | None:
    if not date_of_birth:
        return None
    try:
        if isinstance(date_of_birth, str):
            dob = datetime.fromisoformat(date_of_birth.replace("Z", "+00:00"))
        else:
            dob = datetime.fromtimestamp(int(date_of_birth))
        today = datetime.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except (ValueError, OSError):
        return None


def refine_position(player: dict) -> str:
    """Retorna posição refinada (GK/CB/LB/RB/DM/CM/AM/LW/RW/ST) ou genérica.
    Ordem: REFINED_POSITIONS > position_target (rumor) > position_detailed (SS) > fallback.
    """
    name = player["name"]
    if name in REFINED_POSITIONS:
        return REFINED_POSITIONS[name]
    if player.get("source") == "rumor" and player.get("position_target"):
        return player["position_target"]
    detailed = player.get("position_detailed") or []
    if isinstance(detailed, str):
        detailed = [d.strip() for d in detailed.split(",") if d.strip()]
    if detailed and detailed[0] in REFINED_TO_UI_GROUP:
        return detailed[0]
    return {"G": "GK", "D": "CB", "M": "CM", "F": "ST"}.get(player.get("position", ""), "")


def load_news() -> list[dict]:
    p = CACHE / "news.json"
    if not p.exists():
        print(f"[WARN] {p} não existe — feed ficará vazio. Rotina /schedule já rodou?")
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("items", [])


def merge_data() -> list[dict]:
    squad = json.loads((CACHE / "squad.json").read_text(encoding="utf-8"))["players"]
    rumors = json.loads((CACHE / "rumors.json").read_text(encoding="utf-8"))["players"]
    stats = json.loads((CACHE / "stats.json").read_text(encoding="utf-8"))

    by_id: dict[int, dict] = {}
    for p in squad:
        item = dict(p)
        default_team = (SOURCES.get(p.get("source")) or {}).get("default_team", "")
        item.setdefault("current_team", default_team)
        by_id[p["id"]] = item
    for p in rumors:
        if p["id"] in by_id:
            existing = by_id[p["id"]]
            existing["note"] = p.get("note")
            existing["position_target"] = p.get("position_target")
            existing["source"] = "rumor"
        else:
            by_id[p["id"]] = dict(p)

    merged: list[dict] = []
    for pid, p in by_id.items():
        s = stats.get(str(pid), {})
        refined = refine_position(p)
        ui_group = REFINED_TO_UI_GROUP.get(refined, "")
        team = p.get("current_team") or "Time não informado"

        merged.append({
            "id": pid,
            "name": p["name"],
            "shortName": p.get("shortName", ""),
            "team": team,
            "country": p.get("country"),
            "age": get_age(p.get("dateOfBirth")),
            "preferredFoot": p.get("preferredFoot"),
            "height": p.get("height"),
            "jersey": p.get("jersey"),
            "source": p.get("source") or "main",
            "note": p.get("note"),
            "position_refined": refined,
            "position_group": ui_group,
            "league": s.get("league"),
            "stats": s.get("stats") or {},
            "last_seen": p.get("last_seen"),
            "mentions_count": p.get("mentions_count", 0),
            "latest_news_url": p.get("latest_news_url"),
            "latest_news_title": p.get("latest_news_title"),
            "latest_news_journalist": p.get("latest_news_journalist"),
        })

    return merged


def _build_payload(players: list[dict]) -> dict:
    usable = [p for p in players if p["stats"] and p["position_group"]]
    news = load_news()
    pid_to_name = {p["id"]: p["name"] for p in usable}
    return {
        "generated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "groups": POSITION_GROUPS_UI,
        "sources": SOURCES,
        "stats_by_group": {
            g: [{"key": k, "label": l, "smaller_better": sb} for k, l, sb in STATS_BY_POSITION[g]]
            for g in POSITION_GROUPS_UI
        },
        "players": usable,
        "news": news,
        "player_names": pid_to_name,
    }


# ─────────────────────────────────────────────────────────────────
#  SHARED HTML PARTS
# ─────────────────────────────────────────────────────────────────

HEAD_OPEN = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&family=Big+Shoulders+Display:wght@600;800;900&display=swap" rel="stylesheet">
<style>
  :root {
    --ink: #0c0e1c;
    --ink-rise: #141729;
    --ink-deep: #06080f;
    --paper: #f0e8d6;
    --blue: #1a4faf;
    --blue-deep: #002f6c;
    --grenat: #b3163a;
    --grenat-deep: #82001f;
    --gold: #f5c518;
    --silver: #d4d8e0;
    --mist: #6b7388;
    --rule: #1f2236;
    --rule-bright: #2a2e48;
    --win: #6dd47a;
    --font-display: "Fraunces", "Times New Roman", serif;
    --font-body: "Manrope", -apple-system, system-ui, sans-serif;
    --font-mono: "JetBrains Mono", "SFMono-Regular", monospace;
    --font-numeric: "Big Shoulders Display", "Manrope", sans-serif;
  }
  * { box-sizing: border-box; }
  html { background: var(--ink-deep); }
  body {
    margin: 0;
    font-family: var(--font-body);
    background: var(--ink);
    color: var(--silver);
    line-height: 1.55;
    font-feature-settings: "tnum", "ss01";
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
    background-image:
      radial-gradient(circle at 12% 8%, rgba(26, 79, 175, 0.08), transparent 40%),
      radial-gradient(circle at 88% 92%, rgba(179, 22, 58, 0.06), transparent 45%),
      url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.95 0 0 0 0 0.95 0 0 0 0 0.95 0 0 0 0.04 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
    background-attachment: fixed;
  }
  ::selection { background: var(--gold); color: var(--ink); }
  a { color: var(--silver); text-decoration: none; }

  .wrap { max-width: 1280px; margin: 0 auto; padding: 0 32px 64px; }

  /* ─── ticker top bar ─── */
  .ticker {
    border-bottom: 1px solid var(--rule);
    padding: 10px 0;
    margin-bottom: 36px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.06em;
    color: var(--mist);
    text-transform: uppercase;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px 24px;
  }
  .ticker .live::before {
    content: "";
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--grenat);
    margin-right: 6px;
    vertical-align: 1px;
    animation: pulse 1.6s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(179, 22, 58, 0.7); }
    50%      { box-shadow: 0 0 0 6px rgba(179, 22, 58, 0); }
  }
  .ticker .label { color: var(--silver); }
  .ticker .sep   { color: var(--rule-bright); }
  .ticker .kicker-mercado {
    color: var(--gold);
    font-weight: 600;
    letter-spacing: 0.18em;
  }

  /* ─── masthead ─── */
  .masthead {
    position: relative;
    padding: 12px 0 24px;
    border-bottom: 2px solid var(--paper);
    margin-bottom: 28px;
    overflow: hidden;
  }
  .masthead-shield {
    position: absolute;
    right: -40px;
    top: -10px;
    width: 220px;
    opacity: 0.07;
    pointer-events: none;
  }
  .kicker {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--gold);
    margin: 0 0 14px;
    font-weight: 500;
  }
  h1.title {
    margin: 0;
    font-family: var(--font-display);
    font-weight: 300;
    font-style: italic;
    font-size: clamp(38px, 6vw, 76px);
    line-height: 0.95;
    letter-spacing: -0.025em;
    color: var(--paper);
    font-variation-settings: "opsz" 144;
  }
  h1.title em {
    font-style: normal;
    font-weight: 600;
    color: var(--silver);
  }
  .strap {
    margin: 18px 0 0;
    font-family: var(--font-mono);
    font-size: 11.5px;
    color: var(--mist);
    letter-spacing: 0.04em;
    max-width: 60ch;
    line-height: 1.7;
  }
  .strap b { color: var(--silver); font-weight: 500; }

  /* ─── nav (page tabs) ─── */
  .page-nav {
    display: flex;
    gap: 0;
    margin: 32px 0 0;
    padding: 0;
    border-bottom: 1px solid var(--rule);
  }
  .page-nav a {
    padding: 14px 24px 14px 0;
    margin-right: 28px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--mist);
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: color 200ms;
  }
  .page-nav a:hover { color: var(--silver); }
  .page-nav a.active {
    color: var(--paper);
    border-bottom-color: var(--gold);
  }

  /* ─── section titles ─── */
  section { margin: 48px 0 64px; }
  .section-title {
    display: flex;
    align-items: baseline;
    gap: 16px;
    margin: 0 0 28px;
    border-bottom: 1px solid var(--rule);
    padding-bottom: 14px;
  }
  .section-title h2 {
    margin: 0;
    font-family: var(--font-display);
    font-weight: 400;
    font-style: italic;
    font-size: 28px;
    letter-spacing: -0.01em;
    color: var(--paper);
  }
  .section-title .num {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.16em;
    color: var(--gold);
    text-transform: uppercase;
  }
  .section-title .meta {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--mist);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  /* ───────────────────────────────────────────
     NEWS FEED — OneFootball-style cards
     ─────────────────────────────────────────── */
  .day-block { margin-bottom: 40px; }
  .day-header {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--gold);
    text-transform: uppercase;
    letter-spacing: 0.18em;
    margin: 0 0 16px;
    padding-bottom: 6px;
    border-bottom: 1px dashed var(--rule-bright);
    font-weight: 500;
  }
  .news-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 32px 24px;
    margin-bottom: 8px;
  }
  .news-card {
    transition: transform 240ms ease;
  }
  .news-card:hover { transform: translateY(-4px); }
  .news-card .cover {
    position: relative;
    width: 100%;
    aspect-ratio: 1/1;
    overflow: hidden;
    margin-bottom: 14px;
    border: 1px solid var(--rule);
    background: var(--ink-rise);
  }
  /* Layer 1: foto blurada e ampliada — estende o fundo do photo nos cantos do card */
  .news-card .cover .bg {
    position: absolute;
    inset: -8%;
    background-size: cover;
    background-position: center;
    filter: blur(32px) saturate(1.35) brightness(0.55);
    z-index: 1;
  }
  /* Layer 2: foto nítida contida com padding pra dar zoom-out real */
  .news-card .cover img {
    position: relative;
    z-index: 2;
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
    object-position: center;
    padding: 14px 0;
    box-sizing: border-box;
    transition: transform 600ms ease;
  }
  .news-card:hover .cover img { transform: scale(1.03); }
  /* Text cover (no player matched) */
  .news-card .cover.text {
    align-items: flex-end;
    justify-content: flex-start;
    padding: 22px;
  }
  .news-card .cover.text .text-cover-source {
    position: relative;
    z-index: 2;
    font-family: var(--font-display);
    font-style: italic;
    font-weight: 400;
    font-size: 22px;
    color: var(--paper);
    line-height: 1.15;
    letter-spacing: -0.01em;
  }
  .news-card .cover .badge {
    position: absolute;
    top: 12px;
    left: 12px;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    background: rgba(12, 14, 28, 0.85);
    color: var(--gold);
    padding: 4px 9px;
    backdrop-filter: blur(4px);
    z-index: 3;
  }
  .news-card.rumor .cover .badge { color: var(--grenat); }
  .news-card .meta-row {
    display: flex;
    align-items: center;
    gap: 12px;
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--mist);
    margin-bottom: 10px;
  }
  .news-card .meta-row .journalist {
    color: var(--gold);
    font-weight: 600;
    letter-spacing: 0.14em;
  }
  .news-card h3 {
    margin: 0 0 10px;
    font-family: var(--font-display);
    font-weight: 500;
    font-size: 20px;
    line-height: 1.2;
    letter-spacing: -0.01em;
    color: var(--paper);
    font-variation-settings: "opsz" 36;
  }
  .news-card h3 a { color: inherit; }
  .news-card h3 a:hover { color: var(--gold); }
  .news-card .snippet {
    margin: 0 0 10px;
    font-size: 13.5px;
    line-height: 1.55;
    color: var(--silver);
    opacity: 0.78;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .news-card .player-tags { display: flex; gap: 6px; flex-wrap: wrap; }
  .player-tag {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    color: var(--paper);
    background: rgba(179, 22, 58, 0.18);
    border: 1px solid var(--grenat);
    padding: 2px 8px;
    border-radius: 999px;
    text-transform: uppercase;
    font-weight: 500;
  }
  .news-meta {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--mist);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .news-toggle {
    margin-top: 24px;
    background: transparent;
    border: 1px solid var(--rule);
    color: var(--silver);
    padding: 10px 22px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    cursor: pointer;
    transition: border-color 200ms, color 200ms;
  }
  .news-toggle:hover { border-color: var(--gold); color: var(--gold); }
  .news-empty {
    border: 1px dashed var(--rule-bright);
    padding: 56px 24px;
    text-align: center;
    color: var(--mist);
    font-family: var(--font-mono);
    font-size: 12px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  /* ───────────────────────────────────────────
     COMPARADOR — chips, photo grid, dossiers
     ─────────────────────────────────────────── */
  .position-chips {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 28px;
  }
  .position-chip {
    background: transparent;
    border: 1px solid var(--rule);
    color: var(--silver);
    padding: 10px 18px;
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 180ms;
    font-weight: 500;
  }
  .position-chip:hover { border-color: var(--rule-bright); color: var(--paper); }
  .position-chip.active {
    background: var(--gold);
    color: var(--ink);
    border-color: var(--gold);
  }

  .selection-bar {
    display: flex;
    gap: 14px;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 36px;
    padding: 18px 24px;
    background: var(--ink-rise);
    border-left: 2px solid var(--gold);
    min-height: 96px;
  }
  .selection-bar .hint {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--mist);
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .selection-bar .selected-chip {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 4px 16px 4px 4px;
    background: rgba(245, 197, 24, 0.08);
    border: 1px solid var(--gold);
    cursor: pointer;
    transition: background 150ms;
  }
  .selection-bar .selected-chip:hover { background: rgba(245, 197, 24, 0.16); }
  .selection-bar .selected-chip img {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    object-fit: cover;
    background: var(--ink-deep);
  }
  .selection-bar .selected-chip .info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .selection-bar .selected-chip .name {
    font-weight: 600;
    font-size: 13px;
    color: var(--paper);
  }
  .selection-bar .selected-chip .src {
    font-family: var(--font-mono);
    font-size: 9.5px;
    letter-spacing: 0.14em;
    color: var(--mist);
    text-transform: uppercase;
  }
  .selection-bar .selected-chip .x {
    color: var(--mist);
    font-size: 16px;
    margin-left: 4px;
    line-height: 1;
  }

  .player-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
    gap: 16px;
    margin-bottom: 36px;
  }
  .group-divider {
    grid-column: 1 / -1;
    font-family: var(--font-mono);
    font-size: 10.5px;
    color: var(--gold);
    text-transform: uppercase;
    letter-spacing: 0.18em;
    padding: 14px 0 6px;
    border-bottom: 1px dashed var(--rule);
    margin: 8px 0 4px;
  }
  .player-tile {
    position: relative;
    padding: 22px 14px 18px;
    background: var(--ink-rise);
    border: 1px solid var(--rule);
    cursor: pointer;
    transition: all 200ms ease;
    text-align: center;
    overflow: hidden;
  }
  .player-tile:hover {
    border-color: var(--rule-bright);
    transform: translateY(-3px);
  }
  .player-tile.selected {
    border-color: var(--gold);
    box-shadow: inset 0 0 0 2px var(--gold), 0 8px 24px -12px rgba(245, 197, 24, 0.4);
  }
  .player-tile.selected::after {
    content: "✓";
    position: absolute;
    top: 8px; right: 8px;
    width: 22px; height: 22px;
    background: var(--gold);
    color: var(--ink);
    border-radius: 50%;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
  }
  .player-tile .badge {
    position: absolute;
    top: 8px; left: 8px;
    font-family: var(--font-mono);
    font-size: 9px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--mist);
  }
  .player-tile.rumor .badge { color: var(--grenat); }
  .player-tile.main .badge,
  .player-tile.athletic .badge { color: var(--blue); }
  .player-tile .photo {
    width: 96px;
    height: 96px;
    margin: 8px auto 12px;
    border-radius: 50%;
    background: var(--ink-deep);
    overflow: hidden;
    border: 2px solid var(--rule-bright);
    transition: border-color 200ms;
  }
  .player-tile.rumor .photo { border-color: var(--grenat); }
  .player-tile.main .photo,
  .player-tile.athletic .photo { border-color: var(--blue); }
  .player-tile.selected .photo { border-color: var(--gold); }
  .player-tile .photo img {
    width: 100%; height: 100%;
    object-fit: cover;
    object-position: center top;
  }
  .player-tile .photo.fallback {
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-display);
    font-weight: 600;
    font-style: italic;
    font-size: 32px;
    color: var(--mist);
  }
  .player-tile h4 {
    margin: 0 0 4px;
    font-family: var(--font-body);
    font-weight: 600;
    font-size: 13.5px;
    line-height: 1.25;
    color: var(--paper);
  }
  .player-tile .pos {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.1em;
    color: var(--gold);
    text-transform: uppercase;
    margin-bottom: 4px;
  }
  .player-tile .team {
    font-size: 11px;
    color: var(--mist);
    line-height: 1.3;
  }

  /* ─── comparison area (dossier + ledger) ─── */
  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin: 8px 0 24px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--rule);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--mist);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
  .info-row .pos-tag {
    color: var(--gold);
    font-weight: 600;
    letter-spacing: 0.18em;
    margin-right: 14px;
  }
  .player-cards {
    display: grid;
    gap: 0;
    margin-bottom: 36px;
    border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule);
  }
  .player-cards.cols-2 { grid-template-columns: 1fr 1fr; }
  .player-cards.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
  .pcard {
    position: relative;
    padding: 28px 24px;
    border-right: 1px solid var(--rule);
    overflow: hidden;
  }
  .pcard:last-child { border-right: none; }
  .pcard::before {
    content: "";
    position: absolute;
    top: 0; left: 0;
    width: 3px; height: 56px;
    background: var(--blue);
  }
  .pcard.rumor::before { background: var(--grenat); }
  .pcard .jersey {
    position: absolute;
    right: 18px;
    top: 14px;
    font-family: var(--font-numeric);
    font-weight: 800;
    font-size: 84px;
    line-height: 0.85;
    color: var(--paper);
    opacity: 0.07;
    letter-spacing: -0.04em;
    pointer-events: none;
  }
  .pcard.rumor .jersey { color: var(--grenat); opacity: 0.18; }
  .pcard .pcard-source {
    font-family: var(--font-mono);
    font-size: 9.5px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--mist);
    margin-bottom: 6px;
    font-weight: 500;
  }
  .pcard.main .pcard-source,
  .pcard.athletic .pcard-source { color: var(--blue); }
  .pcard.rumor .pcard-source { color: var(--grenat); }
  .pcard h3 {
    margin: 0 0 8px;
    font-family: var(--font-display);
    font-weight: 500;
    font-size: 26px;
    line-height: 1.05;
    letter-spacing: -0.018em;
    color: var(--paper);
    font-variation-settings: "opsz" 72;
  }
  .pcard .meta {
    color: var(--silver);
    opacity: 0.78;
    font-size: 12.5px;
    line-height: 1.7;
  }
  .pcard .league-line {
    display: block;
    margin-top: 4px;
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.06em;
    color: var(--mist);
    text-transform: uppercase;
  }
  .pcard .note {
    display: block;
    margin-top: 12px;
    font-family: var(--font-display);
    font-style: italic;
    font-size: 13px;
    color: var(--gold);
    line-height: 1.5;
    border-left: 2px solid var(--gold);
    padding-left: 10px;
    opacity: 0.85;
  }

  /* ─── stats ledger ─── */
  .stats-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 12px;
  }
  .stats-table thead th {
    padding: 14px 16px;
    text-align: right;
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--mist);
    font-weight: 500;
    border-bottom: 1px solid var(--paper);
  }
  .stats-table thead th:first-child { text-align: left; color: var(--paper); }
  .stats-table tbody td {
    padding: 12px 16px;
    border-bottom: 1px solid var(--rule);
    text-align: right;
    font-family: var(--font-mono);
    font-size: 14px;
    color: var(--silver);
    font-feature-settings: "tnum";
  }
  .stats-table tbody td:first-child {
    text-align: left;
    font-family: var(--font-body);
    color: var(--silver);
    font-size: 13.5px;
  }
  .stats-table tbody tr:last-child td { border-bottom: none; }
  .stats-table tbody tr:hover td { background: rgba(240, 232, 214, 0.02); }
  .stats-table td.win {
    color: var(--gold);
    font-weight: 600;
  }
  .stats-table td.win::before {
    content: "▲";
    margin-right: 6px;
    font-size: 9px;
    vertical-align: 2px;
  }
  .stats-table td.loss { color: var(--mist); }

  .empty {
    border: 1px dashed var(--rule-bright);
    padding: 56px 24px;
    text-align: center;
    color: var(--mist);
    font-family: var(--font-display);
    font-style: italic;
    font-size: 16px;
  }

  /* ─── footer ─── */
  footer {
    margin-top: 80px;
    padding-top: 24px;
    border-top: 1px solid var(--rule);
    color: var(--mist);
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.06em;
    line-height: 1.7;
  }
  footer code {
    color: var(--silver);
    background: var(--ink-rise);
    padding: 1px 6px;
    font-size: 10px;
  }

  /* ─── reveal ─── */
  .reveal { opacity: 0; transform: translateY(8px); animation: reveal 700ms ease forwards; }
  .reveal.d1 { animation-delay: 50ms; }
  .reveal.d2 { animation-delay: 150ms; }
  .reveal.d3 { animation-delay: 280ms; }
  .reveal.d4 { animation-delay: 420ms; }
  @keyframes reveal { to { opacity: 1; transform: translateY(0); } }

  /* ─── responsive ─── */
  @media (max-width: 1100px) {
    .news-grid { grid-template-columns: repeat(2, 1fr); }
    .news-grid .news-card.hero { grid-template-columns: 1fr; }
    .news-grid .news-card.hero .cover { aspect-ratio: 16/10; min-height: 0; }
  }
  @media (max-width: 720px) {
    .news-grid { grid-template-columns: 1fr; }
    .player-cards.cols-2, .player-cards.cols-3 { grid-template-columns: 1fr; border-right: none; }
    .pcard { border-right: none; border-bottom: 1px solid var(--rule); }
    .pcard:last-child { border-bottom: none; }
  }
  @media (max-width: 560px) {
    .wrap { padding: 0 18px 48px; }
    h1.title { font-size: 40px; }
  }
</style>
</head>
"""


def _masthead(active: str) -> str:
    """Returns the masthead + nav HTML. `active` is either 'index' or 'comparador'."""
    cls_idx = "active" if active == "index" else ""
    cls_cmp = "active" if active == "comparador" else ""
    return f"""<body>
<div class="wrap">

<div class="ticker reveal d1" id="ticker-bar">
  <span class="kicker-mercado">MERCADO</span>
  <span id="ticker-date"></span>
</div>

<header class="masthead reveal d2">
  <svg class="masthead-shield" viewBox="0 0 100 130" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <defs>
      <pattern id="hatch" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="6" stroke="#f0e8d6" stroke-width="0.6"/>
      </pattern>
    </defs>
    <path d="M50 0 L100 18 L100 70 Q100 110 50 130 Q0 110 0 70 L0 18 Z" fill="none" stroke="#f0e8d6" stroke-width="2"/>
    <path d="M50 12 L88 26 L88 68 Q88 100 50 116 Q12 100 12 68 L12 26 Z" fill="url(#hatch)" stroke="#f0e8d6" stroke-width="1"/>
    <line x1="50" y1="12" x2="50" y2="116" stroke="#f0e8d6" stroke-width="1"/>
    <line x1="12" y1="64" x2="88" y2="64" stroke="#f0e8d6" stroke-width="1"/>
  </svg>
  <h1 class="title">Transfer<br><em>Desk</em>&nbsp;FCB.</h1>
  <nav class="page-nav">
    <a href="index.html" class="{cls_idx}">Notícias</a>
    <a href="comparador.html" class="{cls_cmp}">Comparador</a>
  </nav>
</header>
"""


FOOTER_HTML = r"""
</div>
"""


SHARED_SCRIPT = r"""
window.DATA = __DATA__;
// Fotos locais (baixadas via scrapers/fetch_photos.py) — evita bloqueio ORB do Chrome
// quando carregadas direto da CDN do SofaScore em outro domínio (GitHub Pages, etc).
// Cache-buster baseado em window.DATA.generated força o browser a re-baixar quando
// reprocessamos as fotos (ex: pra remover fundo branco).
const PHOTO_VER = encodeURIComponent(window.DATA.generated || "1");
const PHOTO_URL = (id) => `assets/photos/${id}.webp?v=${PHOTO_VER}`;

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}
function fmt(v) {
  if (v == null) return "—";
  if (typeof v === "number") {
    if (Number.isInteger(v)) return v.toString();
    return v.toFixed(2);
  }
  return v.toString();
}
function sourceMeta(s) {
  return window.DATA.sources[s] || { order: 9, label_short: s || "outros", label_long: (s || "OUTROS").toUpperCase(), default_team: "?" };
}
function toDate(iso) {
  if (!iso) return null;
  const hasTZ = /Z$|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasTZ ? iso : iso + "Z");
}
function dayKey(iso) {
  const dt = toDate(iso);
  if (!dt || isNaN(dt)) return "";
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const d = String(dt.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
function dayLabel(key) {
  if (!key) return "Sem data";
  const today = new Date();
  const tk = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,"0")}-${String(today.getDate()).padStart(2,"0")}`;
  const yd = new Date(today.getTime() - 86400000);
  const yk = `${yd.getFullYear()}-${String(yd.getMonth()+1).padStart(2,"0")}-${String(yd.getDate()).padStart(2,"0")}`;
  if (key === tk) return "Hoje";
  if (key === yk) return "Ontem";
  const [y, m, d] = key.split("-");
  return `${d}/${m}/${y}`;
}
function fmtTime(iso) {
  const dt = toDate(iso);
  if (!dt || isNaN(dt)) return "";
  return dt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}
function playerById(id) {
  return window.DATA.players.find(p => p.id === id);
}
function initials(name) {
  return (name || "?").split(/\s+/).filter(Boolean).slice(0, 2)
    .map(w => w[0]).join("").toUpperCase();
}

// Ticker date
(() => {
  const el = document.getElementById("ticker-date");
  if (!el) return;
  const now = new Date();
  const wd = now.toLocaleDateString("pt-BR", { weekday: "long" }).toUpperCase();
  const dt = now.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" }).toUpperCase();
  el.innerHTML = `<span class="label">${esc(wd)}</span> <span class="sep">/</span> ${esc(dt)}`;
})();
"""


# ─────────────────────────────────────────────────────────────────
#  INDEX (news feed) — body + script
# ─────────────────────────────────────────────────────────────────

INDEX_BODY = r"""
<section class="reveal d3">
  <div class="section-title">
    <span class="num">§ 01</span>
    <h2>Feed de notícias</h2>
  </div>
  <div id="news-feed"></div>
  <button class="news-toggle" id="news-toggle" style="display:none">Mostrar mais ↓</button>
</section>
"""


INDEX_SCRIPT = r"""
const NEWS_PAGE_SIZE = 9;
let newsExpanded = false;

function newsCardHTML(it) {
  const time = fmtTime(it.published_at || it.last_seen);
  const tagsHtml = (it.players_mentioned || [])
    .map(pid => window.DATA.player_names[pid])
    .filter(n => n)
    .map(n => `<span class="player-tag">${esc(n)}</span>`).join("");
  const mentioned = (it.players_mentioned || []).map(pid => playerById(pid)).filter(Boolean);
  const isRumor = mentioned.some(p => p.source === "rumor");
  const cardCls = `news-card ${isRumor ? "rumor" : ""}`;

  // Cover: foto do jogador (se mencionado) ou text cover editorial
  let coverHtml;
  if (mentioned.length >= 1) {
    const p = mentioned[0];
    const photoSrc = PHOTO_URL(p.id);
    const moreBadge = mentioned.length > 1
      ? `<span class="badge">+${mentioned.length - 1}</span>`
      : `<span class="badge">${esc((it.journalist || "?").toUpperCase())}</span>`;
    coverHtml = `
      <div class="cover">
        <div class="bg" style="background-image: url('${photoSrc}')"></div>
        ${moreBadge}
        <img src="${photoSrc}" alt="${esc(p.name)}" loading="lazy"
             onerror="this.style.display='none'">
      </div>`;
  } else {
    coverHtml = `
      <div class="cover text">
        <span class="badge">${esc((it.journalist || "?").toUpperCase())}</span>
        <span class="text-cover-source">${esc(it.title.slice(0, 70))}${it.title.length > 70 ? "…" : ""}</span>
      </div>`;
  }

  return `
    <article class="${cardCls}">
      ${coverHtml}
      <div class="meta-row">
        <span class="journalist">${esc(it.journalist || "?")}</span>
        <span>${esc(time)}</span>
      </div>
      <h3><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title)}</a></h3>
      <p class="snippet">${esc(it.snippet || "")}</p>
    </article>`;
}

function renderNews() {
  const container = document.getElementById("news-feed");
  const toggleBtn = document.getElementById("news-toggle");
  const items = window.DATA.news || [];

  if (items.length === 0) {
    container.innerHTML = '<div class="news-empty">Sem notícias capturadas ainda · A rotina rodará em breve</div>';
    toggleBtn.style.display = "none";
    return;
  }

  const visible = newsExpanded ? items : items.slice(0, NEWS_PAGE_SIZE);
  const byDay = {};
  for (const it of visible) {
    const k = dayKey(it.published_at || it.last_seen);
    (byDay[k] = byDay[k] || []).push(it);
  }
  const datedKeys = Object.keys(byDay).filter(k => k).sort().reverse();
  const noDate = byDay[""] ? [""] : [];
  const dayKeys = [...datedKeys, ...noDate];

  let html = "";
  for (const k of dayKeys) {
    html += `<div class="day-block"><h3 class="day-header">${esc(dayLabel(k))}</h3><div class="news-grid">`;
    for (const it of byDay[k]) {
      html += newsCardHTML(it);
    }
    html += `</div></div>`;
  }
  container.innerHTML = html;

  if (items.length > NEWS_PAGE_SIZE) {
    toggleBtn.style.display = "";
    toggleBtn.textContent = newsExpanded
      ? "Mostrar menos ↑"
      : `Mostrar mais ↓ (${items.length - NEWS_PAGE_SIZE} restantes)`;
  } else {
    toggleBtn.style.display = "none";
  }
}

document.getElementById("news-toggle").addEventListener("click", () => {
  newsExpanded = !newsExpanded;
  renderNews();
});

renderNews();
"""


# ─────────────────────────────────────────────────────────────────
#  COMPARADOR — body + script
# ─────────────────────────────────────────────────────────────────

COMPARADOR_BODY = r"""
<section class="reveal d3">
  <div class="section-title">
    <span class="num">§ 02</span>
    <h2>Comparador</h2>
    <span class="meta" id="selection-count">0 / 3 selecionados</span>
  </div>

  <div class="position-chips" id="position-chips"></div>
  <div class="selection-bar" id="selection-bar"></div>
  <div class="player-grid" id="player-grid"></div>
  <div id="comparison-area"></div>
</section>
"""


COMPARADOR_SCRIPT = r"""
// State
let activeGroup = null;
let selectedIds = [];
const MAX_SELECTED = 3;

const chipsEl = document.getElementById("position-chips");
const selBar  = document.getElementById("selection-bar");
const gridEl  = document.getElementById("player-grid");
const compEl  = document.getElementById("comparison-area");
const countEl = document.getElementById("selection-count");

function renderChips() {
  const groups = window.DATA.groups;
  chipsEl.innerHTML = Object.entries(groups).map(([key, label]) =>
    `<button class="position-chip ${activeGroup === key ? "active" : ""}" data-group="${esc(key)}">${esc(label)}</button>`
  ).join("");
  chipsEl.querySelectorAll(".position-chip").forEach(btn => {
    btn.addEventListener("click", () => {
      activeGroup = btn.dataset.group;
      selectedIds = [];
      renderAll();
    });
  });
}

function playersInGroup(group) {
  return window.DATA.players
    .filter(p => p.position_group === group)
    .sort((a, b) => {
      const ao = sourceMeta(a.source).order;
      const bo = sourceMeta(b.source).order;
      if (ao !== bo) return ao - bo;
      return a.name.localeCompare(b.name);
    });
}

function tileHTML(p) {
  const isSel = selectedIds.includes(p.id);
  const src = sourceMeta(p.source);
  return `
    <article class="player-tile ${esc(p.source)} ${isSel ? "selected" : ""}" data-id="${p.id}">
      <span class="badge">${esc(src.label_short)}</span>
      <div class="photo">
        <img src="${PHOTO_URL(p.id)}" alt="${esc(p.name)}" loading="lazy"
             onerror="this.parentElement.classList.add('fallback'); this.outerHTML='${esc(initials(p.name))}'">
      </div>
      <p class="pos">${esc(p.position_refined)}</p>
      <h4>${esc(p.name)}</h4>
      <p class="team">${esc(p.team)}</p>
    </article>`;
}

function renderGrid() {
  if (!activeGroup) {
    gridEl.innerHTML = `<div class="empty" style="grid-column:1/-1">Escolha uma posição acima para ver os jogadores disponíveis.</div>`;
    return;
  }
  const players = playersInGroup(activeGroup);
  if (players.length === 0) {
    gridEl.innerHTML = `<div class="empty" style="grid-column:1/-1">Nenhum jogador com stats nessa posição.</div>`;
    return;
  }
  // Group by source with dividers
  let html = "";
  let lastSource = null;
  for (const p of players) {
    if (p.source !== lastSource) {
      html += `<div class="group-divider">── ${esc(sourceMeta(p.source).label_long)} ──</div>`;
      lastSource = p.source;
    }
    html += tileHTML(p);
  }
  gridEl.innerHTML = html;

  gridEl.querySelectorAll(".player-tile").forEach(tile => {
    tile.addEventListener("click", () => {
      const id = parseInt(tile.dataset.id);
      const idx = selectedIds.indexOf(id);
      if (idx >= 0) {
        selectedIds.splice(idx, 1);
      } else if (selectedIds.length < MAX_SELECTED) {
        selectedIds.push(id);
      }
      renderAll();
    });
  });
}

function renderSelectionBar() {
  countEl.textContent = `${selectedIds.length} / ${MAX_SELECTED} selecionados`;
  if (selectedIds.length === 0) {
    selBar.innerHTML = `<span class="hint">Selecione 2 ou 3 jogadores na grade abaixo · Clique novamente para remover</span>`;
    return;
  }
  const chips = selectedIds.map(id => {
    const p = playerById(id);
    if (!p) return "";
    const src = sourceMeta(p.source);
    return `
      <button class="selected-chip" data-id="${p.id}">
        <img src="${PHOTO_URL(p.id)}" alt="${esc(p.name)}" loading="lazy">
        <span class="info">
          <span class="name">${esc(p.name)}</span>
          <span class="src">${esc(src.label_short)} · ${esc(p.position_refined)}</span>
        </span>
        <span class="x">×</span>
      </button>`;
  }).join("");
  const remaining = MAX_SELECTED - selectedIds.length;
  const hint = selectedIds.length < 2
    ? `<span class="hint">Selecione mais ${2 - selectedIds.length} jogador${2 - selectedIds.length > 1 ? "es" : ""} para comparar</span>`
    : (remaining > 0 ? `<span class="hint">Pode adicionar mais ${remaining}</span>` : "");
  selBar.innerHTML = chips + hint;

  selBar.querySelectorAll(".selected-chip").forEach(b => {
    b.addEventListener("click", () => {
      const id = parseInt(b.dataset.id);
      selectedIds = selectedIds.filter(x => x !== id);
      renderAll();
    });
  });
}

function renderComparison() {
  const selected = selectedIds.map(playerById).filter(Boolean);
  if (selected.length < 2 || !activeGroup) {
    compEl.innerHTML = "";
    return;
  }
  const stats = window.DATA.stats_by_group[activeGroup];

  const cardsHtml = selected.map(p => {
    const src = sourceMeta(p.source);
    const jersey = p.jersey != null ? p.jersey : "—";
    const bio = [
      p.age ? `${p.age} anos` : null,
      p.height ? `${p.height} cm` : null,
      p.preferredFoot ? `pé ${p.preferredFoot.toLowerCase()}` : null,
    ].filter(Boolean).join(" · ");
    return `
      <article class="pcard ${esc(p.source)}">
        <span class="jersey">${esc(jersey)}</span>
        <p class="pcard-source">${esc(src.label_short)} · ${esc(p.position_refined)}</p>
        <h3>${esc(p.name)}</h3>
        <div class="meta">
          ${esc(p.team)}${p.country ? ` · ${esc(p.country)}` : ""}<br>
          ${esc(bio)}
          <span class="league-line">${esc(p.league || "—")}</span>
          ${p.note ? `<span class="note">${esc(p.note)}</span>` : ""}
        </div>
      </article>`;
  }).join("");

  let rowsHtml = "";
  for (const stat of stats) {
    const values = selected.map(p => {
      const v = p.stats[stat.key];
      return typeof v === "number" ? v : null;
    });
    const valid = values.filter(v => v !== null);
    let best = null, allEqual = true;
    if (valid.length > 0) {
      const min = Math.min(...valid), max = Math.max(...valid);
      best = stat.smaller_better ? min : max;
      allEqual = Math.abs(max - min) < 1e-9;
    }
    const cells = values.map(v => {
      if (v === null) return `<td class="loss">—</td>`;
      const isBest = (!allEqual && best !== null && Math.abs(v - best) < 1e-9);
      return `<td class="${isBest ? "win" : ""}">${fmt(v)}</td>`;
    }).join("");
    rowsHtml += `<tr><td>${esc(stat.label)}</td>${cells}</tr>`;
  }

  const headers = selected.map(p => `<th>${esc(p.shortName || p.name)}</th>`).join("");
  const groupLabel = window.DATA.groups[activeGroup];

  compEl.innerHTML = `
    <div class="info-row">
      <span><span class="pos-tag">${esc(groupLabel)}</span>${selected.length} jogadores · stats 25/26</span>
      <span>▲ vencedor por 90 min · — sem dados</span>
    </div>
    <div class="player-cards cols-${selected.length}">${cardsHtml}</div>
    <table class="stats-table">
      <thead><tr><th>Estatística</th>${headers}</tr></thead>
      <tbody>${rowsHtml}</tbody>
    </table>
  `;
}

function renderAll() {
  renderChips();
  renderSelectionBar();
  renderGrid();
  renderComparison();
}

renderAll();
"""


# ─────────────────────────────────────────────────────────────────
#  ASSEMBLE & RENDER
# ─────────────────────────────────────────────────────────────────

def _assemble(active_page: str, title: str, body: str, page_script: str, payload: dict) -> str:
    head = HEAD_OPEN.replace("__TITLE__", title)
    masthead = _masthead(active_page)
    full_script = SHARED_SCRIPT + page_script
    full_script = full_script.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
    return head + masthead + body + FOOTER_HTML + "<script>" + full_script + "</script></body></html>"


def render_index(payload: dict) -> str:
    return _assemble(
        "index",
        "Feed · Transfer Desk FCB",
        INDEX_BODY,
        INDEX_SCRIPT,
        payload,
    )


def render_comparador(payload: dict) -> str:
    return _assemble(
        "comparador",
        "Comparador · Transfer Desk FCB",
        COMPARADOR_BODY,
        COMPARADOR_SCRIPT,
        payload,
    )


def main():
    players = merge_data()
    print(f"merge_data: {len(players)} jogadores")
    payload = _build_payload(players)
    print(f"  {len(payload['players'])}/{len(players)} utilizáveis no picker")
    print(f"  {len(payload['news'])} notícias no feed")

    (ROOT / "index.html").write_text(render_index(payload), encoding="utf-8")
    (ROOT / "comparador.html").write_text(render_comparador(payload), encoding="utf-8")
    print(f"\nOK -> index.html + comparador.html")

    from collections import Counter
    groups = Counter(p["position_group"] for p in payload["players"])
    print(f"  por grupo: {dict(groups)}")


if __name__ == "__main__":
    main()
