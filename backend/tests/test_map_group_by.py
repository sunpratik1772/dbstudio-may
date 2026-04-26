"""
Phase 3 — GROUP_BY + MAP primitive.

GROUP_BY partitions a dataset by column; MAP runs a nested sub-workflow
once per key. Together they give us the fan-out-over-groups pattern the
FRO workflow needs (per-book signal + summary).
"""
from __future__ import annotations

import pandas as pd
import pytest

from engine.context import RunContext
from engine.nodes.extract_scalar import handle_extract_scalar
from engine.nodes.group_by import handle_group_by
from engine.nodes.map_node import handle_map
from engine.registry import NODE_SPECS


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------
def test_group_by_and_map_registered():
    assert "GROUP_BY" in NODE_SPECS
    assert "MAP" in NODE_SPECS


# ---------------------------------------------------------------------------
# GROUP_BY
# ---------------------------------------------------------------------------
def _orders_df():
    return pd.DataFrame({
        "order_id": list(range(6)),
        "book": ["A", "B", "A", "C", "B", "A"],
        "qty": [10, 20, 30, 40, 50, 60],
    })


def test_group_by_publishes_key_list_and_per_key_slices():
    ctx = RunContext()
    ctx.datasets["orders"] = _orders_df()
    handle_group_by({"config": {
        "input_name": "orders",
        "group_by_column": "book",
        "output_prefix": "orders_by_book",
        "order": "sort",
    }}, ctx)

    assert ctx.get("orders_keys") == {"values": ["A", "B", "C"]}
    assert len(ctx.datasets["orders_by_book_A"]) == 3
    assert len(ctx.datasets["orders_by_book_B"]) == 2
    assert len(ctx.datasets["orders_by_book_C"]) == 1
    assert list(ctx.datasets["orders_by_book_A"]["qty"]) == [10, 30, 60]


def test_group_by_first_seen_order():
    ctx = RunContext()
    ctx.datasets["orders"] = _orders_df()
    handle_group_by({"config": {
        "input_name": "orders",
        "group_by_column": "book",
        "output_prefix": "g",
    }}, ctx)
    assert ctx.get("orders_keys") == {"values": ["A", "B", "C"]}


def test_group_by_custom_keys_output_name():
    ctx = RunContext()
    ctx.datasets["orders"] = _orders_df()
    handle_group_by({"config": {
        "input_name": "orders",
        "group_by_column": "book",
        "output_prefix": "g",
        "keys_output_name": "books_touched",
    }}, ctx)
    assert ctx.get("books_touched") == {"values": ["A", "B", "C"]}
    assert ctx.get("orders_keys") is None


def test_group_by_dropna():
    ctx = RunContext()
    ctx.datasets["orders"] = pd.DataFrame({"book": ["A", None, "B"], "q": [1, 2, 3]})
    handle_group_by({"config": {
        "input_name": "orders",
        "group_by_column": "book",
        "output_prefix": "g",
        "dropna": True,
    }}, ctx)
    assert ctx.get("orders_keys") == {"values": ["A", "B"]}


def test_group_by_missing_dataset_raises():
    ctx = RunContext()
    with pytest.raises(KeyError):
        handle_group_by({"config": {
            "input_name": "nope", "group_by_column": "x", "output_prefix": "p",
        }}, ctx)


def test_group_by_missing_column_raises():
    ctx = RunContext()
    ctx.datasets["d"] = pd.DataFrame({"a": [1]})
    with pytest.raises(KeyError):
        handle_group_by({"config": {
            "input_name": "d", "group_by_column": "b", "output_prefix": "p",
        }}, ctx)


# ---------------------------------------------------------------------------
# MAP — using EXTRACT_SCALAR as the per-iteration sub-workflow node
# ---------------------------------------------------------------------------
def test_map_runs_sub_workflow_per_key():
    """GROUP_BY orders by book → MAP runs EXTRACT_SCALAR(sum qty) per book."""
    ctx = RunContext()
    ctx.datasets["orders"] = _orders_df()
    handle_group_by({"config": {
        "input_name": "orders",
        "group_by_column": "book",
        "output_prefix": "orders_by_book",
        "order": "sort",
    }}, ctx)

    sub_workflow = {
        "nodes": [
            {
                "id": "s1",
                "type": "EXTRACT_SCALAR",
                "config": {
                    "input_name": "orders",  # alias — MAP wires the per-book slice here
                    "column": "qty",
                    "reducer": "sum",
                    "output_name": "book_qty",
                },
            },
        ],
        "edges": [],
    }

    handle_map({"config": {
        "keys_key": "orders_keys",
        "iteration_ctx_key": "current_book",
        "dataset_prefix": "orders_by_book",
        "iteration_dataset_alias": "orders",
        "sub_workflow": sub_workflow,
        "collect_values": ["book_qty", "current_book"],
        "output_name": "per_book",
    }}, ctx)

    per_book = ctx.get("per_book")
    assert set(per_book["results"].keys()) == {"A", "B", "C"}
    assert per_book["results"]["A"]["book_qty"] == 100  # 10+30+60
    assert per_book["results"]["B"]["book_qty"] == 70   # 20+50
    assert per_book["results"]["C"]["book_qty"] == 40
    # iteration_ctx_key is visible inside the child — harvested here
    assert per_book["results"]["A"]["current_book"] == "A"


def test_map_harvests_datasets():
    """collect_datasets should publish per-key datasets to the parent ctx."""
    ctx = RunContext()
    ctx.datasets["orders"] = _orders_df()
    handle_group_by({"config": {
        "input_name": "orders",
        "group_by_column": "book",
        "output_prefix": "obb",
        "order": "sort",
    }}, ctx)

    # Sub-workflow: no-op that re-publishes the aliased dataset under a new name
    def _passthrough_sub():
        return {
            "nodes": [
                {
                    "id": "s1",
                    "type": "EXTRACT_SCALAR",
                    "config": {
                        "input_name": "orders",
                        "column": "qty",
                        "reducer": "count",
                        "output_name": "row_count",
                    },
                },
            ],
            "edges": [],
        }

    handle_map({"config": {
        "keys_key": "orders_keys",
        "iteration_ctx_key": "current_book",
        "dataset_prefix": "obb",
        "iteration_dataset_alias": "orders",
        "sub_workflow": _passthrough_sub(),
        "collect_values": ["row_count"],
        "collect_datasets": ["orders"],
        "output_name": "per_book",
    }}, ctx)

    # Datasets surfaced under "{output_name}_{key}_{dataset}"
    assert "per_book_A_orders" in ctx.datasets
    assert len(ctx.datasets["per_book_A_orders"]) == 3
    assert ctx.get("per_book")["results"]["A"]["row_count"] == 3


def test_map_child_values_do_not_leak_to_parent():
    """Iteration-local values written in the sub-workflow must not appear in parent ctx."""
    ctx = RunContext()
    ctx.datasets["orders"] = _orders_df()
    handle_group_by({"config": {
        "input_name": "orders",
        "group_by_column": "book",
        "output_prefix": "g",
        "order": "sort",
    }}, ctx)

    sub = {
        "nodes": [{
            "id": "s1", "type": "EXTRACT_SCALAR",
            "config": {"input_name": "orders", "column": "qty",
                       "reducer": "sum", "output_name": "iter_local"},
        }],
        "edges": [],
    }
    handle_map({"config": {
        "keys_key": "orders_keys",
        "iteration_ctx_key": "current_book",
        "dataset_prefix": "g",
        "iteration_dataset_alias": "orders",
        "sub_workflow": sub,
        "collect_values": [],  # intentionally harvest nothing
        "output_name": "per_book",
    }}, ctx)

    # `iter_local` was set inside the child ctx but we did not collect it.
    assert "iter_local" not in ctx.values
    # `current_book` was the iteration key — also contained in child only.
    assert "current_book" not in ctx.values


def test_map_empty_keys_produces_empty_results():
    ctx = RunContext()
    ctx.set("empty_keys", {"values": []})
    handle_map({"config": {
        "keys_key": "empty_keys",
        "iteration_ctx_key": "k",
        "sub_workflow": {"nodes": [{"id": "s", "type": "EXTRACT_SCALAR",
                                    "config": {"input_name": "x", "column": "y",
                                               "reducer": "count", "output_name": "z"}}],
                         "edges": []},
        "output_name": "out",
    }}, ctx)
    assert ctx.get("out") == {"results": {}}


def test_map_rejects_bad_keys_shape():
    ctx = RunContext()
    ctx.set("bad", ["a", "b"])  # plain list, not {"values": [...]}
    with pytest.raises(ValueError, match="must reference"):
        handle_map({"config": {
            "keys_key": "bad",
            "iteration_ctx_key": "k",
            "sub_workflow": {"nodes": [{"id": "s", "type": "EXTRACT_SCALAR",
                                        "config": {"input_name": "x", "column": "y",
                                                   "reducer": "count", "output_name": "z"}}],
                             "edges": []},
            "output_name": "out",
        }}, ctx)


def test_map_missing_required_config_raises():
    ctx = RunContext()
    ctx.set("keys", {"values": ["a"]})
    with pytest.raises(ValueError, match="requires"):
        handle_map({"config": {
            "keys_key": "keys",
            # iteration_ctx_key missing
            "sub_workflow": {"nodes": [{"id": "x", "type": "EXTRACT_SCALAR",
                                        "config": {}}], "edges": []},
        }}, ctx)
