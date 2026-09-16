"""Unit tests for configuration and CLI orchestration."""

import argparse
import json
import sys
from pathlib import Path

import pytest

from contribution_radar import cli
from contribution_radar.models import Candidate, RepositoryTarget


def write_json(path: Path, payload: object) -> None:
    """Write a compact JSON test fixture."""

    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_targets_validates_and_normalizes_configuration(tmp_path: Path) -> None:
    """Load valid targets and apply the default popularity threshold."""

    config = tmp_path / "repositories.json"
    write_json(
        config,
        {
            "repositories": [
                {"name": "owner/one"},
                {"name": "owner/two", "minimum_stars": 42},
            ]
        },
    )

    targets = cli.load_targets(config)

    assert targets == [
        RepositoryTarget("owner/one", 1_000),
        RepositoryTarget("owner/two", 42),
    ]


@pytest.mark.parametrize(
    "payload,error",
    [
        ({}, "repositories"),
        ({"repositories": []}, "at least one"),
        ({"repositories": ["owner/repo"]}, "must be an object"),
        ({"repositories": [{"name": ""}]}, "non-empty string"),
        ({"repositories": [{"name": "owner/repo", "minimum_stars": True}]}, "minimum_stars"),
        (
            {"repositories": [{"name": "Owner/Repo"}, {"name": "owner/repo"}]},
            "duplicate",
        ),
    ],
)
def test_load_targets_rejects_invalid_configuration(
    tmp_path: Path,
    payload: object,
    error: str,
) -> None:
    """Reject malformed configuration before making network requests."""

    config = tmp_path / "repositories.json"
    write_json(config, payload)

    with pytest.raises(ValueError, match=error):
        cli.load_targets(config)


def test_write_report_creates_parent_and_replaces_content(tmp_path: Path) -> None:
    """Write complete reports atomically into a new directory."""

    output = tmp_path / "nested" / "REPORT.md"

    cli.write_report(output, "first")
    cli.write_report(output, "second")

    assert output.read_text(encoding="utf-8") == "second"


def test_parse_args_applies_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expose predictable defaults for local and scheduled runs."""

    monkeypatch.setattr(sys, "argv", ["contribution-radar"])

    args = cli.parse_args()

    assert args.config == Path("config/repositories.json")
    assert args.output == Path("REPORT.md")
    assert args.limit == 10


def test_main_orchestrates_generation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Connect configuration, discovery, rendering, and persistence."""

    config = tmp_path / "repositories.json"
    output = tmp_path / "REPORT.md"
    write_json(config, {"repositories": [{"name": "owner/repo"}]})
    monkeypatch.setattr(
        cli,
        "parse_args",
        lambda: argparse.Namespace(config=config, output=output, limit=3),
    )

    class FakeRadar:
        """Deterministic replacement for the ranking service."""

        def __init__(self, gateway: object) -> None:
            """Accept the controller's gateway dependency."""

            assert gateway is not None

        def discover(
            self,
            targets: list[RepositoryTarget],
            limit: int,
            now: object,
        ) -> list[Candidate]:
            """Return no candidates after validating controller inputs."""

            assert targets == [RepositoryTarget("owner/repo")]
            assert limit == 3
            assert now is not None
            return []

    monkeypatch.setattr(cli, "ContributionRadar", FakeRadar)

    cli.main()

    assert output.exists()
    assert "No unassigned" in output.read_text(encoding="utf-8")
    assert "Wrote 0 opportunities" in capsys.readouterr().out
