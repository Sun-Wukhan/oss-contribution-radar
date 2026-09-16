"""Ports that separate discovery logic from external data providers."""

from typing import Protocol

from contribution_radar.models import Issue, PullRequest, Repository


class RepositoryGateway(Protocol):
    """Interface required by the contribution-ranking service."""

    def get_repository(self, name: str) -> Repository:
        """Return metadata for one public repository."""

    def list_open_issues(self, name: str) -> list[Issue]:
        """Return open issues and pull requests from a repository."""

    def list_open_pull_requests(self, name: str) -> list[PullRequest]:
        """Return open pull requests used for duplicate-work detection."""
