# Cross-Platform Operation

The templates run Linux containers on Linux, macOS Docker Desktop, and Windows Docker Desktop/WSL2. The host behaviors are not identical; pretending otherwise is how portable examples become portable disappointment.

## Compose file lists

`COMPOSE_FILE` is a path list:

- Linux and macOS: `compose.yaml:compose.dev.yaml`
- Windows: `compose.yaml;compose.dev.yaml`

`COMPOSE_PATH_SEPARATOR` can override that delimiter. A comma is not the standard separator. The helper writes both variables for the selected platform. A shell-exported `COMPOSE_FILE` or `COMPOSE_PROJECT_NAME` overrides the worktree `.env`; inspect the parent environment when Compose selects the wrong stack.

Official reference: <https://docs.docker.com/compose/how-tos/environment-variables/envvars/>

## Source mounts and users

Every steady-state hot-reload dev container must run non-root. Image build steps may run as root to install packages and create the runtime user; the final `USER` and Compose `user:` must be non-root.

- Linux: use the host UID/GID so bind-mounted writable paths remain developer-owned.
- macOS/Windows Docker Desktop: file ownership is translated through the VM. UID/GID `1000:1000` is a reliable default, but the helper still records explicit values.
- Never repair a dependency volume with a root `docker exec npm install` or root watcher. Recreate the volume or use an image-owned mountpoint initialized for the runtime UID.
- Keep dependencies and generated artifacts off the source mount when toolchains encode host-specific paths. The templates isolate Node `node_modules` and .NET NuGet/build output.
- Do not place a dependency volume beneath a bind-mounted parent. Docker can create the hidden host mountpoint as root, defeating image-time `chown`. Mount source separately (for example `/source`), keep the runnable workspace image-owned, and mount writable volumes/tmpfs under that workspace as the Node template does.

On SELinux hosts, a bind mount may need `:z` for private relabeling or `:Z` for exclusive relabeling. Do not add those flags to cross-platform defaults; Docker Desktop and non-SELinux engines do not need them.

## File watching

Desktop VM shares and network filesystems may not deliver native file events. Enable polling only in the dev overlay:

| Stack | Typical command/settings |
|---|---|
| .NET/F# | `dotnet watch --non-interactive ... run`; `DOTNET_USE_POLLING_FILE_WATCHER=1` when events fail |
| Next.js/Vite/Node | `npm run dev -- --hostname 0.0.0.0`; `WATCHPACK_POLLING=true` or framework polling option |
| Python | `uvicorn package.app:app --reload --host 0.0.0.0`; pass reload directories explicitly |
| Go | Build a dev image containing Air; run `air` as non-root |
| Rust | Build a dev image containing `cargo-watch` or `bacon`; keep Cargo target in a project volume |
| Java/Spring | `./mvnw spring-boot:run` or Gradle continuous mode with DevTools |
| Ruby/Rails | `bundle exec rails server -b 0.0.0.0`; keep bundle cache project-scoped |

Polling costs CPU. Use it where bind-mount events are unreliable, not as a ceremonial incantation everywhere.

## Host access

Containers reach sibling services by Compose service name on a shared network, not through `localhost`. Use `host.docker.internal` only when a container intentionally calls a host process. Docker Desktop provides it; Linux may need:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Do not add this merely to make a containerized database reachable; attach the app and database to the same network instead.

## Path and shell rules

- Keep Compose file paths relative to the worktree so the same files work on all hosts.
- Use Python helpers for orchestration; avoid Bash-only arrays, `/dev/tcp`, `sed`, and platform-specific `realpath` flags.
- Commit LF line endings for scripts and YAML. A Python shebang works on POSIX; Windows users invoke `py scripts/devstack.py` or `python scripts/devstack.py`.
- Docker Desktop must be allowed to share the repository directory. A denied file-share often appears as an empty mount or startup failure, not an eloquent permissions diagnosis.
- Avoid worktrees under extremely deep Windows paths; filesystem and toolchain path limits still ambush generated dependency trees.

## PowerShell equivalents

Use single-line helper commands as shown in the main skill. Inspect and clear parent-process Compose overrides with:

```powershell
Get-ChildItem Env:COMPOSE_FILE, Env:COMPOSE_PROJECT_NAME -ErrorAction SilentlyContinue
Remove-Item Env:COMPOSE_FILE, Env:COMPOSE_PROJECT_NAME -ErrorAction SilentlyContinue
```

Inspect a rendered service without Bash command substitution:

```powershell
$container = docker compose ps -q api
docker inspect $container --format '{{.Config.User}}'
docker inspect $container --format '{{json .NetworkSettings.Networks}}'
```

Bash/Zsh users can clear the same inherited overrides with `unset COMPOSE_FILE COMPOSE_PROJECT_NAME`.

## Local names

`*.localhost` is the zero-DNS default for internal-CA development. Browsers and modern resolvers treat `.localhost` as loopback. If a corporate resolver or tool does not, add exact entries to the hosts file or use split-horizon DNS. Do not use `.local`; it is reserved for mDNS and can produce impressively inconsistent results.
