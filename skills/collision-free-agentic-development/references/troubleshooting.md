# Troubleshooting

## Start with rendered and running truth

```bash
docker compose config --quiet
docker compose config --format json
docker compose ps
CONTAINER="$(docker compose ps -q api)"
docker inspect "$CONTAINER" --format '{{.Config.User}}'
docker inspect "$CONTAINER" --format '{{json .Config.Labels}}'
docker inspect "$CONTAINER" --format '{{json .Mounts}}'
docker inspect "$CONTAINER" --format '{{json .NetworkSettings.Networks}}'
```

Run `python "$SKILL_DIR/scripts/devstack.py" doctor --project-dir .` for the package's static audit.

## Wrong branch or worktree is live

A reused Compose project can keep a container whose bind mount points at another worktree. Compare the mount source and `com.docker.compose.project.working_dir` label with the intended checkout. Correct `COMPOSE_PROJECT_NAME`, then recreate from the intended directory. Do not edit the wrong worktree until the mount is proven; that merely makes the accident collaborative.

## `restart` did nothing

`docker compose restart` restarts the existing container. It does not apply changed images, labels, environment, commands, users, mounts, or networks. Validate and recreate:

```bash
docker compose config --quiet
docker compose up --detach --force-recreate
```

For one app service, avoid disturbing stateful dependencies:

```bash
docker compose up --detach --force-recreate --no-deps api
```

Add `--build` when source is baked into an image. Hot-reload source bind mounts do not need image rebuilds for ordinary code edits, but Dockerfile, dependency, and startup-command changes do.

## Shell environment selected the wrong stack

Shell variables outrank `.env`. Check `COMPOSE_FILE`, `COMPOSE_PATH_SEPARATOR`, `COMPOSE_PROJECT_NAME`, hostnames, database variables, and profile variables in the parent process. `docker compose config` shows the final merge. Linux and macOS use `:` in `COMPOSE_FILE`; Windows uses `;` unless `COMPOSE_PATH_SEPARATOR` overrides it.

## Caddy returns 502

Check, in order:

1. The service is actually listening on `0.0.0.0`, not container loopback.
2. The `{{upstreams PORT}}` label uses the container port, not a host port.
3. The routed service and Caddy share the configured ingress network.
4. Running labels contain the current hostname.
5. No orphan container owns the same hostname.
6. DNS resolves to this ingress host.
7. The watcher child process is alive; a container being `Up` does not prove the application is listening.

Wait for restore/build after recreation before diagnosing a transient 502. Watch the real service readiness log, then probe through ingress.

## Caddy serves the wrong app or drops a route

Two containers may claim the same hostname. Search running labels, remove/recreate the stale project, and move to unique service subdomains. If one hostname needs multiple paths, define the complete ordered route tree on one route owner; independent label fragments are not a routing architecture.

## Certificate failures

- Internal CA: confirm the root from the current persistent Caddy data volume is trusted by the client/browser.
- HTTP-01: confirm public DNS plus inbound port 80 and port 443 reach Caddy.
- Cloudflare DNS-01: confirm the image contains the module, the token is visible only to Caddy, scopes include `Zone:DNS:Edit` and `Zone:Zone:Read`, and the token covers the correct zone.
- Public cert but private app: DNS-01 can issue it, but clients still need split-horizon DNS or another route to the private ingress.
- Rate limits: stop repeatedly recreating stale host labels. Fix the hostname/source first.

## Hot reload misses changes

Confirm the source mount points to the current worktree and the dev server binds all interfaces. Then enable framework polling per `cross-platform.md`. For .NET, rude edits can terminate Edit-and-Continue; force-recreate the service. For Node, a new dependency requires installation into the mounted dependency volume; recreating an entrypoint that runs `npm install` is appropriate.

Do not use a root watcher to cure permission errors. Inspect UID/GID and mount ownership, rebuild the dev image/runtime user, or recreate a poisoned project-scoped dependency volume.

## Nested dependency mount is root-owned

If a named volume or tmpfs is mounted at `bind-mounted-parent/node_modules` (or `.next`), Docker may create that hidden mountpoint on the host as root before starting the service. The non-root watcher then gets `Permission denied`, even though the Dockerfile correctly chowned the same image path.

Do not add a root entrypoint or `chmod 777`. Separate the mounts: bind source at `/source`, keep an image-owned writable workspace elsewhere, symlink source entries into that workspace as the runtime UID, and mount dependencies/generated output under the workspace. The Node template implements this pattern.

## Host and container builds corrupt each other

.NET `obj/project.assets.json`, `bin`, Next `.next`, Rust `target`, and similar intermediates can encode absolute toolchain paths or be rewritten concurrently. Keep container artifacts in tmpfs/project volumes. Stop the watcher before host migration generation or other host build operations if the repository has not yet implemented artifact isolation.

## Browser loads HTML but HMR fails

Verify WebSocket upgrades through the public hostname, browser console errors, and mixed content. Browser-visible API/HMR URLs must use HTTPS/WSS when the page is HTTPS. Caddy proxies WebSockets automatically, but framework origin allowlists may need the routed hostname.

## Mount content is stale after a rebuild

Some build tools delete and recreate output directories. Docker can remain attached to the old bind-mount inode. If the host path is current but the container path is empty/stale, force-recreate the container to rebind it.

## Safe cleanup

Use `docker compose down` for the current worktree. Do not use `down --volumes`, global volume prune, or manually remove a similarly named container until its Compose project label is checked. The whole point of deterministic names is to make proof cheap; use it.
