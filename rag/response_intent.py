from __future__ import annotations

import re
from dataclasses import dataclass


_DIAGRAM_REQUEST = re.compile(
    r"\b(?:mermaid|diagram(?:s)?|flow\s*chart(?:s)?|flowchart(?:s)?|"
    r"architecture|architectural|architec\w*|arch)\b",
    re.IGNORECASE,
)
_ALL_DIAGRAMS = re.compile(
    r"\b(?:all|every|each|both|complete set of)\b",
    re.IGNORECASE,
)
_DEEP_DIVE = re.compile(
    r"\b(?:everything|deep\s+dive|in\s+detail|detailed|comprehensive|"
    r"complete\s+(?:overview|breakdown|case\s+study)|full\s+(?:overview|"
    r"breakdown|case\s+study|project\s+details?))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResponseIntent:
    """Deterministic presentation intent; it never authorizes facts or sources."""

    response_profile: str = "concise"
    diagram_scope: str = "none"

    @property
    def is_default(self) -> bool:
        return self.response_profile == "concise" and self.diagram_scope == "none"


def classify_response_intent(question: str) -> ResponseIntent:
    """Detect only explicit detail and diagram wording from the visitor message."""

    wants_diagram = bool(_DIAGRAM_REQUEST.search(question))
    return ResponseIntent(
        response_profile="deep_dive" if _DEEP_DIVE.search(question) else "concise",
        diagram_scope=(
            "all" if wants_diagram and _ALL_DIAGRAMS.search(question) else "single"
            if wants_diagram
            else "none"
        ),
    )
