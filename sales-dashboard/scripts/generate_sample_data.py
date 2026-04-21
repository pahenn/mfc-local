"""Generate realistic sample CSVs for the sales dashboard.

Stdlib only. Outputs to ../source-data/{invoice_header,invoice_detail,accounts}.csv.
Seeded for reproducibility.

Override the "current date" for reproducible snapshots:
    SAMPLE_DATA_AS_OF=2026-04-21 uv run scripts/generate_sample_data.py
"""
from __future__ import annotations

import csv
import os
import random
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

TODAY = date.fromisoformat(os.environ["SAMPLE_DATA_AS_OF"]) if "SAMPLE_DATA_AS_OF" in os.environ else date.today()
START = date(TODAY.year - 3, 1, 1)
OUT = Path(__file__).resolve().parent.parent / "source-data"
OUT.mkdir(parents=True, exist_ok=True)

# (description, category, base_price)
CATALOG = [
    ("Oil change — synthetic",        "Oil change",         85),
    ("Oil change — conventional",     "Oil change",         45),
    ("Oil filter replacement",        "Engine filter",      15),
    ("Engine air filter replacement", "Engine filter",      25),
    ("Tire rotation",                 "Tire rotation",      30),
    ("Tire rotation + balance",       "Tire rotation",      55),
    ("Cabin air filter replacement",  "Cabin air filter",   30),
    ("Brake pad replacement — front", "Brake service",     180),
    ("Brake pad replacement — rear",  "Brake service",     160),
    ("Wiper blade replacement",       "Wipers",             35),
    ("Battery test & replacement",    "Battery",           150),
    ("Coolant flush",                 "Fluids",             90),
    ("Transmission fluid service",    "Fluids",            160),
    ("4-wheel alignment",             "Alignment",          95),
    ("Diagnostic fee",                "Labor",              75),
    ("Shop labor — 1hr",              "Labor",             120),
    ("Shop labor — 2hr",              "Labor",             240),
    ("State inspection",              "Inspection",         25),
]

SEASONALITY = {1:0.85, 2:0.80, 3:0.95, 4:1.00, 5:1.05, 6:1.10,
               7:1.10, 8:1.05, 9:1.20, 10:1.25, 11:1.10, 12:0.90}

def growth_factor(d: date) -> float:
    years = (d - START).days / 365.25
    return 1.0 + 0.08 * years  # ~8% YoY growth

@dataclass
class Account:
    account_id: int
    account_name: str
    parent_account_name: str | None
    segment: str
    status: str
    signup_date: date
    cancelled_date: date | None
    cancellation_reason: str | None
    tier: str = field(default="medium")  # internal; stripped on write

accounts: list[Account] = []
_next_aid = 1000

def add(name, parent, tier, status="Active", cancelled=None, reason=None, signup=None):
    global _next_aid
    accounts.append(Account(
        account_id=_next_aid,
        account_name=name,
        parent_account_name=parent,
        segment="Fleet",
        status=status,
        signup_date=signup or date(START.year - 1, random.randint(1, 12), random.randint(1, 28)),
        cancelled_date=cancelled,
        cancellation_reason=reason,
        tier=tier,
    ))
    _next_aid += 1

# ── Chicago Co-op Fleet Services: parent + 8 child fleets ──
CHICAGO = "Chicago Co-op Fleet Services"
add(CHICAGO, None, "parent_only")
for name, tier in [
    ("Chicago Co-op — Downtown Delivery",    "xl"),
    ("Chicago Co-op — Airport Services",     "large"),
    ("Chicago Co-op — West Side Fleet",      "large"),
    ("Chicago Co-op — North Shore",          "medium"),
    ("Chicago Co-op — South Suburban",       "medium"),
    ("Chicago Co-op — Industrial District",  "large"),
    ("Chicago Co-op — Midway Operations",    "large"),
    ("Chicago Co-op — Expressway Routes",    "xl"),
]:
    add(name, CHICAGO, tier)

# ── Midwest Logistics Group ──
MWL = "Midwest Logistics Group"
add(MWL, None, "parent_only")
for name, tier in [
    ("Midwest Logistics — Milwaukee",    "medium"),
    ("Midwest Logistics — Indianapolis", "large"),
    ("Midwest Logistics — Columbus",     "large"),
    ("Midwest Logistics — Detroit",      "medium"),
]:
    add(name, MWL, tier)

# ── Atlantic Transport Partners ──
ATP = "Atlantic Transport Partners"
add(ATP, None, "parent_only")
for name, tier in [
    ("Atlantic Transport — Boston",       "large"),
    ("Atlantic Transport — Philadelphia", "medium"),
    ("Atlantic Transport — DC Metro",     "medium"),
]:
    add(name, ATP, tier)

# ── Standalone accounts, varied sizes ──
for name, tier in [
    ("Harbor City Express",       "large"),
    ("Sunshine Delivery Co",      "xl"),
    ("Northwood Transport",       "medium"),
    ("Riverbend Logistics",       "medium"),
    ("Summit Freight Services",   "large"),
    ("Pinewood Fleet Solutions",  "small"),
    ("Coastal Courier",           "small"),
    ("Prairie Wind Trucking",     "medium"),
    ("Blue Ridge Fleet",          "medium"),
    ("Evergreen Moving",          "small"),
    ("Meridian Express",          "large"),
    ("Oakwood Distribution",      "medium"),
    ("Silver State Haulers",      "xl"),
    ("Cornerstone Delivery",      "small"),
    ("Red Rock Logistics",        "medium"),
]:
    add(name, None, tier)

# ── Cancelled accounts (mix within 12 and 24 months) ──
for name, tier, months_ago, reason in [
    ("Westview Fleet Operations", "medium",  4,  "Price"),
    ("Lakeshore Transit",         "small",  10,  "Went out of business"),
    ("Twin Peaks Logistics",      "medium",  7,  "Price"),
    ("Heritage Haulers",          "large",  18,  "Service quality"),
    ("Copper Canyon Couriers",    "small",  22,  "Acquired"),
]:
    cancel_dt = TODAY - timedelta(days=int(30.4 * months_ago))
    add(name, None, tier, status="Cancelled", cancelled=cancel_dt, reason=reason,
        signup=date(START.year - 1, 3, 10))

# ── Inactive accounts (no invoices in past 12+ months, not cancelled) ──
for name in ["Golden Gate Fleet", "Magnolia Transport"]:
    add(name, None, "small_inactive")

# ── Invoice generation ──
TIER_FREQ = {"xl": 18, "large": 9, "medium": 4, "small": 1.2, "small_inactive": 1.0, "parent_only": 0}
TIER_AVG_LINES = {"xl": 3.2, "large": 2.8, "medium": 2.2, "small": 1.6, "small_inactive": 1.6, "parent_only": 0}

invoices = []
details = []
invoice_id = 100_000
line_id = 1

for a in accounts:
    if a.tier == "parent_only":
        continue
    start = a.signup_date
    end = a.cancelled_date or TODAY
    if a.tier == "small_inactive":
        end = TODAY - timedelta(days=int(30.4 * 14))  # went inactive 14 months ago

    base_freq = TIER_FREQ[a.tier]
    avg_lines = TIER_AVG_LINES[a.tier]

    cur = date(start.year, start.month, 1)
    while cur <= end:
        expected = base_freq * SEASONALITY[cur.month] * growth_factor(cur)
        n_invoices = max(0, int(round(random.gauss(expected, max(1.0, expected * 0.3)))))
        for _ in range(n_invoices):
            inv_date = date(cur.year, cur.month, random.randint(1, 28))
            if inv_date < start or inv_date > end:
                continue
            invoice_id += 1
            n_lines = max(1, int(round(random.gauss(avg_lines, 1.0))))
            subtotal = 0.0
            inv_lines = []
            for _ in range(n_lines):
                desc, cat, price = random.choice(CATALOG)
                qty = random.choice([1, 1, 1, 1, 2, 4]) if ("tire" in desc.lower() or "brake" in desc.lower()) else 1
                unit = round(price * random.uniform(0.92, 1.12), 2)
                amt = round(unit * qty, 2)
                subtotal += amt
                inv_lines.append({
                    "invoice_id": invoice_id,
                    "line_id": line_id,
                    "description": desc,
                    "category": cat,
                    "quantity": qty,
                    "unit_price": unit,
                    "line_amount": amt,
                })
                line_id += 1
            # ~15% of invoices get a 5–15% discount
            discount = round(subtotal * random.uniform(0.05, 0.15), 2) if random.random() < 0.15 else 0.0
            # 8.25% sales tax on taxable base (subtotal − discount)
            tax = round((subtotal - discount) * 0.0825, 2)
            total = round(subtotal - discount + tax, 2)
            invoices.append({
                "invoice_id": invoice_id,
                "account_id": a.account_id,
                "invoice_date": inv_date.isoformat(),
                "subtotal": round(subtotal, 2),
                "discount_amount": discount,
                "tax_amount": tax,
                "total_amount": total,
            })
            details.extend(inv_lines)

        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)

# ── Write CSVs ──
def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})

write_csv(OUT / "invoice_header.csv", invoices,
          ["invoice_id", "account_id", "invoice_date",
           "subtotal", "discount_amount", "tax_amount", "total_amount"])
write_csv(OUT / "invoice_detail.csv", details,
          ["invoice_id", "line_id", "description", "category", "quantity", "unit_price", "line_amount"])

account_rows = []
for a in accounts:
    d = asdict(a)
    d.pop("tier", None)
    d["signup_date"] = a.signup_date.isoformat() if a.signup_date else ""
    d["cancelled_date"] = a.cancelled_date.isoformat() if a.cancelled_date else ""
    account_rows.append(d)

write_csv(OUT / "accounts.csv", account_rows,
          ["account_id", "account_name", "parent_account_name", "segment",
           "status", "signup_date", "cancelled_date", "cancellation_reason"])

print(f"Wrote {len(accounts)} accounts, {len(invoices)} invoices, {len(details)} detail lines")
print(f"  → {OUT}")
print(f"As of: {TODAY.isoformat()}   Date range: {START.isoformat()} through {TODAY.isoformat()}")
