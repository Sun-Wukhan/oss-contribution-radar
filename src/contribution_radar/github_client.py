"""Read-only GitHub API adapter."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, cast

from contribution_radar.models import Issue, PullRequest, Repository

REPOSITORY_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
GITHUB_API_URL = "https://api.github.com"


class GitHubApiError(RuntimeError):
    """Raised when GitHub cannot provide valid repository data."""


class GitHubClient:
    """Fetch public repository data using GitHub's REST API."""

    def __init__(self, token: str | None = None, timeout_seconds: float = 20.0) -> None:
        """Initialize the adapter with an optional API token."""

        self._token = token
        self._timeout_seconds = timeout_seconds

    def get_repository(self, name: str) -> Repository:
        """Return popularity and lifecycle metadata for a repository."""

        payload = self._request_object(f"/repos/{self._validate_repository_name(name)}")
        return Repository(
            name=self._required_string(payload, "full_name"),
            url=self._required_string(payload, "html_url"),
            stars=self._required_int(payload, "stargazers_count"),
            archived=bool(payload.get("archived", False)),
        )

    def list_open_issues(self, name: str) -> list[Issue]:
        """Return up to 100 recently updated open issues and pull requests."""

        repository = self._validate_repository_name(name)
        payload = self._request_list(
            f"/repos/{repository}/issues?state=open&sort=updated&direction=desc&per_page=100"
        )
        return [self._parse_issue(repository, item) for item in payload]

    def list_open_pull_requests(self, name: str) -> list[PullRequest]:
        """Return up to 100 open pull requests for duplicate-work detection."""

        repository = self._validate_repository_name(name)
        payload = self._request_list(f"/repos/{repository}/pulls?state=open&per_page=100")
        return [
            PullRequest(
                title=self._required_string(item, "title"),
                body=str(item.get("body") or ""),
            )
            for item in payload
        ]

    def _request_object(self, path: str) -> dict[str, Any]:
        """Request one JSON object from GitHub."""

        payload = self._request(path)
        if not isinstance(payload, dict):
            raise GitHubApiError(f"GitHub returned an unexpected object for {path}")
        return cast(dict[str, Any], payload)

    def _request_list(self, path: str) -> list[dict[str, Any]]:
        """Request a JSON list of objects from GitHub."""

        payload = self._request(path)
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise GitHubApiError(f"GitHub returned an unexpected list for {path}")
        return cast(list[dict[str, Any]], payload)

    def _request(self, path: str) -> object:
        """Perform one authenticated, read-only API request."""

        request = urllib.request.Request(
            f"{GITHUB_API_URL}{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "oss-contribution-radar",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="GET",
        )
        if self._token:
            request.add_header("Authorization", f"Bearer {self._token}")

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                return cast(object, json.load(response))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            raise GitHubApiError(f"GitHub request failed for {path}: {error}") from error

    @staticmethod
    def _validate_repository_name(name: str) -> str:
        """Reject malformed names before interpolating them into an API path."""

        if not REPOSITORY_NAME.fullmatch(name):
            raise ValueError(f"invalid repository name: {name!r}")
        return name

    @staticmethod
    def _required_string(payload: dict[str, Any], key: str) -> str:
        """Extract a required string field from a GitHub response."""

        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise GitHubApiError(f"GitHub response is missing string field {key!r}")
        return value

    @staticmethod
    def _required_int(payload: dict[str, Any], key: str) -> int:
        """Extract a required integer field from a GitHub response."""

        value = payload.get(key)
        if not isinstance(value, int):
            raise GitHubApiError(f"GitHub response is missing integer field {key!r}")
        return value

    @classmethod
    def _parse_issue(cls, repository: str, payload: dict[str, Any]) -> Issue:
        """Normalize one item from GitHub's shared issues endpoint."""

        labels = tuple(
            str(label["name"])
            for label in payload.get("labels", [])
            if isinstance(label, dict) and isinstance(label.get("name"), str)
        )
        assignees = tuple(
            str(assignee["login"])
            for assignee in payload.get("assignees", [])
            if isinstance(assignee, dict) and isinstance(assignee.get("login"), str)
        )
        return Issue(
            repository=repository,
            number=cls._required_int(payload, "number"),
            title=cls._required_string(payload, "title"),
            url=cls._required_string(payload, "html_url"),
            labels=labels,
            assignees=assignees,
            comments=cls._required_int(payload, "comments"),
            created_at=cls._parse_datetime(cls._required_string(payload, "created_at")),
            updated_at=cls._parse_datetime(cls._required_string(payload, "updated_at")),
            is_pull_request="pull_request" in payload,
        )

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        """Parse GitHub's UTC ISO-8601 timestamps."""

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise GitHubApiError(f"invalid GitHub timestamp: {value!r}") from error
