---
name: dev-container-package-caches
description: Use when designing package and build caches for non-root development containers without sharing mutable dependency trees, corrupting lockfile state, or leaking credentials across projects and worktrees.
license: MIT
compatibility: Applies to OCI/Docker development containers on Linux, macOS Docker Desktop, and Windows Docker Desktop/WSL2. Package-manager variables and cache formats depend on pinned tool versions.
metadata:
  author: "Brotal LLC"
  version: "1.0.0"
  platforms: "linux,macos,windows"
  parent: "collision-free-agentic-development"
  companions: "rootless-dev-container-filesystems,compose-development-environments,containerized-development-tooling"
---

# Dev-Container Package Caches

## When to Use

Load this skill when dependency installation is slow, a persistent cache serves stale local packages, host and container restores corrupt each other, or a non-root package manager cannot write its cache.

## Core Model

Separate four things that teams habitually call "the cache":

1. **Download/content cache** — reusable accelerator; may be shared cautiously.
2. **Resolved dependency tree** — project/worktree/toolchain-specific (`node_modules`, virtualenv, NuGet assets).
3. **Build output** — project/worktree-specific (`bin`, `obj`, `.next`, `target`, classes).
4. **Credentials/config** — secret, least-privilege, never persisted in a broadly shared cache.

A cache may disappear without changing correctness. If deleting it changes the build result, it was undeclared state wearing a fake moustache.

## Isolation Policy

- Keep mutable dependency trees and build outputs project-scoped.
- Share only content-addressed/download caches among compatible toolchain, OS, architecture, and trust boundaries.
- Mount every cache at the path actually configured for the non-root runtime user.
- Key disposable CI caches by lockfile, toolchain version, OS, and architecture.
- Treat local `file:`/workspace dependencies as source inputs; version or content changes must invalidate packed copies.
- Make cache deletion safe and document the narrowest invalidation unit.

See [package-cache-matrix.md](references/package-cache-matrix.md) for paths and invalidation recipes.

## Common Paths

| Ecosystem | Download/cache root | Project-specific state |
|---|---|---|
| NuGet/.NET | `NUGET_PACKAGES=/home/dev/.nuget/packages` | `obj`, `bin`, assets redirected per worktree |
| npm | `npm_config_cache=/home/dev/.npm` | `node_modules`, framework output |
| pnpm | configured store directory/`PNPM_HOME` | virtual store and linked `node_modules` |
| Yarn | version-specific cache configuration | install state, PnP files, unplugged tree |
| Maven | `/home/dev/.m2/repository` | `target` |
| Gradle | `GRADLE_USER_HOME=/home/dev/.gradle` | project `.gradle`, `build` |
| Cargo | `CARGO_HOME=/home/dev/.cargo` | per-worktree `target` unless deliberately keyed |
| pip/uv | `PIP_CACHE_DIR` / `UV_CACHE_DIR` | virtual environment and build artifacts |

Pin the package manager version and inspect its effective configuration; variable names are not eternal scripture.

## Compose Pattern

```yaml
services:
  api:
    user: "${DEV_UID:-1000}:${DEV_GID:-1000}"
    environment:
      NUGET_PACKAGES: /home/dev/.nuget/packages
    volumes:
      - nuget-cache:/home/dev/.nuget/packages
      - dotnet-output:/workspace/.artifacts

volumes:
  nuget-cache:
  dotnet-output:
```

Compose prefixes these volumes with `COMPOSE_PROJECT_NAME` by default. To share only a download cache across worktrees, make that sharing explicit, document compatibility, and never share the mutable build-output volume.

## Installation Discipline

- Use the repository lockfile and immutable/frozen install mode where supported.
- Run installation as the same non-root identity that runs the watcher.
- Do not run a root `npm install`, `dotnet restore`, or Maven build into the live non-root volume as a quick repair.
- Stop watchers before host-side tools touch bind-shared generated assets.
- Recreate when startup installation logic, mounts, user, or cache variables change.

## Invalidation Sequence

1. Prove the live container uses the intended checkout, lockfile, tool version, and cache path.
2. Inspect the resolved package inside the container.
3. Remove the narrow package/install-state entry first.
4. Reinstall in frozen mode as the runtime user.
5. Remove the whole project dependency tree only if narrow invalidation fails.
6. Remove the shared download cache last; it is usually not the stale resolved tree.
7. Rebuild and run tests from a clean cache at least periodically.

## Common Gotchas

- A named volume at `/workspace/node_modules` is the dependency tree, not the npm download cache.
- Host and container .NET builds can rewrite `obj/project.assets.json` with incompatible package roots.
- Same-version local packages may remain packed in npm/pnpm/Yarn state after source changes.
- Sharing Maven, Gradle, Cargo, or NuGet caches across untrusted projects exposes executable build inputs.
- Cache volume ownership follows the mounted path/init design, not the `user:` field by magic.
- Mutable tags and unpinned package managers can change cache format without a lockfile change.
- Registry tokens in `.npmrc`, NuGet config, Maven settings, or Cargo credentials must not be baked into images or cache volumes.

## Verification Checklist

- [ ] Lockfile and package-manager version pinned
- [ ] Effective cache paths verified inside the live non-root container
- [ ] Download cache separated from dependency tree and build output
- [ ] Mutable state project-scoped; any sharing is explicit and trusted
- [ ] Clean-cache install and test succeed
- [ ] Narrow stale-package invalidation documented and tested
- [ ] No credentials present in images, volumes, logs, or committed config
