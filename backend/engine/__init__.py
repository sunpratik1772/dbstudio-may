"""
dbSherpa execution engine.

**Statelessness invariant**
---------------------------
One production instance of this backend runs many workflows concurrently
for many users. For that to be safe, the engine must obey one rule:

    Nothing that persists beyond a single `RunContext` may be mutated
    by a node handler.

Concretely:

  * Every handler is `fn(node: dict, ctx: RunContext) -> None`.
  * All intermediate state lives on `ctx` (datasets, values, sections,
    disposition, …). `ctx` is fresh per run.
  * Module-level variables are **read-only** after import. No caches,
    no singletons that accumulate state across runs, no global client
    objects that capture per-run credentials.
  * The registry (`engine.registry`) and specs (`engine.node_spec`) are
    populated once at import time and treated as immutable.
  * Network clients (Gemini, Solr, Oculus …) are either reconstructed
    per call or thread-safe stateless wrappers. They never receive a
    reference to `ctx`.

This is what lets a user hand us a YAML workflow and have it run
unchanged against this single backend — and what lets two users run
two different workflows at the same time without interfering.

A future linter check can enforce this by AST-walking every module
under `engine/nodes/` for top-level mutable assignments performed
inside a function. For now the invariant lives here, in the place
handlers are likely to look.
"""
from .context import RunContext
from .dag_runner import load_and_run, run_workflow, run_workflow_stream

__all__ = ["run_workflow", "run_workflow_stream", "load_and_run", "RunContext"]
