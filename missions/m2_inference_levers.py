"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing
from finops import sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    prefix_reads = {}
    prefix_cached_tokens = {}
    for r in rows:
        prefix = r.get("cache_prefix_id", "")
        if prefix:
            key = (r["route_tier"], prefix)
            prefix_reads[key] = int(num(r.get("cache_prefix_reads", 0)))
            prefix_cached_tokens.setdefault(key, []).append(int(num(r["cached_input_tokens"])))
    cache_economics = {}
    for tier in MODEL_PRICES:
        reads = [count for (row_tier, _), count in prefix_reads.items() if row_tier == tier]
        avg_reads = sum(reads) / len(reads) if reads else 0.0
        cache_economics[tier] = {
            "avg_reads": round(avg_reads, 1),
            "break_even_reads": round(pricing.cache_break_even_reads(), 2),
            "worth_it": pricing.cache_is_worth_it(avg_reads),
        }

    base_cost = cascade_cost = cache_cost = opt_cost = 0.0
    cache_write_cost = 0.0
    for (tier, _), token_samples in prefix_cached_tokens.items():
        input_price = MODEL_PRICES[tier][0]
        avg_prefix_tokens = sum(token_samples) / len(token_samples)
        cache_write_cost += avg_prefix_tokens / 1e6 * input_price * 1.25
    total_tokens = 0
    reasoning_cost = non_reasoning_cost = 0.0
    reasoning_wh = non_reasoning_wh = 0.0
    reasoning_requests = 0
    cap_10_savings_usd = cap_10_savings_wh = 0.0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # Measure cascade, cache, and batch independently in a fixed sequence.
        pin, pout = MODEL_PRICES[r["route_tier"]]
        cascade_cost += pricing.request_cost(inp, out, pin, pout)
        cache_allowed = cache_economics[r["route_tier"]]["worth_it"]
        cached_in = cached if cache_allowed else 0
        request_cached_cost = pricing.request_cost(inp, out, pin, pout, cached_in=cached_in)
        cache_cost += request_cached_cost
        request_opt_cost = pricing.request_cost(
            inp, out, pin, pout, cached_in=cached_in, batch=is_batch
        )
        opt_cost += request_opt_cost

        energy = sustainability.wh_per_query(inp + out, is_reasoning=is_reasoning)
        if is_reasoning:
            reasoning_requests += 1
            reasoning_cost += request_opt_cost
            reasoning_wh += energy
            # A normal route uses the same prompt and one-sixth of the generated output.
            standard_cost = pricing.request_cost(
                inp, out / 6, pin, pout, cached_in=cached_in, batch=is_batch
            )
            cap_10_savings_usd += request_opt_cost - standard_cost
            cap_10_savings_wh += energy - sustainability.wh_per_query(inp + out / 6)
        else:
            non_reasoning_cost += request_opt_cost
            non_reasoning_wh += energy

    cache_cost += cache_write_cost
    opt_cost += cache_write_cost
    current_reasoning_share = reasoning_requests / len(rows) if rows else 0.0
    if current_reasoning_share <= 0.10:
        cap_10_savings_usd = cap_10_savings_wh = 0.0
    else:
        excess_fraction = (current_reasoning_share - 0.10) / current_reasoning_share
        cap_10_savings_usd *= excess_fraction
        cap_10_savings_wh *= excess_fraction

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    reasoning_total_cost = reasoning_cost + non_reasoning_cost
    reasoning_total_wh = reasoning_wh + non_reasoning_wh
    reasoning = {
        "requests": reasoning_requests,
        "traffic_pct": round(current_reasoning_share * 100, 2),
        "cost_usd": round(reasoning_cost, 2),
        "cost_pct": round(reasoning_cost / reasoning_total_cost * 100, 2)
        if reasoning_total_cost else 0.0,
        "energy_wh": round(reasoning_wh, 2),
        "energy_pct": round(reasoning_wh / reasoning_total_wh * 100, 2)
        if reasoning_total_wh else 0.0,
        "cap_10_savings_usd": round(cap_10_savings_usd, 2),
        "cap_10_savings_wh": round(cap_10_savings_wh, 2),
    }

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print("lever savings ($/day): "
              f"cascade={base_cost-cascade_cost:.2f}, "
              f"cache={cascade_cost-cache_cost:.2f}, batch={cache_cost-opt_cost:.2f}")
        print("cache economics (reads/prefix): " + ", ".join(
            f"{tier}={info['avg_reads']:.1f} (break-even {info['break_even_reads']:.2f}; "
            f"{'use' if info['worth_it'] else 'skip'})"
            for tier, info in sorted(cache_economics.items())
        ))
        print(f"amortized cache-write premium: ${cache_write_cost:.4f}/day")
        print(f"reasoning: {reasoning['traffic_pct']:.2f}% traffic, "
              f"{reasoning['cost_pct']:.2f}% cost, {reasoning['energy_pct']:.2f}% energy")
        print(f"10% reasoning cap incremental savings: "
              f"${reasoning['cap_10_savings_usd']:.2f}/day, "
              f"{reasoning['cap_10_savings_wh']:.2f} Wh/day")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "lever_savings_daily": {
            "cascade": round(base_cost - cascade_cost, 2),
            "cache": round(cascade_cost - cache_cost, 2),
            "batch": round(cache_cost - opt_cost, 2),
        },
        "cache_write_cost_daily": round(cache_write_cost, 4),
        "cache_economics": cache_economics,
        "reasoning": reasoning,
    }


if __name__ == "__main__":
    run()
