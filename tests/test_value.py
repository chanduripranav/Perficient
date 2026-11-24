from src.value import (CMS_MAX_ANNUAL_PENALTY, call_center_savings, fmt_big,
                       new_patient_revenue, perficient_revenue)


def test_cms_max_penalty_matches_rule():
    assert CMS_MAX_ANNUAL_PENALTY == 2_007_500


def test_new_patient_revenue_formula():
    r = new_patient_revenue(2_000, 3.0, 480)
    assert r["procedures"] == 720 and r["revenue"] == 345_600


def test_missing_input_returns_none():
    assert new_patient_revenue(None, 3.0, 480) is None
    assert perficient_revenue(5, None, 150_000, 3) is None


def test_call_center_savings_formula():
    assert call_center_savings(1_500, 30.0, 6.0)["savings"] == 32_400


def test_perficient_revenue_formula():
    r = perficient_revenue(5, 400_000, 150_000, 3)
    assert r["per_client"] == 850_000 and r["total"] == 4_250_000


def test_fmt_big_rounds_half_up():
    assert fmt_big(65_250_000) == "$65.3M"
    assert fmt_big(750_000) == "$750K"
