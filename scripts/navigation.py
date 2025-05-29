import requests
import os

GITHUB_ORG = os.getenv("GITHUB_ORG")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

TOPICS = ["tsa", "ocm-w-stack", "ocm","aas","orchestration","cam","catalogue","portal","pcm-mobile","pcm-cloud"]

README_PATH = "README.md"
INSERT_ANCHOR = "# XFSC Navigation"

# GitHub API Header
headers = {
    "Accept": "application/vnd.github.mercy-preview+json",
    "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else None,
}


def fetch_all_repos(org):
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/orgs/{org}/repos?per_page=100&page={page}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"GitHub API Error: {response.status_code} - {response.text}")
        page_repos = response.json()
        if not page_repos:
            break
        repos.extend(page_repos)
        page += 1
    return repos


def fetch_topics(repo_full_name):
    url = f"https://api.github.com/repos/{repo_full_name}/topics"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []
    return response.json().get("names", [])


def generate_markdown_table(topic_map):
    lines = ["| Topic | Repositories |", "|-------|--------------|"]
    for topic, repos in topic_map.items():
        if repos:
            repo_md = "<br>".join(repos)  # Für GitHub-kompatiblen Zeilenumbruch
            lines.append(f"| {topic} | {repo_md} |")
    return "\n".join(lines)


def update_readme_section(readme_path, anchor, new_section):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    if anchor not in content:
        raise ValueError(f"Anchor '{anchor}' nicht in README gefunden.")

    pre, _, post = content.partition(anchor)
    post_lines = post.splitlines()

    # Behalte die Überschrift, lösche alles darunter bis zur nächsten H1/H2
    new_post_lines = []
    keep = False
    for line in post_lines:
        if line.strip().startswith("#") and line.strip() != anchor:
            keep = True
        if keep:
            new_post_lines.append(line)

    updated_content = pre + anchor + "\n\n" + new_section + "\n\n" + "\n".join(new_post_lines)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated_content)
    print(f"README.md erfolgreich aktualisiert unter '{anchor}'.")


def main():
    all_repos = fetch_all_repos(GITHUB_ORG)
    topic_map = {topic.upper(): [] for topic in TOPICS}

    for repo in all_repos:
        full_name = repo["full_name"]
        name = repo["name"]
        topics = fetch_topics(full_name)
        for topic in TOPICS:
            if topic in topics:
                markdown_link = f"[{name}](https://github.com/{full_name})"
                topic_map[topic.upper()].append(markdown_link)

    md_table = generate_markdown_table(topic_map)
    update_readme_section(README_PATH, INSERT_ANCHOR, md_table)


if __name__ == "__main__":
    main()
