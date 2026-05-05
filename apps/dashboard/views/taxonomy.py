import json
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse


TAXONOMY_PATH = Path(__file__).resolve().parents[3] / "music_theory_taxonomy_with_branches.json"


def _load_taxonomy_branches() -> list[dict]:
    with open(TAXONOMY_PATH, "r") as handle:
        raw_branches = json.load(handle)

    branches = []
    for index, branch in enumerate(raw_branches):
        label = branch.get("label")
        if not label:
            if index == 0:
                label = "Core Sequence"
            else:
                label = f"Branch {chr(ord('A') + index - 1)}"

        tiers = []
        for tier in branch.get("tiers", []):
            units = []
            for unit in tier.get("units", []):
                analysis = unit.get("analysis") or {}
                units.append(
                    {
                        "n": unit.get("n"),
                        "title": unit.get("title", ""),
                        "feat": unit.get("feat", ""),
                        "tags": unit.get("tags", []),
                        "analysis": {
                            family: {
                                "new": [entry.get("value") for entry in payload.get("new", []) if entry.get("value")],
                                "cumulative": [entry.get("value") for entry in payload.get("cumulative", []) if entry.get("value")],
                            }
                            for family, payload in analysis.items()
                        },
                    }
                )

            tiers.append(
                {
                    "label": tier.get("label", ""),
                    "badge": tier.get("badge", ""),
                    "units": units,
                }
            )

        branches.append(
            {
                "label": label,
                "tiers": tiers,
            }
        )

    return branches


@login_required
def taxonomy_debug_view(request):
    if not request.user.is_staff:
        return redirect(reverse("dashboard:index"))

    branches = _load_taxonomy_branches()
    return render(
        request,
        "dashboard/taxonomy_debug.html",
        {
            "branches": branches,
        },
    )
