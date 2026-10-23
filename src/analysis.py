"""Cookie Cats A/B test: full experiment readout.

Moving the first progression gate from level 30 (control, gate_30) to level 40
(treatment, gate_40). Reproduces every number in the README.

Run:  python src/analysis.py
Writes results/results.json, results/summary.md and figures/*.png
"""
from __future__ import annotations

import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import (confint_proportions_2indep,
                                          proportion_effectsize,
                                          proportions_ztest)

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "cookie_cats.csv"
FIG = ROOT / "figures"
RES = ROOT / "results"
SEED = 42
N_BOOT = 10_000
ALPHA = 0.05
CONTROL, TREATMENT = "gate_30", "gate_40"
OUTLIER_CUTOFF = 10_000  # one player logged 49,854 rounds in 14 days

plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False,
                     "axes.spines.right": False, "font.size": 10})
COLORS = {CONTROL: "#4C72B0", TREATMENT: "#DD8452"}


def load() -> pd.DataFrame:
    df = pd.read_csv(DATA)
    assert df["userid"].is_unique, "duplicate users"
    assert set(df["version"]) == {CONTROL, TREATMENT}
    assert df.isna().sum().sum() == 0
    df["retention_1"] = df["retention_1"].astype(int)
    df["retention_7"] = df["retention_7"].astype(int)
    return df


def srm_check(df: pd.DataFrame) -> dict:
    counts = df["version"].value_counts().reindex([CONTROL, TREATMENT])
    expected = [len(df) / 2] * 2
    chi2, p = stats.chisquare(counts.values, f_exp=expected)
    return {"n_control": int(counts[CONTROL]), "n_treatment": int(counts[TREATMENT]),
            "share_treatment": float(counts[TREATMENT] / len(df)),
            "chi2": float(chi2), "p_value": float(p)}


def two_prop_test(df: pd.DataFrame, metric: str) -> dict:
    g = df.groupby("version")[metric].agg(["sum", "count"]).reindex([CONTROL, TREATMENT])
    x_c, n_c = int(g.loc[CONTROL, "sum"]), int(g.loc[CONTROL, "count"])
    x_t, n_t = int(g.loc[TREATMENT, "sum"]), int(g.loc[TREATMENT, "count"])
    p_c, p_t = x_c / n_c, x_t / n_t
    z, p = proportions_ztest([x_t, x_c], [n_t, n_c], alternative="two-sided")
    lo, hi = confint_proportions_2indep(x_t, n_t, x_c, n_c, method="wald", compare="diff",
                                        alpha=ALPHA)
    return {"metric": metric, "rate_control": p_c, "rate_treatment": p_t,
            "diff_pp": (p_t - p_c) * 100, "rel_lift_pct": (p_t / p_c - 1) * 100,
            "z": float(z), "p_value": float(p),
            "ci95_diff_pp": [float(lo) * 100, float(hi) * 100]}


def bootstrap_diff(a: np.ndarray, b: np.ndarray, stat=np.mean, n=N_BOOT, seed=SEED):
    """Bootstrap distribution of stat(b) - stat(a)."""
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    for i in range(n):
        out[i] = stat(rng.choice(b, b.size)) - stat(rng.choice(a, a.size))
    return out


def bootstrap_rates(df: pd.DataFrame, metric: str) -> dict:
    a = df.loc[df.version == CONTROL, metric].to_numpy()
    b = df.loc[df.version == TREATMENT, metric].to_numpy()
    # Binary metric: resampling a Bernoulli vector == drawing binomial counts.
    rng = np.random.default_rng(SEED)
    pa = rng.binomial(a.size, a.mean(), N_BOOT) / a.size
    pb = rng.binomial(b.size, b.mean(), N_BOOT) / b.size
    diff = (pb - pa) * 100
    return {"metric": metric, "boot_ci95_diff_pp": np.percentile(diff, [2.5, 97.5]).tolist(),
            "prob_control_better": float((diff < 0).mean()), "_dist": diff}


def engagement(df: pd.DataFrame) -> dict:
    clean = df[df.sum_gamerounds <= OUTLIER_CUTOFF]
    a = clean.loc[clean.version == CONTROL, "sum_gamerounds"].to_numpy()
    b = clean.loc[clean.version == TREATMENT, "sum_gamerounds"].to_numpy()
    u, p_mw = stats.mannwhitneyu(b, a, alternative="two-sided")
    t, p_welch = stats.ttest_ind(b, a, equal_var=False)
    mean_diff = bootstrap_diff(a, b, np.mean, n=5_000)
    med_diff = bootstrap_diff(a, b, np.median, n=2_000)
    # winsorized at p99 as a second outlier treatment
    cap = np.percentile(clean.sum_gamerounds, 99)
    aw, bw = np.minimum(a, cap), np.minimum(b, cap)
    return {
        "outliers_removed": int((df.sum_gamerounds > OUTLIER_CUTOFF).sum()),
        "outlier_value": int(df.sum_gamerounds.max()),
        "mean_control": float(a.mean()), "mean_treatment": float(b.mean()),
        "median_control": float(np.median(a)), "median_treatment": float(np.median(b)),
        "mann_whitney_U": float(u), "mann_whitney_p": float(p_mw),
        "welch_t": float(t), "welch_p": float(p_welch),
        "boot_ci95_mean_diff": np.percentile(mean_diff, [2.5, 97.5]).tolist(),
        "boot_ci95_median_diff": np.percentile(med_diff, [2.5, 97.5]).tolist(),
        "winsor_p99_cap": float(cap),
        "winsor_mean_control": float(aw.mean()), "winsor_mean_treatment": float(bw.mean()),
        "winsor_welch_p": float(stats.ttest_ind(bw, aw, equal_var=False).pvalue),
    }


def power_mde(df: pd.DataFrame, metric: str, observed: dict) -> dict:
    n_c = int((df.version == CONTROL).sum())
    n_t = int((df.version == TREATMENT).sum())
    p_c = observed["rate_control"]
    analysis = NormalIndPower()
    ratio = n_t / n_c
    # MDE at 80% power: solve for Cohen's h, then map back to a rate
    h = analysis.solve_power(effect_size=None, nobs1=n_c, alpha=ALPHA, power=0.8,
                             ratio=ratio, alternative="two-sided")
    p_t_mde = np.sin(np.arcsin(np.sqrt(p_c)) - h / 2) ** 2  # detectable drop
    mde_pp = abs(p_c - p_t_mde) * 100
    obs_h = abs(proportion_effectsize(observed["rate_treatment"], p_c))
    achieved = analysis.power(effect_size=obs_h, nobs1=n_c, alpha=ALPHA, ratio=ratio,
                              alternative="two-sided")
    # sample size per arm needed to detect a 1pp absolute change at 80% power
    h1 = abs(proportion_effectsize(p_c - 0.01, p_c))
    n_1pp = analysis.solve_power(effect_size=h1, alpha=ALPHA, power=0.8, ratio=1.0)
    return {"metric": metric, "mde_pp_80power": float(mde_pp),
            "mde_rel_pct": float(mde_pp / (p_c * 100) * 100),
            "power_at_observed_effect": float(achieved),
            "n_per_arm_for_1pp": int(np.ceil(n_1pp))}


# ----------------------------------------------------------------- figures
def fig_retention(tests: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    for ax, m, title in zip(axes, ["retention_1", "retention_7"],
                            ["Day-1 retention (guardrail)", "Day-7 retention (primary)"]):
        r = tests[m]
        rates = [r["rate_control"] * 100, r["rate_treatment"] * 100]
        bars = ax.bar([CONTROL, TREATMENT], rates, color=[COLORS[CONTROL], COLORS[TREATMENT]])
        for bar, v in zip(bars, rates):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 0.3, f"{v:.2f}%", ha="center")
        ax.set_ylim(0, max(rates) * 1.18)
        ax.set_title(f"{title}\nΔ = {r['diff_pp']:+.2f} pp, p = {r['p_value']:.4f}")
        ax.set_ylabel("% of players retained")
    fig.tight_layout()
    fig.savefig(FIG / "retention_by_variant.png")
    plt.close(fig)


def fig_bootstrap(boots: dict, tests: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    for ax, m, title in zip(axes, ["retention_1", "retention_7"], ["Day-1", "Day-7"]):
        d = boots[m]["_dist"]
        lo, hi = boots[m]["boot_ci95_diff_pp"]
        ax.hist(d, bins=60, color="#8172B2", alpha=0.85)
        ax.axvline(0, color="black", lw=1)
        ax.axvline(lo, color="crimson", ls="--", lw=1)
        ax.axvline(hi, color="crimson", ls="--", lw=1)
        ax.set_title(f"{title} retention: gate_40 − gate_30\n95% CI [{lo:.2f}, {hi:.2f}] pp")
        ax.set_xlabel("Difference (percentage points)")
    axes[0].set_ylabel(f"Bootstrap samples (n={N_BOOT:,})")
    fig.tight_layout()
    fig.savefig(FIG / "bootstrap_retention_diff.png")
    plt.close(fig)


def fig_engagement(df: pd.DataFrame) -> None:
    clean = df[df.sum_gamerounds <= OUTLIER_CUTOFF]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    bins = np.arange(0, 201, 5)
    for v in [CONTROL, TREATMENT]:
        axes[0].hist(clean.loc[clean.version == v, "sum_gamerounds"].clip(upper=200), bins=bins,
                     alpha=0.55, label=v, color=COLORS[v])
    axes[0].set_title("Game rounds in first 14 days (clipped at 200)")
    axes[0].set_xlabel("sum_gamerounds")
    axes[0].set_ylabel("Players")
    axes[0].legend()
    # retention-7 curve by rounds played (descriptive, post-treatment)
    for v in [CONTROL, TREATMENT]:
        s = clean[clean.version == v]
        b = pd.cut(s.sum_gamerounds, bins=np.arange(0, 105, 5), right=False)
        curve = s.groupby(b, observed=True)["retention_7"].mean() * 100
        axes[1].plot([i.left for i in curve.index], curve.values, marker="o", ms=3,
                     label=v, color=COLORS[v])
    for g in (30, 40):
        axes[1].axvline(g, color="grey", ls=":", lw=1)
    axes[1].set_title("Day-7 retention by rounds played (descriptive)")
    axes[1].set_xlabel("sum_gamerounds (5-round bins)")
    axes[1].set_ylabel("% retained at day 7")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(FIG / "engagement.png")
    plt.close(fig)


def fig_power(df: pd.DataFrame, tests: dict) -> None:
    p_c = tests["retention_7"]["rate_control"]
    analysis = NormalIndPower()
    effects = np.linspace(0.1, 2.0, 60)
    n_c = int((df.version == CONTROL).sum())
    ratio = int((df.version == TREATMENT).sum()) / n_c
    powers = [analysis.power(abs(proportion_effectsize(p_c - e / 100, p_c)), n_c, ALPHA,
                             ratio=ratio) for e in effects]
    obs = abs(tests["retention_7"]["diff_pp"])
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.plot(effects, np.array(powers) * 100, color="#55A868")
    ax.axhline(80, color="grey", ls="--", lw=1)
    ax.axvline(obs, color="crimson", ls=":", lw=1.2, label=f"observed |Δ| = {obs:.2f} pp")
    ax.set_xlabel("True absolute drop in day-7 retention (pp)")
    ax.set_ylabel("Power (%)")
    ax.set_title(f"Power curve at the observed sample size (n≈{n_c:,} per arm, α=0.05)")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "power_curve.png")
    plt.close(fig)


def main() -> None:
    FIG.mkdir(exist_ok=True)
    RES.mkdir(exist_ok=True)
    df = load()
    srm = srm_check(df)
    tests = {m: two_prop_test(df, m) for m in ["retention_1", "retention_7"]}
    boots = {m: bootstrap_rates(df, m) for m in ["retention_1", "retention_7"]}
    eng = engagement(df)
    power = {m: power_mde(df, m, tests[m]) for m in ["retention_1", "retention_7"]}

    fig_retention(tests)
    fig_bootstrap(boots, tests)
    fig_engagement(df)
    fig_power(df, tests)

    out = {"n_players": len(df), "srm": srm, "two_proportion_tests": tests,
           "bootstrap": {m: {k: v for k, v in b.items() if k != "_dist"}
                         for m, b in boots.items()},
           "engagement": eng, "power": power}
    (RES / "results.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
