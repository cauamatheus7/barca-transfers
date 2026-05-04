"""
Gera index.html com picker dinâmico para comparar:
  - jogadores especulados entre si
  - especulados vs atuais do elenco

Lê squad.json + rumors.json + stats.json e injeta tudo como <script>
em index.html (sem precisar de servidor — abre com duplo clique).
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

BARCA_BLUE   = "#004D98"
BARCA_GRENAT = "#A50044"
BARCA_GOLD   = "#FFED02"

# L3: tabela única para metadata de cada origem do jogador.
# Tudo (sort order, label curto, label long, time default) sai daqui — não duplicar em JS.
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
    Ordem de precedência:
    1. REFINED_POSITIONS (override manual por nome)
    2. position_target (do rumor)
    3. position_detailed (do SofaScore)
    4. fallback genérico G/D/M/F → GK/CB/CM/ST
    """
    name = player["name"]
    if name in REFINED_POSITIONS:
        return REFINED_POSITIONS[name]
    if player.get("source") == "rumor" and player.get("position_target"):
        return player["position_target"]
    # B2: usa position_detailed (lista do SofaScore) se a primeira posição é reconhecida
    detailed = player.get("position_detailed") or []
    if isinstance(detailed, str):
        detailed = [d.strip() for d in detailed.split(",") if d.strip()]
    if detailed and detailed[0] in REFINED_TO_UI_GROUP:
        return detailed[0]
    # Fallback genérico (último recurso)
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

    # B3: indexa por ID; quando colide (ex: Marcus Rashford já no squad e em rumors),
    # mantém metadado do rumor — `note`, target_pos, e classifica como rumor pra UX.
    # Garante current_team em squad pra não perder time real numa colisão.
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
            # mantém current_team original do squad — não sobrescreve
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
            # B8: atividade recente (vinda do news pipeline)
            "last_seen": p.get("last_seen"),
            "mentions_count": p.get("mentions_count", 0),
            "latest_news_url": p.get("latest_news_url"),
            "latest_news_title": p.get("latest_news_title"),
            "latest_news_journalist": p.get("latest_news_journalist"),
        })

    return merged


def render_html(players: list[dict]) -> str:
    # Filtra quem tem stats e position_group válido
    usable = [p for p in players if p["stats"] and p["position_group"]]
    print(f"  {len(usable)}/{len(players)} jogadores utilizáveis no picker")

    news = load_news()
    print(f"  {len(news)} notícias no feed")

    # Mapa player_id -> nome pra mostrar tags clicáveis
    pid_to_name = {p["id"]: p["name"] for p in usable}

    payload = {
        "generated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "groups": POSITION_GROUPS_UI,
        "sources": SOURCES,                                          # L3: única fonte de verdade
        "stats_by_group": {
            g: [{"key": k, "label": l, "smaller_better": sb} for k, l, sb in STATS_BY_POSITION[g]]
            for g in POSITION_GROUPS_UI
        },
        "players": usable,
        "news": news,
        "player_names": pid_to_name,
    }

    return TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Centro de Transferências FC Barcelona — 2026</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&family=Big+Shoulders+Display:wght@600;800;900&display=swap" rel="stylesheet">
<style>
  :root {
    --ink: #0c0e1c;
    --ink-rise: #141729;
    --ink-deep: #06080f;
    --paper: #f0e8d6;
    --paper-dim: rgba(240, 232, 214, 0.08);
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
    /* paper grain via SVG noise */
    background-image:
      radial-gradient(circle at 12% 8%, rgba(26, 79, 175, 0.08), transparent 40%),
      radial-gradient(circle at 88% 92%, rgba(179, 22, 58, 0.06), transparent 45%),
      url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.95 0 0 0 0 0.95 0 0 0 0 0.95 0 0 0 0.04 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
    background-attachment: fixed;
  }
  ::selection { background: var(--gold); color: var(--ink); }
  a { color: var(--silver); }

  /* ─────────  layout shell  ───────── */
  .wrap { max-width: 1280px; margin: 0 auto; padding: 0 32px 64px; }

  /* ─────────  ticker (top status bar)  ───────── */
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
    width: 7px;
    height: 7px;
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

  /* ─────────  masthead  ───────── */
  .masthead {
    position: relative;
    padding: 12px 0 32px;
    border-bottom: 2px solid var(--paper);
    margin-bottom: 56px;
    overflow: hidden;
  }
  .masthead::after {
    content: "";
    position: absolute;
    left: 0; right: 0; bottom: -8px;
    height: 1px;
    background: var(--paper);
    opacity: 0.4;
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
    font-size: clamp(42px, 7vw, 88px);
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
    margin: 22px 0 0;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--mist);
    letter-spacing: 0.04em;
    max-width: 60ch;
    line-height: 1.7;
  }
  .strap b { color: var(--silver); font-weight: 500; }

  /* ─────────  section heading (editorial rule)  ───────── */
  section { margin-bottom: 64px; }
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

  /* ─────────  news feed  ───────── */
  .day-block { margin-bottom: 32px; }
  .day-header {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--gold);
    text-transform: uppercase;
    letter-spacing: 0.18em;
    margin: 0 0 14px;
    padding-bottom: 6px;
    border-bottom: 1px dashed var(--rule-bright);
    font-weight: 500;
  }
  .news-item {
    padding: 18px 0 22px;
    border-bottom: 1px solid var(--rule);
    transition: padding-left 200ms ease;
  }
  .news-item:hover { padding-left: 8px; }
  .news-item:last-child { border-bottom: none; }
  .news-item .row1 {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 8px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .news-item .journalist {
    color: var(--gold);
    font-weight: 600;
    letter-spacing: 0.14em;
  }
  .news-item .row1 span:not(.journalist) { color: var(--mist); }
  .news-item h4 {
    margin: 0 0 8px;
    font-family: var(--font-display);
    font-weight: 400;
    font-size: 22px;
    line-height: 1.25;
    letter-spacing: -0.012em;
    font-variation-settings: "opsz" 36;
  }
  .news-item h4 a { color: var(--paper); text-decoration: none; }
  .news-item h4 a:hover {
    color: var(--gold);
    text-decoration: underline;
    text-decoration-thickness: 1px;
    text-underline-offset: 4px;
  }
  .news-item .snippet {
    margin: 0 0 12px;
    color: var(--silver);
    font-size: 14px;
    line-height: 1.55;
    max-width: 75ch;
    opacity: 0.82;
  }
  .news-item .player-tags { display: flex; gap: 6px; flex-wrap: wrap; }
  .player-tag {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    color: var(--paper);
    background: rgba(179, 22, 58, 0.18);
    border: 1px solid var(--grenat);
    padding: 3px 9px;
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
    margin-top: 20px;
    background: transparent;
    border: 1px solid var(--rule);
    color: var(--silver);
    padding: 9px 18px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    cursor: pointer;
    transition: border-color 200ms, color 200ms;
  }
  .news-toggle:hover { border-color: var(--gold); color: var(--gold); }
  .news-empty {
    border: 1px dashed var(--rule-bright);
    padding: 40px 24px;
    text-align: center;
    color: var(--mist);
    font-family: var(--font-mono);
    font-size: 12px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  /* ─────────  picker (controls)  ───────── */
  .controls {
    display: grid;
    grid-template-columns: minmax(160px, 1fr) minmax(160px, 1fr) 2fr 2fr 2fr;
    gap: 16px;
    padding: 20px 24px;
    background: var(--ink-rise);
    border: 1px solid var(--rule);
    border-left: 2px solid var(--gold);
    margin-bottom: 32px;
    align-items: end;
  }
  .field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
  .field label {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--mist);
    text-transform: uppercase;
    letter-spacing: 0.16em;
    font-weight: 500;
  }
  select {
    background: var(--ink-deep);
    border: 1px solid var(--rule);
    color: var(--silver);
    padding: 11px 14px;
    font-family: var(--font-body);
    font-size: 14px;
    min-height: 42px;
    appearance: none;
    -webkit-appearance: none;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8' fill='none'><path d='M1 1l5 5 5-5' stroke='%23d4d8e0' stroke-width='1.5'/></svg>");
    background-repeat: no-repeat;
    background-position: right 14px center;
    padding-right: 36px;
    cursor: pointer;
    transition: border-color 150ms;
  }
  select:focus {
    outline: none;
    border-color: var(--gold);
  }
  select:hover { border-color: var(--rule-bright); }

  /* ─────────  comparison header  ───────── */
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

  /* ─────────  player dossiers  ───────── */
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
  .pcard.main .pcard-source { color: var(--blue); }
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

  /* ─────────  stats ledger  ───────── */
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
    text-transform: none;
    letter-spacing: 0;
  }
  .stats-table tbody tr:last-child td { border-bottom: none; }
  .stats-table tbody tr:hover td { background: rgba(240, 232, 214, 0.02); }
  .stats-table td.win {
    color: var(--gold);
    font-weight: 600;
    position: relative;
  }
  .stats-table td.win::before {
    content: "▲";
    margin-right: 6px;
    font-size: 9px;
    vertical-align: 2px;
  }
  .stats-table td.loss { color: var(--mist); }

  /* ─────────  empty states  ───────── */
  .empty {
    border: 1px dashed var(--rule-bright);
    padding: 56px 24px;
    text-align: center;
    color: var(--mist);
    font-family: var(--font-display);
    font-style: italic;
    font-size: 16px;
  }

  /* ─────────  footer  ───────── */
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

  /* ─────────  staggered page-load reveal  ───────── */
  .reveal { opacity: 0; transform: translateY(8px); animation: reveal 700ms ease forwards; }
  .reveal.d1 { animation-delay: 50ms; }
  .reveal.d2 { animation-delay: 150ms; }
  .reveal.d3 { animation-delay: 280ms; }
  .reveal.d4 { animation-delay: 420ms; }
  @keyframes reveal {
    to { opacity: 1; transform: translateY(0); }
  }

  /* ─────────  responsive  ───────── */
  @media (max-width: 900px) {
    .controls { grid-template-columns: 1fr 1fr; }
    .player-cards.cols-2, .player-cards.cols-3 {
      grid-template-columns: 1fr;
      border-right: none;
    }
    .pcard { border-right: none; border-bottom: 1px solid var(--rule); }
    .pcard:last-child { border-bottom: none; }
  }
  @media (max-width: 560px) {
    .wrap { padding: 0 18px 48px; }
    .controls { grid-template-columns: 1fr; }
    h1.title { font-size: 44px; }
  }
</style>
</head>
<body>
<div class="wrap">

<div class="ticker reveal d1" id="ticker-bar">
  <span><span class="live">LIVE</span> · MONITOR ATIVO</span>
  <span><span class="label">JANELA</span> <span class="sep">/</span> VERÃO 2026</span>
  <span><span class="label">FONTES</span> <span class="sep">/</span> 7 JORNALISTAS</span>
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
  <p class="kicker">Mercado · Janela 2026 · Edição diária</p>
  <h1 class="title">Transfer<br><em>Desk</em>&nbsp;FCB.</h1>
  <p class="strap">
    Centro de monitoramento de rumores e comparação de jogadores especulados contra o elenco do <b>FC&nbsp;Barcelona</b>. Atualizado três vezes ao dia a partir de fontes selecionadas <b>(Romano · Romero · Moretto · Rahman · Juanmartí · Piera · Soldevila)</b>. Estatísticas de desempenho via <b>SofaScore</b>, temporada 25/26.
  </p>
</header>

<section class="news-section reveal d3">
  <div class="section-title">
    <span class="num">§ 01</span>
    <h2>Feed de notícias</h2>
    <span class="meta" id="news-meta"></span>
  </div>
  <div id="news-feed"></div>
  <button class="news-toggle" id="news-toggle" style="display:none">Mostrar mais ↓</button>
</section>

<section class="reveal d4">
  <div class="section-title">
    <span class="num">§ 02</span>
    <h2>Comparador</h2>
    <span class="meta">Especulados × Elenco atual</span>
  </div>
  <div class="controls">
    <div class="field">
      <label for="position-select">Posição</label>
      <select id="position-select">
        <option value="">— selecione —</option>
      </select>
    </div>
    <div class="field">
      <label for="num-players">Comparar</label>
      <select id="num-players">
        <option value="2">2 jogadores</option>
        <option value="3">3 jogadores</option>
      </select>
    </div>
    <div class="field" id="player1-field" style="display:none">
      <label for="player1-select">Jogador A</label>
      <select id="player1-select"></select>
    </div>
    <div class="field" id="player2-field" style="display:none">
      <label for="player2-select">Jogador B</label>
      <select id="player2-select"></select>
    </div>
    <div class="field" id="player3-field" style="display:none">
      <label for="player3-select">Jogador C</label>
      <select id="player3-select"></select>
    </div>
  </div>

  <div id="comparison-area">
    <div class="empty">Escolha uma posição e os jogadores para comparar.</div>
  </div>
</section>

<footer>
  <p>Dados via <code>cache/stats.json</code> · SofaScore 25/26 · regerado por <code>build.py</code> a cada execução da rotina <code>/schedule</code>.</p>
  <p>Cores: <span style="color:#1a4faf">azul Barça</span> · <span style="color:#b3163a">grená</span> · <span style="color:#f5c518">ouro catalão</span> · sobre tinta marinha.</p>
</footer>

</div>

<script>
window.DATA = __DATA__;

const positionSelect = document.getElementById("position-select");
const numPlayers = document.getElementById("num-players");
const fields = [1, 2, 3].map(i => ({
  field: document.getElementById(`player${i}-field`),
  select: document.getElementById(`player${i}-select`),
}));
const compArea = document.getElementById("comparison-area");

// Popular dropdown de posições
Object.entries(window.DATA.groups).forEach(([key, label]) => {
  const opt = document.createElement("option");
  opt.value = key;
  opt.textContent = label;
  positionSelect.appendChild(opt);
});

function sourceMeta(s) {
  return window.DATA.sources[s] || { order: 9, label_short: s || "outros", label_long: (s || "OUTROS").toUpperCase(), default_team: "?" };
}

function playersFor(group) {
  return window.DATA.players
    .filter(p => p.position_group === group)
    .sort((a, b) => {
      const ao = sourceMeta(a.source).order;
      const bo = sourceMeta(b.source).order;
      if (ao !== bo) return ao - bo;
      return a.name.localeCompare(b.name);
    });
}

function populatePlayerSelect(select, group, excludeIds = []) {
  const players = playersFor(group).filter(p => !excludeIds.includes(p.id));
  select.innerHTML = '<option value="">— selecione —</option>';
  let lastSource = null;
  players.forEach(p => {
    if (p.source !== lastSource) {
      const opt = document.createElement("option");
      opt.disabled = true;
      opt.textContent = `── ${sourceMeta(p.source).label_long} ──`;
      select.appendChild(opt);
      lastSource = p.source;
    }
    const opt = document.createElement("option");
    opt.value = p.id;
    const note = p.source === "rumor" ? ` · ${p.team}` : "";
    opt.textContent = `${p.name}${note}`;
    select.appendChild(opt);
  });
}

function showFields() {
  const n = parseInt(numPlayers.value);
  fields.forEach((f, i) => {
    f.field.style.display = (i < n) ? "" : "none";
  });
}

function refreshDropdowns() {
  const group = positionSelect.value;
  if (!group) {
    fields.forEach(f => f.field.style.display = "none");
    compArea.innerHTML = '<div class="empty">Escolha uma posição e os jogadores para comparar.</div>';
    return;
  }
  showFields();
  const n = parseInt(numPlayers.value);
  for (let i = 0; i < n; i++) {
    const others = fields.slice(0, n)
      .filter((_, j) => j !== i)
      .map(f => parseInt(f.select.value))
      .filter(v => !isNaN(v));
    const prev = fields[i].select.value;
    populatePlayerSelect(fields[i].select, group, others);
    if (prev) fields[i].select.value = prev;
  }
  render();
}

function getPlayerById(id) {
  return window.DATA.players.find(p => p.id === parseInt(id));
}

function fmt(v) {
  if (v == null) return "—";
  if (typeof v === "number") {
    if (Number.isInteger(v)) return v.toString();
    return v.toFixed(2);
  }
  return v.toString();
}

function render() {
  const group = positionSelect.value;
  if (!group) return;
  const n = parseInt(numPlayers.value);
  const selected = fields.slice(0, n)
    .map(f => f.select.value)
    .filter(v => v)
    .map(getPlayerById)
    .filter(p => p);

  if (selected.length < 2) {
    compArea.innerHTML = '<div class="empty">Selecione pelo menos 2 jogadores.</div>';
    return;
  }

  const stats = window.DATA.stats_by_group[group];

  // Player dossier cards
  const cardsHtml = selected.map(p => {
    const sourceLabel = sourceMeta(p.source).label_short;
    const sourceClass = p.source || "main";
    const jerseyDisplay = p.jersey != null ? p.jersey : "—";
    const bioBits = [
      p.age ? `${p.age} anos` : null,
      p.height ? `${p.height} cm` : null,
      p.preferredFoot ? `pé ${esc(p.preferredFoot.toLowerCase())}` : null,
    ].filter(Boolean).join(" · ");
    return `
      <article class="pcard ${esc(sourceClass)}">
        <span class="jersey">${esc(jerseyDisplay)}</span>
        <p class="pcard-source">${esc(sourceLabel)} · ${esc(p.position_refined)}</p>
        <h3>${esc(p.name)}</h3>
        <div class="meta">
          ${esc(p.team)}${p.country ? ` · ${esc(p.country)}` : ""}<br>
          ${esc(bioBits)}
          <span class="league-line">${esc(p.league || "—")}</span>
          ${p.note ? `<span class="note">${esc(p.note)}</span>` : ""}
        </div>
      </article>`;
  }).join("");

  // Stats table — marca o melhor entre os selecionados
  // B4: só destaca quando há diferença real (min !== max).
  let rowsHtml = "";
  for (const stat of stats) {
    const values = selected.map(p => {
      const v = p.stats[stat.key];
      return typeof v === "number" ? v : null;
    });
    const valid = values.filter(v => v !== null);
    let best = null;
    let allEqual = true;
    if (valid.length > 0) {
      const min = Math.min(...valid);
      const max = Math.max(...valid);
      best = stat.smaller_better ? min : max;
      allEqual = Math.abs(max - min) < 1e-9;
    }
    const cells = values.map(v => {
      if (v === null) return `<td class="loss">—</td>`;
      const isBest = (!allEqual && best !== null && Math.abs(v - best) < 1e-9);
      return `<td class="${isBest ? 'win' : ''}">${fmt(v)}</td>`;
    }).join("");
    rowsHtml += `<tr><td>${stat.label}</td>${cells}</tr>`;
  }

  const headers = selected.map(p => `<th>${esc(p.shortName || p.name)}</th>`).join("");
  const groupLabel = window.DATA.groups[group];

  compArea.innerHTML = `
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

positionSelect.addEventListener("change", refreshDropdowns);
numPlayers.addEventListener("change", refreshDropdowns);
fields.forEach(f => f.select.addEventListener("change", refreshDropdowns));

// ====== NEWS FEED ======
const NEWS_PAGE_SIZE = 8;
let newsExpanded = false;

// R1: HTML-escape para conteúdo de fontes externas (title/snippet do WebSearch)
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

// R3: força ISO sem timezone a ser interpretado como UTC (evita drift local-vs-UTC)
function toDate(iso) {
  if (!iso) return null;
  const hasTZ = /Z$|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasTZ ? iso : iso + "Z");
}

function dayKey(iso) {
  const dt = toDate(iso);
  if (!dt || isNaN(dt)) return "";
  // Usa data LOCAL (não UTC) — assim "Hoje" reflete o dia do usuário
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const d = String(dt.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function dayLabel(key) {
  if (!key) return "Sem data";
  const today = new Date();
  const todayKey = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,"0")}-${String(today.getDate()).padStart(2,"0")}`;
  const yd = new Date(today.getTime() - 86400000);
  const yest = `${yd.getFullYear()}-${String(yd.getMonth()+1).padStart(2,"0")}-${String(yd.getDate()).padStart(2,"0")}`;
  if (key === todayKey) return "Hoje";
  if (key === yest) return "Ontem";
  const [y, m, d] = key.split("-");
  return `${d}/${m}/${y}`;
}

function fmtTime(iso) {
  const dt = toDate(iso);
  if (!dt || isNaN(dt)) return "";
  return dt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function renderNews() {
  const container = document.getElementById("news-feed");
  const meta = document.getElementById("news-meta");
  const toggleBtn = document.getElementById("news-toggle");
  const items = window.DATA.news || [];

  if (items.length === 0) {
    container.innerHTML = '<div class="news-empty">Sem notícias capturadas ainda. A rotina rodará 3x por dia.</div>';
    meta.textContent = "";
    return;
  }

  meta.textContent = `${items.length} notícias indexadas · atualizado ${esc(window.DATA.generated)}`;

  const visible = newsExpanded ? items : items.slice(0, NEWS_PAGE_SIZE);
  // Agrupa por dia
  const byDay = {};
  for (const it of visible) {
    const k = dayKey(it.published_at || it.last_seen);
    (byDay[k] = byDay[k] || []).push(it);
  }
  // R2: separa dias com data (ordenados desc) e dia sem data (vai pro fim)
  const datedKeys = Object.keys(byDay).filter(k => k).sort().reverse();
  const noDate = byDay[""] ? [""] : [];
  const dayKeys = [...datedKeys, ...noDate];

  let html = "";
  for (const k of dayKeys) {
    html += `<div class="day-block"><h3 class="day-header">${esc(dayLabel(k))}</h3>`;
    for (const it of byDay[k]) {
      const time = fmtTime(it.published_at || it.last_seen);
      const tags = (it.players_mentioned || [])
        .map(pid => window.DATA.player_names[pid])
        .filter(n => n)
        .map(n => `<span class="player-tag">${esc(n)}</span>`).join("");
      html += `
        <article class="news-item">
          <div class="row1">
            <span class="journalist">${esc(it.journalist || "?")}</span>
            <span>${esc(time)}</span>
          </div>
          <h4><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title)}</a></h4>
          <p class="snippet">${esc(it.snippet || "")}</p>
          ${tags ? `<div class="player-tags">${tags}</div>` : ""}
        </article>`;
    }
    html += `</div>`;
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

// Ticker date
(() => {
  const el = document.getElementById("ticker-date");
  if (!el) return;
  const now = new Date();
  const wd = now.toLocaleDateString("pt-BR", { weekday: "long" }).toUpperCase();
  const dt = now.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" }).toUpperCase();
  el.innerHTML = `<span class="label">${wd}</span> <span class="sep">/</span> ${dt}`;
})();
</script>
</body>
</html>"""


def main():
    players = merge_data()
    print(f"merge_data: {len(players)} jogadores")
    html = render_html(players)
    out = ROOT / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"\nOK -> {out}")
    # Resumo por grupo
    from collections import Counter
    groups = Counter(p["position_group"] for p in players if p["position_group"] and p["stats"])
    print(f"  jogadores utilizáveis por grupo: {dict(groups)}")


if __name__ == "__main__":
    main()
