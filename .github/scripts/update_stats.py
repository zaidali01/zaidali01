"""Refresh the contribution badges in README.md from the GitHub GraphQL API.

Env vars:
  GH_USER   GitHub username (default: zaidali01)
  GH_TOKEN  token used for the API call (PAT with read:user gives the most accurate count)
"""
import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone

USER = os.environ.get("GH_USER", "zaidali01")
TOKEN = os.environ["GH_TOKEN"]
README = "README.md"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch():
    """Rolling last 12 months, the same window the profile page shows."""
    now = datetime.now(timezone.utc)
    body = json.dumps({
        "query": QUERY,
        "variables": {
            "login": USER,
            "from": (now - timedelta(days=365)).isoformat(),
            "to": now.isoformat(),
        },
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = {
        d["date"]: d["contributionCount"]
        for w in cal["weeks"]
        for d in w["contributionDays"]
    }
    return cal["totalContributions"], days


def streaks(days):
    today = date.today()
    counts = {date.fromisoformat(k): v for k, v in days.items() if date.fromisoformat(k) <= today}

    # longest streak in the window
    longest = run = 0
    for d in sorted(counts):
        run = run + 1 if counts[d] > 0 else 0
        longest = max(longest, run)

    # current streak: if today has nothing yet, start counting from yesterday
    d = today if counts.get(today, 0) > 0 else today - timedelta(days=1)
    current = 0
    while counts.get(d, 0) > 0:
        current += 1
        d -= timedelta(days=1)
    return current, longest


def days_label(n):
    return f"{n}_day" if n == 1 else f"{n}_days"


def badge(label, value, color):
    return (
        f'  <img src="https://img.shields.io/badge/{label}-{value}-{color}'
        f'?style=for-the-badge&labelColor=1a1b26&logo=github&logoColor=white" />'
    )


def main():
    total, days = fetch()
    current, longest = streaks(days)
    stamp = datetime.now(timezone.utc).strftime("%b %d, %Y")

    block = (
        "<!-- STATS:START -->\n"
        '<p align="center">\n'
        f'{badge("Contributions_(last_year)", total, "7aa2f7")}\n'
        f'{badge("Current_Streak", days_label(current), "bb9af7")}\n'
        f'{badge("Longest_Streak", days_label(longest), "9ece6a")}\n'
        "</p>\n\n"
        f'<p align="center"><sub>Auto-updated daily via GitHub Actions · last run {stamp}</sub></p>\n'
        "<!-- STATS:END -->"
    )

    with open(README, encoding="utf-8") as f:
        text = f.read()
    new, n = re.subn(r"<!-- STATS:START -->.*?<!-- STATS:END -->", block, text, flags=re.S)
    if n != 1:
        raise SystemExit("STATS markers not found in README.md")
    if new != text:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new)
    print(f"total={total} current={current} longest={longest}")


if __name__ == "__main__":
    main()
