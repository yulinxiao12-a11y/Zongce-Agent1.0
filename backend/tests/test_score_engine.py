from app.score_engine import LedgerInput, compute_score, normalize_addition


def test_weighted_score_uses_school_rule_weights():
    result = compute_score(
        [
            LedgerInput("moral", 2, "志愿服务"),
            LedgerInput("academic", 3, "校级竞赛"),
            LedgerInput("arts_sports", 4, "文体活动"),
        ]
    )
    assert result["rule_version"] == "2024-07-12-electronic-info-v1"
    assert result["total"] == 77.95


def test_normalization_when_class_max_exceeds_cap():
    assert normalize_addition(30, "academic", class_max_raw=40) == 15


def test_duplicate_awards_keep_highest_only():
    result = compute_score(
        [
            LedgerInput("academic", 6, "省三", duplicate_key="蓝桥杯"),
            LedgerInput("academic", 10, "省一", duplicate_key="蓝桥杯"),
        ]
    )
    academic = next(item for item in result["details"] if item["key"] == "academic")
    assert academic["raw_add"] == 10
