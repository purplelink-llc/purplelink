import numpy as np
import pandas as pd
from math import erf, sqrt

rng = np.random.default_rng(2026)

# Specification (everything the output depends on)
constructs = {
    "TRUST":  {"loadings": [0.80, 0.75, 0.70, 0.70], "cuts": [-1.5, -0.5, 0.5, 1.5]},
    "INTENT": {"loadings": [0.85, 0.80, 0.75, 0.70], "cuts": [-1.2, -0.4, 0.4, 1.2]},
}
phi = np.array([[1.0, 0.40],
                [0.40, 1.0]])      # latent correlation TRUST-INTENT
miss_rate = 0.05                   # MCAR, applied to each item response

def simulate(n, miss=0.0, discretize=True):
    names = list(constructs)
    L = np.linalg.cholesky(phi)
    eta = rng.standard_normal((n, len(names))) @ L.T      # latent scores, unit variance
    cols, cont = {}, {}
    for k, name in enumerate(names):
        spec = constructs[name]
        for j, lam in enumerate(spec["loadings"], start=1):
            e = rng.standard_normal(n)
            x = lam * eta[:, k] + np.sqrt(1 - lam**2) * e  # unit-variance indicator
            col = f"{name}{j}"
            cont[col] = x
            # np.digitize returns 0..4 for four cuts, so add 1 for a 1-5 scale
            cols[col] = np.digitize(x, spec["cuts"]) + 1 if discretize else x
    df = pd.DataFrame(cols)
    if miss > 0:
        df = df.mask(rng.random(df.shape) < miss)       # MCAR: every cell has the same chance
    if discretize:
        df = df.astype("Int64")                          # whole numbers, with <NA> for missing
    return df, pd.DataFrame(cont)

# 1. The example data set
df, _ = simulate(500, miss=miss_rate)
df.insert(0, "id", np.arange(1, len(df) + 1))
df["synthetic"] = True
df.to_csv("synthetic_trust_intent.csv", index=False)
print(df.shape)
print(df.head(3).to_string(index=False))
print("missing share:", round(float(df.drop(columns=["id", "synthetic"]).isna().mean().mean()), 3))

# 2. Verification: same generator, large n, no missingness
big, big_cont = simulate(200_000)
def ncdf(z): return 0.5 * (1 + erf(z / sqrt(2)))

print("\nItem-item correlations of the continuous indicators vs lambda_i * lambda_j * rho")
worst = 0.0
for a, b in [("TRUST1", "TRUST2"), ("TRUST1", "INTENT1"), ("TRUST3", "INTENT4"), ("INTENT2", "INTENT3")]:
    la = constructs[a[:-1]]["loadings"][int(a[-1]) - 1]
    lb = constructs[b[:-1]]["loadings"][int(b[-1]) - 1]
    rho = 1.0 if a[:-1] == b[:-1] else phi[0, 1]
    want = la * lb * rho
    got = np.corrcoef(big_cont[a], big_cont[b])[0, 1]
    worst = max(worst, abs(got - want))
    print(f"{a}-{b}: specified {want:.3f}, simulated {got:.3f}")
print("largest absolute gap:", round(worst, 4))

print("\nCategory proportions, TRUST1 and INTENT1: target vs simulated")
for name in ("TRUST1", "INTENT1"):
    cuts = constructs[name[:-1]]["cuts"]
    edges = [-np.inf] + cuts + [np.inf]
    target = [ncdf(hi) - ncdf(lo) if np.isfinite(lo) and np.isfinite(hi)
              else (ncdf(hi) if not np.isfinite(lo) else 1 - ncdf(lo))
              for lo, hi in zip(edges[:-1], edges[1:])]
    sim = big[name].value_counts(normalize=True).sort_index().to_numpy()
    print(name, "target", np.round(target, 3), "simulated", np.round(sim, 3),
          "max gap", round(float(np.abs(np.array(target) - sim).max()), 4))

t_cont = big_cont[["TRUST1", "TRUST2", "TRUST3", "TRUST4"]].mean(axis=1)
i_cont = big_cont[["INTENT1", "INTENT2", "INTENT3", "INTENT4"]].mean(axis=1)
t_ord = big[["TRUST1", "TRUST2", "TRUST3", "TRUST4"]].mean(axis=1)
i_ord = big[["INTENT1", "INTENT2", "INTENT3", "INTENT4"]].mean(axis=1)
print("\nScale-score correlation TRUST-INTENT (latent specified 0.40)")
lt, li = np.array(constructs["TRUST"]["loadings"]), np.array(constructs["INTENT"]["loadings"])
def var_mean(l): return (l.sum() ** 2 + (1 - l**2).sum()) / len(l) ** 2
implied = phi[0, 1] * lt.sum() * li.sum() / 16 / np.sqrt(var_mean(lt) * var_mean(li))
print("implied by the loadings:", round(float(implied), 3))
print("continuous indicators:", round(float(np.corrcoef(t_cont, i_cont)[0, 1]), 3))
print("5-point items:         ", round(float(np.corrcoef(t_ord, i_ord)[0, 1]), 3))
