"""
RunContext — the single shared bag every node reads from and writes to.

Mental model: a workflow is a DAG of stateless handler functions. The
only state that flows between them is the RunContext. Each node mutates
the context in place; the dag_runner re-passes the same instance to
every successor.

Three "shelves" by convention — keep them separate so unrelated nodes
don't accidentally collide on a key:

  • alert_payload — the immutable input (trader_id, event_time, …).
  • values        — scalars / config / signals / disposition / etc.
                    Use ctx.set/get; never reach into .values directly
                    from a handler unless you have a reason.
  • datasets      — pandas DataFrames keyed by output_name. The wiring
                    contract is "input_name of node N == output_name of
                    some upstream node." The validator enforces this.
  • sections      — narrative blocks produced by SECTION_SUMMARY for the
                    final report; CONSOLIDATED_SUMMARY consumes them.

Plus a few terminal flags (disposition, output_branch, report_path) the
final REPORT_OUTPUT / decision nodes set so callers (HTTP, tests) can
inspect the outcome without re-walking the graph.

Stays mutable on purpose — turning this immutable would force every
node to copy O(n) datasets. Discipline is "handlers only mutate; never
read another handler's intermediate state."
"""
import uuid
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class RunContext:
    """Shared mutable context passed across all nodes in a workflow run.

    Every field is initialised empty. Handlers fill them as they run.
    No node should assume a key/dataset exists without checking — order
    is determined by the DAG topology, not field declaration here.
    """
    alert_payload: dict = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)
    datasets: dict[str, pd.DataFrame] = field(default_factory=dict)
    # output_name of each dataset -> DataSource registry id (trades, market, comms, …)
    dataset_provenance: dict[str, str] = field(default_factory=dict)
    sections: dict[str, dict] = field(default_factory=dict)
    executive_summary: str = ""
    disposition: str = ""
    output_branch: str = ""
    report_path: str = ""
    # Unique id for this run. Stamped onto every SSE frame, every log
    # line (once we adopt it in `logging`), and the final run result.
    # Lets an operator grep "run_id=abc123" across frontend trace →
    # backend log → audit trail and reconstruct the full story.
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)
