#!/usr/bin/env python3
"""
Amazon Retail Arbitrage Deal Analyzer
Scores sourced products by profitability using estimated Amazon fees.
"""

import csv
import sys
from datetime import datetime

# Referral fee % by category — verify against Amazon's current fee schedule
REFERRAL_FEES = {
    "grocery": 0.08,
    "health_household": 0.15,
    "toys": 0.15,
    "electronics": 0.08,
    "home": 0.15,
    "beauty": 0.15,
    "clothing": 0.17,
    "default": 0.15,
}
MIN_REFERRAL_FEE = 0.30


def fba_fulfillment_fee(weight_oz):
    """Rough FBA fulfillment fee by weight tier (standard size estimate)."""
    lb = weight_oz / 16
    if lb <= 0.5:
        return 3.22
    elif lb <= 1:
        return 3.40
    elif lb <= 2:
        return 4.00
    elif lb <= 3:
        return 4.45
    elif lb <= 5:
        return 5.15
    elif lb <= 10:
        return 6.30
    elif lb <= 20:
        return 8.50
    return 8.50 + (lb - 20) * 0.35


def analyze_product(row, min_roi=30.0, min_profit=3.0, max_rank=150000):
    cost = float(row["cost"])
    sell_price = float(row["sell_price"])
    weight_oz = float(row.get("weight_oz", 8) or 8)
    category = (row.get("category") or "default").lower()
    sales_rank = int(row.get("sales_rank") or 0)

    referral_pct = REFERRAL_FEES.get(category, REFERRAL_FEES["default"])
    referral_fee = max(sell_price * referral_pct, MIN_REFERRAL_FEE)
    fulfillment_fee = fba_fulfillment_fee(weight_oz)
    total_fees = referral_fee + fulfillment_fee

    net_profit = sell_price - cost - total_fees
    roi = (net_profit / cost * 100) if cost > 0 else 0
    margin = (net_profit / sell_price * 100) if sell_price > 0 else 0

    verdict = "BUY"
    reasons = []
    if roi < min_roi:
        verdict = "SKIP"
        reasons.append(f"ROI {roi:.1f}% < {min_roi}%")
    if net_profit < min_profit:
        verdict = "SKIP"
        reasons.append(f"profit ${net_profit:.2f} < ${min_profit}")
    if sales_rank and sales_rank > max_rank:
        verdict = "SKIP"
        reasons.append(f"rank {sales_rank} > {max_rank}")

    return {
        "name": row.get("name", "unknown"),
        "cost": cost,
        "sell_price": sell_price,
        "referral_fee": round(referral_fee, 2),
        "fulfillment_fee": round(fulfillment_fee, 2),
        "total_fees": round(total_fees, 2),
        "net_profit": round(net_profit, 2),
        "roi_pct": round(roi, 1),
        "margin_pct": round(margin, 1),
        "sales_rank": sales_rank,
        "verdict": verdict,
        "reasons": "; ".join(reasons),
    }


def run(input_file, output_file=None):
    results = []
    with open(input_file, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                results.append(analyze_product(row))
            except (ValueError, KeyError) as e:
                print(f"Skipping bad row {row}: {e}", file=sys.stderr)

    results.sort(key=lambda r: r["roi_pct"], reverse=True)

    print(f"\n{'NAME':25} {'COST':>7} {'SELL':>7} {'FEES':>7} {'PROFIT':>8} {'ROI%':>7} {'RANK':>8}  VERDICT")
    print("-" * 90)
    for r in results:
        print(f"{r['name'][:25]:25} {r['cost']:>7.2f} {r['sell_price']:>7.2f} "
              f"{r['total_fees']:>7.2f} {r['net_profit']:>8.2f} {r['roi_pct']:>6.1f}% "
              f"{r['sales_rank']:>8} {r['verdict']}")

    buys = [r for r in results if r["verdict"] == "BUY"]
    print(f"\n{len(buys)}/{len(results)} products pass your thresholds.")

    if output_file and results:
        with open(output_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"Saved full results to {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python arbitrage_calc.py products.csv [output.csv]")
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else f"results_{datetime.now():%Y%m%d_%H%M}.csv"
    run(input_file, output_file)
