"""Typed domain models for contribution discovery."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RepositoryTarget:
    """A public repository included in the daily discovery scan."""

    name: str
    minimum_stars: int = 1_000


@dataclass(frozen=True, slots=True)
class Repository:
    """Repository metadata used to assess project popularity and activity."""

    name: str
    url: str
    stars: int
    archived: bool


@dataclass(frozen=True, slots=True)
class Issue:
    """A normalized open issue returned by GitHub."""

    repository: str
    number: int
    title: str
    url: str
    labels: tuple[str, ...]
    assignees: tuple[str, ...]
    comments: int
    created_at: datetime
    updated_at: datetime
    is_pull_request: bool = False


@dataclass(frozen=True, slots=True)
class PullRequest:
    """An open pull request used to detect work already underway."""

    title: str
    body: str


@dataclass(frozen=True, slots=True)
class Candidate:
    """A ranked, review-gated open-source contribution opportunity."""

    repository: Repository
    issue: Issue
    score: float
    reasons: tuple[str, ...]
