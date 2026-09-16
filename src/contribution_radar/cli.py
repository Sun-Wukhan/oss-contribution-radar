"""Command-line controller for daily report generation."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from contribution_radar.github_client import GitHubClient
from contribution_radar.models import RepositoryTarget
from contribution_radar.report import render_report
from contribution_radar.service import ContributionRadar


def parse_args() -> argparse.Namespace:
    """Parse and validate command-line options."""

    parser = argparse.ArgumentParser(
        description="Find review-ready issues in established public repositories."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/repositories.json"),
        help="JSON repository target configuration",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("REPORT.md"),
        help="generated Markdown report path",
    )
    parser.add_argument("--limit", type=int, default=10, choices=range(1, 51))
    return parser.parse_args()


def load_targets(path: Path) -> list[RepositoryTarget]:
    """Load validated repository targets from JSON."""

    with path.open(encoding="utf-8") as config_file:
        payload = cast(object, json.load(config_file))

    if not isinstance(payload, dict) or not isinstance(payload.get("repositories"), list):
        raise ValueError("config must contain a 'repositories' list")

    targets: list[RepositoryTarget] = []
    seen: set[str] = set()
    for raw_target in cast(list[Any], payload["repositories"]):
        if not isinstance(raw_target, dict):
            raise ValueError("each repository target must be an object")
        name = raw_target.get("name")
        minimum_stars = raw_target.get("minimum_stars", 1_000)
        if not isinstance(name, str) or not name:
            raise ValueError("repository target name must be a non-empty string")
        if (
            not isinstance(minimum_stars, int)
            or isinstance(minimum_stars, bool)
            or minimum_stars < 0
        ):
            raise ValueError(f"invalid minimum_stars for {name!r}")
        if name.casefold() in seen:
            raise ValueError(f"duplicate repository target: {name}")
        seen.add(name.casefold())
        targets.append(RepositoryTarget(name=name, minimum_stars=minimum_stars))

    if not targets:
        raise ValueError("at least one repository target is required")
    return targets


def write_report(path: Path, content: str) -> None:
    """Atomically write the generated report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as temporary_file:
        temporary_file.write(content)
        temporary_path = Path(temporary_file.name)
    temporary_path.replace(path)


def main() -> None:
    """Generate the daily contribution report."""

    args = parse_args()
    targets = load_targets(args.config)
    generated_at = datetime.now(UTC).replace(microsecond=0)
    radar = ContributionRadar(GitHubClient(token=os.getenv("GITHUB_TOKEN")))
    candidates = radar.discover(targets, limit=args.limit, now=generated_at)
    report = render_report(candidates, generated_at, scanned_repositories=len(targets))
    write_report(args.output, report)
    print(f"Wrote {len(candidates)} opportunities to {args.output}")


if __name__ == "__main__":
    main()
