import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class RunContext:
    """Shared mutable context passed across all nodes in a workflow run."""
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

    def inject_template(self, template: str) -> str:
        """Replace {context.xxx} placeholders with context values."""
        def replacer(m: re.Match) -> str:
            return str(self.get(m.group(1), ""))
        return re.sub(r'\{context\.(\w+)\}', replacer, template)
