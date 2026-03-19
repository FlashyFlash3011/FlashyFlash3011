#!/usr/bin/env python3
"""
GitHub Contribution Graph Filler
Generates realistic-looking commit patterns backdated across the past year.
Usage: python generate_commits.py [--repo PATH] [--intensity low|medium|high]
"""

import subprocess
import random
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Realistic commit patterns: simulate a developer's natural behavior
# Weights represent likelihood of commits on that day (0-1)
PATTERNS = {
    "low": {
        "weekday_base": 0.45,
        "weekend_base": 0.12,
        "max_commits": 4,
        "streak_chance": 0.3,
    },
    "medium": {
        "weekday_base": 0.70,
        "weekend_base": 0.25,
        "max_commits": 8,
        "streak_chance": 0.5,
    },
    "high": {
        "weekday_base": 0.88,
        "weekend_base": 0.40,
        "max_commits": 14,
        "streak_chance": 0.7,
    },
}

# Realistic commit messages a developer might write
COMMIT_MESSAGES = [
    "fix: resolve edge case in validation logic",
    "feat: add utility helper function",
    "refactor: clean up unused imports",
    "docs: update inline comments",
    "style: fix formatting inconsistencies",
    "chore: update dependencies",
    "fix: correct off-by-one error",
    "feat: implement caching layer",
    "test: add unit tests for core module",
    "fix: handle null pointer exception",
    "refactor: extract repeated logic into helper",
    "docs: improve README clarity",
    "feat: add input sanitization",
    "chore: remove deprecated code",
    "fix: resolve merge conflict artifacts",
    "feat: optimize database query",
    "style: apply consistent naming convention",
    "test: improve test coverage",
    "fix: address security vulnerability",
    "feat: add error boundary handling",
    "chore: update CI/CD configuration",
    "refactor: simplify conditional logic",
    "docs: add API documentation",
    "fix: correct timezone handling",
    "feat: implement retry mechanism",
    "chore: cleanup build artifacts",
    "fix: resolve race condition",
    "feat: add logging for debugging",
    "refactor: modularize large function",
    "test: add integration tests",
]

def get_commit_count(day: datetime, pattern: dict, streak: bool) -> int:
    """Determine how many commits to make on a given day."""
    is_weekend = day.weekday() >= 5
    base_chance = pattern["weekend_base"] if is_weekend else pattern["weekday_base"]

    # Streaks slightly boost commit likelihood
    if streak:
        base_chance = min(base_chance * 1.2, 0.95)

    if random.random() > base_chance:
        return 0

    # Weight toward smaller commit counts (more realistic)
    weights = []
    max_c = pattern["max_commits"]
    for i in range(1, max_c + 1):
        weights.append(max_c - i + 1)

    total = sum(weights)
    r = random.random() * total
    cumulative = 0
    for i, w in enumerate(weights):
        cumulative += w
        if r <= cumulative:
            return i + 1
    return 1


def generate_commit_times(date: datetime, count: int) -> list:
    """Generate realistic commit timestamps spread throughout a workday."""
    times = []
    # Most commits happen during work hours (9am-7pm) with some outliers
    work_start = 9
    work_end = 19

    for _ in range(count):
        # Occasionally commit outside work hours
        if random.random() < 0.15:
            hour = random.randint(0, 8) if random.random() < 0.5 else random.randint(20, 23)
        else:
            hour = random.randint(work_start, work_end - 1)

        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        times.append(date.replace(hour=hour, minute=minute, second=second))

    return sorted(times)


def make_commit(repo_path: Path, timestamp: datetime, message: str):
    """Create a single backdated commit."""
    # Write something to a log file to have actual changes
    log_file = repo_path / "activity.log"
    with open(log_file, "a") as f:
        f.write(f"{timestamp.isoformat()} - {message}\n")

    date_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S")

    subprocess.run(["git", "add", "activity.log"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_path,
        check=True,
        capture_output=True,
        env={
            **__import__("os").environ,
            "GIT_AUTHOR_DATE": date_str,
            "GIT_COMMITTER_DATE": date_str,
        },
    )


def run(repo_path: str, intensity: str, days_back: int, dry_run: bool):
    repo = Path(repo_path).resolve()

    if not (repo / ".git").exists():
        print(f"Initializing git repo at {repo}")
        subprocess.run(["git", "init"], cwd=repo, check=True)
        # Create initial commit
        readme = repo / "README.md"
        if not readme.exists():
            readme.write_text("# Activity\n\nThis repository tracks my development activity.\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init: initial commit"], cwd=repo, check=True)

    pattern = PATTERNS[intensity]
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    earliest = datetime(2025, 4, 25)
    start = max(today - timedelta(days=days_back), earliest)

    streak = False
    total_commits = 0
    active_days = 0

    print(f"Generating {intensity} intensity commits over {days_back} days...")
    print(f"Date range: {start.date()} → {today.date()}\n")

    current = start
    while current <= today:
        count = get_commit_count(current, pattern, streak)

        if count > 0:
            active_days += 1
            total_commits += count
            streak = random.random() < pattern["streak_chance"]
            times = generate_commit_times(current, count)

            if not dry_run:
                for ts in times:
                    msg = random.choice(COMMIT_MESSAGES)
                    make_commit(repo, ts, msg)
                    print(f"  [{ts.strftime('%Y-%m-%d %H:%M')}] {msg}")
            else:
                for ts in times:
                    print(f"  DRY [{ts.strftime('%Y-%m-%d %H:%M')}] {random.choice(COMMIT_MESSAGES)}")
        else:
            streak = False

        current += timedelta(days=1)

    print(f"\nDone! {total_commits} commits across {active_days} active days.")
    if not dry_run:
        print(f"\nNext: push to GitHub with:")
        print(f"  cd {repo}")
        print(f"  git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git")
        print(f"  git push -u origin main")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate realistic GitHub contribution history")
    parser.add_argument("--repo", default=".", help="Path to git repo (default: current dir)")
    parser.add_argument(
        "--intensity",
        choices=["low", "medium", "high"],
        default="medium",
        help="Commit frequency intensity (default: medium)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="How many days back to generate commits (default: 365)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview commits without writing them",
    )
    args = parser.parse_args()
    run(args.repo, args.intensity, args.days, args.dry_run)
