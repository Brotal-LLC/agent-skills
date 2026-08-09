---
name: containerized-development-tooling
description: Use when language servers, file watchers, health checks, logs, or debuggers must work reliably against source and toolchains inside Docker Compose or devcontainer environments.
license: MIT
compatibility: Requires Docker or a compatible dev-container runtime. IDE attachment and debugger commands vary by language and editor; verify against pinned tool versions.
metadata:
  author: "Brotal LLC"
  version: "1.0.0"
  platforms: "linux,macos,windows"
  parent: "collision-free-agentic-development"
  companions: "compose-development-environments,rootless-dev-container-filesystems,dev-container-package-caches"
---

# Containerized Development Tooling

## When to Use

Load this skill when the app runs in a container but the LSP sees different dependencies, hot reload misses edits, a watcher parent survives after its child crashes, logs are too noisy to diagnose, or debugger attachment introduces port collisions.

## One-Environment Rule

The editor, language server, compiler, package manager, generated files, and debugger should agree on:

- source path;
- SDK/toolchain version;
- dependency tree;
- environment/build flags;
- generated-code location;
- runtime path mapping.

The most reliable model is a devcontainer/remote-container editor with the LSP running inside the same development image and non-root workspace as the application. A host LSP plus container-only dependencies can work, but it is a separate supported topology that needs mirrored SDKs and path mapping—not an accidental hybrid.

## LSP Workflow

1. Pin the language server and SDK in the development image or reproducible devcontainer feature.
2. Set `remoteUser`/runtime user consistently with workspace ownership.
3. Open the intended worktree inside the container; inspect the live bind source first.
4. Keep generated code and dependency metadata where both build and LSP can read them.
5. Configure container paths in source maps and debugger mappings.
6. Restart/reload the LSP after dependency, generated-code, project-graph, or toolchain changes.
7. Prove navigation, diagnostics, rename, and build on the same symbol; syntax coloring alone proves essentially that colors exist.

See [lsp-logs-and-debugging.md](references/lsp-logs-and-debugging.md) for topology decisions and command recipes.

## Watchers and Hot Reload

Use framework-native watchers (`dotnet watch`, Vite/Next dev server, `uvicorn --reload`, Air, cargo-watch, Spring DevTools). Run them in the foreground as the container's main non-root process so output reaches container logs.

Native filesystem events are preferred. Enable polling only after reproducing missed events on Docker Desktop, WSL/network filesystems, or synchronized workspaces; polling has CPU and battery costs.

A container marked `Up` may contain a living watcher whose child app failed. Read logs and probe the actual listen socket/readiness route.

## Logs and Event Timeline

```bash
docker compose ps --all
docker compose logs --since 10m --timestamps service-name
docker inspect --format '{{json .State}}' container-id
docker inspect --format '{{json .Config.User}}' container-id
docker inspect --format '{{json .Mounts}}' container-id
docker inspect --format '{{json .NetworkSettings.Networks}}' container-id
docker events --since 10m
```

Use bounded time ranges and preserve timestamps. Correlate:

- source edit;
- watcher rebuild/restart;
- process exit/restart count;
- health transition;
- proxy request/error;
- debugger attach/detach.

Do not stream every container forever into an agent context. Collect the smallest window that preserves causality. Never emit a bare `docker inspect` result into agent/debug logs: `.Config.Env` can contain credentials. Request narrowly formatted fields and redact sensitive values before persistence.

## Health and Readiness

- **Process alive:** container state only.
- **healthcheck:** local dependency/application probe used by Docker.
- **readiness:** app can serve requests with required dependencies.
- **acceptance:** real routed hostname, auth/origin, and user-visible behavior work.

Use cheap, deterministic health checks. Keep external CDN/public DNS dependencies out of local process health unless they are truly mandatory.

## Debugger Attachment

Prefer IDE/container attachment or `docker compose exec`, with the debugger bound to container loopback. A listener on `0.0.0.0` inside an application attached to both its private project network and the shared ingress network is reachable from sibling ingress members; calling it "project-only" does not make the packets sentimental.

If the debugger cannot use container loopback, run it in a dedicated debug sidecar/service attached only to the project-private network. Do not attach that sidecar to the shared ingress network. If a host debug port is unavoidable:

- bind to loopback;
- allocate it per worktree rather than hardcoding globally;
- require authentication where supported;
- remove/disable it outside development;
- never route it through Caddy or cloudflared.

Verify the boundary from both sides: attachment through `docker compose exec` or the remote-container IDE must succeed, while a connection from a disposable probe attached only to the shared ingress network must fail. Also inspect the rendered Compose model and live network attachments to prove there is no debugger port publication, Caddy label, or tunnel route. The rendered model must prove no app-service debugger is bound to a wildcard address and no debug sidecar is attached to the shared ingress network.

Run debugger processes as the same non-root identity. Extra Linux capabilities such as `SYS_PTRACE` weaken isolation; add only for the service/session that requires them and remove afterward.

## Common Gotchas

- Host LSP indexes host `node_modules` while runtime uses a named volume.
- LSP uses one SDK while `docker compose build` installs another.
- Generated protobuf/OpenAPI code changed but the watcher/LSP retained stale output.
- File events do not cross Docker Desktop sharing reliably; blind polling hides the root cause and burns resources.
- `docker compose logs --tail` omits the earlier crash that triggered a restart loop; use `--since` plus inspect restart count.
- Healthcheck uses `localhost` for a sibling dependency; inside a container that means itself.
- Debugger path maps point to `/app` while the live source is `/workspace`.
- Debug port `9229`, `5005`, or similar collides across worktrees.
- Debug listener binds `0.0.0.0` in an app attached to shared ingress, exposing it across worktrees without any host port.
- A devcontainer startup hook installs latest global tools, making every rebuild a new environment.

## Verification Checklist

- [ ] Live worktree mount, SDK, LSP, dependency tree, and generated paths agree
- [ ] LSP navigation/diagnostics match a real container build
- [ ] Visible source edit triggers exactly the intended watcher rebuild
- [ ] Container log timeline includes watcher and child application state
- [ ] healthcheck, readiness, and routed acceptance are tested separately
- [ ] Debugger is non-root, narrowly reachable, and correctly path-mapped
- [ ] Shared-ingress probe cannot reach the debugger; loopback/private attachment still succeeds
- [ ] No fixed host debug port collides with sibling worktrees
- [ ] Tooling survives stop/start and recreation predictably
