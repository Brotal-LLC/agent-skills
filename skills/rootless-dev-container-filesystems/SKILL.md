---
name: rootless-dev-container-filesystems
description: Use when development containers must run non-root while bind-mounted source, named volumes, tmpfs outputs, and generated files remain writable without polluting or taking ownership of the host checkout.
license: MIT
compatibility: Requires OCI/Docker-compatible Linux containers. UID/GID behavior differs on Linux, macOS Docker Desktop, Windows Docker Desktop, and WSL2 and must be verified on the target platform.
metadata:
  author: "Brotal LLC"
  version: "1.0.0"
  platforms: "linux,macos,windows"
  parent: "collision-free-agentic-development"
  companions: "compose-development-environments,dev-container-package-caches,containerized-development-tooling"
---

# Rootless Dev-Container Filesystems

## When to Use

Load this skill when a watcher runs as root, a bind mount creates root-owned host files, a non-root process gets `EACCES`, or nested dependency/output mounts behave differently after recreation.

This skill governs steady-state process identity and writable filesystem topology. It does not claim Docker's daemon itself is rootless.

## Invariants

1. The long-running watcher and application process run as a numeric non-root UID/GID.
2. Root host identity (`0:0`) is never propagated as the development identity; use a documented non-root fallback.
3. Source is a read-only source of truth when the toolchain can operate from a separate writable workspace.
4. Dependencies and generated output never rely on root-created directories nested inside a bind-mounted checkout.
5. Writable named volume and tmpfs paths are initialized for the runtime UID/GID before the watcher starts.
6. The container does not recursively `chown` the host repository at startup.
7. Runtime verification checks identity and actual write behavior, not merely a Dockerfile `USER` line.

## Preferred Topology

```yaml
services:
  web:
    user: "${DEV_UID:-1000}:${DEV_GID:-1000}"
    read_only: true
    volumes:
      - type: bind
        source: ./web
        target: /source
        read_only: true
      - type: volume
        source: web-workspace
        target: /workspace
    tmpfs:
      - /tmp:uid=${DEV_UID:-1000},gid=${DEV_GID:-1000},mode=1770

volumes:
  web-workspace:
```

Build an image-owned `/workspace` with the correct ownership or initialize the named volume in a bounded setup step. Then copy/synchronize or create idempotent links from `/source` as the non-root user. See [mount-ownership-patterns.md](references/mount-ownership-patterns.md).

## Dockerfile Pattern

```dockerfile
ARG DEV_UID=1000
ARG DEV_GID=1000
RUN groupadd --gid "$DEV_GID" dev  && useradd --uid "$DEV_UID" --gid "$DEV_GID" --create-home dev  && install -d -o "$DEV_UID" -g "$DEV_GID" /workspace /home/dev/.cache
USER dev
WORKDIR /workspace
```

Real base images may already contain the UID, GID, user, or group. Handle existing identities rather than blindly calling `useradd`. Build stages may run as root; steady state must not.

## Mount Choice

- **Bind mount:** host-visible source/config; use read-only unless host writes are intentional.
- **Named volume:** project-scoped dependencies, writable workspace, SDK caches, persistent generated state.
- **tmpfs:** disposable high-churn outputs, sockets, and temporary files; lost on recreation.
- **Image layer:** immutable toolchain and baseline directories.

A named volume mounted at `/workspace/app/node_modules` below a bind mounted at `/workspace/app` can cause Docker to create or obscure nested paths with surprising ownership. Prefer sibling mount boundaries or read-only `/source` plus writable `/workspace`.

## Runtime Proof

```bash
docker compose exec web id
docker compose exec web sh -lc 'test "$(id -u)" -ne 0'
docker compose exec web sh -lc 'touch /workspace/.write-test && rm /workspace/.write-test'
docker compose exec web sh -lc 'test ! -w /source'
```

Also verify the host checkout contains no root-owned or generated dependency files after install, hot reload, stop/start, and recreation.

## Common Gotchas

- Compose `user:` overrides Dockerfile `USER`; inspect the live object.
- A root entrypoint may launch a non-root child but still create root-owned cache directories first.
- A first-mounted empty named volume can hide image content at the target path.
- Docker Desktop may present synthetic ownership; still test non-root identity and write boundaries inside the container.
- Hardcoding host UID/GID `1000` can collide with a different existing image identity. Build logic must tolerate it.
- User namespaces/rootless Docker change host mappings but do not excuse running the app process as UID 0.
- `chmod 777` is not an ownership design and turns shared mounts into a tampering surface.
- In-place restart retains named-volume symlinks and workspace content; initialization must be idempotent.

## Verification Checklist

- [ ] Live watcher UID is non-zero and expected GID is present
- [ ] Source mount path and read-only flag match design
- [ ] Writable workspace, cache, and tmpfs paths accept runtime writes
- [ ] No recursive host checkout `chown` or world-writable workaround
- [ ] No root-owned files appear in the checkout after normal lifecycle
- [ ] Named volumes are project-scoped and survive intended recreation
- [ ] Initialization succeeds twice against the same workspace
- [ ] Linux and Docker Desktop behavior are documented/tested where supported
