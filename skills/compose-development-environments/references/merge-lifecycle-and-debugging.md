# Merge, Lifecycle, and Debugging

## Precedence Model

Compose behavior comes from several layers:

1. Shell environment and explicit CLI flags.
2. `--env-file` and project `.env` interpolation inputs.
3. Ordered Compose files.
4. Image defaults.
5. Live container objects created from an earlier render.

Always record both the render and live object. Editing YAML does not retroactively edit a container.

Useful commands:

```bash
docker compose config --quiet
docker compose config --environment
docker compose config --format json
docker compose ps --all
docker compose images
```

Redact secrets before persisting outputs.

## Merge Semantics

- Service maps merge by key.
- Environment and labels represented as maps merge by variable/label name.
- Many sequences append or deduplicate according to Compose rules rather than replacing wholesale.
- Relative paths are resolved according to the project/base-file rules, not necessarily the overlay's directory.
- `!reset` and `!override` can express replacement in Compose versions that support them; pin and test the minimum Compose version before relying on tags.

A dangerous dev overlay:

```yaml
services:
  web:
    labels:
      caddy: "${DEV_HOST}"
```

If the base supplies imports or TLS labels, they can survive. Inspect the merged label map rather than assuming omission means deletion.

## Environment Pollution

A shell export wins over `.env` interpolation:

```bash
printf 'COMPOSE_PROJECT_NAME=%s
' "$COMPOSE_PROJECT_NAME"
docker compose config --environment
```

Do not print secret variables. Launch a sanitized shell or explicitly unset only known conflicting names. Avoid wrappers that silently select a different project or file list.

## Project Identity

Compose uses the project name for default container, network, and volume names. Derive it from a readable project/worktree slug plus a stable path hash. Human-readable names alone collide when two clones have the same leaf directory.

Reject:

- fixed application `container_name`;
- top-level volume `name` unless deliberately shared;
- top-level network `name` unless deliberately external/shared;
- host `ports` allocated from a hand-maintained spreadsheet;
- mutable DB/cache namespaces shared by feature worktrees.

## Restart, Recreate, Rebuild

| Change | Operation |
|---|---|
| App source observed by a live watcher | No Compose operation |
| Watcher process died or container command must rerun | Recreate preferred |
| Environment, label, network, mount, user, command | `up --force-recreate` |
| Dockerfile/toolchain/dependency layer | `up --build --force-recreate` |
| Base image tag changed remotely | Pull/build, then recreate |
| Persistent data intentionally reset | Explicit `down --volumes` after scope proof |

`docker compose restart` reuses the same container object and stale configuration. It is valid only when restarting exactly that object is the goal.

## Dependency Readiness

`depends_on` without a condition expresses ordering, not readiness. Use a healthcheck for infrastructure that has a meaningful local readiness probe, then make the application resilient to transient dependency failure anyway.

A healthcheck should test the service from where it runs, while end-to-end readiness should test the routed dependency chain. Do not make a healthcheck depend on public DNS or an external CDN unless that dependency is genuinely required for process health.

## Evidence-First Debugging

```bash
docker compose logs --since 10m --timestamps service-name
docker inspect --format '{{json .State}}' container-id
docker inspect --format '{{json .Config.User}}' container-id
docker inspect --format '{{json .Mounts}}' container-id
docker inspect --format '{{json .NetworkSettings.Networks}}' container-id
docker inspect --format '{{json .Config.Labels}}' container-id
docker inspect --format '{{json .Image}}' container-id
docker events --since 10m
docker network inspect network-name
```

Never capture or persist a bare `docker inspect` dump in agent/debug logs: it includes `.Config.Env` and can expose connection strings, passwords, and tokens. Select only the fields needed for the hypothesis, and redact sensitive values from labels, health output, and application logs before sharing them.

Check:

- state, exit code, OOM kill, restart count;
- health history, not only current status;
- exact command/entrypoint and runtime user;
- mount source/destination/type/read-only flag;
- network aliases and selected IPs;
- labels as seen by the daemon;
- image ID, not just mutable tag.

For an in-network probe, use a disposable client attached to the same network. Do not install curl into the production image merely to debug it.

## Cleanup Safety

Before removing resources:

1. Record `docker compose ls` and project label filters.
2. Confirm the working directory and project name.
3. List volumes/networks selected by `com.docker.compose.project` labels.
4. Back up mutable state when it is not disposable.
5. Remove only the intended project.

Never prune globally while another agent or worktree is active. Shared ingress and shared databases are machine-level dependencies, not leftovers.

## Cross-Platform Notes

- Linux bind mounts expose host ownership directly.
- Docker Desktop mediates ownership and file notifications through its VM; performance and watcher behavior differ.
- Windows-native `COMPOSE_FILE` uses `;`; PowerShell and CMD quoting differ from POSIX shells.
- WSL2 works best when source lives in the Linux filesystem rather than `/mnt/c` for I/O-heavy watchers.
- Case-insensitive host filesystems can hide case-only import defects that Linux containers expose.

## Sources

- Compose file merge rules: https://docs.docker.com/reference/compose-file/merge/
- Compose environment precedence: https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/
- Compose project names: https://docs.docker.com/compose/how-tos/project-name/
- Compose profiles: https://docs.docker.com/compose/how-tos/profiles/
- Compose networking: https://docs.docker.com/compose/how-tos/networking/
- Compose startup order: https://docs.docker.com/compose/how-tos/startup-order/
