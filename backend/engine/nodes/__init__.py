"""
Node handler package.

Every node lives in its own module and exports two top-level symbols:

- `handle_<type>(node, ctx)` — the pure handler function. Must not
  mutate module-level state; everything it needs is in `node` (the
  user's config) and `ctx` (the per-run context).

- `NODE_SPEC` — a `NodeSpec` instance declared via `_spec(...)`.
  This is what `engine.registry` auto-discovers; adding a new node
  is a one-file change.

The registry picks up `NODE_SPEC` by walking this package with
`pkgutil.iter_modules`, so the file name does not have to match the
type_id; only the module-level attribute matters.
"""
