import numpy as np
from scipy import stats
from statsmodels.stats.power import TTestIndPower

rng = np.random.default_rng(7)
loadings = np.array([0.80, 0.75, 0.70, 0.70])
cuts = [-1.5, -0.5, 0.5, 1.5]

def scale_scores(n, shift, discretize=True):
    """Mean of four items for n people whose latent score is shifted by `shift`."""
    eta = rng.standard_normal(n) + shift                    # latent, within-group SD 1
    e = rng.standard_normal((n, len(loadings)))
    x = loadings * eta[:, None] + np.sqrt(1 - loadings**2) * e
    items = np.digitize(x, cuts) + 1 if discretize else x
    return items.mean(axis=1)

def power(n_per_group, shift, reps=5000, discretize=True, alpha=0.05):
    hits = 0
    for _ in range(reps):
        a = scale_scores(n_per_group, 0.0, discretize)
        b = scale_scores(n_per_group, shift, discretize)
        hits += stats.ttest_ind(b, a).pvalue < alpha         # pooled-variance t test
    return hits / reps

def mc_margin(p, reps):  # approximate 95% margin from the binomial standard error
    return 1.96 * np.sqrt(p * (1 - p) / reps)

n, shift, reps = 64, 0.5, 5000
solver = TTestIndPower()

# Check 1: one continuous score, d = 0.5, no items and no thresholds
# (closed form should be close to 0.80)
hits = 0
for _ in range(reps):
    a = rng.standard_normal(n); b = rng.standard_normal(n) + shift
    hits += stats.ttest_ind(b, a).pvalue < 0.05
p_single = hits / reps
print(f"1. continuous score, d = 0.50, n = {n} per group")
print(f"   simulated power {p_single:.3f} (+/- {mc_margin(p_single, reps):.3f}), "
      f"statsmodels {solver.power(effect_size=0.5, nobs1=n, alpha=0.05, ratio=1.0):.3f}")

# Effective d of the four-item, 5-point scale score for a latent shift of 0.5
big_a, big_b = scale_scores(400_000, 0.0), scale_scores(400_000, shift)
pooled_sd = np.sqrt((big_a.var(ddof=1) + big_b.var(ddof=1)) / 2)
d_eff = (big_b.mean() - big_a.mean()) / pooled_sd
print(f"\n2. four 5-point items, latent shift {shift}, n = {n} per group")
print(f"   effective d on the scale score: {d_eff:.3f}")
p_scale = power(n, shift, reps)
print(f"   simulated power {p_scale:.3f} (+/- {mc_margin(p_scale, reps):.3f}), "
      f"statsmodels at d = {d_eff:.3f}: {solver.power(effect_size=d_eff, nobs1=n, alpha=0.05, ratio=1.0):.3f}")
p_null = power(n, 0.0, reps)
print(f"   simulated rejection rate with shift 0: {p_null:.3f} (alpha 0.05)")
need = solver.solve_power(effect_size=d_eff, power=0.80, alpha=0.05, ratio=1.0)
print(f"   statsmodels n per group for 80% power at d = {d_eff:.3f}: {need:.1f}")
