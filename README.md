# Barça Transfers — Centro de Comparação

Site local (HTML estático) para comparar jogadores especulados na janela de transferências do FC Barcelona com o elenco atual + Barça Atlètic. Picker dinâmico por posição, stats específicas pra cada uma.

Abrir `index.html` no navegador (duplo clique).

## Estrutura

```
cache/                      ← dados externos serializados
  squad.json                ← elenco principal + Atlètic + emprestados
  rumors.json               ← especulados (lista editável em scrape_rumors.py)
  stats.json                ← stats SofaScore 25/26 indexadas por player_id
scrapers/
  scrape_squad.py           ← popula squad.json
  scrape_rumors.py          ← popula rumors.json (resolve nomes → IDs)
  scrape_stats.py           ← popula stats.json (multi-liga)
position_config.py          ← grupos posicionais + stats por posição + overrides
build.py                    ← lê cache/*.json e gera index.html
index.html                  ← saída final
```

## Atualizar dados

```powershell
# uma vez no computador:
pip install curl_cffi

# qualquer hora que quiser refresh:
$env:PYTHONIOENCODING="utf-8"

python scrapers\scrape_squad.py        # raro - só quando muda elenco
python scrapers\scrape_rumors.py       # quando sair rumor novo
python scrapers\scrape_stats.py        # toda semana ~1 min (use --force pra refazer tudo)
python build.py                        # regerar HTML
```

`build.py` é offline puro: pode regerar o HTML 100x sem refazer scraping.

## Adicionar novos especulados

Edite a lista `RUMORS` no topo de [scrapers/scrape_rumors.py](scrapers/scrape_rumors.py):

```python
{"search": "Nome do Jogador", "team_hint": "Time atual", "target_pos": "ST", "note": "..."},
```

`team_hint` ajuda a desambiguar quando há jogadores homônimos (ex: vários "João Pedro"). `target_pos` é a posição em que o Barça pretende usar o jogador (GK/CB/LB/RB/DM/CM/AM/LW/RW/ST).

Re-rode `scrape_rumors.py` + `scrape_stats.py` (vai pegar só os novos por causa do cache) + `build.py`.

## Reclassificar posição de um jogador

Se um jogador aparece no grupo errado do picker, edite `REFINED_POSITIONS` em [position_config.py](position_config.py):

```python
"Nome do Jogador": "RB",
```

Vale: GK, CB, LB, RB, DM, CM, AM, LW, RW, ST. Re-rode `build.py`.

## Por que SofaScore e não FBref

FBref tem Cloudflare e dados defensivos limitados pra La Liga 25/26. SofaScore expõe API JSON sem auth via `curl_cffi` com TLS de Chrome — acessível, multi-liga, dados completos. Sem dependência de Playwright pra esse projeto.

## Atualização automática 3x/dia (rotina remota)

O repo está conectado a uma rotina agendada do Claude Code que roda **8h, 14h e 18h** (horário de Brasília) todos os dias.

**O que ela faz:**
1. WebSearch em 7 jornalistas especializados em Barça (Fabrizio Romano, Gerard Romero, Matteo Moretto, Reshad Rahman, Toni Juanmartí, Joaquim Piera, Adrià Soldevila)
2. Filtra resultados que mencionam Barcelona/Barça e são recentes (<30 dias)
3. Salva em `cache/news_raw.json` e roda `process_news.py` (atualiza `news.json` + `rumors.json`)
4. Roda `scrape_stats.py` (busca SofaScore só pra players novos)
5. Roda `build.py` (regenera `index.html` com feed atualizado)
6. `git commit` + `git push origin main`

**Pra ver os updates:**
```powershell
cd C:\Users\caua\Claude\barca-transfers
git pull
```

**Pra gerenciar a rotina:**
- Status / histórico de execuções: https://claude.ai/code/routines/trig_01Lr1rxFyUh3ctk95hW5FHct
- Pausar / habilitar / mudar horários: na mesma página
- Mudar o prompt da rotina: editar via `/schedule update` (ou manual no link acima)
- Forçar um run manual: clica em "Run now" no link, ou pergunta pro Claude

**Custo:** as 3 execuções diárias rodam no plano de Claude Code que você já tem.

## Feed de notícias no `index.html`

Cada execução da rotina adiciona itens em `cache/news.json`. O `build.py` lê esse arquivo e renderiza um feed no topo da página, agrupado por dia (Hoje, Ontem, datas anteriores), mostrando:
- Jornalista que reportou (badge azul Barça)
- Hora da notícia
- Título (link clicável pra fonte original)
- Snippet
- Tags grenat dos jogadores mencionados (cruzadas contra `rumors.json` + `squad.json`)

Quanto mais um rumor é mencionado, mais alto ele fica no picker (`rumors.json` é ordenado por `last_seen` desc).
