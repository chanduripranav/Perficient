"""Business-case calculations for a hospital client and for Perficient.

Every input either comes from a cited public source, from the hospital's own published
price file (the CareConnect dataset), or must be supplied by the hospital / Perficient.
No input is invented here: functions return None when a required input is missing.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# Cited facts --------------------------------------------------------------------------
CMS_PT_URL = "https://www.cms.gov/priorities/key-initiatives/hospital-price-transparency"
# CY2022 OPPS final rule: hospitals with more than 550 beds can be fined $5,500 per day.
CMS_MAX_DAILY_PENALTY = 5_500
CMS_MAX_ANNUAL_PENALTY = CMS_MAX_DAILY_PENALTY * 365  # $2,007,500

RRH_URL = "https://www.perficient.com/outcomes/rochester-regional-health"
RRH_SCHEDULING_LIFT = 0.26       # +26% online scheduling, existing patients (Perficient-reported)
RRH_MONTHLY_CALL_SAVINGS = 79_000  # $79K+ per month call-center savings (Perficient-reported)

# Worked example: illustrative inputs used only when the presenter asks for them.
WORKED_EXAMPLE = {
    "h_visitors": 2_000,     # price-shopping visits per month for the procedure
    "h_conversion": 3.0,     # % of those visits that become a booked procedure
    "h_calls": 1_500,        # price-related calls per month
    "h_deflect": 30.0,       # % of those calls answered by CareConnect instead
    "h_cost_call": 6.0,      # fully loaded cost per call ($)
    "p_impl": 400_000,       # Perficient implementation fee ($)
    "p_managed": 150_000,    # Perficient managed services per year ($)
    "p_clients": 5,          # hospital clients
    "p_years": 3,            # contract years
}


def _ready(*values) -> bool:
    return all(v is not None for v in values)


def new_patient_revenue(visitors_per_month, conversion_pct, rate):
    """Added procedures/yr = visitors/month x 12 x conversion; revenue = procedures x rate."""
    if not _ready(visitors_per_month, conversion_pct, rate):
        return None
    procedures = visitors_per_month * 12 * conversion_pct / 100
    return {"procedures": procedures, "revenue": procedures * rate}


def call_center_savings(calls_per_month, deflect_pct, cost_per_call):
    """Savings/yr = price calls/month x 12 x share deflected x cost per call."""
    if not _ready(calls_per_month, deflect_pct, cost_per_call):
        return None
    deflected = calls_per_month * 12 * deflect_pct / 100
    return {"calls": deflected, "savings": deflected * cost_per_call}


def perficient_revenue(clients, implementation_fee, managed_per_year, years):
    """Per client = implementation + managed x years; total = per client x clients."""
    if not _ready(clients, implementation_fee, managed_per_year, years):
        return None
    per_client = implementation_fee + managed_per_year * years
    return {"per_client": per_client, "total": per_client * clients,
            "recurring_per_year": managed_per_year * clients}


def _round_half_up(x: float, places: int) -> Decimal:
    return Decimal(str(x)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def fmt_big(value: float) -> str:
    """Compact dollars with standard half-up rounding ($65,250,000 -> $65.3M)."""
    for size, suffix, places in ((1e9, "B", 1), (1e6, "M", 1), (1e3, "K", 0)):
        if abs(value) >= size:
            return f"${_round_half_up(value / size, places):,}{suffix}"
    return f"${_round_half_up(value, 0):,}"
