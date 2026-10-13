"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly",
                 analysis: dict | None = None) -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}",
        f"**Baseline spend:** ${baseline_usd:,.0f}",
        f"**Optimized spend:** ${optimized_usd:,.0f}",
        f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Electricity cost per query: ${sustainability.get('electricity_usd', 0):.8f}",
            f"- Cleanest region: {sustainability.get('best_region', 'n/a')}",
        ]
    if analysis:
        inference = analysis.get("inference", {})
        if inference:
            lines += [
                "",
                "## Inference unit economics and lever attribution",
                "",
                "| Measure | Baseline | Optimized |",
                "|---|---:|---:|",
                f"| Spend per day | ${inference.get('baseline_daily', 0):,.2f} | ${inference.get('optimized_daily', 0):,.2f} |",
                f"| Cost per 1M tokens | ${inference.get('baseline_per_m', 0):.3f} | ${inference.get('optimized_per_m', 0):.3f} |",
                "",
                "Inference savings by sequentially applied lever (monthly):",
                "",
                "| Lever | Savings (USD/month) |",
                "|---|---:|",
            ]
            for name, amount in inference.get("lever_savings_daily", {}).items():
                lines.append(f"| {name.title()} | ${amount * 30:,.2f} |")
            lines += [
                "",
                f"Cache write premiums are amortized in optimized spend "
                f"(${inference.get('cache_write_cost_daily', 0):.4f}/day). Caching is enabled "
                "only when observed reads per shared prompt prefix exceed the modeled break-even "
                "(write premium / cached-read saving).",
                "",
                "| Model tier | Observed reads/prefix | Break-even reads | Cache policy |",
                "|---|---:|---:|---|",
            ]
            for tier, data in inference.get("cache_economics", {}).items():
                lines.append(
                    f"| {tier} | {data['avg_reads']:.1f} | {data['break_even_reads']:.2f} | "
                    f"{'enabled' if data['worth_it'] else 'disabled'} |"
                )
            reasoning = inference.get("reasoning", {})
            lines += [
                "",
                "### Reasoning budget",
                "",
                f"Reasoning represents {reasoning.get('traffic_pct', 0):.2f}% of requests, "
                f"{reasoning.get('cost_pct', 0):.2f}% of optimized inference spend, and "
                f"{reasoning.get('energy_pct', 0):.2f}% of modeled inference energy "
                f"({reasoning.get('energy_wh', 0):,.2f} Wh/day).",
                f"A 10% traffic cap would save ${reasoning.get('cap_10_savings_usd', 0):,.2f}/day "
                f"and {reasoning.get('cap_10_savings_wh', 0):,.2f} Wh/day under this dataset; "
                "it is a ceiling, not a mandate to increase reasoning traffic.",
                "",
                "## Carbon-aware scheduling extension",
                "",
            ]
            carbon = analysis.get("carbon_schedule", {})
            lines += [
                f"Interruptible workloads use {carbon.get('interruptible_energy_kwh', 0):,.2f} kWh "
                "in the modeled period.",
                f"Moving them from us-east-1 to the cleanest region avoids "
                f"{carbon.get('us_east_carbon_saving_kg', 0):,.2f} kgCO2e; moving to the "
                f"cheapest-electricity region saves "
                f"${carbon.get('us_east_electricity_saving_usd', 0):,.2f} in electricity. "
                "These electricity costs are separate from GPU rental charges.",
                "",
                "| Region | Electricity (USD) | Carbon (kgCO2e) |",
                "|---|---:|---:|",
            ]
            for region, values in carbon.get("regions", {}).items():
                lines.append(
                    f"| {region} | ${values['electricity_usd']:,.2f} | {values['carbon_kg']:,.2f} |"
                )
            lines += [
                "",
                f"Cheapest: **{carbon.get('cheapest_region', 'n/a')}**; cleanest: "
                f"**{carbon.get('cleanest_region', 'n/a')}**; equal-weight cost/carbon choice: "
                f"**{carbon.get('balanced_region', 'n/a')}**. Validate latency and data-residency "
                "constraints before moving production jobs.",
                "",
                "## Interpretation and actions",
                "",
                "1. Start with purchasing commitments: this is the largest measured monthly lever. "
                "Keep only stable, high-duty-cycle demand reserved; checkpoint interruptible training "
                "for spot capacity.",
                "2. Route easy requests to the small model and use batch for deferrable jobs; "
                "the inference unit metric falls because savings are measured per token, not per GPU-hour.",
                "3. Investigate high-util/low-MFU GPUs before buying more capacity. Memory stalls, "
                "small kernels, synchronization, or launch overhead can keep a device active while "
                "tensor throughput remains low.",
                "4. Shut down scheduled idle capacity and move only latency-tolerant training to "
                "cleaner/cheaper regions after a latency and data-residency review.",
            ]
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str) -> str:
    """Write a cumulative savings waterfall PNG. Returns the path."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers.keys())
    vals = [levers[n] for n in names]
    fig, ax = plt.subplots(figsize=(10, 5))
    cumulative = 0.0
    for name, value in zip(names, vals):
        ax.bar(name, value, bottom=cumulative, color="#2e548a")
        ax.text(name, cumulative + value, f"${value:,.0f}", ha="center", va="bottom", fontsize=8)
        cumulative += value
    ax.bar("Total savings", cumulative, color="#1b7f5a")
    ax.text("Total savings", cumulative, f"${cumulative:,.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("Savings (USD / month)")
    ax.set_title("GPU cost savings waterfall by FinOps lever")
    plt.xticks(rotation=20, ha="right")
    ax.set_ylim(0, cumulative * 1.18 if cumulative > 0 else 1)
    ax.grid(axis="y", alpha=0.2)
    plt.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
