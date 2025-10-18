import os
import requests
import re

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_ORG = os.environ["GITHUB_ORG"]
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}


# --------------------------------------------------------
# API: Repositories abrufen
# --------------------------------------------------------
def fetch_repos():
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/orgs/{GITHUB_ORG}/repos?type=public&per_page=100&page={page}"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        repos.extend([repo["name"] for repo in data])
        page += 1
    return repos


# --------------------------------------------------------
# API: Letzten Workflow-Run-Status abrufen
# --------------------------------------------------------
def fetch_latest_run_status(repo):
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/actions/runs?per_page=1"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 404:
            return "—"  # Kein Workflow vorhanden
        response.raise_for_status()
        data = response.json()
        runs = data.get("workflow_runs", [])
        if not runs:
            return "—"
        run = runs[0]
        status = run.get("conclusion") or run.get("status") or "—"
        return status
    except Exception as e:
        print(f"[WARN] Konnte Run-Status für {repo} nicht abrufen: {e}")
        return "—"


# --------------------------------------------------------
# Markdown-Tabelle generieren
# --------------------------------------------------------
def generate_table(repos):
    table = "| Repo + Status | Workflow | Quality Gate | Coverage | Duplication | Maintainability | Reliability |\n"
    table += "|:--------------|:----------|:-------------|:---------|:------------|:----------------|:------------|\n"
    
    for repo in sorted(repos):
        project_key = f"{GITHUB_ORG}_{repo}"

        # Repo-Link & SonarCloud-Link
        repo_link = f"[{repo}](https://github.com/{GITHUB_ORG}/{repo}) [🔎](https://sonarcloud.io/dashboard?id={project_key})"

        # GitHub Actions Status
        status = fetch_latest_run_status(repo)
        if status.lower() == "success":
            status_badge = f"![Run: success](https://img.shields.io/badge/run-success-brightgreen)"
        elif status.lower() in ("failure", "failed"):
            status_badge = f"![Run: failed](https://img.shields.io/badge/run-failed-red)"
        elif status.lower() == "cancelled":
            status_badge = f"![Run: cancelled](https://img.shields.io/badge/run-cancelled-lightgrey)"
        else:
            status_badge = f"![Run: unknown](https://img.shields.io/badge/run-unknown-grey)"

        # Mini-Badges: Security, Bugs, Vulnerabilities
        security = f"![Security](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=security_rating)"
        bugs = f"![Bugs](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=bugs)"
        vulnerabilities = f"![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=vulnerabilities)"
        mini_badges = f"{security} {bugs} {vulnerabilities}"

        # Weitere Badges
        quality_gate = f"![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=alert_status)"
        coverage = f"![Coverage](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=coverage)"
        duplication = f"![Duplication](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=duplicated_lines_density)"
        maintainability = f"![Maintainability](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=sqale_rating)"
        reliability = f"![Reliability](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=reliability_rating)"

        # Zeile zusammensetzen
        table += (
            f"| {repo_link}<br>{mini_badges} "
            f"| {status_badge} "
            f"| {quality_gate} | {coverage} | {duplication} | {maintainability} | {reliability} |\n"
        )
    
    return table


# --------------------------------------------------------
# README aktualisieren
# --------------------------------------------------------
def update_readme(table):
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    new_content = re.sub(
        r"(# Repo Status\s*)(.*?)(^#|\Z)", 
        rf"\1\n\n{table}\n\n\3", 
        content, 
        flags=re.DOTALL | re.MULTILINE
    )

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new_content)


# --------------------------------------------------------
# Main
# --------------------------------------------------------
def main():
    repos = fetch_repos()
    table = generate_table(repos)
    update_readme(table)


if __name__ == "__main__":
    main()
