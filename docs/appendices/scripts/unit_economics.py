#!/usr/bin/env python3
"""
Deepforge unit-economics model: retention, lifetime value (LTV), break-even CPI and
monthly P&L scenarios. Companion to docs/07-monetization-and-business-model.md.

    python3 docs/appendices/scripts/unit_economics.py
    python3 docs/appendices/scripts/unit_economics.py --d1 0.38 --d7 0.13 --arpdau 0.15

Every input is a hypothesis to be replaced by soft-launch measurements. The point of the
model is the *shape* of the answer (what CPI we can afford, how sensitive profit is to
retention), not the specific dollar figures.

Retention is modelled with the common power-law fit  R(d) = D1 * d^(-b), where b is solved
from the D1 and D7 inputs. Lifetime days within a horizon H = 1 + sum_{d=1}^{H-1} R(d).
"""
from __future__ import annotations

import argparse
import math

DAYS_PER_MONTH = 30.4


def decay_exponent(d1: float, d7: float) -> float:
    return math.log(d1 / d7) / math.log(7)


def retention(d: int, d1: float, b: float) -> float:
    return 1.0 if d == 0 else d1 * d ** (-b)


def lifetime_days(d1: float, b: float, horizon: int) -> float:
    return sum(retention(d, d1, b) for d in range(horizon))


def platform_fee(annual_gross: float) -> float:
    """Blended Google Play service fee: 15% on the first US$1M of annual earnings
    (requires enrolment in the 15% tier), 30% above. Subscriptions are 15% throughout."""
    if annual_gross <= 1_000_000:
        return 0.15
    return (1_000_000 * 0.15 + (annual_gross - 1_000_000) * 0.30) / annual_gross


SCENARIOS = {
    # DAU at steady state (~month 6), gross ARPDAU (USD), monthly infrastructure (USD),
    # monthly fixed operating cost excluding salaries (CS, community, tools, legal retainer),
    # monthly paid UA budget (USD).
    "conservative": dict(dau=3_000, arpdau=0.08, infra=900, fixed=3_500, ua=2_000),
    "base":         dict(dau=15_000, arpdau=0.18, infra=1_800, fixed=6_000, ua=15_000),
    "upside":       dict(dau=60_000, arpdau=0.28, infra=5_500, fixed=12_000, ua=60_000),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--d1", type=float, default=0.40, help="day-1 retention")
    ap.add_argument("--d7", type=float, default=0.15, help="day-7 retention")
    ap.add_argument("--arpdau", type=float, default=0.18, help="gross ARPDAU (USD) for LTV")
    ap.add_argument("--vat", type=float, default=0.05, help="consumption tax inside the price (Taiwan VAT 5%)")
    ap.add_argument("--salaries", type=float, default=4 * 4_500, help="monthly team cost (USD), 4 people")
    args = ap.parse_args()

    b = decay_exponent(args.d1, args.d7)
    print(f"Retention fit R(d) = {args.d1:.2f} * d^-{b:.3f}")
    for d in (1, 7, 14, 30, 60, 90, 180):
        print(f"  D{d:<3d} {retention(d, args.d1, b):6.1%}")

    net_share = (1 - 0.15) / (1 + args.vat)   # small-developer fee tier, VAT-inclusive pricing
    print(f"\nNet revenue share after 15% store fee and {args.vat:.0%} VAT: {net_share:.1%} of gross\n")
    print("| Horizon | Lifetime days | Gross LTV | Net LTV (= break-even CPI) |")
    print("|---|---|---|---|")
    for h in (30, 90, 180, 365):
        lt = lifetime_days(args.d1, b, h)
        print(f"| {h} d | {lt:.1f} | ${lt * args.arpdau:.2f} | ${lt * args.arpdau * net_share:.2f} |")

    print("\nSensitivity: net 180-day LTV by D1 (rows) and ARPDAU (columns), D7 = D1 * 0.375\n")
    arps = (0.10, 0.15, 0.20, 0.30)
    print("| D1 \\ ARPDAU | " + " | ".join(f"${a:.2f}" for a in arps) + " |")
    print("|---|" + "---|" * len(arps))
    for d1 in (0.30, 0.35, 0.40, 0.45, 0.50):
        bb = decay_exponent(d1, d1 * 0.375)
        lt = lifetime_days(d1, bb, 180)
        print(f"| {d1:.0%} | " + " | ".join(f"${lt * a * net_share:.2f}" for a in arps) + " |")

    print(f"\nMonthly P&L at steady state (salaries ${args.salaries:,.0f}/month):\n")
    print("| Scenario | DAU | ARPDAU | Gross | Store fee | VAT | Net revenue | Infra | Fixed ops | Paid UA | Salaries | Operating result |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for name, s in SCENARIOS.items():
        gross = s["dau"] * s["arpdau"] * DAYS_PER_MONTH
        vat = gross - gross / (1 + args.vat)
        fee_rate = platform_fee(gross * 12)
        fee = (gross - vat) * fee_rate
        net = gross - vat - fee
        result = net - s["infra"] - s["fixed"] - s["ua"] - args.salaries
        print(f"| {name} | {s['dau']:,} | ${s['arpdau']:.2f} | ${gross:,.0f} | ${fee:,.0f} ({fee_rate:.0%}) | ${vat:,.0f} | "
              f"${net:,.0f} | ${s['infra']:,} | ${s['fixed']:,} | ${s['ua']:,} | ${args.salaries:,.0f} | ${result:,.0f} |")
    print("\nInfrastructure per DAU-month: " + ", ".join(
        f"{n} ${s['infra'] / s['dau']:.3f}" for n, s in SCENARIOS.items()))


if __name__ == "__main__":
    main()
