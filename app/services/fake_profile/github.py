from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from app.core.logging import get_logger

log = get_logger(__name__)

_GITHUB_API = "https://api.github.com"
_FRESH_ACCOUNT_DAYS = 90
_LANG_MATCH_TOP_N = 10

_USERNAME_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))",
    re.IGNORECASE,
)


def extract_username_from_text(text: str | None) -> str | None:
    if not text:
        return None
    m = _USERNAME_RE.search(text)
    if not m:
        return None
    username = m.group(1).strip("/")
    # GitHub usernames don't end with a dash
    return username.rstrip("-") or None


@dataclass
class GitHubResult:
    checked: bool
    username: str | None = None
    profile_url: str | None = None
    account_age_days: int | None = None
    public_repos: int | None = None
    followers: int | None = None
    top_languages: list[str] = field(default_factory=list)
    claimed_skills_found_in_repos: list[str] = field(default_factory=list)
    claimed_skills_missing_in_repos: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


class GitHubChecker:
    def __init__(self, token: str = "", timeout: float = 10.0):
        self.token = token
        self.timeout = timeout

    def check(self, username: str, claimed_skills: list[str]) -> GitHubResult:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            with httpx.Client(timeout=self.timeout, headers=headers) as client:
                profile = client.get(f"{_GITHUB_API}/users/{username}")
                if profile.status_code == 404:
                    return GitHubResult(
                        checked=True,
                        username=username,
                        error=f"GitHub user '{username}' not found.",
                    )
                if profile.status_code == 403 and "rate limit" in profile.text.lower():
                    return GitHubResult(
                        checked=True,
                        username=username,
                        error="GitHub API rate limit exceeded. Set GITHUB_TOKEN to raise it.",
                    )
                profile.raise_for_status()
                p = profile.json()

                repos = client.get(
                    f"{_GITHUB_API}/users/{username}/repos",
                    params={"per_page": 100, "sort": "updated", "type": "owner"},
                )
                repos.raise_for_status()
                r_list = repos.json()
        except httpx.TimeoutException:
            return GitHubResult(
                checked=True, username=username, error="GitHub API request timed out."
            )
        except httpx.HTTPStatusError as exc:
            return GitHubResult(
                checked=True,
                username=username,
                error=f"GitHub returned HTTP {exc.response.status_code}.",
            )
        except httpx.HTTPError as exc:
            return GitHubResult(
                checked=True, username=username, error=f"GitHub request failed: {exc}"
            )

        created_at = _parse_iso(p.get("created_at"))
        now = datetime.now(timezone.utc)
        age_days = int((now - created_at).total_seconds() // 86400) if created_at else None

        lang_counts: Counter[str] = Counter()
        for r in r_list:
            if r.get("language"):
                lang_counts[r["language"].lower()] += 1
        top_languages = [lang for lang, _ in lang_counts.most_common(_LANG_MATCH_TOP_N)]

        claimed_norm = [s.strip().lower() for s in claimed_skills if s and s.strip()]
        repo_haystack = " ".join(
            (r.get("name") or "") + " " + (r.get("description") or "") for r in r_list
        ).lower()

        found: list[str] = []
        missing: list[str] = []
        for skill in claimed_norm:
            if skill in top_languages or skill in repo_haystack:
                found.append(skill)
            else:
                missing.append(skill)

        warnings: list[str] = []
        if age_days is not None and age_days < _FRESH_ACCOUNT_DAYS:
            warnings.append(
                f"GitHub account is only {age_days} days old — unusually fresh for a senior profile."
            )
        if p.get("public_repos", 0) == 0:
            warnings.append("GitHub account has 0 public repositories.")
        if claimed_norm and missing and len(missing) == len(claimed_norm):
            warnings.append(
                "None of the resume's listed skills appear in any public repo or top language."
            )

        return GitHubResult(
            checked=True,
            username=username,
            profile_url=p.get("html_url"),
            account_age_days=age_days,
            public_repos=p.get("public_repos"),
            followers=p.get("followers"),
            top_languages=top_languages,
            claimed_skills_found_in_repos=found,
            claimed_skills_missing_in_repos=missing,
            warnings=warnings,
        )


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
