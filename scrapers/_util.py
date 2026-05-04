"""
Helpers compartilhados entre os 3 scrapers (squad, rumors, stats).

L1: get_json — wrapper único pra chamadas SofaScore (impersonate Chrome via curl_cffi).
L2: normalize_player — formato canônico de jogador (drop campos derivados).
"""
from __future__ import annotations
from curl_cffi import requests as cr

API = "https://www.sofascore.com/api/v1"


def get_json(url: str, timeout: int = 20) -> dict | None:
    """GET na API SofaScore. Retorna None em 404, levanta em outros erros HTTP."""
    r = cr.get(url, impersonate="chrome131", timeout=timeout)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def normalize_player(raw: dict | None, source: str, **extras) -> dict | None:
    """Normaliza um player do SofaScore pra o formato do projeto.

    `source`: 'main' | 'athletic' | 'loan' | 'rumor' — origem do registro.
    `extras`: campos adicionais específicos do contexto. Ex pra rumor:
              note=..., position_target=..., current_team=..., current_team_id=...
              Ex pra loan: loan_to=..., loan_until=...

    Note: o campo derivado `position_group` (DEF/MID/FWD/GK) NÃO é incluído —
    build.py recomputa a posição refinada via position_detailed + REFINED_POSITIONS.
    """
    if not raw or "id" not in raw:
        return None
    return {
        "id": raw["id"],
        "name": raw.get("name", ""),
        "shortName": raw.get("shortName", ""),
        "slug": raw.get("slug", ""),
        "position": raw.get("position", ""),
        "position_detailed": raw.get("positionsDetailed", ""),
        "jersey": raw.get("jerseyNumber"),
        "dateOfBirth": raw.get("dateOfBirth"),
        "country": (raw.get("country") or {}).get("name"),
        "preferredFoot": raw.get("preferredFoot"),
        "height": raw.get("height"),
        "source": source,
        **extras,
    }
