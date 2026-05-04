"""
Processa news_raw.json (gerado pelo agente agendado via WebSearch) e atualiza:
- cache/news.json: feed de notícias acumulado, com first_seen / last_seen / mentions
- cache/rumors.json: bumpa last_seen + latest_news_* nos players já listados

Lógica de "ressuscitar rumor antigo": ao detectar uma notícia mais recente
mencionando o jogador, last_seen é atualizado → ele sobe no sort do feed.

Estrutura de news_raw.json (input do agente):
{
  "fetched_at": "2026-05-04T08:00:00",
  "items": [
    {"journalist": "Fabrizio Romano", "query": "...", "title": "...",
     "url": "...", "snippet": "...", "published_at": "2026-05-04T07:30:00" | null}
  ]
}
"""
from __future__ import annotations
import json
import hashlib
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "cache"


def slugify(s: str) -> str:
    """Sem acento + lowercase + sem pontuação — pra comparação fuzzy de nomes.

    R4: pontuação removida ('A. Bastoni' -> 'a bastoni') antes do match contra texto
    de notícias que normalmente vem sem ponto.
    """
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z0-9 ]+", " ", s)   # punctuação -> espaço
    s = re.sub(r"\s+", " ", s)               # collapse spaces
    return s.lower().strip()


def url_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def load_known_players() -> list[dict]:
    """Carrega rumors + squad pra termos um whitelist de nomes a detectar.

    R6: avisa explicitamente se algum arquivo está faltando — sem ele, detecção
    silenciosa retornaria zero menções e usuário pensaria que é semana fraca.
    """
    out = []
    for fname in ["rumors.json", "squad.json"]:
        p = CACHE / fname
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            out.extend(data.get("players", []))
        else:
            print(f"[WARN] {p} não existe — detecção de menções vai ser parcial")
    return out


def build_name_index(players: list[dict]) -> dict[str, int]:
    """Mapeia variações de nome (com/sem acento, sobrenome só) -> player id.

    Não cria entradas pra sobrenomes muito comuns ('Silva', 'Garcia', 'Martin')
    pra evitar falso positivo.
    """
    BLACKLIST_SURNAMES = {
        "garcia", "martin", "silva", "lopez", "torres", "fernandez",
        "rodriguez", "gomez", "perez", "ferreira", "santos",
    }
    idx: dict[str, int] = {}
    for p in players:
        full = slugify(p["name"])
        idx[full] = p["id"]
        # variações: sobrenome (último token), shortName, slug
        if p.get("shortName"):
            idx[slugify(p["shortName"])] = p["id"]
        parts = full.split()
        if len(parts) >= 2:
            surname = parts[-1]
            if surname not in BLACKLIST_SURNAMES:
                idx.setdefault(surname, p["id"])
    return idx


def detect_players(text: str, name_index: dict[str, int]) -> list[int]:
    """Encontra IDs de jogadores mencionados no texto."""
    norm = slugify(text)
    found = set()
    for needle, pid in name_index.items():
        # Boundary check: precisa ser palavra completa ou conjunto de palavras
        # Match de "alvarez" deve casar em "julian alvarez" mas evitar prefix-match acidental
        pattern = r"(?:^|[^a-z])" + re.escape(needle) + r"(?:$|[^a-z])"
        if re.search(pattern, norm):
            found.add(pid)
    return sorted(found)


def parse_dt(s: str | None) -> str | None:
    """Normaliza ISO datetime. Loga (não silencia) inputs malformados."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.isoformat()
    except (ValueError, TypeError):
        print(f"[WARN] published_at inválido descartado: {s!r}")
        return None


def merge_news(existing: dict, raw: dict, name_index: dict[str, int]) -> dict:
    """Merge raw items into existing news.json. Atualiza last_seen em duplicatas."""
    fetched_at = parse_dt(raw.get("fetched_at")) or datetime.now(timezone.utc).isoformat(timespec="seconds")
    items_by_id: dict[str, dict] = {it["id"]: it for it in existing.get("items", [])}

    new_count = updated_count = 0
    for raw_item in raw.get("items", []):
        url = raw_item.get("url")
        if not url:
            continue
        nid = url_id(url)
        text = " ".join(filter(None, [raw_item.get("title"), raw_item.get("snippet")]))
        mentions = detect_players(text, name_index)

        if nid in items_by_id:
            existing_item = items_by_id[nid]
            existing_item["last_seen"] = fetched_at
            # Mescla menções caso o snippet tenha mudado
            existing_item["players_mentioned"] = sorted(set(
                existing_item.get("players_mentioned", []) + mentions
            ))
            updated_count += 1
        else:
            items_by_id[nid] = {
                "id": nid,
                "url": url,
                "title": raw_item.get("title", ""),
                "snippet": raw_item.get("snippet", ""),
                "journalist": raw_item.get("journalist", ""),
                "query": raw_item.get("query", ""),
                "published_at": parse_dt(raw_item.get("published_at")),
                "first_seen": fetched_at,
                "last_seen": fetched_at,
                "players_mentioned": mentions,
            }
            new_count += 1

    items_sorted = sorted(
        items_by_id.values(),
        key=lambda it: it.get("published_at") or it["last_seen"],
        reverse=True,
    )
    return {
        "items": items_sorted,
        "_meta": {
            "total": len(items_sorted),
            "last_run": fetched_at,
            "added_this_run": new_count,
            "updated_this_run": updated_count,
        },
    }


def update_rumor_activity(rumors_data: dict, news_data: dict) -> dict:
    """Bumpa last_seen / latest_news_* em cada rumor baseado no feed."""
    items = news_data.get("items", [])
    # Reverse map: player_id -> [news items mencionando ele] (já em ordem desc)
    by_player: dict[int, list[dict]] = {}
    for it in items:
        for pid in it.get("players_mentioned", []):
            by_player.setdefault(pid, []).append(it)

    for player in rumors_data.get("players", []):
        mentions = by_player.get(player["id"], [])
        if not mentions:
            player.setdefault("last_seen", None)
            player.setdefault("mentions_count", 0)
            continue
        latest = mentions[0]
        player["last_seen"] = latest.get("published_at") or latest.get("last_seen")
        player["mentions_count"] = len(mentions)
        player["latest_news_url"] = latest["url"]
        player["latest_news_title"] = latest["title"]
        player["latest_news_journalist"] = latest.get("journalist", "")

    # Reordena por last_seen desc (None vai pro fim)
    rumors_data["players"].sort(
        key=lambda p: (p.get("last_seen") or "", p.get("mentions_count") or 0),
        reverse=True,
    )
    rumors_data["last_processed"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return rumors_data


def main(argv: list[str]) -> int:
    raw_path = CACHE / "news_raw.json"
    if len(argv) > 1:
        raw_path = Path(argv[1])

    if not raw_path.exists():
        print(f"[ERR] {raw_path} não encontrado")
        return 1

    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    known_players = load_known_players()
    name_index = build_name_index(known_players)
    print(f"name_index: {len(name_index)} variações de {len(known_players)} jogadores")
    if not name_index:
        # R6: aborta antes de gerar dados zerados silenciosamente
        print("[ERR] name_index vazio — squad.json e rumors.json estão ausentes ou vazios.")
        return 2

    news_path = CACHE / "news.json"
    existing_news = json.loads(news_path.read_text(encoding="utf-8")) if news_path.exists() else {"items": []}
    new_news = merge_news(existing_news, raw, name_index)
    news_path.write_text(json.dumps(new_news, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = new_news["_meta"]
    print(f"news.json: total={meta['total']}, novos={meta['added_this_run']}, atualizados={meta['updated_this_run']}")

    rumors_path = CACHE / "rumors.json"
    rumors_data = json.loads(rumors_path.read_text(encoding="utf-8"))
    updated = update_rumor_activity(rumors_data, new_news)
    rumors_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    active = sum(1 for p in updated["players"] if p.get("mentions_count", 0) > 0)
    print(f"rumors.json: {active}/{len(updated['players'])} com menções recentes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
