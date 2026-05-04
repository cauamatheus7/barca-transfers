"""
Define os grupos de posição e as estatísticas relevantes para cada um.

Cada grupo tem:
- label: nome legível
- stats: lista de (key_sofascore, label_pt, smaller_better) — métricas específicas

Para detecção da posição refinada de jogadores do elenco,
usamos REFINED_POSITIONS (override manual). Para rumores,
usamos o campo `position_target` já no rumors.json.
"""
from __future__ import annotations

# Mapeamento de override pra elenco do Barça (SofaScore retorna só G/D/M/F)
REFINED_POSITIONS = {
    # Goleiros
    "Joan García": "GK",
    "Wojciech Szczęsny": "GK",
    "Diego Kochen": "GK",
    "Eder Aller": "GK",

    # Zagueiros
    "Pau Cubarsí": "CB",
    "Ronald Araújo": "CB",
    "Andreas Christensen": "CB",
    "Eric García": "CB",
    "Xavi Espart": "CB",

    # Laterais
    "Jules Koundé": "RB",
    "João Cancelo": "RB",
    "Alejandro Balde": "LB",
    "Gerard Martín": "LB",

    # Volantes
    "Marc Casadó": "DM",
    "Marc Bernal": "DM",
    "Frenkie de Jong": "DM",

    # Meio-campo
    "Pedri": "CM",
    "Pablo Gavi": "CM",
    "Fermín López": "AM",
    "Dani Olmo": "AM",

    # Pontas
    "Lamine Yamal": "RW",
    "Raphinha": "LW",
    "Marcus Rashford": "LW",
    "Roony Bardghji": "RW",

    # Centroavantes
    "Robert Lewandowski": "ST",
    "Ferran Torres": "ST",
}


# Grupos de posição agrupados para o picker (UI mostra esses)
POSITION_GROUPS_UI = {
    "GK": "Goleiro",
    "CB": "Zagueiro",
    "FB": "Lateral",         # agrupa LB + RB
    "DM": "Volante",
    "CM": "Meio-campista",
    "AM": "Meia-atacante",
    "W":  "Ponta",           # agrupa LW + RW
    "ST": "Centroavante",
}

# Mapeamento de posição refinada -> grupo do picker
REFINED_TO_UI_GROUP = {
    "GK": "GK",
    "CB": "CB",
    "LB": "FB", "RB": "FB",
    "DM": "DM",
    "CM": "CM",
    "AM": "AM",
    "LW": "W", "RW": "W",
    "ST": "ST",
}


# Estatísticas por grupo de posição (key SofaScore, label_pt, smaller_better)
STATS_BY_POSITION = {
    "GK": [
        ("saves",                          "Defesas",                        False),
        ("savedShotsFromInsideTheBox",     "Defesas dentro da área",         False),
        ("savedShotsFromOutsideTheBox",    "Defesas de fora da área",        False),
        ("penaltyFaced",                   "Pênaltis enfrentados",           False),
        ("penaltySave",                    "Pênaltis defendidos",            False),
        ("cleanSheet",                     "Jogos sem sofrer gol",           False),
        ("goalsConcededInsideTheBox",      "Gols sofridos (área)",           True),
        ("goalsConcededOutsideTheBox",     "Gols sofridos (fora)",           True),
        ("accuratePassesPercentage",       "% de passes certos",             False),
        ("accurateLongBalls",              "Lançamentos certos",             False),
    ],
    "CB": [
        ("totalClearance",                 "Cortes",                         False),
        ("aerialDuelsWon",                 "Duelos aéreos ganhos",           False),
        ("aerialDuelsWonPercentage",       "% duelos aéreos",                False),
        ("interceptions",                  "Interceptações",                 False),
        ("tackles",                        "Desarmes",                       False),
        ("totalDuelsWon",                  "Duelos totais ganhos",           False),
        ("errorLeadToGoal",                "Erros que levaram a gol",        True),
        ("errorLeadToShot",                "Erros que levaram a chute",      True),
        ("accuratePassesPercentage",       "% de passes certos",             False),
        ("accurateLongBalls",              "Lançamentos certos",             False),
    ],
    "FB": [
        ("tackles",                        "Desarmes",                       False),
        ("interceptions",                  "Interceptações",                 False),
        ("totalDuelsWon",                  "Duelos ganhos",                  False),
        ("totalDuelsWonPercentage",        "% duelos",                       False),
        ("accurateCrosses",                "Cruzamentos certos",             False),
        ("accurateCrossesPercentage",      "% cruzamentos",                  False),
        ("keyPasses",                      "Passes-chave",                   False),
        ("assists",                        "Assistências",                   False),
        ("successfulDribbles",             "Dribles certos",                 False),
        ("yellowCards",                    "Cartões amarelos",               True),
    ],
    "DM": [
        ("tackles",                        "Desarmes",                       False),
        ("interceptions",                  "Interceptações",                 False),
        ("totalDuelsWon",                  "Duelos ganhos",                  False),
        ("aerialDuelsWon",                 "Duelos aéreos ganhos",           False),
        ("accuratePasses",                 "Passes certos",                  False),
        ("accuratePassesPercentage",       "% de passes",                    False),
        ("accurateLongBalls",              "Lançamentos certos",             False),
        ("possessionLost",                 "Posses perdidas",                True),
        ("yellowCards",                    "Cartões amarelos",               True),
        ("rating",                         "Nota média SofaScore",           False),
    ],
    "CM": [
        ("accuratePasses",                 "Passes certos",                  False),
        ("accuratePassesPercentage",       "% de passes",                    False),
        ("keyPasses",                      "Passes-chave",                   False),
        ("assists",                        "Assistências",                   False),
        ("expectedAssists",                "Expected Assists (xA)",          False),
        ("bigChancesCreated",              "Grandes chances criadas",        False),
        ("successfulDribbles",             "Dribles certos",                 False),
        ("totalDuelsWon",                  "Duelos ganhos",                  False),
        ("interceptions",                  "Interceptações",                 False),
        ("rating",                         "Nota média SofaScore",           False),
    ],
    "AM": [
        ("goals",                          "Gols",                           False),
        ("assists",                        "Assistências",                   False),
        ("expectedGoals",                  "Expected Goals (xG)",            False),
        ("expectedAssists",                "Expected Assists (xA)",          False),
        ("keyPasses",                      "Passes-chave",                   False),
        ("bigChancesCreated",              "Grandes chances criadas",        False),
        ("successfulDribbles",             "Dribles certos",                 False),
        ("shotsOnTarget",                  "Finalizações no alvo",           False),
        ("totalShots",                     "Finalizações",                   False),
        ("rating",                         "Nota média SofaScore",           False),
    ],
    "W": [
        ("goals",                          "Gols",                           False),
        ("assists",                        "Assistências",                   False),
        ("expectedGoals",                  "Expected Goals (xG)",            False),
        ("expectedAssists",                "Expected Assists (xA)",          False),
        ("successfulDribbles",             "Dribles certos",                 False),
        ("successfulDribblesPercentage",   "% de dribles",                   False),
        ("accurateCrosses",                "Cruzamentos certos",             False),
        ("keyPasses",                      "Passes-chave",                   False),
        ("bigChancesCreated",              "Grandes chances criadas",        False),
        ("rating",                         "Nota média SofaScore",           False),
    ],
    "ST": [
        ("goals",                          "Gols",                           False),
        ("expectedGoals",                  "Expected Goals (xG)",            False),
        ("shotsOnTarget",                  "Finalizações no alvo",           False),
        ("totalShots",                     "Finalizações totais",            False),
        ("goalConversionPercentage",       "% conversão de chutes",          False),
        ("bigChancesMissed",               "Grandes chances perdidas",       True),
        ("aerialDuelsWon",                 "Duelos aéreos ganhos",           False),
        ("assists",                        "Assistências",                   False),
        ("penaltyGoals",                   "Gols de pênalti",                False),
        ("rating",                         "Nota média SofaScore",           False),
    ],
}
