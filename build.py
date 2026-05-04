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
    B2: prefere position_detailed (do SofaScore) antes do fallback genérico."""
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
<style>
  :root {
    --bg: #0f1419;
    --panel: #1a1f2e;
    --panel-2: #232938;
    --text: #e6e8eb;
    --muted: #8a93a3;
    --border: #2a3142;
    --barca-blue: #004D98;
    --barca-grenat: #A50044;
    --barca-gold: #FFED02;
    --win: #5cd673;
    --loss: #e57373;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }
  .stripe {
    height: 6px;
    background: linear-gradient(to right,
      var(--barca-blue) 0%, var(--barca-blue) 50%,
      var(--barca-grenat) 50%, var(--barca-grenat) 100%);
  }
  .wrap { max-width: 1200px; margin: 0 auto; padding: 24px 20px; }
  header h1 {
    margin: 0 0 6px; font-size: 26px;
    background: linear-gradient(90deg, var(--barca-blue), var(--barca-grenat));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    display: inline-block;
  }
  header p.sub { margin: 0 0 24px; color: var(--muted); font-size: 13px; }

  .controls {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 18px;
    margin-bottom: 24px;
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    align-items: end;
  }
  .field { display: flex; flex-direction: column; gap: 4px; min-width: 180px; }
  .field label {
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  select, button {
    background: var(--panel-2);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 9px 12px;
    border-radius: 6px;
    font-size: 14px;
    font-family: inherit;
    min-height: 38px;
  }
  select:focus { outline: 1px solid var(--barca-blue); border-color: var(--barca-blue); }
  button { cursor: pointer; }
  button:hover { border-color: var(--barca-grenat); }
  button.primary {
    background: var(--barca-blue);
    border-color: var(--barca-blue);
    color: white;
  }
  button.primary:hover { background: var(--barca-grenat); border-color: var(--barca-grenat); }

  .player-cards { display: grid; gap: 16px; margin-bottom: 24px; }
  .player-cards.cols-2 { grid-template-columns: 1fr 1fr; }
  .player-cards.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
  .pcard {
    background: var(--panel);
    border: 1px solid var(--border);
    border-left: 4px solid var(--barca-blue);
    border-radius: 8px;
    padding: 16px 18px;
  }
  .pcard.rumor { border-left-color: var(--barca-grenat); }
  .pcard h3 { margin: 0 0 4px; font-size: 18px; }
  .pcard .meta { color: var(--muted); font-size: 12px; line-height: 1.6; }
  .pcard .badges { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
  .badge {
    background: var(--panel-2);
    color: var(--muted);
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
  }
  .badge.rumor { background: var(--barca-grenat); color: white; }
  .badge.main { background: var(--barca-blue); color: white; }
  .badge.athletic { background: #555; color: white; }

  .stats-table {
    width: 100%;
    border-collapse: collapse;
    background: var(--panel);
    border-radius: 8px;
    overflow: hidden;
    font-size: 13px;
  }
  .stats-table th, .stats-table td {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    text-align: right;
  }
  .stats-table th:first-child, .stats-table td:first-child { text-align: left; }
  .stats-table thead th {
    background: var(--panel-2);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
  }
  .stats-table tbody tr:last-child td { border-bottom: none; }
  .stats-table td.win { color: var(--win); font-weight: 600; }
  .stats-table td.loss { color: var(--muted); }

  .empty {
    background: var(--panel);
    border-radius: 8px;
    padding: 40px;
    text-align: center;
    color: var(--muted);
    font-style: italic;
  }
  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    color: var(--muted);
    font-size: 13px;
  }
  .info-row .pos-tag {
    color: var(--barca-gold);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.08em;
  }

  footer {
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid var(--border);
    color: var(--muted);
    font-size: 12px;
  }

  /* News feed */
  .news-section { margin-bottom: 32px; }
  .news-meta { color: var(--muted); font-size: 12px; margin: 0 0 12px; }
  .day-block { margin-bottom: 20px; }
  .day-header {
    font-size: 11px;
    color: var(--barca-gold);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0 0 8px;
    padding-bottom: 4px;
    border-bottom: 1px dashed var(--border);
  }
  .news-item {
    background: var(--panel);
    border: 1px solid var(--border);
    border-left: 3px solid var(--barca-blue);
    border-radius: 6px;
    padding: 12px 14px;
    margin-bottom: 8px;
  }
  .news-item .row1 {
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: 11px;
    color: var(--muted);
    margin-bottom: 4px;
  }
  .news-item .journalist {
    background: var(--barca-blue);
    color: white;
    padding: 1px 8px;
    border-radius: 10px;
    font-weight: 500;
  }
  .news-item h4 {
    margin: 2px 0 4px;
    font-size: 14px;
    line-height: 1.35;
  }
  .news-item h4 a { color: var(--text); text-decoration: none; }
  .news-item h4 a:hover { color: var(--barca-grenat); text-decoration: underline; }
  .news-item .snippet { color: var(--muted); font-size: 12.5px; margin: 0 0 6px; }
  .news-item .player-tags { display: flex; gap: 4px; flex-wrap: wrap; }
  .player-tag {
    background: var(--barca-grenat);
    color: white;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 10.5px;
    font-weight: 500;
  }
  .news-toggle {
    background: var(--panel-2);
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 6px 14px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    margin-top: 8px;
  }
  .news-toggle:hover { color: var(--text); }
  .news-empty {
    color: var(--muted);
    font-style: italic;
    padding: 16px;
    background: var(--panel);
    border-radius: 6px;
    text-align: center;
  }

  @media (max-width: 800px) {
    .player-cards.cols-2, .player-cards.cols-3 { grid-template-columns: 1fr; }
    .controls { flex-direction: column; align-items: stretch; }
    .field { width: 100%; }
  }
</style>
</head>
<body>
<div class="stripe"></div>
<div class="wrap">

<header>
  <h1>Centro de Transferências FC Barcelona</h1>
  <p class="sub">Janela de transferências 2026 · Comparação entre especulados e elenco atual · Fonte: SofaScore</p>
</header>

<section class="news-section">
  <h2 style="font-size:18px;margin:0 0 6px;color:var(--muted);text-transform:uppercase;letter-spacing:0.05em;">📰 Feed de notícias</h2>
  <p class="news-meta" id="news-meta"></p>
  <div id="news-feed"></div>
  <button class="news-toggle" id="news-toggle" style="display:none">Mostrar mais ↓</button>
</section>

<section>
  <div class="controls">
    <div class="field">
      <label for="position-select">1. Escolha a posição</label>
      <select id="position-select">
        <option value="">— selecione —</option>
      </select>
    </div>
    <div class="field">
      <label for="num-players">Quantos comparar</label>
      <select id="num-players">
        <option value="2">2 jogadores</option>
        <option value="3">3 jogadores</option>
      </select>
    </div>
    <div class="field" id="player1-field" style="display:none">
      <label for="player1-select">Jogador 1</label>
      <select id="player1-select"></select>
    </div>
    <div class="field" id="player2-field" style="display:none">
      <label for="player2-select">Jogador 2</label>
      <select id="player2-select"></select>
    </div>
    <div class="field" id="player3-field" style="display:none">
      <label for="player3-select">Jogador 3</label>
      <select id="player3-select"></select>
    </div>
  </div>

  <div id="comparison-area">
    <div class="empty">
      Escolha uma posição e os jogadores para comparar.
    </div>
  </div>
</section>

<footer>
  <p>Dados gerados a partir de <code>cache/stats.json</code> (SofaScore, temporada 25/26).
  Para atualizar: rodar <code>scrape_squad.py</code> + <code>scrape_rumors.py</code> +
  <code>scrape_stats.py</code> + <code>build.py</code>.</p>
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

  // Cards header
  const cardsHtml = selected.map(p => {
    const sourceLabel = sourceMeta(p.source).label_short;
    return `
      <div class="pcard ${p.source === 'rumor' ? 'rumor' : ''}">
        <h3>${p.name}</h3>
        <div class="meta">
          ${p.team}${p.country ? ` · ${p.country}` : ""}<br>
          ${p.age ? `${p.age} anos` : "Idade ?"}${p.height ? ` · ${p.height}cm` : ""}${p.preferredFoot ? ` · pé ${p.preferredFoot.toLowerCase()}` : ""}<br>
          <span style="color: var(--muted)">Liga: ${p.league || "—"} · ${p.position_refined}</span>
          ${p.note ? `<br><span style="color: var(--muted); font-style: italic">${p.note}</span>` : ""}
        </div>
        <div class="badges">
          <span class="badge ${p.source}">${sourceLabel}</span>
          ${p.jersey ? `<span class="badge">#${p.jersey}</span>` : ""}
        </div>
      </div>`;
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

  const headers = selected.map(p => `<th>${p.shortName || p.name}</th>`).join("");
  const groupLabel = window.DATA.groups[group];

  compArea.innerHTML = `
    <div class="info-row">
      <span><span class="pos-tag">${groupLabel}</span> — ${selected.length} jogadores · stats temporada 25/26</span>
      <span>Melhor valor por linha em verde</span>
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

function dayKey(iso) {
  if (!iso) return "?";
  return iso.slice(0, 10);
}

function dayLabel(key) {
  if (key === "?") return "Sem data";
  const today = new Date();
  const todayKey = today.toISOString().slice(0, 10);
  const yest = new Date(today.getTime() - 86400000).toISOString().slice(0, 10);
  if (key === todayKey) return "Hoje";
  if (key === yest) return "Ontem";
  const [y, m, d] = key.split("-");
  return `${d}/${m}/${y}`;
}

function fmtTime(iso) {
  if (!iso) return "";
  const dt = new Date(iso);
  return isNaN(dt) ? "" : dt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
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

  meta.textContent = `${items.length} notícias indexadas · atualizado ${window.DATA.generated}`;

  const visible = newsExpanded ? items : items.slice(0, NEWS_PAGE_SIZE);
  // Agrupa por dia
  const byDay = {};
  for (const it of visible) {
    const k = dayKey(it.published_at || it.last_seen);
    (byDay[k] = byDay[k] || []).push(it);
  }
  const dayKeys = Object.keys(byDay).sort().reverse();

  let html = "";
  for (const k of dayKeys) {
    html += `<div class="day-block"><h3 class="day-header">${dayLabel(k)}</h3>`;
    for (const it of byDay[k]) {
      const time = fmtTime(it.published_at || it.last_seen);
      const tags = (it.players_mentioned || [])
        .map(pid => window.DATA.player_names[pid])
        .filter(n => n)
        .map(n => `<span class="player-tag">${n}</span>`).join("");
      html += `
        <article class="news-item">
          <div class="row1">
            <span class="journalist">${it.journalist || "?"}</span>
            <span>${time}</span>
          </div>
          <h4><a href="${it.url}" target="_blank" rel="noopener">${it.title}</a></h4>
          <p class="snippet">${it.snippet || ""}</p>
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
