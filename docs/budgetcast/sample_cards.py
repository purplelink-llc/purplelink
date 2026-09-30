#!/usr/bin/env python3
"""Source notes for the illustrative cards on /budgetcast/. Every figure on the
page comes from this script; rerun it and update the page if any input changes.

Tax inputs (2026, single):
  Federal standard deduction $16,100 and the ordinary-income brackets:
  IRS Rev. Proc. 2025-32 (irs.gov/pub/irs-drop/rp-25-32.pdf), section 3.
  Verified against the PDF text on 2026-09-30.
  Social Security wage base $184,500: SSA announcement, 2025-10-24
  (ssa.gov/oact/cola/cbb.html). Rates 6.2% and 1.45% are statutory.
  Georgia: approximated as 4.99% of FEDERAL taxable income. This ignores
  Georgia's own deductions, exemptions and credits. It is not a Georgia return.
Nothing here is tax advice.
"""
import numpy as np

WAGES = 95_000
STD = 16_100
BRACKETS = [(12_400, .10), (50_400, .12), (105_700, .22), (201_775, .24),
            (256_225, .32), (640_600, .35), (float("inf"), .37)]
SS_BASE, SS_RATE, MED_RATE, GA_RATE = 184_500, .062, .0145, .0499


def federal(taxable):
    tax, lo = 0.0, 0.0
    for hi, r in BRACKETS:
        if taxable > lo:
            tax += (min(taxable, hi) - lo) * r
        lo = hi
    return tax


taxable = WAGES - STD
fed = federal(taxable)
ss = min(WAGES, SS_BASE) * SS_RATE
med = WAGES * MED_RATE
ga = taxable * GA_RATE
total = fed + ss + med + ga
print(f"taxable income      {taxable:>10,.0f}")
print(f"federal income tax  {fed:>10,.0f}")
print(f"social security     {ss:>10,.0f}")
print(f"medicare            {med:>10,.0f}")
print(f"georgia (approx.)   {ga:>10,.0f}")
print(f"total               {total:>10,.0f}   ({total / WAGES:.1%} of wages)")

# Retirement illustration: 10,000 scenarios, annual real (inflation-adjusted)
# return ~ Normal(4.5%, 12%), age 35 to 65, $80,000 saved, $12,000 added per
# year at year end, goal $1,000,000 in today's dollars. Assumptions, not forecasts.
rng = np.random.default_rng(2026)
N, YEARS, START, ADD, GOAL = 10_000, 30, 80_000, 12_000, 1_000_000
bal = np.full(N, float(START))
for _ in range(YEARS):
    bal = bal * (1 + rng.normal(.045, .12, N)) + ADD
p10, p50, p90 = np.percentile(bal, [10, 50, 90])
print(f"retirement P10 {p10:,.0f}  P50 {p50:,.0f}  P90 {p90:,.0f}  share>=goal {np.mean(bal >= GOAL):.0%}")
