"""
Quick smoke test — runs the FX FRO workflow with mock data.
No LLM needed (section_summary and consolidated_summary gracefully degrade).
"""
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
sys.path.insert(0, str(Path(__file__).parent))

from engine import load_and_run

PAYLOAD = {
    "trader_id": "T001",
    "book": "FX-SPOT",
    "alert_date": "2024-01-15",
    "currency_pair": "EUR/USD",
    "alert_id": "ALT-2024-001",
}

if __name__ == "__main__":
    dag_path = Path(__file__).parent / "workflows" / "fx_fro_workflow.json"
    print(f"\nRunning: {dag_path}")
    ctx = load_and_run(str(dag_path), PAYLOAD)
    print("\n" + "═" * 55)
    print("  RESULT")
    print("═" * 55)
    print(f"  Disposition : {ctx.disposition}")
    print(f"  Flag count  : {ctx.get('flag_count', 0)}")
    print(f"  Datasets    : {list(ctx.datasets.keys())}")
    print(f"  Sections    : {list(ctx.sections.keys())}")
    print(f"  Report      : {ctx.report_path}")
    print("═" * 55)
    if ctx.report_path and Path(ctx.report_path).exists():
        print(f"\n  ✅ Excel report written to: {ctx.report_path}")
    else:
        print("\n  ⚠️  Report not written (check error above)")
