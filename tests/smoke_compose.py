#!/usr/bin/env python3
"""Render every app mode and the ingress template with Docker Compose."""

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


def load_devstack():
    spec = importlib.util.spec_from_file_location("devstack_smoke", SCRIPT)
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
    "CADDY_IMAGE",
    "CLOUDFLARE_API_TOKEN",
}


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value for key, value in os.environ.items() if key not in COMPOSE_OVERRIDE_KEYS
    }
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )


def main() -> int:
    if shutil.which("docker") is None:
        print("docker CLI is required", file=sys.stderr)
        return 2
    devstack = load_devstack()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        app = root / "app"
        ingress = root / "ingress"
        shutil.copytree(SKILL / "templates" / "app", app)
        shutil.copytree(SKILL / "templates" / "ingress", ingress)

        for platform_name in ("linux", "windows"):
            for data_mode in ("worktree", "shared"):
                for tls_mode in ("internal", "cloudflare", "http"):
                    values = devstack.build_env(
                        app,
                        project_name="smoke",
                        domain="dev.example.com",
                        tls_mode=tls_mode,
                        data_mode=data_mode,
                        platform_name=platform_name,
                    )
                    if data_mode == "shared":
                        values["POSTGRES_PASSWORD"] = "compose-smoke-placeholder"
                    devstack.write_env(app / ".env", values, force=True)
                    result = run(["docker", "compose", "config", "--quiet"], app)
                    if result.returncode:
                        print(
                            f"{platform_name}/{data_mode}/{tls_mode}: {result.stderr}",
                            file=sys.stderr,
                        )
                        return result.returncode
                    rendered = run(["docker", "compose", "config", "--format", "json"], app)
                    if rendered.returncode:
                        print(rendered.stderr, file=sys.stderr)
                        return rendered.returncode
                    issues = devstack.audit_compose_config(
                        json.loads(rendered.stdout), "agent-ingress"
                    )
                    if issues:
                        print("\n".join(issues), file=sys.stderr)
                        return 1
                    print(
                        f"rendered app mode: platform={platform_name}, "
                        f"data={data_mode}, tls={tls_mode}"
                    )

        shutil.copyfile(ingress / ".env.example", ingress / ".env")
        ingress_result = run(["docker", "compose", "config", "--quiet"], ingress)
        if ingress_result.returncode:
            print(ingress_result.stderr, file=sys.stderr)
            return ingress_result.returncode
        print("rendered ingress template")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
