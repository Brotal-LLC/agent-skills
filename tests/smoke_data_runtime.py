#!/usr/bin/env python3
"""Run the per-worktree PostgreSQL/Redis profile and prove isolation basics."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "collision-free-agentic-development"
SCRIPT = SKILL / "scripts" / "devstack.py"
COMPOSE_OVERRIDE_KEYS = {
    "COMPOSE_FILE",
    "COMPOSE_PATH_SEPARATOR",
    "COMPOSE_PROFILES",
    "COMPOSE_PROJECT_NAME",
    "STACK_ID",
    "INGRESS_NETWORK",
    "SHARED_DATA_NETWORK",
    "DEV_UID",
    "DEV_GID",
    "WEB_HOST",
    "API_HOST",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "REDIS_PREFIX",
    "DB_HOST",
    "REDIS_HOST",
}


def load_devstack():
    spec = importlib.util.spec_from_file_location("collision_free_devstack", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def clean_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in COMPOSE_OVERRIDE_KEYS}


def run(
    command: list[str], cwd: Path | None = None, *, emit_stdout: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=clean_environment(),
        text=True,
        capture_output=True,
        check=False,
    )
    if emit_stdout and result.stdout:
        print(result.stdout, end="")
    if result.returncode and result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result


def main() -> int:
    if shutil.which("docker") is None:
        print("docker CLI is required", file=sys.stderr)
        return 2

    devstack = load_devstack()
    tmp = tempfile.mkdtemp(prefix="agent-skills-data-smoke-")
    app = Path(tmp) / "app"
    try:
        shutil.copytree(SKILL / "templates" / "app", app)
        values = devstack.build_env(
            app,
            project_name="data-smoke",
            domain="localhost",
            tls_mode="internal",
            data_mode="worktree",
            platform_name="linux",
        )
        devstack.write_env(app / ".env", values)

        up = run(
            [
                "docker",
                "compose",
                "up",
                "--detach",
                "--wait",
                "--wait-timeout",
                "90",
                "dev-postgres",
                "dev-redis",
            ],
            app,
        )
        if up.returncode:
            return up.returncode

        postgres_id = run(["docker", "compose", "ps", "--quiet", "dev-postgres"], app)
        if postgres_id.returncode or not postgres_id.stdout.strip():
            print("PostgreSQL container ID was not resolved", file=sys.stderr)
            return 1
        inspected = run(["docker", "inspect", postgres_id.stdout.strip()], app, emit_stdout=False)
        if inspected.returncode:
            return inspected.returncode
        container = json.loads(inspected.stdout)[0]
        destinations = {mount["Destination"] for mount in container["Mounts"]}
        if "/var/lib/postgresql" not in destinations:
            print(
                f"unexpected PostgreSQL mount destinations: {sorted(destinations)}", file=sys.stderr
            )
            return 1
        if "/var/lib/postgresql/data" in destinations:
            print("legacy PostgreSQL data mount was rendered", file=sys.stderr)
            return 1

        sql = run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "dev-postgres",
                "psql",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                values["POSTGRES_USER"],
                "-d",
                values["POSTGRES_DB"],
                "-Atc",
                "SELECT current_database();",
            ],
            app,
        )
        if sql.returncode or sql.stdout.strip() != values["POSTGRES_DB"]:
            print("PostgreSQL logical database isolation check failed", file=sys.stderr)
            return 1

        key = f"{values['REDIS_PREFIX']}runtime-smoke"
        set_result = run(
            ["docker", "compose", "exec", "-T", "dev-redis", "redis-cli", "SET", key, "ok"],
            app,
        )
        get_result = run(
            ["docker", "compose", "exec", "-T", "dev-redis", "redis-cli", "GET", key],
            app,
        )
        if set_result.returncode or get_result.returncode or get_result.stdout.strip() != "ok":
            print("Redis namespaced key check failed", file=sys.stderr)
            return 1

        print(
            f"worktree data runtime smoke passed for database {values['POSTGRES_DB']} "
            f"and prefix {values['REDIS_PREFIX']}"
        )
        return 0
    finally:
        if (app / ".env").exists():
            run(
                ["docker", "compose", "down", "--volumes", "--remove-orphans"],
                app,
            )
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
