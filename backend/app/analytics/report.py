"""Turn an experiment's raw results into the paper's tables and figures.

    python -m app.analytics.report experiments/results/main

Writes tables (CSV + Markdown) next to the results and figures (PNG + PDF) to
experiments/figures/<name>/.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd

from app.analytics.convergence import fitness_from_penalty, generations_to_reach, mean_std_band, stack_histories
from app.analytics.experiment_runner import PROJECT_ROOT, sweep_config_name
from app.analytics.statistics import cliffs_delta, improvement_percent, mann_whitney_less, summarize

LABELS = {
    "ga": "Genetic algorithm",
    "greedy": "Greedy (first-fit)",
    "greedy_cost_aware": "Greedy (cost-aware)",
    "randomized_greedy": "Randomized greedy",
    "random_feasible": "Random",
}
COLORS = {  # Okabe-Ito, colour-blind safe
    "ga": "#0072B2",
    "greedy": "#7F7F7F",
    "greedy_cost_aware": "#E69F00",
    "randomized_greedy": "#009E73",
    "random_feasible": "#D55E00",
}
METHOD_ORDER = ["greedy", "greedy_cost_aware", "randomized_greedy", "random_feasible"]


def _style() -> None:
    plt.rcParams.update({
        "figure.dpi": 120, "savefig.dpi": 200, "savefig.bbox": "tight", "font.size": 9.5,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
        "grid.color": "#E6E6E6", "grid.linewidth": 0.7, "axes.axisbelow": True,
        "axes.titlesize": 10.5, "axes.titleweight": "bold", "legend.frameon": False,
        "axes.edgecolor": "#555555", "xtick.color": "#333333", "ytick.color": "#333333",
    })


def _save(fig, figures: Path, name: str) -> None:
    figures.mkdir(parents=True, exist_ok=True)
    fig.savefig(figures / f"{name}.png")
    fig.savefig(figures / f"{name}.pdf")
    plt.close(fig)


def _markdown(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def _write_table(df: pd.DataFrame, tables: Path, name: str) -> None:
    tables.mkdir(parents=True, exist_ok=True)
    df.to_csv(tables / f"{name}.csv", index=False)
    (tables / f"{name}.md").write_text(_markdown(df), encoding="utf-8")


def _fmt(x: float, digits: int = 0) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:,.{digits}f}"


def _fmt_p(p: float | None) -> str:
    if p is None:
        return "—"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


# --- tables ------------------------------------------------------------------------------------
def comparison_table(runs: pd.DataFrame, dataset: str, config: str = "default") -> pd.DataFrame:
    """GA vs every baseline on one dataset: descriptive stats, improvement %, significance."""
    d = runs[runs["dataset"] == dataset]
    ga = d[(d["method"] == "ga") & (d["config"] == config)]
    ga_pen = ga["final_penalty"].to_numpy()
    rows = []

    def row(label: str, frame: pd.DataFrame, is_ga: bool) -> dict:
        pen = frame["final_penalty"].to_numpy()
        s = summarize(pen)
        valid = frame[frame["valid"]]
        out = {
            "Method": label, "Runs": len(frame), "Feasible": f"{len(valid)}/{len(frame)}",
            "Mean": _fmt(s["mean"]), "Median": _fmt(s["median"]), "Std": _fmt(s["std"]),
            "Min": _fmt(s["min"]), "Max": _fmt(s["max"]),
            "Hard viol. (mean)": _fmt(frame["hard_violations"].mean(), 1),
            "Runtime s (mean)": _fmt(frame["runtime_seconds"].mean(), 2),
            "GA improvement %": "—", "p (GA < method)": "—", "Cliff's δ": "—",
        }
        if not is_ga and len(valid):
            imp = improvement_percent(float(valid["final_penalty"].mean()), float(ga_pen.mean()))
            out["GA improvement %"] = _fmt(imp, 1) if imp is not None else "n/a"
            mw = mann_whitney_less(ga_pen, valid["final_penalty"].to_numpy())
            if mw:
                out["p (GA < method)"] = _fmt_p(mw["p"])
                out["Cliff's δ"] = f"{cliffs_delta(ga_pen, valid['final_penalty'].to_numpy()):.2f}"
        elif not is_ga:
            out["GA improvement %"] = "n/a (infeasible)"
        return out

    if len(ga):
        rows.append(row(LABELS["ga"], ga, True))
    for m in METHOD_ORDER:
        frame = d[d["method"] == m]
        if len(frame):
            rows.append(row(LABELS[m], frame, False))
    return pd.DataFrame(rows)


def config_table(runs: pd.DataFrame, dataset: str, configs: list[tuple[str, str]]) -> pd.DataFrame:
    """Rows for (label, config name) pairs of GA runs on one dataset."""
    d = runs[(runs["dataset"] == dataset) & (runs["method"] == "ga")]
    rows = []
    for label, config in configs:
        frame = d[d["config"] == config]
        if frame.empty:
            continue
        s = summarize(frame["final_penalty"].to_numpy())
        rows.append({
            "Setting": label, "Runs": len(frame), "Feasible": f"{int(frame['valid'].sum())}/{len(frame)}",
            "Mean": _fmt(s["mean"]), "Median": _fmt(s["median"]), "Std": _fmt(s["std"]),
            "Min": _fmt(s["min"]), "Max": _fmt(s["max"]),
            "Runtime s (mean)": _fmt(frame["runtime_seconds"].mean(), 2),
        })
    return pd.DataFrame(rows)


# --- figures -----------------------------------------------------------------------------------
def fig_convergence(histories: dict, runs: pd.DataFrame, dataset: str, config: str, figures: Path) -> None:
    per_seed = histories[dataset][config]
    best = stack_histories(per_seed, "best")
    gens = np.arange(best.shape[1])
    mean, std = mean_std_band(best)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.2, 3.5))
    for curve in best:
        ax1.plot(gens, curve, color=COLORS["ga"], alpha=0.12, lw=0.8)
    ax1.fill_between(gens, mean - std, mean + std, color=COLORS["ga"], alpha=0.18, lw=0)
    ax1.plot(gens, mean, color=COLORS["ga"], lw=2, label=f"GA mean of {best.shape[0]} runs")
    d = runs[runs["dataset"] == dataset]
    for m in ("greedy", "greedy_cost_aware"):
        frame = d[(d["method"] == m) & d["valid"]]
        if len(frame):
            ax1.axhline(frame["final_penalty"].mean(), color=COLORS[m], ls="--", lw=1.2, label=LABELS[m])
    ax1.set_yscale("log")
    ax1.set(xlabel="Generation", ylabel="Best penalty (log scale)", title="Penalty vs generation")
    ax1.legend(fontsize=8, loc="center right")

    fit = fitness_from_penalty(best)
    fmean, fstd = mean_std_band(fit)
    ax2.fill_between(gens, fmean - fstd, fmean + fstd, color=COLORS["ga"], alpha=0.18, lw=0)
    ax2.plot(gens, fmean, color=COLORS["ga"], lw=2)
    ax2.set(xlabel="Generation", ylabel="Best fitness  1 / (1 + penalty)", title="Fitness vs generation")
    ax2.ticklabel_format(axis="y", style="sci", scilimits=(-3, 3))
    fig.tight_layout()
    _save(fig, figures, f"convergence_{dataset}")


def fig_baseline_bars(runs: pd.DataFrame, dataset: str, config: str, figures: Path) -> None:
    d = runs[(runs["dataset"] == dataset) & runs["valid"]]
    entries = [(m, d[d["method"] == m]["final_penalty"].to_numpy()) for m in METHOD_ORDER[:3]]
    entries.append(("ga", d[(d["method"] == "ga") & (d["config"] == config)]["final_penalty"].to_numpy()))
    entries = [(m, v) for m, v in entries if len(v)]
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    x = np.arange(len(entries))
    means = [v.mean() for _, v in entries]
    errs = [v.std(ddof=1) if len(v) > 1 else 0 for _, v in entries]
    ax.bar(x, means, yerr=errs, capsize=4, color=[COLORS[m] for m, _ in entries], width=0.62,
           error_kw={"elinewidth": 1, "ecolor": "#333333"})
    top = max(m + e for m, e in zip(means, errs)) * 1.12
    for xi, mean, err in zip(x, means, errs):
        ax.text(xi, mean + err + top * 0.015, f"{mean:,.0f}", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(x, [LABELS[m].replace(" (", "\n(").replace("Genetic ", "Genetic\n") for m, _ in entries])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set(ylabel="Final penalty (mean ± std)", title="Baselines vs genetic algorithm (lower is better)")
    ax.set_ylim(0, top * 1.08)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    _save(fig, figures, f"baseline_vs_ga_{dataset}")


def fig_distribution(runs: pd.DataFrame, dataset: str, config: str, figures: Path) -> None:
    d = runs[(runs["dataset"] == dataset) & runs["valid"]]
    groups = [("ga", d[(d["method"] == "ga") & (d["config"] == config)]["final_penalty"].to_numpy())]
    groups.append(("randomized_greedy", d[d["method"] == "randomized_greedy"]["final_penalty"].to_numpy()))
    groups = [(m, v) for m, v in groups if len(v)]
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    bp = ax.boxplot([v for _, v in groups], tick_labels=[LABELS[m] for m, _ in groups], widths=0.5,
                    patch_artist=True, medianprops={"color": "#222222", "lw": 1.6},
                    flierprops={"marker": "o", "markersize": 3})
    rng = np.random.default_rng(0)
    for patch, (m, v) in zip(bp["boxes"], groups):
        patch.set(facecolor=COLORS[m], alpha=0.35, edgecolor=COLORS[m])
    for i, (m, v) in enumerate(groups, 1):
        ax.scatter(i + rng.uniform(-0.1, 0.1, len(v)), v, s=14, color=COLORS[m], zorder=3)
    for m in ("greedy", "greedy_cost_aware"):
        frame = d[d["method"] == m]
        if len(frame):
            ax.axhline(frame["final_penalty"].iloc[0], color=COLORS[m], ls="--", lw=1.2, label=LABELS[m])
    ax.set_yscale("log")
    ax.set(ylabel="Final penalty (log scale)", title="Penalty distribution across seeds")
    ax.legend(fontsize=8, loc="center right")
    fig.tight_layout()
    _save(fig, figures, f"penalty_boxplot_{dataset}")


def fig_sensitivity(runs: pd.DataFrame, meta: dict, dataset: str, figures: Path) -> pd.DataFrame:
    base = meta["base_params"]
    d = runs[(runs["dataset"] == dataset) & (runs["method"] == "ga")]
    sweep = meta["sweep"]
    fig, axes = plt.subplots(1, len(sweep), figsize=(3.1 * len(sweep), 3.3), sharey=True)
    axes = np.atleast_1d(axes)
    rows = []
    titles = {"population_size": "Population size", "mutation_rate": "Mutation rate",
              "crossover_rate": "Crossover rate", "generations": "Generations"}
    for ax, (param, values) in zip(axes, sweep.items()):
        xs, ms, ss = [], [], []
        for value in values:
            config = "default" if value == base.get(param) else sweep_config_name(param, value)
            frame = d[d["config"] == config]
            if frame.empty:
                continue
            pen = frame["final_penalty"].to_numpy()
            s = summarize(pen)
            xs.append(value); ms.append(s["mean"]); ss.append(s["std"])
            rows.append({
                "Parameter": param, "Value": value, "Runs": len(frame),
                "Feasible": f"{int(frame['valid'].sum())}/{len(frame)}", "Mean": _fmt(s["mean"]),
                "Median": _fmt(s["median"]), "Std": _fmt(s["std"]), "Min": _fmt(s["min"]), "Max": _fmt(s["max"]),
                "Runtime s (mean)": _fmt(frame["runtime_seconds"].mean(), 1),
            })
            ax.scatter([value] * len(pen), pen, s=9, color=COLORS["ga"], alpha=0.25, zorder=2)
        ms, ss = np.array(ms), np.array(ss)
        ax.errorbar(xs, ms, yerr=ss, color=COLORS["ga"], marker="o", ms=5, lw=1.8, capsize=3, zorder=3)
        ax.axvline(base.get(param), color="#999999", ls=":", lw=1)
        ax.set(xlabel=titles.get(param, param), xticks=xs)
        ax.tick_params(axis="x", labelsize=8)
    axes[0].set_ylabel("Final penalty (mean ± std)")
    fig.suptitle("Parameter sensitivity (dotted line = default)", fontsize=10.5, fontweight="bold", y=1.02)
    fig.tight_layout()
    _save(fig, figures, f"sensitivity_{dataset}")
    return pd.DataFrame(rows)


def fig_ablation(runs: pd.DataFrame, dataset: str, configs: list[str], figures: Path) -> None:
    d = runs[(runs["dataset"] == dataset) & (runs["method"] == "ga")]
    data = [(c, d[d["config"] == c]["final_penalty"].to_numpy()) for c in configs]
    data = [(c, v) for c, v in data if len(v)]
    order = sorted(data, key=lambda t: np.median(t[1]))
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    bp = ax.boxplot([v for _, v in order], tick_labels=[c.replace("_", "\n") for c, _ in order], widths=0.55,
                    patch_artist=True, medianprops={"color": "#222222", "lw": 1.5}, flierprops={"markersize": 3})
    for patch, (c, _) in zip(bp["boxes"], order):
        color = COLORS["ga"] if c == "default" else "#999999"
        patch.set(facecolor=color, alpha=0.35, edgecolor=color)
    ax.set_yscale("log")
    ax.set(ylabel="Final penalty (log scale)", title="Ablation: contribution of each GA component")
    ax.tick_params(axis="x", labelsize=8)
    fig.tight_layout()
    _save(fig, figures, f"ablation_{dataset}")


def fig_scaling(runs: pd.DataFrame, datasets: list[str], config: str, figures: Path) -> pd.DataFrame:
    rows = []
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.6, 3.5))
    methods = ["greedy", "greedy_cost_aware", "randomized_greedy", "ga"]
    width = 0.2
    for k, m in enumerate(methods):
        means, errs = [], []
        for ds in datasets:
            d = runs[(runs["dataset"] == ds) & runs["valid"]]
            f = d[(d["method"] == "ga") & (d["config"] == config)] if m == "ga" else d[d["method"] == m]
            pen = f["final_penalty"].to_numpy()
            means.append(pen.mean() if len(pen) else np.nan)
            errs.append(pen.std(ddof=1) if len(pen) > 1 else 0)
        ax1.bar(np.arange(len(datasets)) + (k - 1.5) * width, means, width, yerr=errs, capsize=2.5,
                color=COLORS[m], label=LABELS[m], error_kw={"elinewidth": 0.9})
    ax1.set_yscale("log")
    ax1.set_xticks(np.arange(len(datasets)), datasets)
    ax1.set(ylabel="Final penalty (log scale)", title="Solution quality by problem size")
    ax1.legend(fontsize=7.5, ncol=2, loc="upper left")
    ax1.grid(axis="x", visible=False)

    sizes, runtimes, rt_err = [], [], []
    for ds in datasets:
        frame = runs[(runs["dataset"] == ds) & (runs["method"] == "ga") & (runs["config"] == config)]
        sizes.append(ds)
        runtimes.append(frame["runtime_seconds"].mean())
        rt_err.append(frame["runtime_seconds"].std(ddof=1) if len(frame) > 1 else 0)
        rows.append({"Dataset": ds, "GA runtime s (mean)": _fmt(frame["runtime_seconds"].mean(), 1),
                     "GA runtime s (max)": _fmt(frame["runtime_seconds"].max(), 1),
                     "Feasible": f"{int(frame['valid'].sum())}/{len(frame)}"})
    ax2.errorbar(sizes, runtimes, yerr=rt_err, marker="o", color=COLORS["ga"], lw=1.8, capsize=3)
    ax2.set(ylabel="GA runtime (s)", title="Runtime by problem size")
    fig.tight_layout()
    _save(fig, figures, "scaling")
    return pd.DataFrame(rows)


# --- orchestration -----------------------------------------------------------------------------
def build_report(results_dir: str | Path, figures_dir: str | Path | None = None) -> dict[str, list[str]]:
    results = Path(results_dir)
    if not results.is_absolute() and not results.exists():
        results = PROJECT_ROOT / results
    meta = json.loads((results / "meta.json").read_text(encoding="utf-8"))
    runs = pd.read_csv(results / "runs.csv")
    histories = json.loads((results / "histories.json").read_text(encoding="utf-8"))
    figures = Path(figures_dir) if figures_dir else PROJECT_ROOT / "experiments" / "figures" / meta["name"]
    tables = results / "tables"
    _style()
    made: dict[str, list[str]] = {"tables": [], "figures": []}

    datasets = list(dict.fromkeys(runs["dataset"]))
    ga_configs = list(dict.fromkeys(runs[runs["method"] == "ga"]["config"]))
    main_config = "default" if "default" in ga_configs else (ga_configs[0] if ga_configs else None)
    has_baselines = bool(meta.get("baselines"))

    for ds in datasets:
        if main_config and has_baselines:
            _write_table(comparison_table(runs, ds, main_config), tables, f"comparison_{ds}")
            made["tables"].append(f"comparison_{ds}")
            fig_baseline_bars(runs, ds, main_config, figures)
            fig_distribution(runs, ds, main_config, figures)
            made["figures"] += [f"baseline_vs_ga_{ds}", f"penalty_boxplot_{ds}"]
        if main_config and ds in histories and main_config in histories[ds]:
            fig_convergence(histories, runs, ds, main_config, figures)
            made["figures"].append(f"convergence_{ds}")
            best = stack_histories(histories[ds][main_config], "best")
            mean, _ = mean_std_band(best)
            print(f"[{ds}] mean best penalty: gen0={mean[0]:,.0f} -> final={mean[-1]:,.0f}; "
                  f"95% of the improvement by generation {generations_to_reach(mean)}")

    if meta.get("sweep"):
        ds = datasets[0]
        _write_table(fig_sensitivity(runs, meta, ds, figures), tables, f"sensitivity_{ds}")
        made["tables"].append(f"sensitivity_{ds}")
        made["figures"].append(f"sensitivity_{ds}")
    elif len(ga_configs) > 1 and len(datasets) == 1:
        ds = datasets[0]
        _write_table(config_table(runs, ds, [(c, c) for c in ga_configs]), tables, f"configs_{ds}")
        fig_ablation(runs, ds, ga_configs, figures)
        made["tables"].append(f"configs_{ds}")
        made["figures"].append(f"ablation_{ds}")
    if len(datasets) > 1 and main_config:
        _write_table(fig_scaling(runs, datasets, main_config, figures), tables, "scaling")
        made["tables"].append("scaling")
        made["figures"].append("scaling")
    return made


def main() -> None:
    parser = argparse.ArgumentParser(description="Build tables and figures from an experiment's results.")
    parser.add_argument("results_dir", help="e.g. experiments/results/main")
    parser.add_argument("--figures", help="output directory for figures")
    args = parser.parse_args()
    made = build_report(args.results_dir, args.figures)
    print("tables :", ", ".join(made["tables"]) or "-")
    print("figures:", ", ".join(made["figures"]) or "-")


if __name__ == "__main__":
    main()
