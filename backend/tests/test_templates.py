"""
Phase 7+ — template registry + intent-driven selector.

Falsifiable claims under test:

  * Both bundled templates load from disk and expose required parameters.
  * Each template's skeleton validates clean against `validate_dag`
    — i.e. a planner that drops a template skeleton straight onto the
    runtime never produces a structurally invalid workflow.
  * The selector returns the right template for each scenario keyword,
    handles synonyms, breaks ties by dataset overlap, and returns None
    when no signal matches.
"""
from __future__ import annotations

from engine.validator import validate_dag
from agent.templates import Template, TemplateRegistry


def test_registry_loads_bundled_templates():
    reg = TemplateRegistry.from_directory()
    names = sorted(t.name for t in reg.all())
    assert names == ["fi_spoof_layering", "fx_front_running"]


def test_template_skeletons_validate_clean():
    """A planner picks a template, fills parameters, and runs. The
    skeleton it starts from must be runnable as-is."""
    reg = TemplateRegistry.from_directory()
    for tmpl in reg.all():
        result = validate_dag(tmpl.skeleton)
        assert result.valid, (
            f"template '{tmpl.name}' skeleton invalid: "
            f"{[i.message for i in result.errors]}"
        )
        assert result.warnings == [], (
            f"template '{tmpl.name}' skeleton has warnings: "
            f"{[i.message for i in result.warnings]}"
        )


def test_templates_declare_required_parameters():
    reg = TemplateRegistry.from_directory()
    fro = reg.get("fx_front_running")
    fisl = reg.get("fi_spoof_layering")
    assert "trader_id" in fro.required_parameters()
    assert "currency_pair" in fro.required_parameters()
    assert "event_time" in fro.required_parameters()
    assert "trader_id" in fisl.required_parameters()
    assert "event_time" in fisl.required_parameters()


def test_selector_picks_fro_for_front_running_intent():
    reg = TemplateRegistry.from_directory()
    match = reg.select({
        "scenarios": ["front-running"],
        "datasets": ["orders", "executions", "comms"],
    })
    assert match is not None
    assert match.template.name == "fx_front_running"
    assert "front-running" in match.matched_scenarios or "frontrun" in match.matched_scenarios


def test_selector_picks_fisl_for_spoofing_intent():
    reg = TemplateRegistry.from_directory()
    match = reg.select({"scenarios": ["spoofing"], "datasets": ["orders"]})
    assert match is not None
    assert match.template.name == "fi_spoof_layering"


def test_selector_handles_synonym_layering():
    reg = TemplateRegistry.from_directory()
    match = reg.select({"scenarios": ["layering"]})
    assert match is not None
    assert match.template.name == "fi_spoof_layering"


def test_selector_returns_none_for_unknown_intent():
    reg = TemplateRegistry.from_directory()
    assert reg.select({"scenarios": ["insider-trading"], "datasets": []}) is None
    assert reg.select({}) is None


def test_selector_breaks_ties_by_dataset_overlap():
    """Two templates matching scenario weights equally — dataset
    overlap is the deciding signal."""
    a = Template.from_dict({
        "name": "alpha",
        "matches": {"scenarios": ["spoofing"], "datasets": ["orders"]},
    })
    b = Template.from_dict({
        "name": "beta",
        "matches": {"scenarios": ["spoofing"], "datasets": ["orders", "executions"]},
    })
    reg = TemplateRegistry([a, b])
    match = reg.select({
        "scenarios": ["spoofing"],
        "datasets": ["orders", "executions"],
    })
    assert match.template.name == "beta"


def test_selector_dataset_only_match_still_works():
    """If the user names datasets but no scenario keyword, the
    template with overlapping datasets still wins."""
    reg = TemplateRegistry.from_directory()
    match = reg.select({"datasets": ["orders", "executions", "comms", "market"]})
    assert match is not None
    assert match.template.name == "fx_front_running"
