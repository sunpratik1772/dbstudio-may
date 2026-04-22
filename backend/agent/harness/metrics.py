"""
Lightweight in-memory metrics for the agent harness.

Purpose: give us visibility into how well the repair loop is
actually working without standing up a telemetry stack. The numbers
are per-process — a Cloud Run restart resets them — but they let us
surface a `/agent/metrics` endpoint for the UI status bar and catch
regressions (success rate dropping, auto-fix firing less, attempts
trending up) early.

The shape is intentionally flat. When we move to real telemetry we'll
mirror these names as counters / histograms.
"""
from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class AgentMetrics:
    runs_started: int = 0
    runs_succeeded: int = 0
    runs_failed: int = 0

    attempts_total: int = 0
    auto_fix_runs: int = 0
    auto_fix_rules_fired: Counter = field(default_factory=Counter)

    failure_codes: Counter = field(default_factory=Counter)

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ── write side ───────────────────────────────────────────────────────────
    def record_run_start(self) -> None:
        with self._lock:
            self.runs_started += 1

    def record_run_success(self, attempts: int) -> None:
        with self._lock:
            self.runs_succeeded += 1
            self.attempts_total += attempts

    def record_run_failure(self, attempts: int, error_codes: list[str]) -> None:
        with self._lock:
            self.runs_failed += 1
            self.attempts_total += attempts
            for code in error_codes:
                self.failure_codes[code] += 1

    def record_auto_fix(self, rules_applied: list[str]) -> None:
        with self._lock:
            self.auto_fix_runs += 1
            for desc in rules_applied:
                # Strip the node-scoped prefix so the counter aggregates
                # by rule kind, not by node id. "n02.query_template: ..."
                # -> "query_template".
                key = desc.split(":", 1)[0]
                self.auto_fix_rules_fired[key] += 1

    # ── read side ────────────────────────────────────────────────────────────
    def snapshot(self) -> dict:
        with self._lock:
            completed = self.runs_succeeded + self.runs_failed
            success_rate = (self.runs_succeeded / completed) if completed else None
            avg_attempts = (self.attempts_total / completed) if completed else None
            return {
                "runs_started": self.runs_started,
                "runs_succeeded": self.runs_succeeded,
                "runs_failed": self.runs_failed,
                "success_rate": success_rate,
                "avg_attempts": avg_attempts,
                "auto_fix_runs": self.auto_fix_runs,
                "auto_fix_rules_fired": dict(self.auto_fix_rules_fired),
                "failure_codes": dict(self.failure_codes.most_common(20)),
            }

    def reset(self) -> None:
        with self._lock:
            self.runs_started = 0
            self.runs_succeeded = 0
            self.runs_failed = 0
            self.attempts_total = 0
            self.auto_fix_runs = 0
            self.auto_fix_rules_fired.clear()
            self.failure_codes.clear()


# Process-global singleton — deliberately simple. Tests that want
# isolation can instantiate their own AgentMetrics.
_metrics = AgentMetrics()


def get_metrics() -> AgentMetrics:
    return _metrics
