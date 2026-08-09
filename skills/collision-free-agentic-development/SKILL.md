---
name: collision-free-agentic-development
description: Use when setting up or operating parallel local development stacks for applications, branches, clones, or Git worktrees. Builds collision-free Docker Compose environments with non-root hot reload, label-driven Caddy ingress, TLS, and isolated state.
license: MIT
compatibility: Requires Python 3.11+ and Docker Compose 2.x using Linux containers. Supports Linux, macOS Docker Desktop, and Windows Docker Desktop/WSL2.
metadata:
  author: "Brotal LLC"
  version: "1.0.0"
  platforms: "linux,macos,windows"
---

# Collision-Free Agentic Development

## Overview

Build local development environments that multiple humans or coding agents can run concurrently without stealing ports, containers, hostnames, volumes, source mounts, databases, caches, or certificates from one another.

The architecture uses:

- one machine-level Caddy Docker Proxy ingress on ports 80/443;
- one deterministic Compose project identity per worktree;
- unique, environment-backed hostnames per routed service;
- non-root framework-native hot-reload containers;
- no application host-port publishing;
- project-scoped dependencies and build artifacts;
- either shared data servers with isolated namespaces or per-worktree data services;
- rendered-config and end-to-end verification before declaring success.

This skill is compatible with the Agent Skills `SKILL.md` format. Its Python helper uses only the standard library and works on Linux, macOS, and Windows Docker Desktop.

## When to Use

Load this skill when:

- creating a Compose-based local or development environment;
- making several Git worktrees, clones, branches, or agents runnable in parallel;
- adding `dotnet watch`, Next.js/Vite, Python reload, Air, cargo-watch, or another watcher to containers;
- putting local services behind Caddy Docker Proxy with HTTPS;
- diagnosing a dev hostname that serves the wrong branch, stale labels, 502s, root-owned files, or database cross-talk;
- choosing shared versus per-worktree databases/caches.

Do not use this as a production deployment guide. The topology can resemble production, but production needs separate threat modeling, secret management, backup/restore, availability, image pinning, and rollout controls.

## Non-Negotiable Invariants

1. **Unique project identity.** Every worktree sets `COMPOSE_PROJECT_NAME` and `STACK_ID`; path-derived hash prevents same-name clone collisions.
2. **No fixed application container names.** Never set `container_name` in reusable app stacks.
3. **One shared ingress, zero app ports.** Only Caddy publishes 80/443; routed services join ingress and expose container ports only.
4. **One owner per hostname.** Different services get different hostnames unless one route owner defines the complete path tree.
5. **Hostnames are configuration.** Every `caddy` label uses a required `.env` variable such as `${WEB_HOST:?WEB_HOST required}`.
6. **Steady-state dev containers are non-root.** Build as root if needed; run the watcher and app as an explicit non-root UID/GID.
7. **Source is mounted from the current worktree.** Dependencies and environment-specific outputs live in project volumes/tmpfs, not shared host `node_modules`, `obj`, `bin`, `.next`, or `target` trees.
8. **Mutable state is namespaced.** Separate DB/schema/role, cache prefix, queue namespace, object prefix, and migration history per worktree—or run per-worktree services.
9. **Rendered Compose is authoritative.** Run `docker compose config --quiet` before mutation and inspect `config --format json` when behavior differs from source.
10. **Recreate after object-config changes.** `docker compose restart` cannot apply labels, env, mounts, user, network, command, or image changes.

See [architecture.md](references/architecture.md) for the full collision matrix.

## Procedure

Resolve this installed skill's absolute directory through the active agent/client and assign it once for copied commands.

Bash/Zsh:

```bash
export SKILL_DIR=/absolute/path/to/collision-free-agentic-development
```

PowerShell:

```powershell
$SKILL_DIR = "C:\absolute\path\to\collision-free-agentic-development"
```

### 1. Inspect before editing

Determine:

- repository root and current worktree path;
- framework/project manifests and exact application startup projects;
- container listen ports and required health/readiness paths;
- existing Compose files, `.env` precedence, project name, volumes, and external networks;
- whether a Caddy Docker Proxy ingress already exists;
- certificate mode: internal CA, public HTTP-01, or Cloudflare DNS-01;
- data mode: shared servers with unique namespaces or per-worktree services;
- framework origin/CORS/HMR allowlists for the final HTTPS hostnames.

Do not guess paths, commands, users, or ports from the template. Adapt them to the repository.

### 2. Install the app templates

Copy `templates/app/` into the repository, or use the helper from the skill directory:

```bash
python "$SKILL_DIR/scripts/devstack.py" scaffold --target .
```

The command refuses to overwrite files unless `--force` is explicit. For existing Compose stacks, merge surgically instead of replacing application logic.

Customize:

- `src/App.Api/App.Api.csproj` and `/workspace/web` paths;
- API/web ports and Caddy upstream labels;
- package manager (`npm install`, `npm ci`, pnpm, Yarn, NuGet restore policy);
- startup and health commands;
- browser-visible API URL and server-internal service URL;
- generated artifact paths;
- service names and any internal dependencies.

For .NET, merge `Directory.Build.props.example` into the repository's `Directory.Build.props`; `CONTAINER_BUILD_ROOT` only works when MSBuild consumes it.

### 3. Start or verify the shared ingress

If no compatible Caddy Docker Proxy exists, copy `templates/ingress/` to a machine-level infrastructure directory, create gitignored `.env` from `.env.example`, and run:

```bash
docker compose config --quiet
docker compose up --detach
```

The default image is `ghcr.io/skb50bd/caddy`, which includes Caddy Docker Proxy and Cloudflare DNS support. Pin a tested release/digest for durable use. A compatible upstream/custom image may be substituted.

The ingress network name must match `INGRESS_NETWORK` in every worktree. Preserve Caddy's data volume; it contains certificates and the internal CA. See [tls-and-dns.md](references/tls-and-dns.md) before exposing ports or adding a Cloudflare token.

### 4. Generate the worktree-local `.env`

Run inside each worktree:

```bash
python "$SKILL_DIR/scripts/devstack.py" init \
  --project-dir . \
  --project-name myapp \
  --domain localhost \
  --tls internal \
  --data-mode worktree
```

PowerShell equivalent:

```powershell
python "$SKILL_DIR/scripts/devstack.py" init --project-dir . --project-name myapp --domain localhost --tls internal --data-mode worktree
```

Useful alternatives (single-line form works in Bash, Zsh, and PowerShell):

```bash
# Public names, DNS-01 token remains in ingress .env only
python "$SKILL_DIR/scripts/devstack.py" init --project-dir . --project-name myapp --domain dev.example.com --tls cloudflare --data-mode shared

# Public ACME using HTTP-01/TLS-ALPN-01
python "$SKILL_DIR/scripts/devstack.py" init --project-dir . --project-name myapp --domain dev.example.com --tls http --data-mode worktree
```

The helper writes:

- native `COMPOSE_PATH_SEPARATOR` and a complete `COMPOSE_FILE` list;
- `COMPOSE_PROJECT_NAME`, `STACK_ID`, and optional `COMPOSE_PROFILES`;
- unique API/web hostnames;
- non-root UID/GID;
- unique PostgreSQL database and Redis prefix;
- selected ingress/data network names.

For shared data mode it intentionally leaves `POSTGRES_PASSWORD` empty. Supply the matching shared-server credential before startup. Never commit `.env`; commit `.env.example` with placeholders.

### 5. Select framework-native hot reload

Use an SDK/dev image that contains the compiler and watcher. Do not put a production runtime image in a loop and call it hot reload.

| Stack | Dev image | Steady-state command |
|---|---|---|
| C# / F# / ASP.NET Core | matching `mcr.microsoft.com/dotnet/sdk` | `dotnet watch --non-interactive --project <project> run` |
| Next.js / Vite / Node | matching Node LTS image | package install, then `npm run dev -- --hostname 0.0.0.0` |
| FastAPI / Starlette | Python dev image with project deps | `uvicorn <module>:app --reload --host 0.0.0.0` |
| Django | Python dev image with project deps | `python manage.py runserver 0.0.0.0:<port>` |
| Go | Go image with Air installed at build time | `air` |
| Rust | Rust image with cargo-watch or bacon | `cargo watch -x run` or `bacon run` |
| Spring Boot | matching JDK build image | Maven/Gradle run task with DevTools |
| Rails | Ruby dev image with bundle cache | `bundle exec rails server -b 0.0.0.0` |

Pin language/toolchain versions to the repository. Enable polling on Docker Desktop or network filesystems only when native events fail. Keep watcher output visible in container logs.

Do not nest a dependency volume or generated-output tmpfs beneath a bind-mounted source parent and assume image ownership survives. Docker can create the hidden host mountpoint as root before the non-root watcher starts. The Node template mounts source at `/source`, builds an image-owned workspace at `/workspace/web` using non-root symlinks, and mounts `node_modules`/`.next` there. Adapt that separation for other toolchains with nested writable outputs.

### 6. Validate before starting

```bash
docker compose config --quiet
python "$SKILL_DIR/scripts/devstack.py" doctor --project-dir .
```

The doctor renders Compose JSON and rejects common collisions: application `container_name`, published ports, root/no-user hot-reload services, missing ingress attachment, missing Caddy upstream labels, and duplicate Caddy hosts.

Review the final model manually as well:

```bash
docker compose config --format json
docker compose images
docker compose ps --all
```

### 7. Start and verify

Initial start:

```bash
python "$SKILL_DIR/scripts/devstack.py" up --project-dir . --build
```

Wait for dependency installation, compilation, migrations, and application readiness. Then verify:

- every hot-reload container's runtime user is non-root;
- bind-mount source points to this worktree;
- Caddy and routed services share ingress;
- app containers publish no host ports;
- each HTTPS hostname resolves and returns the expected app;
- browser console has no mixed-content/origin failures;
- edit a visible source string and prove the browser updates without manual rebuild/restart;
- DB/cache writes appear only in this worktree's namespace;
- sibling worktree remains available and unchanged.

A container marked `Up` and a homepage returning 200 are necessary, not sufficient.

## Daily Operations

```bash
# Plain start; COMPOSE_FILE comes from this worktree's .env
docker compose up --detach

# Compose/env/label/network/user/mount change
docker compose config --quiet
docker compose up --detach --force-recreate

# One app service, leave stateful dependencies alone
docker compose up --detach --force-recreate --no-deps api

# Rebuild when Dockerfile/dependencies/image-baked content changed
docker compose up --detach --build --force-recreate --no-deps api

# Stop this worktree, preserve project volumes
docker compose down
```

Equivalent helper commands are `up`, `apply`, `recreate`, and `down`. Never add `--volumes` to routine shutdown.

## Data Mode Decision

- **Shared servers:** use `compose.shared-data.yaml`; create a unique database/role and cache namespace. Lowest resource cost.
- **Per-worktree services:** use `compose.worktree-data.yaml` and profile `worktree-data`. Strongest migration/destructive-test isolation.
- **Automated integration tests:** use disposable Testcontainers, not either developer data mode.

See [data-isolation.md](references/data-isolation.md) for SQL, cache, queue, and cleanup guidance.

## Common Pitfalls

1. Changing only hostname while reusing `COMPOSE_PROJECT_NAME`, volumes, fixed ports, and DB names. That is cosmetic isolation.
2. Using comma-separated `COMPOSE_FILE`. Linux/macOS use `:`; Windows uses `;`; `COMPOSE_PATH_SEPARATOR` can override it.
3. Running `compose.dev.yaml` alone even though it is an overlay and depends on `compose.yaml`.
4. Putting Cloudflare credentials in app `.env` or app containers. Only ingress needs the token.
5. Expecting two containers with the same `caddy` hostname to merge routes.
6. Running hot reload as root to silence permissions failures. Fix ownership/mount design instead.
7. Sharing host/container `obj`, `bin`, `.next`, `node_modules`, or `target` outputs.
8. Calling container siblings through `localhost`; use private Compose service DNS.
9. Using `docker compose restart` after labels, env, mounts, users, networks, commands, or images changed.
10. Trusting a running watcher parent when the child app crashed; verify the listen socket and routed readiness.
11. Deleting volumes during routine cleanup or pruning before checking Compose project labels.
12. Forgetting that shell-exported Compose/env values outrank the worktree `.env`.

Use [troubleshooting.md](references/troubleshooting.md) for the evidence-first decision tree and [cross-platform.md](references/cross-platform.md) for OS-specific behavior.

## Verification Checklist

- [ ] Unique `COMPOSE_PROJECT_NAME` and `STACK_ID` for every live worktree
- [ ] No application `container_name`, fixed volume name, fixed network name, or published port
- [ ] `.env` is gitignored; `.env.example` contains no secrets
- [ ] Every routed hostname comes from a required env var and has one route owner
- [ ] Every routed service joins the configured ingress network
- [ ] Every steady-state hot-reload service runs as non-root
- [ ] Dependencies/build outputs are isolated from host and sibling worktrees
- [ ] `docker compose config --quiet` and `devstack.py doctor` pass
- [ ] Correct TLS mode, DNS path, token scope, and client trust verified
- [ ] Shared state has unique DB/cache/queue/object namespaces, or state is per-worktree
- [ ] Real HTTPS request, browser/HMR edit, and data-isolation checks pass
- [ ] A second worktree runs concurrently without changing the first
