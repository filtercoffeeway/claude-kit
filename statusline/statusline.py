#!/usr/bin/env python3
"""Claude Code status line.

Reads the session JSON that Claude Code pipes on stdin and prints one line:

    Opus 5.5 │ cache 52m │ ctx 45.2k/200k 23% │ $1.84 │ PR #12 open ✓ │ MyTools ⎇ main

Segments:
  - model, folder, git branch
  - PR number + state for the current branch (via `gh`, cached and refreshed in the background)
  - context size: tokens in the last request vs. the context window
  - prompt cache time left: last API call + cache TTL (5m or 1h, detected from the transcript)
  - API-equivalent cost of the session (cost.total_cost_usd from Claude Code)

Only uses the standard library. Never raises: a broken segment is skipped.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "mytools" / "statusline"
PR_CACHE_TTL = 60  # seconds before a PR lookup is refreshed
TRANSCRIPT_TAIL_BYTES = 1_000_000

RESET = "\033[0m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
SEP = f" {DIM}│{RESET} "


def color(text, c):
    return f"{c}{text}{RESET}"


def fmt_tokens(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(n)


def run(cmd, cwd, timeout=1.0):
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


# ---------------------------------------------------------------- transcript

def read_usage_entries(transcript_path):
    """Return (timestamp, usage) for main-thread assistant messages, oldest first."""
    entries = []
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - TRANSCRIPT_TAIL_BYTES))
            lines = f.read().splitlines()
    except Exception:
        return entries
    for raw in lines:
        if b'"usage"' not in raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue  # first line may be cut by the tail seek
        if obj.get("isSidechain") or obj.get("type") != "assistant":
            continue
        usage = (obj.get("message") or {}).get("usage")
        ts = obj.get("timestamp")
        if usage and ts:
            entries.append((ts, usage))
    return entries


def parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# ---------------------------------------------------------------- segments

def seg_model(data):
    name = (data.get("model") or {}).get("display_name")
    return color(name, MAGENTA) if name else None


def seg_location(data, cwd):
    folder = os.path.basename((data.get("workspace") or {}).get("current_dir") or cwd)
    branch = run(["git", "branch", "--show-current"], cwd, timeout=0.5)
    out = color(folder, BLUE)
    if branch:
        out += " " + color(f"⎇ {branch}", CYAN)
    return out, branch


def seg_context(data, entries):
    cw = data.get("context_window") or {}
    size = cw.get("context_window_size") or (1_000_000 if "[1m]" in str(data.get("model")) else 200_000)
    current = cw.get("current_usage")
    if isinstance(current, dict):
        used = sum(current.get(k) or 0 for k in
                   ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    elif entries:
        u = entries[-1][1]
        used = sum(u.get(k) or 0 for k in
                   ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    else:
        return None
    pct = used / size * 100 if size else 0
    c = GREEN if pct < 50 else YELLOW if pct < 80 else RED
    return f"ctx {fmt_tokens(used)}/{fmt_tokens(size)} " + color(f"{pct:.0f}%", c)


def cache_ttl_seconds(entries):
    """1h if the session has written 1h cache entries recently, else 5m."""
    for _, u in reversed(entries[-20:]):
        cc = u.get("cache_creation") or {}
        if cc.get("ephemeral_1h_input_tokens"):
            return 3600
        if cc.get("ephemeral_5m_input_tokens"):
            return 300
    return 300


def seg_cache(entries):
    if not entries:
        return None
    try:
        last = parse_ts(entries[-1][0])
    except Exception:
        return None
    ttl = cache_ttl_seconds(entries)
    left = ttl - (datetime.now(timezone.utc) - last).total_seconds()
    if left <= 0:
        return color("cache expired", RED)
    m, s = divmod(int(left), 60)
    text = f"cache {m}m" if m >= 5 else f"cache {m}m{s:02d}s"
    c = GREEN if left > ttl * 0.5 else YELLOW if left > 120 else RED
    return color(text, c)


def seg_cost(data):
    cost = (data.get("cost") or {}).get("total_cost_usd")
    if cost is None:
        return None
    return color(f"${cost:.2f}", YELLOW)


# ---------------------------------------------------------------- PR lookup

def pr_cache_file(cwd, branch):
    root = run(["git", "rev-parse", "--show-toplevel"], cwd, timeout=0.5) or cwd
    key = hashlib.sha1(f"{root}\0{branch}".encode()).hexdigest()[:16]
    return CACHE_DIR / f"pr-{key}.json", root


def refresh_pr(cache_file, root, branch):
    """Run in a detached child: query gh and write the cache file."""
    info = {"fetched": time.time(), "pr": None}
    out = run(["gh", "pr", "view", branch, "--json",
               "number,state,isDraft,reviewDecision,statusCheckRollup"], root, timeout=15)
    if out:
        try:
            info["pr"] = json.loads(out)
        except Exception:
            pass
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(info))
    tmp.replace(cache_file)


def spawn_refresh(cache_file, root, branch):
    lock = cache_file.with_suffix(".lock")
    try:
        if lock.exists() and time.time() - lock.stat().st_mtime < 30:
            return  # a refresh is already running
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        lock.touch()
        subprocess.Popen(
            [sys.executable, __file__, "--refresh-pr", str(cache_file), root, branch],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def checks_summary(rollup):
    states = []
    for c in rollup or []:
        states.append((c.get("conclusion") or c.get("state") or c.get("status") or "").upper())
    if not states:
        return ""
    if any(s in ("FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED") for s in states):
        return color(" ✗", RED)
    if any(s in ("PENDING", "IN_PROGRESS", "QUEUED", "EXPECTED", "WAITING", "") for s in states):
        return color(" ●", YELLOW)
    return color(" ✓", GREEN)


def seg_pr(cwd, branch):
    if not branch:
        return None
    cache_file, root = pr_cache_file(cwd, branch)
    info = None
    try:
        info = json.loads(cache_file.read_text())
    except Exception:
        pass
    if info is None or time.time() - info.get("fetched", 0) > PR_CACHE_TTL:
        spawn_refresh(cache_file, root, branch)
    pr = (info or {}).get("pr")
    if not pr:
        return None
    state = pr.get("state", "").lower()
    if pr.get("isDraft") and state == "open":
        state = "draft"
    c = {"open": GREEN, "draft": DIM, "merged": MAGENTA, "closed": RED}.get(state, "")
    review = {"APPROVED": " approved", "CHANGES_REQUESTED": " changes"}.get(pr.get("reviewDecision") or "", "")
    return color(f"PR #{pr.get('number')} {state}{review}", c) + checks_summary(pr.get("statusCheckRollup"))


# ---------------------------------------------------------------- main

def main():
    if len(sys.argv) == 5 and sys.argv[1] == "--refresh-pr":
        cache_file = Path(sys.argv[2])
        try:
            refresh_pr(cache_file, sys.argv[3], sys.argv[4])
        finally:
            cache_file.with_suffix(".lock").unlink(missing_ok=True)
        return

    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    cwd = data.get("cwd") or (data.get("workspace") or {}).get("current_dir") or os.getcwd()
    entries = read_usage_entries(data["transcript_path"]) if data.get("transcript_path") else []

    try:
        location, branch = seg_location(data, cwd)
    except Exception:
        location, branch = None, None

    parts = []
    for fn in (
        lambda: seg_model(data),
        lambda: seg_cache(entries),
        lambda: seg_context(data, entries),
        lambda: seg_cost(data),
        lambda: seg_pr(cwd, branch),
        lambda: location,
    ):
        try:
            seg = fn()
        except Exception:
            seg = None
        if seg:
            parts.append(seg)
    print(SEP.join(parts))


if __name__ == "__main__":
    main()
