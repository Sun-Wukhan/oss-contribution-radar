"""Unit tests for the read-only GitHub adapter."""

import io
import json
import urllib.error
import urllib.request

import pytest

from contribution_radar.github_client import GitHubApiError, GitHubClient


def test_client_normalizes_repository_issues_and_pull_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Convert representative GitHub payloads into typed domain models."""

    responses: dict[str, object] = {
        "/repos/owner/project": {
            "full_name": "owner/project",
            "html_url": "https://github.com/owner/project",
            "stargazers_count": 5_000,
            "archived": False,
        },
        "/repos/owner/project/issues?state=open&sort=updated&direction=desc&per_page=100": [
            {
                "number": 7,
                "title": "Fix a bug",
                "html_url": "https://github.com/owner/project/issues/7",
                "labels": [{"name": "help wanted"}, {"invalid": True}],
                "assignees": [{"login": "alice"}, {"invalid": True}],
                "comments": 2,
                "created_at": "2026-09-01T00:00:00Z",
                "updated_at": "2026-09-16T00:00:00Z",
                "pull_request": {"url": "https://api.github.com/example"},
            }
        ],
        "/repos/owner/project/pulls?state=open&per_page=100": [
            {"title": "Existing work", "body": None}
        ],
    }
    client = GitHubClient()
    monkeypatch.setattr(client, "_request", lambda path: responses[path])

    repository = client.get_repository("owner/project")
    issues = client.list_open_issues("owner/project")
    pull_requests = client.list_open_pull_requests("owner/project")

    assert repository.stars == 5_000
    assert issues[0].labels == ("help wanted",)
    assert issues[0].assignees == ("alice",)
    assert issues[0].is_pull_request is True
    assert pull_requests[0].body == ""


@pytest.mark.parametrize("name", ["owner", "../owner/repo", "owner/repo/name", "owner/repo?x=1"])
def test_client_rejects_invalid_repository_names(name: str) -> None:
    """Prevent malformed repository names from entering request paths."""

    with pytest.raises(ValueError, match="invalid repository name"):
        GitHubClient().get_repository(name)


def test_request_adds_token_and_decodes_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Send authenticated requests with the expected API headers."""

    captured_request: urllib.request.Request | None = None

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        """Capture the request and return a JSON response stream."""

        nonlocal captured_request
        captured_request = request
        assert timeout == 3.0
        return io.BytesIO(json.dumps({"ok": True}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    payload = GitHubClient(token="test-token", timeout_seconds=3.0)._request("/example")

    assert payload == {"ok": True}
    assert captured_request is not None
    assert captured_request.get_header("Authorization") == "Bearer test-token"
    assert captured_request.get_method() == "GET"


def test_request_wraps_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expose network failures through the adapter's stable exception."""

    def fail_urlopen(request: urllib.request.Request, timeout: float) -> object:
        """Simulate a GitHub HTTP failure."""

        del request, timeout
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)

    with pytest.raises(GitHubApiError, match="GitHub request failed"):
        GitHubClient()._request("/example")


def test_client_rejects_malformed_api_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject response shapes and required fields that violate the API contract."""

    client = GitHubClient()
    monkeypatch.setattr(client, "_request", lambda path: [] if path == "/object" else {})

    with pytest.raises(GitHubApiError, match="unexpected object"):
        client._request_object("/object")
    with pytest.raises(GitHubApiError, match="unexpected list"):
        client._request_list("/list")
    with pytest.raises(GitHubApiError, match="missing string"):
        client._required_string({}, "name")
    with pytest.raises(GitHubApiError, match="missing integer"):
        client._required_int({}, "count")
    with pytest.raises(GitHubApiError, match="invalid GitHub timestamp"):
        client._parse_datetime("not-a-date")
