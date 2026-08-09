# Collision-Free Architecture

## Collision model

A hostname is only one namespace. Parallel worktrees also compete for Docker project names, physical container names, published host ports, external-network DNS aliases, volume names, database/schema names, cache keys, queues, buckets, and migration locks. Isolate every mutable namespace deliberately.

| Namespace | Collision-free rule |
|---|---|
| Compose resources | Give every worktree a deterministic `COMPOSE_PROJECT_NAME`/`STACK_ID`. |
| Containers | Do not set `container_name` in application stacks. Let Compose prefix names. |
| App networks and volumes | Keep names project-scoped; do not set top-level `name:` unless it contains `${STACK_ID}`. |
| Ingress | Share exactly one attachable ingress network; route by unique hostname. |
| Host ports | Do not publish application ports. Only the shared proxy publishes 80/443. |
| Caddy routes | One owner per hostname; use separate service subdomains by default. |
| Shared PostgreSQL | Unique database (and preferably role) per worktree. |
| Shared Redis/Valkey | Unique key prefix; separate logical DBs alone are insufficient for ACL/eviction isolation. |
| Queues/object storage | Prefix virtual hosts, topics, queues, consumer groups, and bucket names with `STACK_ID`. |
| Bind mounts | Resolve from the current worktree; inspect the running mount source before debugging code. |

The bundled helper derives a stable identity from project name, canonical worktree path, and an eight-character SHA-256 suffix. The hash prevents two equally named worktrees in different parent directories from colliding. The human-readable prefix keeps `docker compose ps` comprehensible.

## Network topology

```text
host :80/:443
      |
shared Caddy Docker Proxy
      | agent-ingress (shared, attachable)
      +------------------+------------------+
      |                  |                  |
worktree A web/api   worktree B web/api   worktree C web/api
      | private default  | private default  | private default
      + local data OR shared data network with unique namespaces
```

Attach only services that Caddy must reach to ingress. Keep databases, caches, queues, and internal workers off ingress. Service-to-service traffic should use the private project network whenever possible.

Caddy Docker Proxy's `{{upstreams PORT}}` placeholder discovers the labeled service's container addresses. It avoids published ports and does not require globally unique Docker DNS service names. Still use project-specific service names when humans frequently operate across stacks; `docker compose` scopes service commands, while a raw `docker` command does not.

## Caddy route ownership

The safe default is one hostname per service:

```yaml
labels:
  caddy: ${API_HOST:?API_HOST required}
  caddy.reverse_proxy: "{{upstreams 8080}}"
```

Do not put the same `caddy` site address on independent containers and expect their routes to merge. Caddy Docker Proxy builds object-specific route fragments; duplicate site ownership can be ambiguous or last-writer-wins. For a single hostname with `/api/*` plus frontend fallback, place the complete ordered route tree on one owner (or use a dedicated router service), then proxy to both upstreams. Separate subdomains are simpler and harder to misconfigure.

## Worktree lifecycle

1. Create the worktree.
2. Run `devstack.py init` inside it; never copy another worktree's `.env` unchanged.
3. Customize source paths and framework commands in the templates.
4. Render and audit with `docker compose config --quiet` and `devstack.py doctor`.
5. Start with `devstack.py up`.
6. Apply Compose/env/label/network changes with `devstack.py apply`, or recreate only changed app services with `devstack.py recreate SERVICE`.
7. Stop with `devstack.py down`. Do not add `--volumes` unless the worktree's state is intentionally disposable and deletion is explicitly requested.

## Anti-patterns

- Fixed `container_name`, volume `name`, or network `name` copied into every worktree.
- `localhost:5432`, `localhost:6379`, or fixed host ports inside containers.
- One shared database name for branches that run different migrations.
- Production and dev containers claiming the same Caddy hostname.
- A generic app service publishing `3000:3000` or `8080:8080` in every worktree.
- Root-owned `node_modules`, NuGet caches, `.next`, `bin`, or `obj` created by a root steady-state container.
- Using branch name alone as identity: branch names can repeat across clones and contain invalid DNS characters.

## Authoritative inspection

Rendered Compose and running container metadata outrank source-file intuition:

```bash
docker compose config --quiet
docker compose config --format json
docker compose ps
CONTAINER="$(docker compose ps -q api)"
docker inspect "$CONTAINER" --format '{{json .Mounts}}'
docker inspect "$CONTAINER" --format '{{json .Config.Labels}}'
```

A clean YAML file is merely a proposal. Docker's rendered model and the running object's labels, mounts, user, networks, and image are the deployed truth.
