# Upstream Protocols and Routing

## Evidence Order

Diagnose in this order:

1. **Process mode:** `caddy docker-proxy` versus `caddy run --config ...`.
2. **Rendered labels:** Compose interpolation and overlay merging.
3. **Discovery:** container labels visible to the watched Docker API.
4. **Network:** CDP and target share the address CDP selected.
5. **Transport:** HTTP, HTTPS, h2c, FastCGI, and SNI match.
6. **Application:** host/origin/auth/path behavior accepts the proxied request.

Skipping directly to application logs is how a network-selection defect gets promoted into a framework rewrite.

## CDP Label Translation

CDP converts dotted label keys into Caddyfile directives. A minimal service is:

```yaml
labels:
  caddy: "${SERVICE_HOST:?SERVICE_HOST required}"
  caddy.reverse_proxy: "{{upstreams 8080}}"
```

Use numbered labels when the same key must appear more than once. Use directive ordering or an explicit route/handle tree when path-specific backends and a fallback share one host. The safest ownership model is still one labeled container producing the entire site block.

Do not assume this works:

```yaml
# Container A owns the hostname and root fallback.
caddy: "${APP_HOST}"
caddy.reverse_proxy: "{{upstreams 3000}}"

# Container B independently tries to add /api.
caddy: "${APP_HOST}"
caddy.handle_path: "/api/*"
```

Those are separate generated site candidates, not a cooperative transaction. Put the full route tree on one owner or use `api.<domain>` and `app.<domain>`.

## Transport Matrix

### Cleartext HTTP

```yaml
caddy.reverse_proxy: "{{upstreams 8080}}"
```

CDP emits container addresses discovered on the selected network. `expose` is documentation; it does not publish a host port and does not itself guarantee the app listens.

### HTTPS upstream

```yaml
caddy.reverse_proxy: "{{upstreams https 8443}}"
caddy.reverse_proxy.transport: "http"
caddy.reverse_proxy.transport.tls_server_name: "backend.internal.example"
```

The Caddy container must trust the upstream issuer. Mount a public certificate chain or an internal root CA into a controlled trust path. Never finish with `tls_insecure_skip_verify`; it turns encryption without identity into a very elaborate shrug.

### h2c and gRPC

```yaml
caddy.reverse_proxy: "{{upstreams h2c 5000}}"
```

h2c is cleartext HTTP/2. It is appropriate for a backend that explicitly accepts HTTP/2 prior knowledge. Many servers advertised as "HTTP/1 and HTTP/2" only select HTTP/2 through TLS ALPN; they are not automatically h2c servers.

CDP version drift matters here: the current README summarizes the function as `upstreams [http|https] [port]`, while the current generator source also registers an `h2c` template helper. `{{upstreams h2c 5000}}` therefore works in versions containing that helper, but pin the CDP image and inspect its generated config instead of assuming an older deployment matches current source.

Native gRPC requires HTTP/2. Verify with a real generated client or `grpcurl`, including reflection only when the server intentionally enables it. A successful TCP connect, health endpoint over HTTP/1.1, or gRPC-Web request does not prove native gRPC.

### WebSocket

Use the ordinary HTTP or HTTPS upstream. Caddy automatically handles the upgrade headers. Verify status `101`, bidirectional frames, authentication, origin validation, and an idle interval long enough to expose timeout behavior.

### SSE and streaming responses

Use ordinary HTTP/HTTPS and test incremental delivery through the full edge path. Caddy's reverse proxy can stream, but application buffering, compression, intermediary/CDN behavior, and response flush policy can make an event stream arrive in one useless lump. Set `flush_interval -1` only when the route genuinely requires low-latency flushing and load-test the trade-off.

### FastCGI

FastCGI is not HTTP. Use `php_fastcgi` or the corresponding FastCGI transport/directive rather than inventing `fastcgi://` for `reverse_proxy`. Confirm script root and split-path behavior; a reachable PHP-FPM socket can still execute the wrong file tree.

Raw TCP/UDP protocols are outside Caddy's HTTP `reverse_proxy`. They require an explicitly installed Layer 4 or protocol-specific module and separate labels/configuration. Verify the module exists before documenting a route; CDP cannot translate directives that the Caddy binary does not know.

## Discovery Scope and Label Namespaces

CDP scans matching labels across every Docker resource visible through its configured Docker API/socket. Network attachment and `CADDY_INGRESS_NETWORKS` only affect which addresses the `upstreams` template emits; ingress selection does not scope discovery.

Therefore:

- Prefer one machine-level singleton for the default `caddy` prefix.
- Never start a disposable or per-worktree default-prefix controller against a shared daemon; it can ingest unrelated routes, snippets, and global options.
- For intentional logical separation on one trusted daemon, set a unique `CADDY_DOCKER_LABEL_PREFIX`, for example `team_a`, and label that controller's workloads with `team_a`, `team_a.reverse_proxy`, and related dotted keys.
- Treat prefixes as namespacing, not authorization. Any workload able to set labels on that daemon can target another prefix.
- For mutually untrusted workloads or hard isolation, use a separate Docker daemon/context/API identity and separately controlled socket access.

Example logical namespace:

```yaml
services:
  caddy-team-a:
    environment:
      CADDY_DOCKER_LABEL_PREFIX: team_a
      CADDY_INGRESS_NETWORKS: team-a-ingress

  api:
    labels:
      team_a: api.dev.example.com
      team_a.reverse_proxy: "{{upstreams 8080}}"
```

Keep the Docker socket/API boundary in the threat model. A read-only socket mount does not make Docker metadata harmless, and broad API visibility can reveal labels/configuration from unrelated stacks.

## Network Selection

- Put CDP and every routed service on one external ingress network.
- Set `CADDY_INGRESS_NETWORKS` on CDP.
- If supported by the deployed CDP version, a per-container `caddy_ingress_network` label can narrow selection further.
- Keep databases and internal dependencies off ingress unless the edge must reach them.
- Avoid generic service aliases on a shared external network; unique aliases reduce cross-project DNS ambiguity.

Inspect the live selection:

```bash
docker inspect caddy --format '{{json .NetworkSettings.Networks}}'
docker inspect app-api --format '{{json .NetworkSettings.Networks}}'
docker network inspect agent-ingress
```

Replace example container/network names with discovered values; do not bake fixed names into reusable Compose files.

## Generated Configuration

Use three views:

```bash
docker compose config --format json
docker inspect app-api --format '{{json .Config.Labels}}'
docker compose logs --since 10m caddy
```

Then inspect Caddy's adapted or live JSON through a protected local admin endpoint when available. Never expose the admin API publicly. A label can be present on a container yet absent from live config because translation rejected it or another block replaced it.

## Failure Signatures

| Symptom | Likely layer |
|---|---|
| Default/fallback site | Host not present in live generated config |
| 502 immediately | No reachable upstream, wrong network/port, TLS handshake failure |
| 502 only for gRPC | h2c/HTTPS/ALPN mismatch |
| Works by container IP, fails by service name | Docker DNS alias ambiguity or network mismatch |
| HTTPS upstream fails by IP | SNI or CA identity mismatch |
| Web page works, socket disconnects | Upgrade auth/origin/idle behavior |
| Route changes ignored after restart | Container needed recreation, not process restart |
| Directive missing | Caddy image lacks required module |

## Security Boundary

The Docker socket is effectively infrastructure control. Prefer a narrowly scoped socket proxy where the deployment supports one; otherwise mount read-only and prevent untrusted containers from controlling labels on the watched Docker endpoint. Labels are configuration input, not harmless metadata.

Do not trust broad RFC1918 or Docker bridge ranges for client-IP authorization merely because requests pass through them. Trust only known proxy hops and sanitize forwarded headers at the edge.

## Sources

- Caddy Docker Proxy: https://github.com/lucaslorentz/caddy-docker-proxy
- CDP upstream template implementation: https://github.com/lucaslorentz/caddy-docker-proxy/blob/master/generator/labels.go
- CDP label-prefix flag and environment binding: https://github.com/lucaslorentz/caddy-docker-proxy/blob/master/cmd.go
- Caddy `reverse_proxy`: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- Caddy request matchers and route ordering: https://caddyserver.com/docs/caddyfile/matchers
- Docker Compose networking: https://docs.docker.com/compose/how-tos/networking/
- Docker socket security context: https://docs.docker.com/engine/security/protect-access/
