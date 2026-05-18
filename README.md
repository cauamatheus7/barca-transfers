# Barça Transfer Desk

Static site (HTML + CSS + vanilla JS) que agrega rumores de transferência do FC Barcelona, valor de mercado e estatísticas dos jogadores, com:

- **Feed de notícias** alimentado por fontes selecionadas (configurável)
- **Pauta de especulados** com barra de confiança calculada por tier de jornalista + diversidade de fontes
- **Comparador** visual de jogadores (especulados × elenco) com stats SofaScore e botão de exportar imagem PNG

Sem servidor, sem framework, sem build step pesado. `python build.py` lê os caches JSON e gera 3 HTMLs estáticos.

---

## Deploy em 3 passos

### 1. Suba o repo

Fork do projeto, ou clone direto:

```bash
git clone https://github.com/SEU-USUARIO/barca-transfers.git
cd barca-transfers
```

### 2. Ative GitHub Pages

No GitHub: **Settings → Pages → Source: `main` / root → Save**.

URL ficará: `https://SEU-USUARIO.github.io/barca-transfers/`

### 3. Configure a URL e regere

Defina a URL pública no env (vai pras meta tags Open Graph) e regere:

```bash
pip install curl_cffi pillow
SITE_URL=https://SEU-USUARIO.github.io/barca-transfers python build.py
git add -A && git commit -m "Site setup" && git push
```

Pronto. Em ~1 min, GitHub Pages publica.

---

## Estrutura

```
build.py                      ← gera index.html, pauta.html, comparador.html
position_config.py            ← grupos posicionais + stats por posição + overrides
scrapers/
  _util.py                    ← helpers compartilhados
  scrape_squad.py             ← elenco Barça (SofaScore)
  scrape_rumors.py            ← lista de especulados (editável no topo do arquivo)
  scrape_stats.py             ← stats temporada SofaScore
  scrape_tm_values.py         ← valor de mercado Transfermarkt
  fetch_photos.py             ← fotos cacheadas em assets/photos/{id}.webp
  process_news.py             ← merge news_raw → news + cálculo de confiança
  generate_og.py              ← imagem Open Graph 1200×630
cache/
  squad.json, rumors.json, stats.json, news.json, tm_ids.json, tm_values.json
assets/
  photos/{player_id}.webp     ← cacheadas localmente (evita CORS/ORB)
  og-image.png                ← preview pra compartilhar
index.html, pauta.html, comparador.html  ← gerados
```

---

## Atualizar dados

```bash
SITE_URL=https://SEU-USUARIO.github.io/barca-transfers
export SITE_URL  # ou usar em cada comando abaixo

python scrapers/scrape_squad.py         # raro — só quando muda elenco
python scrapers/scrape_rumors.py        # quando editar a lista RUMORS
python scrapers/scrape_stats.py         # semanal
python scrapers/scrape_tm_values.py     # semanal
python scrapers/fetch_photos.py         # automático nos novos players
python build.py
git add -A && git commit -m "Update" && git push
```

### Notícias

`news.json` é alimentado por um pipeline externo (originalmente uma rotina Claude Code com WebSearch, ver `daily_prompt.md` como referência). Pra automatizar você pode:

- **GitHub Actions** rodando `WebSearch` via Bing API ou similar a cada hora
- **n8n / Zapier** monitorando RSS feeds dos jornalistas
- **Anthropic Claude API** com tool `web_search` (pago por token)
- **Manual** — edite `cache/news_raw.json` e rode `python scrapers/process_news.py`

O formato de `cache/news_raw.json`:

```json
{
  "fetched_at": "2026-01-01T08:00:00+00:00",
  "items": [
    {
      "title": "Headline",
      "url": "https://...",
      "snippet": "...",
      "journalist": "Fabrizio Romano",
      "query": "...",
      "published_at": "2026-01-01T07:30:00"
    }
  ]
}
```

`process_news.py` faz dedupe por URL hash, cruza com `squad.json + rumors.json` pra detectar menções a jogadores, e atualiza `news.json + rumors.json`.

---

## Customização rápida

### Adicionar/remover especulado

Edite `scrapers/scrape_rumors.py`, lista `RUMORS`:

```python
{"search": "Nome do Jogador", "team_hint": "Time atual", "target_pos": "ST", "note": "..."},
```

Aí: `python scrapers/scrape_rumors.py && python scrapers/scrape_stats.py && python scrapers/fetch_photos.py && python build.py`.

### Reclassificar posição

`position_config.py`, dict `REFINED_POSITIONS`. Posições válidas: GK, CB, LB, RB, DM, CM, AM, LW, RW, ST.

### Trocar jornalistas no cálculo de confiança

`scrapers/process_news.py`, dict `JOURNALIST_TIER`.

---

## Stack

- **Frontend:** HTML + CSS + JS vanilla. Sem framework. Fontes do Google Fonts (Fraunces, Manrope, JetBrains Mono, Big Shoulders Display).
- **Backend (offline):** Python 3.10+ com `curl_cffi`, `pillow`. Sem servidor em runtime.
- **Dados:** SofaScore API (sem auth via curl_cffi com TLS Chrome) + Transfermarkt (scrape do profile via regex).
- **Hospedagem:** GitHub Pages (grátis) ou Vercel / Netlify / Cloudflare Pages.

---

## Licença

[MIT](LICENSE) — use livremente.
