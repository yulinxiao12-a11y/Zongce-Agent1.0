from __future__ import annotations

from dataclasses import dataclass

RULE_VERSION = "2024-07-12-electronic-info-v1"

DIMENSIONS = {
    "moral": {"label": "德育", "base": 70.0, "cap": 30.0, "weight": 0.20},
    "academic": {"label": "学业", "base": 80.0, "cap": 20.0, "weight": 0.65},
    "arts_sports": {"label": "文体", "base": 60.0, "cap": 40.0, "weight": 0.15},
}

DEFAULT_CLASS_MAX_RAW = {
    "moral": 30.0,
    "academic": 20.0,
    "arts_sports": 40.0,
}


@dataclass(frozen=True)
class LedgerInput:
    dimension: str
    score: float
    title: str
    duplicate_key: str = ""


def normalize_addition(raw_score: float, dimension: str, class_max_raw: float | None = None) -> float:
    config = DIMENSIONS[dimension]
    cap = config["cap"]
    class_max = class_max_raw if class_max_raw is not None else DEFAULT_CLASS_MAX_RAW[dimension]
    if class_max > cap and class_max > 0:
        return raw_score / class_max * cap
    return raw_score


def collapse_duplicate_awards(items: list[LedgerInput]) -> list[LedgerInput]:
    kept: dict[tuple[str, str], LedgerInput] = {}
    passthrough: list[LedgerInput] = []
    for item in items:
        if not item.duplicate_key:
            passthrough.append(item)
            continue
        key = (item.dimension, item.duplicate_key)
        if key not in kept or item.score > kept[key].score:
            kept[key] = item
    return passthrough + list(kept.values())


def compute_score(
    ledgers: list[LedgerInput],
    deductions: dict[str, float] | None = None,
    class_max_raw: dict[str, float] | None = None,
) -> dict:
    deductions = deductions or {}
    class_max_raw = class_max_raw or DEFAULT_CLASS_MAX_RAW
    valid_ledgers = [l for l in ledgers if l.dimension in DIMENSIONS]
    collapsed = collapse_duplicate_awards(valid_ledgers)

    details = []
    weighted_total = 0.0
    for key, config in DIMENSIONS.items():
        raw_add = sum(item.score for item in collapsed if item.dimension == key)
        normalized_add = normalize_addition(raw_add, key, class_max_raw.get(key))
        deduction = deductions.get(key, 0.0)
        dimension_score = max(0.0, min(100.0, config["base"] + normalized_add - deduction))
        weighted = dimension_score * config["weight"]
        weighted_total += weighted
        details.append(
            {
                "key": key,
                "label": config["label"],
                "base": config["base"],
                "raw_add": round(raw_add, 2),
                "normalized_add": round(normalized_add, 2),
                "deduction": round(deduction, 2),
                "score": round(dimension_score, 2),
                "weight": config["weight"],
                "weighted": round(weighted, 2),
                "cap": config["cap"],
            }
        )

    return {
        "rule_version": RULE_VERSION,
        "total": round(weighted_total, 2),
        "details": details,
    }
