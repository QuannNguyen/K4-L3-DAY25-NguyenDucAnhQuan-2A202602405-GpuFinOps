import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from data import generate
from finops import pricing
from missions import m2_inference_levers


def test_cache_break_even_and_gate():
    assert abs(pricing.cache_break_even_reads(1.25, 0.10) - 1.25 / 0.90) < 1e-9
    assert not pricing.cache_is_worth_it(1.0, 1.25, 0.10)
    assert pricing.cache_is_worth_it(2.0, 1.25, 0.10)


def test_m2_extensions_use_measured_dataset():
    generate.main()
    result = m2_inference_levers.run(verbose=False)
    assert all(info["worth_it"] for info in result["cache_economics"].values())
    assert 0 < result["reasoning"]["traffic_pct"] < 10
    assert result["lever_savings_daily"]["batch"] > 0
