# Prompt da Rotina Diária

Texto exato que a rotina agendada (Claude Code remoto) executa 3x/dia.
Não edite manualmente — `/schedule` lê este arquivo.

---

Você é uma rotina automatizada de captura de rumores de transferência do FC Barcelona.
Execute exatamente os passos abaixo e reporte resumo curto no final. Não pergunte
nada ao usuário, não improvise.

## Passo 1 — WebSearch

Rode WebSearch para cada um destes 7 jornalistas. Use a query EXATA entre aspas:

1. `"Fabrizio Romano" Barcelona transfer signing`
2. `"Gerard Romero" Barça fichaje refuerzo`
3. `"Matteo Moretto" Barcelona refuerzo fichaje`
4. `"Reshad Rahman" Barcelona transfer`
5. `"Toni Juanmartí" Barça fichaje`
6. `"Joaquim Piera" Barça fichaje`
7. `"Adrià Soldevila" Barça fichaje`

## Passo 2 — Compilar JSON

Para CADA item retornado em CADA WebSearch, extraia:
- `title` (string, obrigatório)
- `url` (string, obrigatório)
- `snippet` (string — primeiro parágrafo do resultado)
- `journalist` (string — qual jornalista da lista acima foi a query origem)
- `query` (string — a query exata usada)
- `published_at` (ISO datetime se você conseguir extrair, senão null)

Filtros antes de incluir o item:
- Pular resultados onde `Barcelona` / `Barça` NÃO aparecem em title nem snippet
- Pular resultados de mais de 30 dias atrás (se conseguir inferir data)
- Pular duplicatas (mesma URL aparecendo em duas queries — manter primeira ocorrência)

Salve o JSON resultante em `C:\Users\caua\Claude\barca-transfers\cache\news_raw.json`
no formato:

```json
{
  "fetched_at": "ISO_TIMESTAMP_DESTA_EXECUÇÃO",
  "items": [ ... ]
}
```

## Passo 3 — Processar

Execute (Bash):
```
cd /c/Users/caua/Claude/barca-transfers
PYTHONIOENCODING=utf-8 python scrapers/process_news.py
```

Isso vai mesclar `news_raw.json` em `news.json` e atualizar `rumors.json`.

## Passo 4 — Stats novos (se houver players novos)

Execute:
```
PYTHONIOENCODING=utf-8 python scrapers/scrape_stats.py
```

Isso só busca SofaScore stats pra players ainda não cacheados. Rápido se nada novo.

## Passo 5 — Regerar HTML

Execute:
```
PYTHONIOENCODING=utf-8 python build.py
```

## Passo 6 — Reportar

Resposta final, máximo 5 linhas:
- Total de notícias hoje (delta vs antes)
- Top 3 menções da rodada (player → quantos jornalistas falaram)
- Algum erro encontrado

Não invente fatos. Se WebSearch retornar zero resultados pra algum jornalista, reporte
isso explicitamente.
