#!/usr/bin/env python3
"""Build and run the Node dev template to prove rootless mount ownership."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "collision-free-agentic-development"
SCRIPT = SKILL / "scripts" / "devstack.py"


def load_devstack():
    spec = importlib.util.spec_from_file_location("devstack_node_smoke", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    "DB_HOST",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "REDIS_HOST",
    "REDIS_PREFIX",
}


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value for key, value in os.environ.items() if key not in COMPOSE_OVERRIDE_KEYS
    }
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode and result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result


def run_web(app: Path) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "docker",
            "compose",
            "up",
            "--no-deps",
            "--abort-on-container-exit",
            "--exit-code-from",
            "web",
            "web",
        ],
        app,
    )


def main() -> int:
    if shutil.which("docker") is None:
        print("docker CLI is required", file=sys.stderr)
        return 2
    devstack = load_devstack()
    network = f"agent-skills-smoke-{uuid.uuid4().hex[:10]}"
    created_network = False
    tmp = tempfile.mkdtemp(prefix="agent-skills-node-smoke-")
    app = Path(tmp) / "app"
    try:
        shutil.copytree(SKILL / "templates" / "app", app)
        web = app / "web"
        web.mkdir()
        (web / "package.json").write_text(
            json.dumps(
                {
                    "name": "rootless-template-smoke",
                    "private": True,
                    "scripts": {"dev": "node server.js"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (web / "server.js").write_text(
            "const fs = require('node:fs');\n"
            "fs.writeFileSync('/source/runtime-proof.json', JSON.stringify({\n"
            "  uid: process.getuid(),\n"
            "  cwd: process.cwd(),\n"
            "  deps: fs.existsSync('/workspace/web/node_modules'),\n"
            "  generated: fs.existsSync('/workspace/web/.next')\n"
            "}));\n",
            encoding="utf-8",
        )
        values = devstack.build_env(
            app,
            project_name="node-smoke",
            domain="localhost",
            tls_mode="internal",
            data_mode="worktree",
            platform_name="linux",
            ingress_network=network,
        )
        devstack.write_env(app / ".env", values)

        network_result = run(["docker", "network", "create", network])
        if network_result.returncode:
            return network_result.returncode
        created_network = True

        build = run(["docker", "compose", "build", "web"], app)
        if build.returncode:
            return build.returncode
        up = run_web(app)
        if up.returncode:
            return up.returncode

        first_container = run(["docker", "compose", "ps", "--all", "--quiet", "web"], app)
        if first_container.returncode or not first_container.stdout.strip():
            print("Node container ID was not resolved", file=sys.stderr)
            return 1

        proof_path = web / "runtime-proof.json"
        if not proof_path.is_file():
            print("runtime proof was not written through the source mount", file=sys.stderr)
            return 1
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        expected_uid = os.getuid() if hasattr(os, "getuid") else 1000
        if proof != {
            "uid": expected_uid,
            "cwd": "/workspace/web",
            "deps": True,
            "generated": True,
        }:
            print(f"unexpected runtime proof: {proof}", file=sys.stderr)
            return 1
        leaked = [path.name for path in (web / "node_modules", web / ".next") if path.exists()]
        if leaked:
            print(f"generated mountpoints leaked into host source: {leaked}", file=sys.stderr)
            return 1

        proof_path.unlink()
        restart = run_web(app)
        if restart.returncode:
            print("same-container Node restart failed", file=sys.stderr)
            return restart.returncode
        second_container = run(["docker", "compose", "ps", "--all", "--quiet", "web"], app)
        if second_container.returncode:
            return second_container.returncode
        if second_container.stdout.strip() != first_container.stdout.strip():
            print("Node restart unexpectedly recreated the container", file=sys.stderr)
            return 1
        if not proof_path.is_file():
            print("Node restart did not execute the application", file=sys.stderr)
            return 1

        print(f"rootless Node runtime and same-container restart passed as uid {expected_uid}")
        return 0
    finally:
        if (app / ".env").exists():
            run(
                [
                    "docker",
                    "compose",
                    "down",
                    "--volumes",
                    "--remove-orphans",
                    "--rmi",
                    "local",
                ],
                app,
            )
        if created_network:
            run(["docker", "network", "rm", network])
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
