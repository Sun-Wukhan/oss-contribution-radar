# OSS Contribution Radar

[![Daily radar](https://github.com/Sun-Wukhan/oss-contribution-radar/actions/workflows/daily-radar.yml/badge.svg)](https://github.com/Sun-Wukhan/oss-contribution-radar/actions/workflows/daily-radar.yml)
[![Tests](https://github.com/Sun-Wukhan/oss-contribution-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/Sun-Wukhan/oss-contribution-radar/actions/workflows/ci.yml)

OSS Contribution Radar publishes a daily, ranked shortlist of genuine contribution
opportunities from established infrastructure projects.

The generated [`REPORT.md`](REPORT.md) is a discovery aid, not an autonomous contribution
bot. It never comments on third-party issues, claims work, opens pull requests, or writes to
external repositories. A human must review each issue, follow the target project's contribution
guide, implement and test a substantive change, and decide whether to submit it.

## How selection works

Candidates must satisfy every eligibility rule:

- The repository is active and above its configured star threshold.
- The issue is open and unassigned.
- Maintainers labeled it `good first issue`, `help wanted`, or an equivalent invitation.
- No currently open pull request declares that it closes the issue.

Ranking favors explicit beginner-friendly labels, bugs and documentation work, active discussions,
recent updates, and established repositories. The policy is intentionally conservative: an empty
report is better than a low-quality recommendation.

## Daily automation

The `Daily contribution radar` workflow runs at 13:00 UTC every day and can also be started
manually. It:

1. Uses GitHub's read-only public API to collect repository and issue metadata.
2. Generates `REPORT.md`.
3. Publishes the report in the workflow summary.
4. Commits a changed report as `github-actions[bot]`.

The workflow receives only `contents: write` permission for this repository. It cannot modify
third-party repositories.

## Local usage

Python 3.11 or newer and [uv](https://docs.astral.sh/uv/) are recommended.

```bash
uv sync
GITHUB_TOKEN="$(gh auth token)" uv run contribution-radar
```

The token is optional for small scans, but authenticated requests receive a higher GitHub API rate
limit. Use a short-lived token and never commit it.

Customize repository targets and minimum popularity thresholds in
[`config/repositories.json`](config/repositories.json).

## Development

```bash
uv sync
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

Test coverage must remain at or above 90%.

## Architecture

- `github_client.py` is the read-only GitHub data adapter.
- `service.py` contains eligibility and ranking business rules.
- `report.py` renders the public Markdown artifact.
- `cli.py` validates inputs and coordinates the application.

This separation keeps external API access out of the ranking logic and makes the policy
deterministically testable.

## Contributing

Please open an issue before making a substantial change. Pull requests should include tests,
type annotations, docstrings, and a clear explanation of the ranking behavior they change.

## License

MIT
