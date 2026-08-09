---
name: compose-development-environments
description: Use when designing or debugging layered Docker Compose development environments that must remain portable, independently launchable, collision-free, and safe to recreate.
license: MIT
compatibility: Requires Docker Compose 2.x with Linux containers. Covers Linux, macOS Docker Desktop, Windows Docker Desktop, and WSL2 path-separator and filesystem behavior.
metadata:
  author: "Brotal LLC"
  version: "1.0.0"
  platforms: "linux,macos,windows"
  parent: "collision-free-agentic-development"
  companions: "rootless-dev-container-filesystems,dev-container-package-caches,containerized-development-tooling,caddy-docker-proxy-routing"
---

# Compose Development Environments

## When to Use

Load this skill when splitting base/dev/data/TLS overlays, launching multiple worktrees, resolving Compose merge surprises, choosing profiles, or deciding between restart, recreate, rebuild, and teardown.

Load `collision-free-agentic-development` for the complete scaffold. This companion focuses on Compose's model, lifecycle, and diagnostics.

## Invariants

1. Each independently running checkout has a unique `COMPOSE_PROJECT_NAME`.
2. Reusable development services do not use fixed `container_name`, fixed global volume/network names, or host `ports` for routed applications.
3. `compose.dev.yaml` is an overlay, not a standalone application definition.
4. Rendered configuration is authoritative; YAML files viewed separately are merely witnesses with unreliable memories.
5. Labels, environment, mounts, users, networks, commands, and images require recreation.
6. Routine shutdown preserves volumes. Destructive state removal is explicit and scoped.
7. Optional stateful services use profiles without making core app topology ambiguous.

## Layering Contract

A portable worktree `.env` may select:

```dotenv
COMPOSE_PROJECT_NAME=app-feature-a1b2c3
COMPOSE_PATH_SEPARATOR=:
COMPOSE_FILE=compose.yaml:compose.dev.yaml:compose.worktree-data.yaml:compose.tls-internal.yaml
COMPOSE_PROFILES=worktree-data
```

Linux and macOS use `:` for `COMPOSE_FILE`; Windows uses `;`. Set `COMPOSE_PATH_SEPARATOR` when generating files across platforms.

Recommended responsibilities:

- `compose.yaml`: services, internal networks, dependency relationships, portable defaults.
- `compose.dev.yaml`: SDK images, watcher commands, source mounts, non-root user, dev-only labels.
- `compose.worktree-data.yaml`: optional per-worktree state profile and project-scoped volumes.
- `compose.shared-data.yaml`: external servers plus logical namespace configuration.
- TLS overlays: only route/certificate directives that genuinely differ by mode.

See [merge-lifecycle-and-debugging.md](references/merge-lifecycle-and-debugging.md) for merge semantics, environment precedence, and failure signatures.

## Collision-Free Shape

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.dev
    expose:
      - "8080"
    networks:
      - default
      - ingress

networks:
  ingress:
    external: true
    name: "${INGRESS_NETWORK:?INGRESS_NETWORK required}"
```

Do not add `container_name`. Let Compose prefix containers, default networks, and named volumes with the project identity. Shared external networks are the deliberate exception and must be named via environment configuration.

## Lifecycle Decision

```bash
# Prove interpolation and merge validity.
docker compose config --quiet

# Start unchanged model.
docker compose up --detach

# Labels/env/mount/user/network/command changed.
docker compose up --detach --force-recreate

# Dockerfile, dependency manifest, or image-baked tooling changed.
docker compose up --detach --build --force-recreate

# Stop while preserving project volumes.
docker compose down
```

Use `--no-deps service-name` only after proving dependencies need no corresponding change. `docker compose restart` restarts the old container object; it cannot apply object configuration.

## Profiles

Profiles are appropriate for optional databases, queues, tracing, or heavy local tools. Core services should not require a secret profile name to exist. Render both default and profile-enabled models in tests:

```bash
docker compose config --quiet
docker compose --profile worktree-data config --quiet
```

## Diagnostic Sequence

1. Capture project identity and selected files: `docker compose config --environment` and `docker compose config --format json`.
2. Compare live labels/mounts/networks with rendered values using `docker inspect`.
3. Use `docker compose ps --all` to include exited one-shot and watcher containers.
4. Read bounded logs with timestamps.
5. Inspect Docker events for restart/kill/health transitions.
6. Probe dependencies from the failing service's network namespace.
7. Recreate the smallest coherent service set and re-run the routed acceptance check.

## Common Gotchas

- Shell-exported values override `.env`; clear contaminated variables before rendering.
- Map keys such as labels merge across overlays; an omitted production label can survive in dev.
- Lists may append instead of replace. Use Compose's supported override/reset tags only after checking target-version compatibility.
- `docker compose -f compose.dev.yaml up` drops inherited environment, health checks, and networks.
- `docker compose down -v` is data destruction, not cleanup punctuation.
- A fixed external network is intentional; a fixed application volume is usually a cross-worktree collision.
- Generic service aliases on shared networks can resolve to another project's service.
- `depends_on` controls startup ordering, not application readiness unless a supported health condition is configured.
- Bind-mounted source can point at the wrong worktree even when the container name looks familiar; inspect mount sources.

## Verification Checklist

- [ ] Project name unique per independently running checkout
- [ ] Complete `COMPOSE_FILE` list portable for the current platform
- [ ] No application `container_name`, fixed host port, or global state name
- [ ] Default and profile-enabled renders pass
- [ ] Live mount source points to the intended worktree
- [ ] Object changes applied with `--force-recreate`
- [ ] Routine down preserves volumes
- [ ] Logs, health, and routed request prove the application child is ready
