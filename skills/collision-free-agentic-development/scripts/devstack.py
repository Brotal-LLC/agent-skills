#!/usr/bin/env python3
"""Cross-platform helpers for collision-free Compose development stacks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
APP_TEMPLATES = SKILL_DIR / "templates" / "app"


@dataclass(frozen=True)
class Identity:
    stack_id: str
    postgres_db: str
    redis_prefix: str
    web_host_label: str
    api_host_label: str


def normalise_slug(value: str, *, max_length: int = 63) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    slug = re.sub(r"-+", "-", slug) or "dev"
    if not slug[0].isalnum():
        slug = f"dev-{slug}"
    return slug[:max_length].rstrip("-")


def derive_identity(project_path: Path, project_name: str | None = None) -> Identity:
    canonical = project_path.expanduser().resolve(strict=False)
    project = normalise_slug(project_name or canonical.parent.name or "app", max_length=20)
    worktree = normalise_slug(canonical.name or "worktree", max_length=26)
    digest = hashlib.sha256(os.path.normcase(str(canonical)).encode("utf-8")).hexdigest()[:8]
    stack_id = normalise_slug(f"{project}-{worktree}-{digest}")
    postgres_db = re.sub(r"[^a-z0-9_]", "_", stack_id.replace("-", "_"))[:63]
    if not postgres_db[0].isalpha():
        postgres_db = f"d_{postgres_db}"[:63]
    return Identity(
        stack_id=stack_id,
        postgres_db=postgres_db,
        redis_prefix=f"{stack_id}:",
        web_host_label=f"web-{stack_id}",
        api_host_label=f"api-{stack_id}",
    )


def compose_separator(platform_name: str | None = None) -> str:
    name = (platform_name or platform.system()).casefold()
    return ";" if name.startswith("win") else ":"


def default_uid_gid(platform_name: str | None = None) -> tuple[int, int]:
    target = (platform_name or platform.system()).casefold()
    if target.startswith("win") or not all(hasattr(os, name) for name in ("getuid", "getgid")):
        return 1000, 1000
    uid, gid = os.getuid(), os.getgid()
    return (uid if uid > 0 else 1000), (gid if gid > 0 else 1000)


def _hostname(label: str, domain: str) -> str:
    clean_domain = domain.casefold().strip().strip(".")
    if not clean_domain:
        raise ValueError("domain cannot be empty")
    if clean_domain == "localhost":
        return f"{label}.localhost"
    dns_label = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
    if len(clean_domain) > 253 or any(
        not dns_label.fullmatch(part) for part in clean_domain.split(".")
    ):
        raise ValueError(f"invalid DNS domain: {domain}")
    hostname = f"{label}.{clean_domain}"
    if len(hostname) > 253 or not dns_label.fullmatch(label):
        raise ValueError(f"generated hostname is invalid: {hostname}")
    return hostname


def _network_name(value: str, variable: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise ValueError(f"invalid {variable}: {value!r}")
    return value


def build_env(
    project_dir: Path,
    *,
    project_name: str | None,
    domain: str,
    tls_mode: str,
    data_mode: str,
    platform_name: str,
    ingress_network: str = "agent-ingress",
    shared_data_network: str = "agent-data",
) -> dict[str, str]:
    if data_mode not in {"worktree", "shared"}:
        raise ValueError(f"unsupported data mode: {data_mode}")
    if domain.strip().lower().strip(".") == "localhost" and tls_mode != "internal":
        raise ValueError("localhost supports only internal TLS; use a resolvable domain for ACME")
    ingress_network = _network_name(ingress_network, "ingress network")
    shared_data_network = _network_name(shared_data_network, "shared data network")
    identity = derive_identity(project_dir, project_name)
    separator = compose_separator(platform_name)
    uid, gid = default_uid_gid(platform_name)
    files = ["compose.yaml", "compose.dev.yaml"]
    files.append(
        "compose.worktree-data.yaml" if data_mode == "worktree" else "compose.shared-data.yaml"
    )
    if tls_mode == "internal":
        files.append("compose.tls-internal.yaml")
    elif tls_mode == "cloudflare":
        files.append("compose.tls-cloudflare.yaml")
    elif tls_mode != "http":
        raise ValueError(f"unsupported TLS mode: {tls_mode}")

    values = {
        "COMPOSE_PATH_SEPARATOR": separator,
        "COMPOSE_FILE": separator.join(files),
        "COMPOSE_PROJECT_NAME": identity.stack_id,
        "COMPOSE_PROFILES": "worktree-data" if data_mode == "worktree" else "",
        "STACK_ID": identity.stack_id,
        "INGRESS_NETWORK": ingress_network,
        "SHARED_DATA_NETWORK": shared_data_network,
        "DEV_UID": str(uid),
        "DEV_GID": str(gid),
        "WEB_HOST": _hostname(identity.web_host_label, domain),
        "API_HOST": _hostname(identity.api_host_label, domain),
        "POSTGRES_DB": identity.postgres_db,
        "POSTGRES_USER": "dev",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24) if data_mode == "worktree" else "",
        "REDIS_PREFIX": identity.redis_prefix,
        "DB_HOST": "dev-postgres" if data_mode == "worktree" else "postgres",
        "REDIS_HOST": "dev-redis" if data_mode == "worktree" else "redis",
    }
    return values


def render_env(values: Mapping[str, str]) -> str:
    order = (
        "COMPOSE_PATH_SEPARATOR",
        "COMPOSE_FILE",
        "COMPOSE_PROJECT_NAME",
        "COMPOSE_PROFILES",
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
    )
    for key, value in values.items():
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError(f"invalid environment key: {key!r}")
        if any(character in value for character in ("\r", "\n", "\0")):
            raise ValueError(f"environment value for {key} contains a forbidden control character")
    missing = [key for key in order if key not in values]
    if missing:
        raise ValueError(f"missing environment values: {', '.join(missing)}")
    lines = [
        "# Generated by collision-free-agentic-development/scripts/devstack.py.",
        "# This file is worktree-local and must remain gitignored.",
    ]
    lines.extend(f"{key}={values[key]}" for key in order)
    return "\n".join(lines) + "\n"


def write_env(path: Path, values: Mapping[str, str], *, force: bool = False) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite {path}; pass --force after reviewing it")
    path.write_text(render_env(values), encoding="utf-8", newline="\n")


def _service_networks(service: Mapping[str, Any]) -> set[str]:
    networks = service.get("networks", {})
    if isinstance(networks, list):
        return {str(value) for value in networks}
    if isinstance(networks, dict):
        return {str(value) for value in networks}
    return set()


def _labels(service: Mapping[str, Any]) -> dict[str, str]:
    labels = service.get("labels", {})
    if isinstance(labels, dict):
        return {str(key): str(value) for key, value in labels.items()}
    result: dict[str, str] = {}
    if isinstance(labels, list):
        for value in labels:
            key, _, item = str(value).partition("=")
            result[key] = item
    return result


def infer_ingress_network(config: Mapping[str, Any]) -> str:
    networks = config.get("networks", {})
    if not isinstance(networks, dict):
        return "agent-ingress"
    logical_ingress = networks.get("ingress", {})
    if isinstance(logical_ingress, dict) and logical_ingress.get("name"):
        return str(logical_ingress["name"])

    candidates: set[str] = set()
    for raw_service in config.get("services", {}).values():
        service = raw_service if isinstance(raw_service, dict) else {}
        labels = _labels(service)
        if not labels.get("caddy"):
            continue
        for key in _service_networks(service):
            raw_network = networks.get(key, {})
            network = raw_network if isinstance(raw_network, dict) else {}
            if network.get("external") and network.get("name"):
                candidates.add(str(network["name"]))
    return candidates.pop() if len(candidates) == 1 else "agent-ingress"


def audit_compose_config(config: Mapping[str, Any], ingress_network: str) -> list[str]:
    issues: list[str] = []
    claimed_hosts: dict[str, str] = {}
    ingress_keys = {ingress_network}
    for key, raw_network in config.get("networks", {}).items():
        network = raw_network if isinstance(raw_network, dict) else {}
        if key == ingress_network or network.get("name") == ingress_network:
            ingress_keys.add(str(key))
    for service_name, raw_service in config.get("services", {}).items():
        service = raw_service if isinstance(raw_service, dict) else {}
        labels = _labels(service)
        hot_reload = labels.get("dev.agent-skills.hot-reload", "").casefold() == "true"
        if service.get("container_name"):
            issues.append(f"{service_name}: container_name defeats Compose project isolation")
        if service.get("ports"):
            issues.append(f"{service_name}: published port can collide across worktrees")
        if hot_reload:
            user = str(service.get("user", "")).strip().casefold()
            if not user or user == "root" or user == "0" or user.startswith("0:"):
                issues.append(f"{service_name}: hot-reload dev service runs as root or has no user")
            if not (_service_networks(service) & ingress_keys):
                issues.append(
                    f"{service_name}: routed dev service is missing ingress "
                    f"network {ingress_network}"
                )
            if "caddy.reverse_proxy" not in labels:
                issues.append(f"{service_name}: routed dev service lacks caddy.reverse_proxy")
        host = labels.get("caddy", "").strip()
        if host:
            if host in claimed_hosts:
                issues.append(
                    f"{service_name}: caddy host {host} is also claimed by {claimed_hosts[host]}"
                )
            claimed_hosts[host] = str(service_name)
    return issues


def compose_command(args: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=cwd,
        text=True,
        check=False,
    )


def validate_compose(project_dir: Path) -> None:
    result = compose_command(["config", "--quiet"], cwd=project_dir)
    if result.returncode:
        raise RuntimeError("docker compose config --quiet failed")


def rendered_compose(project_dir: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=project_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "docker compose config failed")
    return json.loads(result.stdout)


def copy_templates(target: Path, *, force: bool = False) -> list[Path]:
    sources = sorted(source for source in APP_TEMPLATES.rglob("*") if source.is_file())
    destinations = [(source, target / source.relative_to(APP_TEMPLATES)) for source in sources]
    conflicts = [destination for _, destination in destinations if destination.exists()]
    if conflicts and not force:
        paths = ", ".join(str(path) for path in conflicts)
        raise FileExistsError(f"refusing partial scaffold; existing paths: {paths}")
    copied: list[Path] = []
    for source, destination in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied.append(destination)
    return copied


def trust_instructions(cert: Path, platform_name: str | None = None) -> str:
    name = (platform_name or platform.system()).casefold()
    quoted = str(cert.resolve())
    if name.startswith("win"):
        return (
            "Run elevated PowerShell:\n"
            f'Import-Certificate -FilePath "{quoted}" '
            "-CertStoreLocation Cert:\\LocalMachine\\Root"
        )
    if name == "darwin":
        return (
            "Run:\n"
            f"sudo security add-trusted-cert -d -r trustRoot "
            f'-k /Library/Keychains/System.keychain "{quoted}"'
        )
    return (
        "Debian/Ubuntu:\n"
        f'sudo install -m 0644 "{quoted}" /usr/local/share/ca-certificates/agent-ingress.crt\n'
        "sudo update-ca-certificates\n\n"
        "Fedora/RHEL:\n"
        f'sudo cp "{quoted}" /etc/pki/ca-trust/source/anchors/agent-ingress.crt\n'
        "sudo update-ca-trust"
    )


def _project_dir(value: str) -> Path:
    return Path(value).expanduser().resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    identity = subparsers.add_parser("identity", help="derive collision-free worktree identity")
    identity.add_argument("--project-dir", default=".")
    identity.add_argument("--project-name")

    init = subparsers.add_parser("init", help="write a worktree-local .env")
    init.add_argument("--project-dir", default=".")
    init.add_argument("--project-name")
    init.add_argument("--domain", default="localhost")
    init.add_argument("--tls", choices=("internal", "cloudflare", "http"), default="internal")
    init.add_argument("--data-mode", choices=("worktree", "shared"), default="worktree")
    init.add_argument("--platform", default=platform.system())
    init.add_argument("--ingress-network", default="agent-ingress")
    init.add_argument("--shared-data-network", default="agent-data")
    init.add_argument("--output", default=".env")
    init.add_argument("--force", action="store_true")

    scaffold = subparsers.add_parser("scaffold", help="copy app Compose templates")
    scaffold.add_argument("--target", default=".")
    scaffold.add_argument("--force", action="store_true")

    doctor = subparsers.add_parser("doctor", help="validate and audit rendered Compose")
    doctor.add_argument("--project-dir", default=".")
    doctor.add_argument("--ingress-network")

    for command, help_text in (
        ("up", "start the selected stack"),
        ("apply", "force-recreate the selected stack after config changes"),
        ("down", "stop the stack without deleting volumes"),
    ):
        sub = subparsers.add_parser(command, help=help_text)
        sub.add_argument("--project-dir", default=".")
        if command in {"up", "apply"}:
            sub.add_argument("--build", action="store_true")

    recreate = subparsers.add_parser("recreate", help="force-recreate app services only")
    recreate.add_argument("services", nargs="+")
    recreate.add_argument("--project-dir", default=".")
    recreate.add_argument("--build", action="store_true")

    export_ca = subparsers.add_parser("export-ca", help="copy Caddy internal root CA to the host")
    export_ca.add_argument("--container", default="agent-ingress-caddy")
    export_ca.add_argument("--output", default="agent-ingress-root.crt")
    export_ca.add_argument("--platform", default=platform.system())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "identity":
            value = derive_identity(_project_dir(args.project_dir), args.project_name)
            print(json.dumps(value.__dict__, indent=2))
            return 0
        if args.command == "init":
            project_dir = _project_dir(args.project_dir)
            output = Path(args.output)
            if not output.is_absolute():
                output = project_dir / output
            values = build_env(
                project_dir,
                project_name=args.project_name,
                domain=args.domain,
                tls_mode=args.tls,
                data_mode=args.data_mode,
                platform_name=args.platform,
                ingress_network=args.ingress_network,
                shared_data_network=args.shared_data_network,
            )
            write_env(output, values, force=args.force)
            print(f"wrote {output}")
            if args.data_mode == "shared":
                print("set POSTGRES_PASSWORD in the generated .env before starting the stack")
            return 0
        if args.command == "scaffold":
            paths = copy_templates(_project_dir(args.target), force=args.force)
            print(f"copied {len(paths)} template files")
            return 0
        if args.command == "doctor":
            project_dir = _project_dir(args.project_dir)
            validate_compose(project_dir)
            config = rendered_compose(project_dir)
            ingress_network = args.ingress_network or infer_ingress_network(config)
            issues = audit_compose_config(config, ingress_network)
            if issues:
                print("\n".join(f"ERROR: {issue}" for issue in issues), file=sys.stderr)
                return 1
            print("Compose config is collision-safe")
            return 0
        if args.command in {"up", "apply", "down", "recreate"}:
            project_dir = _project_dir(args.project_dir)
            if args.command == "down":
                return compose_command(["down"], cwd=project_dir).returncode
            validate_compose(project_dir)
            command = ["up", "--detach"]
            if args.command in {"apply", "recreate"}:
                command.append("--force-recreate")
            if getattr(args, "build", False):
                command.append("--build")
            if args.command == "recreate":
                command.extend(["--no-deps", *args.services])
            return compose_command(command, cwd=project_dir).returncode
        if args.command == "export-ca":
            output = Path(args.output).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [
                    "docker",
                    "cp",
                    f"{args.container}:/data/caddy/pki/authorities/local/root.crt",
                    str(output),
                ],
                text=True,
                check=False,
            )
            if result.returncode:
                return result.returncode
            print(f"exported {output}\n\n{trust_instructions(output, args.platform)}")
            return 0
    except (FileExistsError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
