"""
Verification: run the ellipse Monte Carlo 100 times (10,000 points each)
using exactly the same math as 01-original-ellipse/ellipse_area.py,
and check whether the "skew away from 1" is a real problem.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import skew, norm

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ellipse_100_runs.png")
rng = np.random.default_rng(2026)

# Same setup as the original script: box centered (0,0) 10x10, ellipse a=4 (vertical), b=2
hb, kb, w, ht = 0, 0, 10, 10
h, k, a, b = 0, 0, 4, 2
n, runs = 10_000, 100
A, E = w * ht, np.pi * a * b
p = E / A

paths = np.empty((runs, n))
running_skew = np.empty(runs)
raw_final_S = np.empty(runs)
for r in range(runs):
    x = rng.uniform(hb - w/2, hb + w/2, n)
    y = rng.uniform(kb - ht/2, kb + ht/2, n)
    i = ((x-h)**2)/(b**2) + ((y-k)**2)/(a**2) <= 1
    inside = np.cumsum(i.astype(int))
    S = A * inside / np.arange(1, n+1)       # exactly what the script's loop computes
    paths[r] = S / E                         # what goes into `estimates`
    running_skew[r] = skew(paths[r])         # the "Skew" printed at the last line
    raw_final_S[r] = S[-1]

js = np.arange(1, n+1)
final = paths[:, -1]
sd_theory = np.sqrt((1-p)/(p*js))
frac_above = (paths > 1).mean(axis=1)
# time-in-lead measured after the first 100 points (avoid the j=1 0/4 artifacts)
frac_above_late = (paths[:, 100:] > 1).mean(axis=1)

print(f"p = E/A = {p:.4f}, E = {E:.3f}, A = {A}")
print(f"Final estimate/true over 100 runs: mean={final.mean():.4f}, sd={final.std(ddof=1):.4f}, theory sd={sd_theory[-1]:.4f}")
print(f"  min={final.min():.4f} max={final.max():.4f}, runs above 1: {(final>1).sum()}")
print(f"  skew of the 100 FINAL estimates: {skew(final):+.3f}  (theory {(1-2*p)/np.sqrt(n*p*(1-p)):+.3f})")
print(f"'Running skew' (script's statistic) across runs: mean={running_skew.mean():+.2f}, "
      f"range {running_skew.min():+.2f}..{running_skew.max():+.2f}, positive in {(running_skew>0).sum()}/100")
print(f"Mean of all estimates in a run (script's 'Mean'): avg over runs {paths.mean(axis=1).mean():.4f}")
print(f"Fraction of run spent above 1 (after pt 100): <10% or >90% in {((frac_above_late<.1)|(frac_above_late>.9)).sum()} runs, 40-60% in {((frac_above_late>.4)&(frac_above_late<.6)).sum()} runs")
print(f"Raw S at end (what figure 2 actually plots) avg = {raw_final_S.mean():.2f}; red line drawn at 1")

# ---------- figure ----------
BLUE, ORANGE, INK, INK2, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.facecolor": "#fcfcfb",
                     "axes.facecolor": "#fcfcfb"})
fig, ax = plt.subplots(2, 2, figsize=(13, 9.5))

# A: all 100 running paths
a0 = ax[0, 0]
for r in range(runs):
    a0.plot(js, paths[r], color=BLUE, lw=0.6, alpha=0.25)
hi = np.argmax(frac_above_late); lo = np.argmin(frac_above_late)
a0.plot(js, paths[hi], color=BLUE, lw=1.6)
a0.plot(js, paths[lo], color=ORANGE, lw=1.6)
a0.plot(js, 1 + 1.96*sd_theory, color=INK, lw=1.2, ls="--")
a0.plot(js, 1 - 1.96*sd_theory, color=INK, lw=1.2, ls="--", label="theory 95% band  ±1.96·√((1−p)/(p·n))")
a0.axhline(1, color=INK2, lw=0.8)
a0.set_xscale("log"); a0.set_ylim(0.5, 1.5)
a0.set_xlabel("number of points n (log scale)"); a0.set_ylabel("estimated area / true area")
a0.set_title("A. 100 runs: every path funnels toward 1 like 1/√n", loc="left", fontsize=11)
a0.text(700, 1.16, "a run that stays above 1", color=BLUE, fontsize=9)
a0.text(700, 0.80, "a run that stays below 1", color=ORANGE, fontsize=9)
a0.legend(loc="lower right", fontsize=8, frameon=False)
a0.grid(color=GRID, lw=0.6)

# B: final estimates
a1 = ax[0, 1]
a1.hist(final, bins=15, color=BLUE, edgecolor="#fcfcfb", linewidth=2, density=True)
xx = np.linspace(final.min()-0.03, final.max()+0.03, 200)
a1.plot(xx, norm.pdf(xx, 1, sd_theory[-1]), color=INK, lw=1.5, label="theory: Normal(1, %.3f)" % sd_theory[-1])
a1.axvline(1, color=INK2, lw=0.8)
a1.set_xlabel(f"estimated / true area after n = {n:,}")
a1.set_ylabel("density")
a1.set_title(f"B. Final estimates of the 100 runs: mean {final.mean():.4f}, unbiased", loc="left", fontsize=11)
a1.legend(frameon=False, fontsize=8)

# C: fraction of each run spent above 1
a2 = ax[1, 0]
a2.hist(frac_above_late, bins=10, range=(0, 1), color=BLUE, edgecolor="#fcfcfb", linewidth=2, density=True)
t = np.linspace(0.005, 0.995, 300)
a2.plot(t, 1/(np.pi*np.sqrt(t*(1-t))), color=INK, lw=1.5, label="arcsine law (theory)")
a2.set_xlabel("fraction of the run (points 100 to 10,000) where the estimate is above 1")
a2.set_ylabel("density")
a2.set_title("C. Runs tend to sit on ONE side of 1, not hop around it", loc="left", fontsize=11)
a2.legend(frameon=False, fontsize=8)

# D: the script's "skew" statistic
a3 = ax[1, 1]
a3.hist(running_skew, bins=20, color=ORANGE, edgecolor="#fcfcfb", linewidth=2)
a3.axvline(0, color=INK2, lw=0.8)
a3.set_xlabel("'Skew' printed by the script at the last point (skew of the running estimates)")
a3.set_ylabel("number of runs")
a3.set_title(f"D. The printed skew is noise: sign flips run to run ({(running_skew>0).sum()}/100 positive)", loc="left", fontsize=11)

fig.suptitle(f"Monte Carlo ellipse area: a={a}, b={b} inside a {w}×{ht} box, {n:,} points × {runs} runs  (p = E/A = {p:.3f})",
             fontsize=13, x=0.01, ha="left", color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig(OUT, dpi=140)
print("saved", OUT)
