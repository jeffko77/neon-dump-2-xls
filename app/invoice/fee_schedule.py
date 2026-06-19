from __future__ import annotations

from typing import TypedDict


class FeeOption(TypedDict):
    label: str
    amount: float


class FeeField(TypedDict):
    key: str
    label: str
    default: float
    options: list[FeeOption]


STANDARD_FEE_SCHEDULE: list[FeeField] = [
    {
        "key": "base_amount",
        "label": "Base amount",
        "default": 110.0,
        "options": [
            {"label": "$110.00 — Schedule preparation", "amount": 110.0},
        ],
    },
    {
        "key": "revision_amount",
        "label": "Revision fee",
        "default": 0.0,
        "options": [
            {"label": "$0.00 — Not applicable", "amount": 0.0},
            {"label": "$50.00 — Revision", "amount": 50.0},
        ],
    },
    {
        "key": "dual_sport_fee",
        "label": "Dual-sport fee",
        "default": 0.0,
        "options": [
            {"label": "$0.00 — Single sport", "amount": 0.0},
            {"label": "$100.00 — Lacrosse + Field Hockey", "amount": 100.0},
        ],
    },
    {
        "key": "ranking_services",
        "label": "Ranking services",
        "default": 0.0,
        "options": [
            {"label": "$0.00 — Not enrolled", "amount": 0.0},
            {"label": "$12.00 — Ranking services", "amount": 12.0},
        ],
    },
    {
        "key": "c_team_scheduling",
        "label": "C-team scheduling",
        "default": 0.0,
        "options": [
            {"label": "$0.00 — Not enrolled", "amount": 0.0},
            {"label": "$20.00 — C-team scheduling", "amount": 20.0},
        ],
    },
    {
        "key": "fh_ranking_services",
        "label": "FH ranking services",
        "default": 0.0,
        "options": [
            {"label": "$0.00 — Not enrolled", "amount": 0.0},
            {"label": "$15.00 — Field Hockey ranking", "amount": 15.0},
        ],
    },
]

FEE_DEFAULTS_BY_SPORT: dict[str, dict[str, float]] = {
    "Lacrosse": {
        "base_amount": 110.0,
        "revision_amount": 0.0,
        "dual_sport_fee": 0.0,
        "ranking_services": 0.0,
        "c_team_scheduling": 0.0,
        "fh_ranking_services": 0.0,
    },
    "Field Hockey": {
        "base_amount": 110.0,
        "revision_amount": 0.0,
        "dual_sport_fee": 0.0,
        "ranking_services": 0.0,
        "c_team_scheduling": 0.0,
        "fh_ranking_services": 15.0,
    },
}
