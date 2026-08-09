---
name: caddy-docker-proxy-routing
description: Use when routing Docker or Compose services through Caddy Docker Proxy, especially when upstream protocols, shared hostnames, TLS transports, or ingress-network selection can fail silently.
license: MIT
compatibility: Requires Docker, Caddy Docker Proxy, and label-compatible Compose or Docker APIs. Examples target Linux containers on Linux, macOS Docker Desktop, and Windows Docker Desktop/WSL2.
metadata:
  author: "Brotal LLC"
  version: "1.0.0"
  platforms: "linux,macos,windows"
  parent: "collision-free-agentic-development"
  companions: "compose-development-environments,development-pki-and-split-dns,cloudflare-tunnels-and-caddy-dns"
---

# Caddy Docker Proxy Routing

## When to Use

Load this skill when a Docker service must be discovered from labels, when a route returns 404/502 despite a healthy container, or when the upstream is HTTPS, h2c, gRPC, WebSocket, or FastCGI rather than ordinary HTTP/1.1.

Load `collision-free-agentic-development` first when the goal is a complete parallel worktree environment. This companion owns ingress translation and transport correctness; it does not own source mounts, package caches, or certificate policy.

## Invariants

1. Confirm the running edge is actually Caddy Docker Proxy (CDP), not static Caddy. Labels do nothing to a static Caddyfile process.
2. Every routed service and CDP share at least one explicitly selected ingress network.
3. Run one default `caddy` label namespace per Docker API endpoint. `CADDY_INGRESS_NETWORKS` selects upstream addresses; it does not scope discovery.
4. Use one route owner to define the complete route tree for a hostname. Do not expect labels from unrelated containers to merge safely.
5. Use the container listen port, never a host-published port, in `{{upstreams ...}}`.
6. Select the upstream protocol deliberately. A TCP connection is not proof that HTTP, TLS, ALPN, or gRPC semantics match.
7. Keep Docker API access read-only where supported and isolate the proxy from untrusted workloads.
8. Render labels, inspect generated Caddy config, and probe the real routed request before declaring success.

## Baseline Labels

```yaml
services:
  api:
    expose:
      - "8080"
    labels:
      caddy: "${API_HOST:?API_HOST required}"
      caddy.reverse_proxy: "{{upstreams 8080}}"
    networks:
      - default
      - ingress

networks:
  ingress:
    external: true
    name: "${INGRESS_NETWORK:?INGRESS_NETWORK required}"
```

The CDP process should receive `CADDY_INGRESS_NETWORKS` with the same external network name. If a container joins several networks, make selection explicit rather than accepting whichever address discovery happens to return.

CDP still reads every matching label visible through its Docker API, including matching labels on containers outside the selected ingress network. Do not launch a second default-prefix CDP as a per-project convenience on a shared daemon. If multiple logical controllers are intentional, assign each a unique `CADDY_DOCKER_LABEL_PREFIX` and use that prefix instead of `caddy` on its workloads. A prefix is only a configuration namespace, not a security boundary; use a separate Docker daemon/API identity when workloads do not trust one another.

## Upstream Protocol Decision

| Upstream | CDP value | Additional requirement |
|---|---|---|
| HTTP/1.1 or HTTP/2 negotiated normally | `{{upstreams 8080}}` | Backend listens in cleartext on the selected port |
| HTTPS | `{{upstreams https 8443}}` | Configure correct `tls_server_name`; trust the upstream CA |
| h2c | `{{upstreams h2c 8080}}` | Backend truly supports cleartext HTTP/2, not merely HTTP/1.1 + HTTP/2 with TLS ALPN |
| gRPC without upstream TLS | `{{upstreams h2c 5000}}` | Preserve HTTP/2 end to end and probe a real RPC |
| gRPC with upstream TLS | `{{upstreams https 5001}}` | SNI, CA trust, and HTTP/2 ALPN must all match |
| WebSocket | ordinary HTTP/HTTPS upstream | Caddy handles upgrades automatically; test a real upgrade |
| SSE/streaming HTTP | ordinary HTTP/HTTPS upstream | Verify flush latency and cancellation; tune `flush_interval` only from evidence |
| FastCGI | `php_fastcgi`/FastCGI directive labels | It is not an HTTP reverse-proxy scheme |
| Raw TCP/UDP | not handled by HTTP `reverse_proxy` | Requires a separately installed Layer 4/transport solution and threat model |

For CDP's upstream template, the scheme is the first argument: `{{upstreams h2c 8080}}`. `h2c://{{upstreams 8080}}` is not equivalent and can generate unusable config.

See [upstream-protocols-and-routing.md](references/upstream-protocols-and-routing.md) for transport blocks, route ownership, generated-config inspection, and failure signatures.

## Workflow

1. Inspect the running Caddy command, modules, environment, networks, and Docker socket mount.
2. Inspect the backend's actual listen sockets and protocol configuration inside its container.
3. Render Compose with `docker compose config --format json`; verify final labels and networks.
4. Recreate after changing labels, networks, environment, command, or image:

```bash
docker compose up --detach --force-recreate --no-deps api
```

5. Inspect CDP logs and its generated Caddy configuration. A valid Compose model can still translate to a dropped or conflicting site block.
6. Probe the backend directly from a disposable container on ingress, then probe the public hostname through Caddy.
7. For gRPC/WebSocket, run a protocol-native client. HTTP 200 is decorative evidence, not protocol proof.

## Common Gotchas

- Two containers declare the same `caddy` hostname and one silently wins; give one container ownership or use distinct hostnames.
- A second default-prefix CDP on the same Docker socket imports the machine's other `caddy.*` labels. Use the shared singleton, a unique label prefix, or a separate Docker API boundary.
- A service is on `default` while CDP is only on `ingress`; Docker DNS may resolve a name to an unreachable address.
- `https` upstream points to an IP while the certificate expects a DNS name; set `tls_server_name` and trust the issuing CA.
- `tls_insecure_skip_verify` hides an identity failure. Use only as a bounded diagnostic, never as the completed fix.
- Kestrel configured for HTTP/1.1 + HTTP/2 on cleartext may still reject h2c because HTTP/2 selection normally relied on TLS ALPN.
- Caddy supports WebSocket upgrades automatically, but upstream auth, origin checks, or idle timeouts can still break the session.
- A custom directive label is ignored because the image lacks its Caddy module. Verify with `caddy list-modules`.
- Compose overlay label maps merge. Production imports may survive into development unless explicitly overridden.

## Verification Checklist

- [ ] Running edge confirmed as CDP and required modules listed
- [ ] Docker API discovery scope and label-prefix ownership confirmed
- [ ] Final labels inspected from rendered Compose and live container
- [ ] CDP and backend share the intended ingress network
- [ ] Correct container port and upstream scheme selected
- [ ] HTTPS upstream verifies CA and SNI without insecure bypass
- [ ] One owner controls each hostname route tree
- [ ] Generated Caddy config contains the expected host, matcher, and upstream
- [ ] Protocol-native request succeeds through the real hostname
- [ ] Label/network changes were applied with recreation
