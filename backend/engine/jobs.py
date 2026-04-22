"""
Execution seam between the HTTP layer and the DAG runner.

Today `/run` and `/run/stream` call `run_workflow` / `run_workflow_stream`
synchronously inside the request handler. That's fine for a single
workflow on a single instance but does not scale — long-running
pipelines block a worker, and we have no place to hook in queueing,
rate-limiting, tracing, or back-pressure.

This module introduces a `JobRunner` protocol that the HTTP layer
calls. The default `InlineJobRunner` preserves today's behaviour
exactly (call the engine in-process, yield results immediately). A
future `CloudTaskJobRunner` / `CeleryJobRunner` can slot in by
implementing the same two methods — **no changes to `app/routers/`
required** beyond a single DI swap.

The public surface is deliberately tiny:

    runner.run(dag, alert_payload) -> RunResult      # blocking
    runner.stream(dag, alert_payload) -> Iterator    # per-node events

Everything observable (report download URL, per-node timings, warnings)
continues to travel through the same event shapes the UI already
consumes, so queueing can be introduced without a frontend change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol

from . import RunContext, run_workflow, run_workflow_stream


@dataclass(frozen=True)
class RunResult:
    """Structured output of a synchronous `JobRunner.run()` call."""

    context: RunContext


class JobRunner(Protocol):
    """
    The only two verbs the HTTP layer needs. A distributed backend
    (Cloud Tasks, Celery, K8s Job) implements the same protocol and
    becomes a drop-in replacement without touching the routers.
    """

    def run(self, dag: dict, alert_payload: dict) -> RunResult: ...

    def stream(self, dag: dict, alert_payload: dict) -> Iterator[dict]: ...


class InlineJobRunner:
    """
    Runs the DAG in the current process. This is the production
    default today and also the safest thing to run in development —
    every request handler gets a fresh `RunContext`, so multiple
    concurrent HTTP requests remain isolated.
    """

    def run(self, dag: dict, alert_payload: dict) -> RunResult:
        ctx = run_workflow(dag, alert_payload)
        return RunResult(context=ctx)

    def stream(self, dag: dict, alert_payload: dict) -> Iterator[dict]:
        yield from run_workflow_stream(dag, alert_payload)


# Single process-wide runner. Swap this for a distributed runner by
# setting an env var + rebinding in `app.deps.get_job_runner()`.
_DEFAULT: JobRunner = InlineJobRunner()


def get_default_runner() -> JobRunner:
    return _DEFAULT


__all__ = ["JobRunner", "InlineJobRunner", "RunResult", "get_default_runner"]
