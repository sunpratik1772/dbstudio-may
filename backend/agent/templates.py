"""
Workflow template registry + intent-driven selector.

Every scenario the platform supports starts as a *template*: a vetted
skeleton DAG with metadata describing which intents/datasets it covers
and which parameters the planner has to fill. The planner uses a
template as its starting point rather than generating a workflow from
scratch — that bounds the generation surface and gives the validator
something well-formed to start from.

A template file is JSON:

    {
      "name": "fx_front_running",
      "description": "...",
      "matches": {
        "scenarios": ["front-running", "FRO", ...],
        "datasets":  ["orders", "executions", ...],
        "semantics": ["trader", "time"]
      },
      "parameters": [
        {"name": "trader_id", "type": "string", "required": true},
        ...
      ],
      "skeleton": { ...full nodes + edges... }
    }

`select_template(intent)` scores every loaded template against the
caller's intent dict and returns the best match (or None). Scenario
and dataset matches are weighted differently so a workflow with the
right name but wrong dataset shape can still lose to a plain-old
dataset-coverage match.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "templates"


@dataclass(frozen=True)
class Template:
    name: str
    description: str
    scenarios: tuple[str, ...]
    datasets: tuple[str, ...]
    semantics: tuple[str, ...]
    parameters: tuple[dict, ...]
    skeleton: dict
    source_path: str = ""

    @classmethod
    def from_dict(cls, raw: dict, source_path: str = "") -> "Template":
        matches = raw.get("matches") or {}
        return cls(
            name=raw.get("name", ""),
            description=raw.get("description", ""),
            scenarios=tuple(s.lower() for s in matches.get("scenarios") or []),
            datasets=tuple(matches.get("datasets") or []),
            semantics=tuple(matches.get("semantics") or []),
            parameters=tuple(raw.get("parameters") or []),
            skeleton=raw.get("skeleton") or {},
            source_path=source_path,
        )

    def required_parameters(self) -> list[str]:
        return [
            p.get("name", "")
            for p in self.parameters
            if p.get("required") and p.get("name")
        ]


@dataclass
class TemplateMatch:
    template: Template
    score: int
    matched_scenarios: list[str] = field(default_factory=list)
    matched_datasets: list[str] = field(default_factory=list)


class TemplateRegistry:
    """Loads `templates/*.json` once and answers selector queries.

    Cheap to instantiate (the disk I/O happens here, not in the hot
    path) so callers can safely build a fresh registry per request
    in tests; in production the planner reuses a single instance.
    """

    def __init__(self, templates: Iterable[Template] = ()) -> None:
        self._by_name: dict[str, Template] = {t.name: t for t in templates if t.name}

    @classmethod
    def from_directory(cls, directory: str | Path | None = None) -> "TemplateRegistry":
        path = Path(directory) if directory is not None else _DEFAULT_DIR
        templates: list[Template] = []
        if not path.is_dir():
            return cls(templates)
        for entry in sorted(path.glob("*.json")):
            try:
                with entry.open() as f:
                    raw = json.load(f)
            except Exception:
                continue
            tmpl = Template.from_dict(raw, source_path=str(entry))
            if tmpl.name:
                templates.append(tmpl)
        return cls(templates)

    def all(self) -> list[Template]:
        return list(self._by_name.values())

    def get(self, name: str) -> Template | None:
        return self._by_name.get(name)

    # ------------------------------------------------------------------
    # Selector
    # ------------------------------------------------------------------
    def select(self, intent: dict) -> TemplateMatch | None:
        """Return the highest-scoring template, or None if no template
        matches at least one signal in the intent.

        Scoring (deliberately simple — explainable in one sentence):
          * +10 per scenario keyword overlap (scenarios are the strongest
            signal; the user said "front-running" — give them FRO).
          * +1 per dataset name overlap (a tie-break that favours templates
            already familiar with the data shape).

        A template wins only if its score is > 0. Ties are broken by
        template name to keep ordering deterministic.
        """
        scenario_terms = _normalise_terms(intent.get("scenarios"))
        dataset_terms = _normalise_terms(intent.get("datasets"), lower=False)

        candidates: list[TemplateMatch] = []
        for tmpl in self._by_name.values():
            matched_scen = [s for s in tmpl.scenarios if _matches_any(s, scenario_terms)]
            matched_data = [d for d in tmpl.datasets if d in dataset_terms]
            score = 10 * len(matched_scen) + len(matched_data)
            if score == 0:
                continue
            candidates.append(
                TemplateMatch(
                    template=tmpl,
                    score=score,
                    matched_scenarios=matched_scen,
                    matched_datasets=matched_data,
                )
            )
        if not candidates:
            return None
        candidates.sort(key=lambda m: (-m.score, m.template.name))
        return candidates[0]


def _normalise_terms(raw, *, lower: bool = True) -> set[str]:
    if not raw:
        return set()
    if isinstance(raw, str):
        items = [raw]
    else:
        items = list(raw)
    if lower:
        return {str(x).lower() for x in items if x}
    return {str(x) for x in items if x}


def _matches_any(scenario_term: str, intent_terms: set[str]) -> bool:
    """Loose match: substring either way handles 'front-running' vs 'FRO'
    where the intent text might contain the longer phrase but the template
    keyword is the abbreviation."""
    if not scenario_term or not intent_terms:
        return False
    for term in intent_terms:
        if not term:
            continue
        if scenario_term == term or scenario_term in term or term in scenario_term:
            return True
    return False


__all__ = ["Template", "TemplateMatch", "TemplateRegistry"]
