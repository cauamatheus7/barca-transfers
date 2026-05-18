# Prompt da Rotina Automatizada (template)

Texto de referência pra quem quiser conectar uma automação (Claude Code routine, GitHub Action, n8n, etc.) ao site. O pipeline é idempotente — pode rodar quantas vezes quiser.

---

Você é uma rotina automatizada de captura de rumores de transferência do FC Barcelona (entradas E saídas). O repositório já está clonado em `$PWD`. Execute exatamente os passos abaixo. Não improvise.

## Passo 0 — Setup

```bash
pip install --quiet curl_cffi pillow
```

## Passo 1 — WebSearch (9 queries de exemplo)

Rode WebSearch em cada query (ajuste os nomes pros jornalistas que VOCÊ confia):

1. `"Fabrizio Romano" Barcelona transfer 2026`
2. `"Gerard Romero" Barça mercado 2026`
3. `"Matteo Moretto" Barcelona mercado 2026`
4. `"Reshad Rahman" Barcelona transfer 2026`
5. `"Toni Juanmartí" Barça mercado`
6. `"Joaquim Piera" Barça mercado`
7. `"Adrià Soldevila" Barça mercado`
8. `Barcelona player leaving exit transfer 2026`
9. `Barça salida jugador venta 2026`

## Passo 2 — Compilar JSON em `cache/news_raw.json`

Para cada item: `title`, `url`, `snippet`, `journalist` (use `"Geral"` para queries 8 e 9), `query`, `published_at` (null se não conseguir extrair).

Filtros:
- Pular sem 'Barcelona' nem 'Barça' em title/snippet
- Pular >30 dias
- Pular duplicatas de URL (mesma URL em queries diferentes — manter primeira ocorrência)

Formato:
```json
{
  "fetched_at": "ISO_UTC",
  "items": [...]
}
```

## Passo 3 — Processar notícias

```bash
PYTHONIOENCODING=utf-8 python scrapers/process_news.py
```

## Passo 4 — Stats SofaScore (só players novos)

```bash
PYTHONIOENCODING=utf-8 python scrapers/scrape_stats.py
```

## Passo 5 — Fotos novas

```bash
PYTHONIOENCODING=utf-8 python scrapers/fetch_photos.py
```

## Passo 6 — Regerar HTML

```bash
SITE_URL=https://SEU-DOMINIO PYTHONIOENCODING=utf-8 python build.py
```

## Passo 7 — Commit e push (só se mudou)

```bash
git add cache/ index.html pauta.html comparador.html assets/photos/
if git diff --cached --quiet; then
  echo "Nenhuma mudança"
else
  git -c user.name="bot" -c user.email="bot@local" commit -m "Auto-update $(date -u +%Y-%m-%dT%H:%M)Z"
  git push origin main
fi
```

## Passo 8 — Reporte (max 6 linhas)

- Total de notícias em cache/news.json (delta)
- Top 3 menções: "Player → N jornalistas" + confidence %
- Queries com zero resultados
- Erros encontrados

Não invente. Reporte falhas honestamente.
