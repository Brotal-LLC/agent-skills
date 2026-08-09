# Package Cache Matrix

## Cache-Key Inputs

For transferable CI or machine-shared caches, include:

- dependency lockfile digest;
- exact package-manager version;
- SDK/runtime version;
- OS/libc and CPU architecture when native artifacts may appear;
- relevant feature flags/build profiles;
- registry source/config identity without embedding credentials.

Do not use branch name alone. Do not omit architecture for caches that may contain native packages.

## .NET / NuGet

Set one package root:

```dotenv
NUGET_PACKAGES=/home/dev/.nuget/packages
```

Redirect `obj` and `bin`/artifacts outside bind-shared source. `project.assets.json` records package paths; a host restore and container restore against different roots can make the watcher report packages missing even though both caches contain them.

Recovery:

1. Stop the watcher.
2. Remove only affected project `obj`/`bin` in the correct filesystem boundary.
3. Restore with the container's `NUGET_PACKAGES` as the runtime user.
4. Recreate the watcher and verify the real service.

## npm

Set:

```dotenv
npm_config_cache=/home/dev/.npm
```

Keep `/home/dev/.npm` separate from `/workspace/app/node_modules`. The former accelerates downloads; the latter is the resolved dependency tree. A `file:` dependency may remain stale in `node_modules` even when the download cache is current. Inspect the installed package before wiping everything.

Use `npm ci` for a lockfile-driven clean install where appropriate. For hot-reload startup that preserves a volume, define how dependency changes trigger reinstall and prove same-container restart.

## pnpm

Pin pnpm through Corepack or the repository's package-manager declaration. Configure a writable store and `PNPM_HOME`; do not assume an npm variable controls pnpm's content-addressed store. The virtual store and linked project `node_modules` remain project-specific even if a compatible content store is shared.

Cross-filesystem links, differing pnpm versions, native builds, and store pruning can invalidate sharing assumptions. Verify with `pnpm config get store-dir` inside the container.

## Yarn

First determine Yarn Classic versus Berry/modern Yarn. `YARN_CACHE_FOLDER` is not a universal answer across generations. Commit the selected Yarn release/config and inspect `yarn config`.

Modern Yarn may use `.yarn/cache`, `.pnp.*`, install-state, unplugged directories, or `node_modules` linker output. Decide which are repository artifacts versus per-worktree mutable outputs. Do not casually share `.pnp` or unplugged/native trees across worktrees.

## Maven

Use a non-root home such as `/home/dev/.m2`; the repository cache is normally `/home/dev/.m2/repository`. Keep `target` per worktree. Mount credentials-bearing `settings.xml` separately and read-only; do not persist it inside the repository volume.

A shared Maven repository is executable supply-chain input. Share only among trusted projects and verify checksums/repository policy.

## Gradle

Set:

```dotenv
GRADLE_USER_HOME=/home/dev/.gradle
```

Keep project `.gradle` and `build` outputs scoped to the worktree. Gradle's dependency cache includes file locks and version-specific formats; uncontrolled concurrent sharing across containers can be fragile. Prefer separate project volumes and intentionally shared read/download layers only when validated.

## Cargo

Set `CARGO_HOME=/home/dev/.cargo` for registry/git caches and tool installs. Keep `target` per worktree unless a cache key includes toolchain, target triple, features, profile, rustflags, and relevant environment. Native build scripts make casual cross-project `target` sharing especially inventive.

Never mount host Cargo credentials into an untrusted project with broader access than required.

## Python pip and uv

Use `PIP_CACHE_DIR` or `UV_CACHE_DIR` for download/build caches. Keep the virtual environment per worktree and do not share it across host/container paths or incompatible Python builds. Wheels can be interpreter, ABI, platform, and architecture specific.

## BuildKit Cache Mounts

Build-time cache mounts accelerate image builds without becoming runtime volumes:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/package-manager package-manager install
```

Set ownership/options appropriate to the build user. BuildKit cache is not a substitute for a runtime cache used by hot reload, and it must not contain secrets. Use secret mounts for authenticated package access.

## Credential Boundary

Keep these outside shared cache roots:

- `.npmrc` auth tokens;
- NuGet credentials/config;
- Maven `settings.xml` secrets;
- Gradle properties containing credentials;
- Cargo credentials;
- pip/uv authenticated index configuration.

Use read-only secret files or secret mounts and redact command output.

## Reproducibility Closure

For each supported ecosystem, prove:

1. install with warm cache;
2. install after deleting only the dependency tree;
3. install with an empty download cache;
4. tests/build produce the same result;
5. lockfile mutation invalidates the right layer;
6. sibling worktree cache activity does not change this worktree's result.

## Sources

- npm cache: https://docs.npmjs.com/cli/using-npm/config#cache
- pnpm settings: https://pnpm.io/settings
- Yarn configuration: https://yarnpkg.com/configuration/yarnrc
- NuGet global packages/cache folders: https://learn.microsoft.com/nuget/consume-packages/managing-the-global-packages-and-cache-folders
- Maven local repository: https://maven.apache.org/repositories/local.html
- Gradle dependency caching: https://docs.gradle.org/current/userguide/dependency_caching.html
- Cargo environment variables: https://doc.rust-lang.org/cargo/reference/environment-variables.html
- Docker Build cache mounts: https://docs.docker.com/build/cache/optimize/
