#!/usr/bin/env python3
"""Repository-wide quality gate with no third-party runtime dependencies."""

from __future__ import annotations

import argparse
import compileall
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ALLOWED_FRONTMATTER = {
    "name",
    "description",
    "license",
    "allowed-tools",
    "metadata",
    "compatibility",
}
PRIVATE_PATTERN = re.compile(
    r"(?:aamar\.cloud|shakib\.io|skb\.bd|10\.(?:\d{1,3}\.){2}\d{1,3}|discord\.com/channels)",
    re.IGNORECASE,
)
SECRET_PATTERN = re.compile(
    r"(?:ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----)"
)
TEXT_SUFFIXES = {
    "",
    ".dev",
    ".example",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def repository_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    )
    return [REPO / line for line in result.stdout.splitlines() if line]


def check_text(path: Path) -> list[str]:
    if path.suffix.casefold() not in TEXT_SUFFIXES and path.name not in {
        "Dockerfile",
        "LICENSE",
    }:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    relative = path.relative_to(REPO)
    issues: list[str] = []
    if text and not text.endswith("\n"):
        issues.append(f"{relative}: missing final newline")
    for number, line in enumerate(text.splitlines(), 1):
        if line.rstrip(" \t") != line:
            issues.append(f"{relative}:{number}: trailing whitespace")
    if PRIVATE_PATTERN.search(text):
        issues.append(f"{relative}: private infrastructure identifier in public artifact")
    if SECRET_PATTERN.search(text):
        issues.append(f"{relative}: secret-shaped value in public artifact")
    return issues


def frontmatter_fields(skill_md: Path) -> tuple[set[str], list[str]]:
    text = skill_md.read_text(encoding="utf-8")
    issues: list[str] = []
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return set(), [f"{skill_md.relative_to(REPO)}: invalid frontmatter delimiters"]
    block = text.split("---\n", 2)[1]
    fields = {
        match.group(1)
        for line in block.splitlines()
        if (match := re.match(r"^([a-z][a-z0-9-]*):", line))
    }
    name_match = re.search(r"(?m)^name:\s*([^\s]+)\s*$", block)
    if not name_match:
        issues.append(f"{skill_md.relative_to(REPO)}: missing name")
    else:
        name = name_match.group(1)
        if name != skill_md.parent.name:
            issues.append(f"{skill_md.relative_to(REPO)}: name must match parent directory")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
            issues.append(f"{skill_md.relative_to(REPO)}: invalid skill name")
    description = re.search(r"(?m)^description:\s*(.+)$", block)
    if not description or len(description.group(1).strip()) > 1024:
        issues.append(f"{skill_md.relative_to(REPO)}: invalid description")
    compatibility = re.search(r"(?m)^compatibility:\s*(.+)$", block)
    if compatibility and len(compatibility.group(1).strip()) > 500:
        issues.append(f"{skill_md.relative_to(REPO)}: compatibility exceeds 500 characters")
    return fields, issues


def check_skills() -> list[str]:
    issues: list[str] = []
    for skill_md in sorted((REPO / "skills").glob("*/SKILL.md")):
        fields, field_issues = frontmatter_fields(skill_md)
        issues.extend(field_issues)
        unknown = fields - ALLOWED_FRONTMATTER
        missing = {"name", "description"} - fields
        if unknown:
            issues.append(f"{skill_md.relative_to(REPO)}: unsupported fields {sorted(unknown)}")
        if missing:
            issues.append(f"{skill_md.relative_to(REPO)}: missing fields {sorted(missing)}")
        if len(skill_md.read_text(encoding="utf-8").splitlines()) > 500:
            issues.append(f"{skill_md.relative_to(REPO)}: SKILL.md exceeds 500 lines")
    return issues


def run_tests() -> int:
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=REPO,
        check=False,
    ).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-tests", action="store_true")
    args = parser.parse_args()

    issues: list[str] = []
    for path in repository_files():
        if path.is_file():
            issues.extend(check_text(path))
    issues.extend(check_skills())
    if not compileall.compile_dir(REPO, quiet=1):
        issues.append("Python compilation failed")
    if issues:
        print("\n".join(f"ERROR: {issue}" for issue in issues), file=sys.stderr)
        return 1
    if not args.no_tests and run_tests():
        return 1
    print("repository quality gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
