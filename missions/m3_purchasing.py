"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing, sustainability

DAYS = 30


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []
    interruptible_kwh = 0.0
    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        if interruptible:
            interruptible_kwh += (
                num(c["watts"]) * hpd * num(j["days"]) * ngpu / 1000.0
            )
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        tier = pricing.recommend_tier(hpd, interruptible)
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od)
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
        else:
            opt_cost = on_demand_cost

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": round(on_demand_cost), "optimized": round(opt_cost)})

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0
    regional_impact = {
        region: {
            "electricity_usd": round(interruptible_kwh * price, 2),
            "carbon_kg": round(interruptible_kwh * sustainability.REGION_CARBON[region] / 1000, 2),
        }
        for region, price in sustainability.REGION_PRICE_KWH.items()
    }
    cheapest_region = min(regional_impact, key=lambda r: regional_impact[r]["electricity_usd"])
    cleanest_region = min(regional_impact, key=lambda r: regional_impact[r]["carbon_kg"])
    max_cost = max(v["electricity_usd"] for v in regional_impact.values()) or 1.0
    max_carbon = max(v["carbon_kg"] for v in regional_impact.values()) or 1.0
    balanced_region = min(
        regional_impact,
        key=lambda r: regional_impact[r]["electricity_usd"] / max_cost
        + regional_impact[r]["carbon_kg"] / max_carbon,
    )
    carbon_schedule = {
        "interruptible_energy_kwh": round(interruptible_kwh, 2),
        "regions": regional_impact,
        "cheapest_region": cheapest_region,
        "cleanest_region": cleanest_region,
        "balanced_region": balanced_region,
        "us_east_carbon_saving_kg": round(
            regional_impact["us-east-1"]["carbon_kg"]
            - regional_impact[cleanest_region]["carbon_kg"], 2
        ),
        "us_east_electricity_saving_usd": round(
            regional_impact["us-east-1"]["electricity_usd"]
            - regional_impact[cheapest_region]["electricity_usd"], 2
        ),
    }

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")
        print(f"interruptible jobs: {interruptible_kwh:.1f} kWh; "
              f"best price={cheapest_region}, cleanest={cleanest_region}, "
              f"balanced={balanced_region}")
        print(f"moving interruptible jobs from us-east-1 to {cleanest_region} "
              f"avoids {carbon_schedule['us_east_carbon_saving_kg']:.1f} kgCO2e "
              f"(electricity delta to cheapest: "
              f"${carbon_schedule['us_east_electricity_saving_usd']:.2f})")

    return {"recommendations": recs, "on_demand_monthly": round(on_demand_monthly),
            "optimized_monthly": round(optimized_monthly), "savings_pct": round(savings_pct, 1),
            "carbon_schedule": carbon_schedule}


if __name__ == "__main__":
    run()
