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
