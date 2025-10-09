#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
xfsc_commit_scan_full.py

Scannt:
 - GitHub Org: eclipse-xfsc
 - GitLab: https://gitlab.eclipse.org/eclipse/xfsc

Erzeugt:
 - CSV pro Repo/Projekt
 - index.csv mit Übersicht und commit_count

Features:
✅ CSV-Ausgabe pro Repo
✅ index.csv mit Commit-Anzahl
✅ Resume-Modus (überspringt fertige Repos)
✅ Rate-Limit-Handhabung (GitHub & GitLab)
✅ Optional: Tokens für höhere Limits
   -> export GITHUB_TOKEN=ghp_...
   -> export GITLAB_TOKEN=glpat_...
"""

import argparse
import csv
import datetime as dt
import os
import re
import sys
import time
from pathlib import Path
import requests

# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"

def parse_iso(s: str) -> str:
    s = s.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        s += "T00:00:00Z"
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")

def wait_until(timestamp: int):
    now = int(time.time())
    delay = max(0, timestamp - now) + 3
    reset_time = dt.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"🕒 Rate limit erreicht → warte bis {reset_time} ({delay}s)", file=sys.stderr)
    time.sleep(delay)

# -------------------------------------------------------------------
# GitHub API
# -------------------------------------------------------------------

def gh_headers():
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def github_request(url, params):
    while True:
        r = requests.get(url, headers=gh_headers(), params=params)
        # Rate limit handling
        if r.status_code == 403:
            reset = r.headers.get("X-RateLimit-Reset")
            remaining = r.headers.get("X-RateLimit-Remaining", "0")
            if remaining == "0" and reset:
                wait_until(int(reset))
                continue
        if r.status_code >= 400:
            raise RuntimeError(f"GitHub Fehler {r.status_code}: {r.text}")
        return r

def gh_paginate(url, params):
    while url:
        r = github_request(url, params)
        data = r.json()
        yield from data if isinstance(data, list) else [data]
        link = r.headers.get("Link", "")
        m = re.search(r'<([^>]+)>;\s*rel="next"', link)
        url = m.group(1) if m else None
        params = {}

def gh_list_org_repos(org):
    url = f"https://api.github.com/orgs/{org}/repos"
    return list(gh_paginate(url, {"type": "all", "per_page": "100"}))

def gh_list_commits(owner, repo, since, until):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    commits = []
    for c in gh_paginate(url, {"since": since, "until": until, "per_page": "100"}):
        commit = c.get("commit", {})
        author = commit.get("author") or {}
        committer = commit.get("committer") or {}
        commits.append({
            "commit_sha": c.get("sha", ""),
            "commit_message": (commit.get("message") or "").splitlines()[0],
            "commit_url": c.get("html_url", ""),
            "committer": (c.get("author") or {}).get("login") or author.get("name") or committer.get("name") or "",
            "commit_date": author.get("date") or committer.get("date") or "",
        })
    commits.sort(key=lambda x: x["commit_date"])
    return commits

# -------------------------------------------------------------------
# GitLab API (gitlab.eclipse.org)
# -------------------------------------------------------------------

def gl_headers():
    h = {"Accept": "application/json"}
    token = os.getenv("GITLAB_TOKEN")
    if token:
        h["PRIVATE-TOKEN"] = token
    return h

def gl_api_base():
    return "https://gitlab.eclipse.org/api/v4"

def gl_paginate(url, params):
    session = requests.Session()
    page = 1
    while True:
        local = {**params, "per_page": "100", "page": str(page)}
        r = session.get(url, headers=gl_headers(), params=local)
        if r.status_code == 429:  # Rate limited (rare)
            reset = int(r.headers.get("RateLimit-Reset", "10"))
            print(f"[GitLab] Rate limit → warte {reset}s", file=sys.stderr)
            time.sleep(reset)
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"GitLab Fehler {r.status_code}: {r.text}")
        data = r.json()
        if not data:
            break
        yield from data
        total_pages = int(r.headers.get("X-Total-Pages", "1"))
        if page >= total_pages:
            break
        page += 1

def gl_group_by_path(group_path: str):
    base = gl_api_base()
    url = f"{base}/groups/{requests.utils.quote(group_path, safe='')}"
    r = requests.get(url, headers=gl_headers())
    if r.status_code == 404:
        raise RuntimeError(f"GitLab Gruppe {group_path} nicht gefunden")
    return r.json()

def gl_list_group_projects(group_path: str):
    base = gl_api_base()
    group = gl_group_by_path(group_path)
    gid = group["id"]
    url = f"{base}/groups/{gid}/projects"
    projects = {}
    for archived in ("false", "true"):
        for p in gl_paginate(url, {"archived": archived, "include_subgroups": "true"}):
            projects[p["id"]] = p
    return list(projects.values())

def gl_list_commits(pid, since, until):
    base = gl_api_base()
    url = f"{base}/projects/{pid}/repository/commits"
    commits = []
    for c in gl_paginate(url, {"since": since, "until": until}):
        commits.append({
            "commit_sha": c.get("id", ""),
            "commit_message": (c.get("title") or "").splitlines()[0],
            "commit_url": c.get("web_url", ""),
            "committer": c.get("author_name") or c.get("committer_name") or "",
            "commit_date": c.get("committed_date") or "",
        })
    commits.sort(key=lambda x: x["commit_date"])
    return commits

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    since = parse_iso(args.since)
    until = parse_iso(args.until)
    out = Path(args.out)
    ensure_dir(out)

    index_rows = []

    # ---------- GitHub ----------
    github_org = "eclipse-xfsc"
    print(f"[GitHub] Scanne Org {github_org} …", file=sys.stderr)
    try:
        repos = gh_list_org_repos(github_org)
    except Exception as e:
        print(f"[GitHub] Fehler: {e}", file=sys.stderr)
        repos = []

    for repo in repos:
        owner = (repo.get("owner") or {}).get("login") or github_org
        name = repo.get("name", "")
        full = f"{owner}/{name}"
        slug = f"github_{slugify(name)}"
        csv_file = out / f"{slug}.csv"

        if csv_file.exists() and csv_file.stat().st_size > 100:
            print(f"[GitHub] Überspringe {full} (bereits vorhanden)", file=sys.stderr)
            continue

        print(f"[GitHub] Verarbeite {full}", file=sys.stderr)
        commits = gh_list_commits(owner, name, since, until)
        commit_count = len(commits)

        with csv_file.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["commit_sha","commit_message","commit_url","committer","commit_date"])
            w.writeheader()
            w.writerows(commits)

        first, last = (commits[0], commits[-1]) if commits else ({}, {})
        index_rows.append({
            "platform": "github",
            "repo_name": full,
            "remote_url": repo.get("html_url",""),
            "csv_file": csv_file.name,
            "commit_count": commit_count,
            "first_commit_time": first.get("commit_date",""),
            "last_commit_time": last.get("commit_date",""),
            "last_committer": last.get("committer","")
        })

    # ---------- GitLab ----------
    gitlab_group = "eclipse/xfsc"
    print(f"[GitLab] Scanne Gruppe {gitlab_group} …", file=sys.stderr)
    try:
        projects = gl_list_group_projects(gitlab_group)
    except Exception as e:
        print(f"[GitLab] Fehler: {e}", file=sys.stderr)
        projects = []

    for proj in projects:
        name = proj.get("path_with_namespace") or proj.get("name")
        slug = f"gitlab_{slugify(name)}_{proj['id']}"
        csv_file = out / f"{slug}.csv"

        if csv_file.exists() and csv_file.stat().st_size > 100:
            print(f"[GitLab] Überspringe {name} (bereits vorhanden)", file=sys.stderr)
            continue

        print(f"[GitLab] Verarbeite {name}", file=sys.stderr)
        commits = gl_list_commits(proj["id"], since, until)
        commit_count = len(commits)

        with csv_file.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["commit_sha","commit_message","commit_url","committer","commit_date"])
            w.writeheader()
            w.writerows(commits)

        first, last = (commits[0], commits[-1]) if commits else ({}, {})
        index_rows.append({
            "platform": "gitlab",
            "repo_name": name,
            "remote_url": proj.get("web_url",""),
            "csv_file": csv_file.name,
            "commit_count": commit_count,
            "first_commit_time": first.get("commit_date",""),
            "last_commit_time": last.get("commit_date",""),
            "last_committer": last.get("committer","")
        })

    # ---------- Index ----------
    index_path = out / "index.csv"
    with index_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "platform","repo_name","remote_url","csv_file",
            "commit_count","first_commit_time","last_commit_time","last_committer"
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(sorted(index_rows, key=lambda x: x["repo_name"].lower()))

    print(f"✅ Fertig! Index unter {index_path}")

if __name__ == "__main__":
    main()
