#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["duckdb>=1.0"]
# ///
"""
Build a self-contained HTML reconciliation report from a DuckDB built by the
driven-brands-analytics pipeline (00_load -> 10_reconciliation_view ->
40_variance_daily). All numbers are queried live from the DB; charts are
inline SVG so the report has no external dependencies and works offline.

Usage:
    ./build_recon_report.py [db_path] [out_html]
Defaults:
    db_path  = db_aug2025.duckdb   (relative to driven-brands-analytics/)
    out_html = reports/reconciliation_aug2025.html
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else ROOT / "db_aug2025.duckdb"
OUT = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else ROOT / "reports" / "reconciliation_aug2025.html"

# ── palette ────────────────────────────────────────────────────────────────
C_GOOD = "#16a34a"; C_MID = "#f59e0b"; C_BAD = "#dc2626"
C_LOCAL = "#2563eb"; C_NATIONAL = "#7c3aed"
C_MFC = "#0ea5e9"; C_DRIVEN = "#f97316"
C_INK = "#0f172a"; C_MUTE = "#64748b"; C_LINE = "#e2e8f0"


def q(con, sql, params=None):
    return con.execute(sql, params or []).fetchall()


def money(v):
    return f"${v:,.0f}" if v is not None else "—"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ── tiny inline-SVG chart helpers ────────────────────────────────────────────
def svg_hbars(items, width=560, bar_h=26, gap=10, pad_left=170, fmt=str, max_val=None):
    """items: list of (label, value, color). Horizontal bars with value labels."""
    if not items:
        return "<p class='muted'>no data</p>"
    max_val = max_val or max((it[1] for it in items), default=1) or 1
    inner = width - pad_left - 70
    h = len(items) * (bar_h + gap) + gap
    parts = [f"<svg viewBox='0 0 {width} {h}' style='width:100%;max-width:{width}px;height:auto;display:block;margin:0 auto' role='img'>"]
    y = gap
    for label, val, color in items:
        w = max(1, inner * (val / max_val))
        parts.append(
            f"<text x='{pad_left-10}' y='{y+bar_h*0.68}' text-anchor='end' "
            f"font-size='12' fill='{C_INK}'>{esc(label)}</text>"
            f"<rect x='{pad_left}' y='{y}' width='{w:.1f}' height='{bar_h}' rx='4' fill='{color}'/>"
            f"<text x='{pad_left+w+6:.1f}' y='{y+bar_h*0.68}' font-size='12' "
            f"fill='{C_MUTE}'>{esc(fmt(val))}</text>"
        )
        y += bar_h + gap
    parts.append("</svg>")
    return "".join(parts)


def svg_stacked(rows, segs, width=560, bar_h=34, gap=18, pad_left=90):
    """100%-width stacked bars.
    rows: list of (row_label, [(seg_value)...]) aligned to `segs` = [(name,color)].
    """
    h = len(rows) * (bar_h + gap) + gap + 26
    parts = [f"<svg viewBox='0 0 {width} {h}' style='width:100%;max-width:{width}px;height:auto;display:block;margin:0 auto' role='img'>"]
    y = gap
    inner = width - pad_left - 16
    for label, vals in rows:
        total = sum(vals) or 1
        x = pad_left
        parts.append(f"<text x='{pad_left-10}' y='{y+bar_h*0.64}' text-anchor='end' "
                     f"font-size='12.5' fill='{C_INK}'>{esc(label)}</text>")
        for (name, color), v in zip(segs, vals):
            w = inner * (v / total)
            if w <= 0:
                continue
            parts.append(f"<rect x='{x:.1f}' y='{y}' width='{w:.1f}' height='{bar_h}' fill='{color}'/>")
            if w > 38:
                parts.append(f"<text x='{x+w/2:.1f}' y='{y+bar_h*0.64}' text-anchor='middle' "
                             f"font-size='11.5' fill='#fff' font-weight='600'>{v:,.0f}</text>")
            x += w
        y += bar_h + gap
    # legend
    lx = pad_left
    for name, color in segs:
        parts.append(f"<rect x='{lx}' y='{y-4}' width='12' height='12' rx='2' fill='{color}'/>"
                     f"<text x='{lx+17}' y='{y+6}' font-size='11.5' fill='{C_MUTE}'>{esc(name)}</text>")
        lx += 22 + len(name) * 7.2
    parts.append("</svg>")
    return "".join(parts)


def svg_grouped(groups, series, width=560, gh=70, pad_left=90, fmt=money):
    """Grouped horizontal bars.
    groups: list of (group_label, [v1, v2, ...]) aligned to `series`=[(name,color)].
    """
    allv = [v for _, vs in groups for v in vs] or [1]
    mx = max(allv) or 1
    inner = width - pad_left - 90
    h = len(groups) * gh + 26
    parts = [f"<svg viewBox='0 0 {width} {h}' style='width:100%;max-width:{width}px;height:auto;display:block;margin:0 auto' role='img'>"]
    y = 8
    sh = 20
    for label, vals in groups:
        parts.append(f"<text x='{pad_left-10}' y='{y+ (len(series)*sh)/2 +4}' text-anchor='end' "
                     f"font-size='12.5' fill='{C_INK}'>{esc(label)}</text>")
        yy = y
        for (name, color), v in zip(series, vals):
            w = max(1, inner * (v / mx))
            parts.append(f"<rect x='{pad_left}' y='{yy}' width='{w:.1f}' height='{sh-4}' rx='3' fill='{color}'/>"
                         f"<text x='{pad_left+w+6:.1f}' y='{yy+sh*0.62}' font-size='11' fill='{C_MUTE}'>{esc(fmt(v))}</text>")
            yy += sh
        y += gh
    lx = pad_left
    for name, color in series:
        parts.append(f"<rect x='{lx}' y='{h-14}' width='12' height='12' rx='2' fill='{color}'/>"
                     f"<text x='{lx+17}' y='{h-4}' font-size='11.5' fill='{C_MUTE}'>{esc(name)}</text>")
        lx += 26 + len(name) * 7.2
    parts.append("</svg>")
    return "".join(parts)


def main():
    if not DB.exists():
        sys.exit(f"DB not found: {DB}. Build it with 00_load + 10_reconciliation_view + 40_variance_daily.")
    con = duckdb.connect(str(DB), read_only=True)

    # ── context: windows + volumes ──
    kpi_lo, kpi_hi, kpi_n = q(con, "SELECT MIN(date), MAX(date), COUNT(*) FROM driven_brands_kpi_daily")[0]
    inv_lo, inv_hi, inv_n = q(con, "SELECT MIN(CAST(invoiceDate AS DATE)), MAX(CAST(invoiceDate AS DATE)), COUNT(*) FROM invoices")[0]
    seg_counts = dict(q(con, "SELECT segment, COUNT(*) FROM driven_brands_kpi_daily GROUP BY 1"))

    # ── status summary (canonical) ──
    summ = q(con, """
        SELECT segment, reconStatus, rows, mfcGrossExTax, drivenNet, netVariance
        FROM v_variance_daily_summary ORDER BY segment, reconStatus""")

    # ── metric evolution: within-5% rate under each comparison basis ──
    metric = q(con, """
        WITH b AS (
          SELECT segment,
            abs(varianceGross) / NULLIF(drivenGrossSales,0) g,
            abs(varianceNet)   / NULLIF(drivenNetSales,0)   n,
            abs(reconVariancePct)                           c
          FROM v_variance_daily_filtered WHERE drivenNetSales > 0)
        SELECT segment, COUNT(*) tot,
          100.0*SUM(CASE WHEN g<=0.05 THEN 1 ELSE 0 END)/COUNT(*) bal_gross,
          100.0*SUM(CASE WHEN n<=0.05 THEN 1 ELSE 0 END)/COUNT(*) bal_net,
          100.0*SUM(CASE WHEN c<=0.05 THEN 1 ELSE 0 END)/COUNT(*) gross_net
        FROM b GROUP BY 1 ORDER BY 1""")

    # ── before/after >5% dollars (filtered pop) ──
    ba = q(con, """
        SELECT segment,
          SUM(CASE WHEN drivenGrossSales>0 AND abs(varianceGross)/drivenGrossSales>0.05 THEN abs(varianceGross) ELSE 0 END) before_usd,
          SUM(CASE WHEN drivenNetSales>0  AND abs(reconVariancePct)>0.05 THEN abs(reconVariance) ELSE 0 END) after_usd
        FROM v_variance_daily_filtered WHERE segment IS NOT NULL GROUP BY 1 ORDER BY 1""")

    # ── canonical bins ──
    bins = q(con, "SELECT segment, bin, rows, absVarianceUSD FROM v_variance_daily_bins ORDER BY segment, bin")

    # ── matched reconciliation proof ──
    matched = q(con, """
        SELECT segment, rows, mfcGrossExTax, drivenNet, netVariance
        FROM v_variance_daily_summary WHERE reconStatus='matched' ORDER BY segment""")

    # ── top fleets by remaining (canonical) variance ──
    topf = q(con, """
        SELECT fleetAccountNumber, fleetName, ANY_VALUE(segment) seg,
               COUNT(*) n, SUM(abs(reconVariance)) usd
        FROM v_variance_daily_filtered WHERE reconStatus='variance'
        GROUP BY 1,2 ORDER BY usd DESC LIMIT 10""")

    # ── missing_mfc: Driven rang sales but MFC issued no invoice ──
    mm_break = q(con, """
        SELECT segment,
               CASE WHEN isEducationFleet THEN 'education / prepaid' ELSE 'standard' END kind,
               COUNT(*) n, SUM(drivenNetSales) drivenNet
        FROM v_variance_daily_missing_mfc GROUP BY 1,2 ORDER BY drivenNet DESC""")
    mm_top = q(con, """
        SELECT fleetAccountNumber, fleetName, ANY_VALUE(segment) seg,
               COUNT(*) storeWeeks, SUM(drivenNetSales) drivenNet,
               BOOL_OR(isEducationFleet) edu
        FROM v_variance_daily_missing_mfc
        GROUP BY 1,2 ORDER BY drivenNet DESC LIMIT 12""")

    # ── headline totals ──
    tot_match_rows = sum(r[1] for r in matched)
    tot_match_mfc = sum(r[2] for r in matched)
    tot_match_drv = sum(r[3] for r in matched)
    tot_var_rows = sum(r[2] for r in summ if r[1] == 'variance')
    tot_var_usd = sum(abs(r[5]) for r in summ if r[1] == 'variance')
    miss_mfc_usd = sum(r[3] for r in mm_break)
    miss_mfc_edu = sum(r[3] for r in mm_break if r[1].startswith('education'))

    seg_color = {"local": C_LOCAL, "national": C_NATIONAL}
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── charts ──
    metric_chart = svg_grouped(
        [(r[0], [r[2], r[3], r[4]]) for r in metric],
        [("Balance vs Gross", C_BAD), ("Balance vs Net", C_MID), ("Gross-ex-tax vs Net (used)", C_GOOD)],
        fmt=lambda v: f"{v:.0f}%",
    )
    ba_chart = svg_grouped(
        [(r[0], [r[1], r[2]]) for r in ba],
        [("Before (balance vs gross)", C_BAD), ("After (gross-ex-tax vs net)", C_GOOD)],
        fmt=money,
    )
    # bins stacked per segment
    bin_order = ['1) <=2% or <$5', '2) >2% to <=5%', '3) >5%']
    bins_by_seg = {}
    for seg, b, rows, usd in bins:
        bins_by_seg.setdefault(seg, {})[b] = rows
    bins_chart = svg_stacked(
        [(seg, [bins_by_seg.get(seg, {}).get(b, 0) for b in bin_order]) for seg in bins_by_seg],
        [("≤2% / <$5", C_GOOD), (">2–5%", C_MID), (">5%", C_BAD)],
    )
    matched_chart = svg_grouped(
        [(r[0], [r[2], r[3]]) for r in matched],
        [("MFC gross-ex-tax", C_MFC), ("Driven net", C_DRIVEN)], fmt=money,
    )
    topf_chart = svg_hbars(
        [(f"{str(n)[:22]} ({s})", float(u), seg_color.get(s, C_MUTE)) for (_, n, s, _, u) in topf],
        fmt=money, width=620, pad_left=250,
    )
    mm_color = {("national", "standard"): C_NATIONAL, ("local", "standard"): C_LOCAL,
                ("local", "education / prepaid"): C_MID, ("national", "education / prepaid"): C_MID}
    miss_chart = svg_hbars(
        [(f"{seg} · {kind}", float(usd), mm_color.get((seg, kind), C_MUTE))
         for seg, kind, n, usd in mm_break],
        fmt=money, pad_left=200,
    )

    # ── table builders ──
    def status_rows():
        out = []
        for seg, st, rows, mfc, drv, var in summ:
            if st == 'missing_driven' or seg == '<mfc-only>':
                continue  # stores Driven doesn't report — out of scope
            out.append(f"<tr><td>{esc(seg)}</td><td>{esc(st)}</td><td class='r'>{rows:,}</td>"
                       f"<td class='r'>{money(mfc)}</td><td class='r'>{money(drv)}</td>"
                       f"<td class='r {'pos' if var>=0 else 'neg'}'>{money(var)}</td></tr>")
        return "".join(out)

    def bins_rows():
        out = []
        for seg, b, rows, usd in bins:
            out.append(f"<tr><td>{esc(seg)}</td><td>{esc(b)}</td><td class='r'>{rows:,}</td>"
                       f"<td class='r'>{money(usd)}</td></tr>")
        return "".join(out)

    def topf_rows():
        out = []
        for fid, name, seg, n, usd in topf:
            out.append(f"<tr><td class='r'>{fid}</td><td>{esc(name)}</td><td>{esc(seg)}</td>"
                       f"<td class='r'>{n:,}</td><td class='r'>{money(usd)}</td></tr>")
        return "".join(out)

    def mm_top_rows():
        out = []
        for fid, name, seg, sw, drv, edu in mm_top:
            tag = " <span class='tag'>edu</span>" if edu else ""
            out.append(f"<tr><td class='r'>{fid}</td><td>{esc(name)}{tag}</td><td>{esc(seg)}</td>"
                       f"<td class='r'>{sw:,}</td><td class='r'>{money(drv)}</td></tr>")
        return "".join(out)

    overall_rate = (tot_match_rows) / (tot_match_rows + tot_var_rows) * 100 if (tot_match_rows + tot_var_rows) else 0

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SoundBilling × Driven Brands — Reconciliation (Aug 2025)</title>
<style>
  :root {{ --ink:{C_INK}; --mute:{C_MUTE}; --line:{C_LINE}; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         color:var(--ink); background:#f8fafc; }}
  .wrap {{ max-width:820px; margin:0 auto; padding:28px 20px 64px; }}
  header.hero {{ border-bottom:3px solid var(--ink); padding-bottom:18px; margin-bottom:28px; }}
  h1 {{ font-size:27px; margin:0 0 6px; letter-spacing:-.4px; }}
  h2 {{ font-size:19px; margin:38px 0 6px; letter-spacing:-.2px; }}
  .sub {{ color:var(--mute); font-size:13px; }}
  p.lead {{ font-size:15.5px; }}
  .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:22px 0 6px; }}
  .card {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:15px 16px; }}
  .card .k {{ font-size:11px; text-transform:uppercase; letter-spacing:.6px; color:var(--mute); }}
  .card .v {{ font-size:23px; font-weight:700; margin-top:4px; letter-spacing:-.5px; }}
  .card .v.green {{ color:{C_GOOD}; }} .card .v.red {{ color:{C_BAD}; }} .card .v.amber {{ color:{C_MID}; }}
  .card .note {{ font-size:11.5px; color:var(--mute); margin-top:3px; }}
  .panel {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:18px 20px; margin-top:14px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; margin-top:8px; }}
  th,td {{ text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); }}
  th {{ font-size:11px; text-transform:uppercase; letter-spacing:.5px; color:var(--mute); }}
  td.r,th.r {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.pos {{ color:{C_GOOD}; }} td.neg {{ color:{C_BAD}; }}
  .muted {{ color:var(--mute); }}
  .callout {{ border-left:4px solid {C_GOOD}; background:#f0fdf4; padding:12px 16px; border-radius:0 8px 8px 0; margin:14px 0; }}
  .callout.warn {{ border-color:{C_MID}; background:#fffbeb; }}
  .pill {{ display:inline-block; font-size:11px; padding:2px 9px; border-radius:999px; background:#eef2ff; color:#3730a3; font-weight:600; }}
  .tag {{ display:inline-block; font-size:10px; padding:1px 6px; border-radius:4px; background:#fef3c7; color:#92400e; font-weight:600; vertical-align:middle; }}
  code {{ background:#f1f5f9; padding:1px 5px; border-radius:4px; font-size:12.5px; }}
  footer {{ margin-top:46px; color:var(--mute); font-size:12px; border-top:1px solid var(--line); padding-top:14px; }}
  @media (max-width:720px) {{ .cards {{ grid-template-columns:repeat(2,1fr); }} }}
</style></head>
<body><div class="wrap">

<header class="hero">
  <span class="pill">Reconciliation report</span>
  <h1>SoundBilling invoices × Driven Brands Fleet KPI</h1>
  <div class="sub">Window <b>{kpi_lo} → {kpi_hi}</b> (Aug 2025) · grain: week-ending × fleet × store · generated {gen}</div>
</header>

<p class="lead">Reconciles MFC <b>SoundBilling</b> invoice revenue against Driven Brands' Fleet KPI
export at the (week-ending&nbsp;× fleet&nbsp;× store) grain — limited to the stores Driven actually reports
(rows Driven didn't send are out of scope). Headline finding: once the comparison uses the
<b>right MFC number</b> — pre-tax gross invoice, not post-prepayment balance — the two systems
reconcile to the dollar on matched rows. What's left is mostly <b>nationally-billed accounts MFC never
invoices per store</b>, not billed-amount disagreements.</p>

<div class="cards">
  <div class="card"><div class="k">Matched rows</div><div class="v green">{tot_match_rows:,}</div>
     <div class="note">within $1, both sides present</div></div>
  <div class="card"><div class="k">Matched agreement</div><div class="v green">{money(tot_match_mfc)}</div>
     <div class="note">vs Driven {money(tot_match_drv)} · Δ {money(tot_match_mfc-tot_match_drv)}</div></div>
  <div class="card"><div class="k">Real amount variance</div><div class="v amber">{money(tot_var_usd)}</div>
     <div class="note">{tot_var_rows:,} rows, both sides present</div></div>
  <div class="card"><div class="k">Driven sales, no MFC invoice</div><div class="v red">{money(miss_mfc_usd)}</div>
     <div class="note">mostly national central-billing</div></div>
</div>

<h2>1 · The number we compare</h2>
<p>Driven's <b>Net Sales</b> = gross − discounts and <b>excludes tax</b>. The MFC figure that matches it is the
<b>pre-tax gross invoice</b> (<code>invoiceTotalAmount − tax</code>) — not the post-prepayment balance
(<code>invoiceTotalAmount − prepaid</code>), which reads $0 for prepaid fleets even though the store rang real
sales. Below: share of fleet/store/weeks reconciling within 5% under each candidate basis.</p>
<div class="panel">{metric_chart}</div>
<div class="callout">Moving from the balance to the pre-tax gross invoice lifts the within-5% match rate to
<b>~{overall_rate:.0f}%</b> of rows with both sides present, and collapses the &gt;5% dollar variance
dramatically (next chart).</div>

<h2>2 · &gt;5% variance dollars — before vs after</h2>
<p>Same population (education fleets and one-sided rows removed), scored on the old basis
(balance vs gross) versus the pre-tax-gross-vs-net basis we settled on.</p>
<div class="panel">{ba_chart}</div>

<h2>3 · Variance-% bins</h2>
<p class="sub">Pre-tax gross invoice vs Driven net, per fleet × store × week, by segment. A $5 floor folds tiny-ticket rounding into the good bin.</p>
<div class="panel">{bins_chart}
  <table><thead><tr><th>Segment</th><th>Bin</th><th class="r">Rows</th><th class="r">Abs variance</th></tr></thead>
  <tbody>{bins_rows()}</tbody></table>
</div>

<h2>4 · Matched rows reconcile to the dollar</h2>
<div class="panel">{matched_chart}
  <table><thead><tr><th>Segment</th><th class="r">Rows</th><th class="r">MFC gross-ex-tax</th><th class="r">Driven net</th><th class="r">Net Δ</th></tr></thead>
  <tbody>{''.join(f"<tr><td>{esc(s)}</td><td class='r'>{r:,}</td><td class='r'>{money(m)}</td><td class='r'>{money(d)}</td><td class='r {'pos' if v>=0 else 'neg'}'>{money(v)}</td></tr>" for s,r,m,d,v in matched)}</tbody></table>
</div>

<h2>5 · Driven sales MFC never invoiced</h2>
<p>These are stores Driven reported but where SoundBilling has <b>no invoice</b> for that (fleet, store, week) —
<b>{money(miss_mfc_usd)}</b> of Driven net sales. It's not a billing-amount problem: it's overwhelmingly
<b>national fleet-management, leasing and rental accounts</b> (Enterprise, Element, LeasePlan, Hertz, ARI/Holman,
Emkay, Merchants…) that are billed centrally and never flow through per-store SoundBilling invoices. A small
slice ({money(miss_mfc_edu)}) is education / prepaid programs. The local <i>standard</i> rows are the only ones
worth chasing as possible intake or store-key gaps.</p>
<div class="panel">{miss_chart}
  <p class="sub" style="margin:10px 0 2px"><b>Largest accounts Driven reports but MFC doesn't invoice per store</b></p>
  <table><thead><tr><th class="r">Fleet #</th><th>Fleet</th><th>Segment</th><th class="r">Store-weeks</th><th class="r">Driven net</th></tr></thead>
  <tbody>{mm_top_rows()}</tbody></table>
</div>

<h2>6 · Largest remaining amount variances</h2>
<p class="sub">Both sides present, ranked by absolute variance — where to look first.</p>
<div class="panel">{topf_chart}
  <table><thead><tr><th class="r">Fleet #</th><th>Fleet</th><th>Segment</th><th class="r">Rows</th><th class="r">Abs variance</th></tr></thead>
  <tbody>{topf_rows()}</tbody></table>
</div>

<h2>Status detail (in-scope stores)</h2>
<div class="panel"><table>
  <thead><tr><th>Segment</th><th>Status</th><th class="r">Rows</th><th class="r">MFC gross-ex-tax</th><th class="r">Driven net</th><th class="r">Net variance</th></tr></thead>
  <tbody>{status_rows()}</tbody></table></div>

</div></body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}  ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
