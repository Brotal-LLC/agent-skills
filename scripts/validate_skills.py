#!/usr/bin/env python3
"""Validate every installable Agent Skill in the repository."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "skills"


def discover_skills() -> list[Path]:
    return sorted(path.parent for path in SKILLS.glob("*/SKILL.md"))


def validator_command() -> list[str] | None:
    validator = shutil.which("agentskills")
    if validator is not None:
        return [validator]
    uvx = shutil.which("uvx")
    if uvx is not None:
        return [uvx, "--from", "skills-ref==0.1.1", "agentskills"]
    return None


def main() -> int:
    validator = validator_command()
    if validator is None:
        print("ERROR: agentskills and uvx executables not found", file=sys.stderr)
        return 2

    skills = discover_skills()
    if not skills:
        print("ERROR: no skills/*/SKILL.md packages found", file=sys.stderr)
        return 1

    failures: list[str] = []
    for skill in skills:
        relative = skill.relative_to(REPO)
        print(f"==> validating {relative}", flush=True)
        result = subprocess.run(
            [*validator, "validate", str(skill)],
            cwd=REPO,
            check=False,
        )
        if result.returncode:
            failures.append(str(relative))

    if failures:
        print(
            f"ERROR: {len(failures)} skill validation failure(s): " + ", ".join(failures),
            file=sys.stderr,
        )
        return 1

    print(f"validated {len(skills)} skill package(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
