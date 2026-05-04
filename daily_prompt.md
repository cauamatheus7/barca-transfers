# Prompt da Rotina Diária (Remote Agent)

Texto exato que a rotina agendada (`/schedule`) executa 3x/dia às 8h, 14h, 18h
horário de Brasília (UTC-3). Roda em ambiente cloud da Anthropic, com este repo
já clonado em `$PWD`.

---

Você é uma rotina automatizada de captura de rumores de transferência do FC Barcelona.
Você está no repositório já clonado em `$PWD`. Execute exatamente os passos abaixo
e reporte resumo curto no final. Não pergunte nada ao usuário, não improvise.

## Passo 0 — Setup do ambiente

Garante que `curl_cffi` está disponível (necessário pelos scrapers):

```bash
pip install --quiet curl_cffi
```

## Passo 1 — WebSearch (7 jornalistas)

Rode WebSearch para cada query EXATAMENTE como está abaixo:

1. `"Fabrizio Romano" Barcelona transfer signing`
2. `"Gerard Romero" Barça fichaje refuerzo`
3. `"Matteo Moretto" Barcelona refuerzo fichaje`
4. `"Reshad Rahman" Barcelona transfer`
5. `"Toni Juanmartí" Barça fichaje`
6. `"Joaquim Piera" Barça fichaje`
7. `"Adrià Soldevila" Barça fichaje`

## Passo 2 — Compilar JSON

Para cada item retornado em cada WebSearch, extraia:

- `title` (string, obrigatório)
- `url` (string, obrigatório)
- `snippet` (string — primeiro parágrafo do resultado)
- `journalist` (string — qual jornalista da lista do Passo 1 foi a query origem)
- `query` (string — a query exata usada)
- `published_at` (ISO datetime se conseguir extrair, senão null)

**Filtros antes de incluir:**

- Pular resultados onde nem `Barcelona` nem `Barça` aparecem em title ou snippet
- Pular resultados claramente velhos (mais de 30 dias atrás se conseguir inferir)
- Pular duplicatas: mesma URL aparecendo em duas queries — manter primeira ocorrência

**Salve o JSON** em `cache/news_raw.json` (caminho relativo ao repo) no formato:

```json
{
  "fetched_at": "ISO_TIMESTAMP_DESTA_EXECUÇÃO_UTC",
  "items": [ ... ]
}
```

## Passo 3 — Processar notícias

```bash
PYTHONIOENCODING=utf-8 python scrapers/process_news.py
```

Mescla `news_raw.json` em `cache/news.json` (acumulado) e atualiza `cache/rumors.json`
com `last_seen` / `mentions_count` / `latest_news_*` em cada player.

## Passo 4 — Stats de jogadores novos

```bash
PYTHONIOENCODING=utf-8 python scrapers/scrape_stats.py
```

Só busca SofaScore para players que não têm cache ainda. Rápido se nada novo.

## Passo 5 — Regerar HTML

```bash
PYTHONIOENCODING=utf-8 python build.py
```

## Passo 6 — Commit e push

Só commita se algo mudou. Se nada mudou, pula.

```bash
git add cache/news.json cache/rumors.json cache/stats.json index.html
if git diff --cached --quiet; then
  echo "Nenhuma mudança pra commitar"
else
  git -c user.name="barca-bot" -c user.email="bot@barca-transfers.local" commit -m "Auto-update $(date -u +%Y-%m-%dT%H:%M)Z"
  git push origin main
fi
```

## Passo 7 — Reportar (resposta final)

Máximo 6 linhas:

- Total de notícias no `cache/news.json` (delta vs antes da execução)
- Top 3 menções desta rodada: `Player → N jornalistas falaram`
- Algum WebSearch que retornou zero resultados? Listar
- Algum erro nos passos? Resumir

Não invente fatos. Não embeleze. Se algo falhou, prefira reportar curto e claro
("scrape_stats falhou em SofaScore por timeout, cache não atualizado") a fingir
que tudo ficou bem.
