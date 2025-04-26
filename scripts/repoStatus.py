import os
import requests
import re

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_ORG = os.environ["GITHUB_ORG"]
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

SONARCLOUD_URL = "https://sonarcloud.io"

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

def generate_table(repos):
    table = "| Repo | Quality Gate | Coverage | Bugs | Code Smells | Security |\n"
    table += "|:-----|:-------------|:---------|:-----|:------------|:---------|\n"
    for repo in sorted(repos):
        project_key = f"{GITHUB_ORG}_{repo}"

        repo_link = f"[{repo}](https://github.com/{GITHUB_ORG}/{repo})"
        sonar_link = f"[🔎](https://sonarcloud.io/dashboard?id={project_key})"

        quality_gate = f"![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=alert_status)"
        coverage = f"![Coverage](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=coverage)"
        bugs = f"![Bugs](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=bugs)"
        code_smells = f"![Code Smells](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=code_smells)"
        security = f"![Security](https://sonarcloud.io/api/project_badges/measure?project={project_key}&metric=security_hotspots)"

        table += f"| {repo_link} {sonar_link} | {quality_gate} | {coverage} | {bugs} | {code_smells} | {security} |\n"
    return table

def update_readme(table):
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    # Match "# Repo Status" until next "#", "##" or end of file
    new_content = re.sub(
        r"(# Repo Status\s*)(.*?)(^#|\Z)", 
        rf"\1\n\n{table}\n\n\3", 
        content, 
        flags=re.DOTALL | re.MULTILINE
    )

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new_content)

def main():
    repos = fetch_repos()
    table = generate_table(repos)
    update_readme(table)

if __name__ == "__main__":
    main()
