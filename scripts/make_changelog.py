#!/usr/bin/env python3
"""
Vygeneruje novou sekci v CHANGELOG.md ze git commitů od posledního tagu.

Použití:
    python scripts/make_changelog.py              # vezme nejnovější tag jako verzi
    python scripts/make_changelog.py v0.9.0       # pojmenuj sekci ručně

Workflow:
    git tag v0.9.0
    python scripts/make_changelog.py v0.9.0
    git add CHANGELOG.md && git commit -m "docs: changelog v0.9.0"
"""

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

CHANGELOG = Path(__file__).parent.parent / "CHANGELOG.md"

PREFIXES = {
    "feat": "Přidáno",
    "fix": "Opraveno",
    "style": "Styl",
    "refactor": "Refaktoring",
    "docs": "Dokumentace",
    "test": "Testy",
}


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()


def get_tags() -> list[str]:
    out = run(["git", "tag", "--sort=-version:refname"])
    return [t for t in out.splitlines() if t]


def get_commits_between(from_ref: str, to_ref: str) -> list[str]:
    if from_ref:
        log_range = f"{from_ref}..{to_ref}"
    else:
        log_range = to_ref
    out = run(["git", "log", log_range, "--pretty=format:%s"])
    return [l for l in out.splitlines() if l]


def classify(commits: list[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for msg in commits:
        m = re.match(r"^(\w+)(?:\(.+?\))?:\s*(.+)", msg)
        if m:
            prefix, text = m.group(1), m.group(2)
            label = PREFIXES.get(prefix)
            if label:
                buckets.setdefault(label, []).append(text)
        else:
            buckets.setdefault("Ostatní", []).append(msg)
    return buckets


def build_section(version: str, buckets: dict[str, list[str]]) -> str:
    today = date.today().isoformat()
    lines = [f"## [{version}] — {today}", ""]
    for label, items in buckets.items():
        lines.append(f"### {label}")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def prepend_to_changelog(section: str) -> None:
    original = CHANGELOG.read_text(encoding="utf-8")
    # Vlož za první řádek (nadpis) a prázdný řádek
    parts = original.split("\n", 3)
    if len(parts) >= 3:
        new_content = parts[0] + "\n" + parts[1] + "\n" + parts[2] + "\n\n" + section + parts[3]
    else:
        new_content = section + original
    CHANGELOG.write_text(new_content, encoding="utf-8")


def main():
    tags = get_tags()
    # Verze pro novou sekci
    if len(sys.argv) > 1:
        new_version = sys.argv[1]
        # Pokud byl tag zadán a existuje, použij ho jako horní hranici
        current_tag = new_version if new_version in tags else "HEAD"
        # Předchozí tag = druhý nejnovější (nebo žádný)
        tag_index = tags.index(new_version) if new_version in tags else -1
        prev_tag = tags[tag_index + 1] if tag_index + 1 < len(tags) else None
    elif tags:
        # Bez argumentu: nejnovější tag jako horní, druhý jako spodní hranice
        current_tag = tags[0]
        new_version = current_tag
        prev_tag = tags[1] if len(tags) > 1 else None
    else:
        current_tag = "HEAD"
        new_version = "Unreleased"
        prev_tag = None

    commits = get_commits_between(prev_tag or "", current_tag)
    if not commits:
        print(f"Žádné commity mezi {prev_tag or 'začátkem'} a {current_tag}.")
        return

    buckets = classify(commits)
    section = build_section(new_version, buckets)

    print(section)
    answer = input("Přidat do CHANGELOG.md? [y/N] ").strip().lower()
    if answer == "y":
        prepend_to_changelog(section)
        print(f"CHANGELOG.md aktualizován — sekce {new_version}.")


if __name__ == "__main__":
    main()
