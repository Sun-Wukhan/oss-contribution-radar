"""Business rules for selecting worthwhile contribution opportunities."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime

from contribution_radar.models import Candidate, Issue, PullRequest, Repository, RepositoryTarget
from contribution_radar.ports import RepositoryGateway

CONTRIBUTION_LABEL_WEIGHTS = {
    "good first issue": 55.0,
    "help wanted": 40.0,
    "good first contribution": 55.0,
    "contributions welcome": 35.0,
}
QUALITY_LABEL_WEIGHTS = {
    "bug": 15.0,
    "documentation": 12.0,
    "docs": 12.0,
    "kind/bug": 15.0,
    "kind/documentation": 12.0,
}


class ContributionRadar:
    """Rank review-ready issues without creating upstream activity."""

    def __init__(self, gateway: RepositoryGateway) -> None:
        """Initialize the service with a read-only repository gateway."""

        self._gateway = gateway

    def discover(
        self,
        targets: list[RepositoryTarget],
        limit: int = 10,
        now: datetime | None = None,
    ) -> list[Candidate]:
        """Return the highest-quality unassigned opportunities."""

        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")

        evaluated_at = now or datetime.now(UTC)
        candidates: list[Candidate] = []
        for target in targets:
            repository = self._gateway.get_repository(target.name)
            if repository.archived or repository.stars < target.minimum_stars:
                continue

            pull_requests = self._gateway.list_open_pull_requests(target.name)
            for issue in self._gateway.list_open_issues(target.name):
                candidate = self._evaluate(repository, issue, pull_requests, evaluated_at)
                if candidate is not None:
                    candidates.append(candidate)

        candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                candidate.repository.name.casefold(),
                candidate.issue.number,
            )
        )
        return candidates[:limit]

    def _evaluate(
        self,
        repository: Repository,
        issue: Issue,
        pull_requests: list[PullRequest],
        now: datetime,
    ) -> Candidate | None:
        """Apply eligibility checks and score one issue."""

        if issue.is_pull_request or issue.assignees:
            return None

        labels = {label.casefold() for label in issue.labels}
        contribution_labels = labels.intersection(CONTRIBUTION_LABEL_WEIGHTS)
        if not contribution_labels:
            return None
        if self._has_competing_pull_request(repository.name, issue.number, pull_requests):
            return None

        reasons = [
            f"label: {label}"
            for label in sorted(contribution_labels | labels.intersection(QUALITY_LABEL_WEIGHTS))
        ]
        label_score = sum(CONTRIBUTION_LABEL_WEIGHTS[label] for label in contribution_labels)
        quality_score = sum(
            QUALITY_LABEL_WEIGHTS[label] for label in labels.intersection(QUALITY_LABEL_WEIGHTS)
        )
        popularity_score = min(math.log10(max(repository.stars, 1)) * 10.0, 60.0)
        age_days = max((now - issue.updated_at).total_seconds() / 86_400, 0.0)
        freshness_score = max(30.0 - age_days / 6.0, 0.0)
        discussion_penalty = min(issue.comments, 20) * 0.5

        return Candidate(
            repository=repository,
            issue=issue,
            score=round(
                label_score
                + quality_score
                + popularity_score
                + freshness_score
                - discussion_penalty,
                1,
            ),
            reasons=tuple(reasons),
        )

    @staticmethod
    def _has_competing_pull_request(
        repository: str,
        issue_number: int,
        pull_requests: list[PullRequest],
    ) -> bool:
        """Detect open pull requests that claim to close the issue."""

        escaped_repository = re.escape(repository)
        pattern = re.compile(
            rf"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+"
            rf"(?:{escaped_repository})?#?{issue_number}\b",
            re.IGNORECASE,
        )
        return any(
            pattern.search(f"{pull_request.title}\n{pull_request.body}")
            for pull_request in pull_requests
        )
