---
name: cloudflare-tunnels-and-caddy-dns
description: Use when connecting development services through Cloudflare named tunnels or issuing Caddy certificates with Cloudflare DNS-01, while keeping tokens scoped, origins private, and wildcard policy centralized.
license: MIT
compatibility: Requires a Cloudflare-managed zone or Zero Trust account, cloudflared for tunnels, and a Caddy build containing the Cloudflare DNS provider for DNS-01.
metadata:
  author: "Brotal LLC"
  version: "1.0.0"
  platforms: "linux,macos,windows"
  parent: "collision-free-agentic-development"
  companions: "development-pki-and-split-dns,caddy-docker-proxy-routing,compose-development-environments"
---

# Cloudflare Tunnels and Caddy DNS

## When to Use

Load this skill when choosing between a Cloudflare Tunnel and direct Caddy ingress, routing public or private tunnel hostnames to Compose services, or using Cloudflare DNS-01 for wildcard/public certificates.

A tunnel token and a DNS API token solve different problems:

- **Tunnel connector token:** allows `cloudflared` to connect one named tunnel.
- **DNS API token:** allows Caddy's DNS provider to create validation records.

Never substitute an account-wide API key because both contain the word Cloudflare.

## Architecture Decision

### Direct Caddy edge

Use when clients can reach the edge on 80/443 and Caddy should terminate TLS. Caddy can use HTTP-01/TLS-ALPN-01 or DNS-01.

### Public hostname tunnel

Use when outbound-only `cloudflared` should carry requests from Cloudflare to a private origin. Decide whether the tunnel origin is:

- Caddy, preserving one routing/TLS/header policy; or
- the application directly, bypassing Caddy deliberately.

Do not add a direct-tunnel hostname to Caddy Docker Proxy labels if traffic never traverses Caddy; that can trigger useless certificate automation and route conflicts.

### Private network route

Use a Cloudflare private network route when enrolled/authorized clients should reach private IPs or hostnames through Zero Trust/WARP. Publishing a DNS hostname alone does not create private routing or authorization.

See [tunnels-and-dns-challenge.md](references/tunnels-and-dns-challenge.md) for connector topology, ingress rules, and token boundaries.

## Named Tunnel Invariants

1. Use a named tunnel with a narrowly scoped connector token.
2. Run `cloudflared` non-root with read-only filesystem where possible and a writable tmpfs only for required runtime files.
3. Store the connector token in a gitignored mode-restricted secret file or platform secret store.
4. Every active connector for one tunnel must be able to satisfy every configured origin route, or requests become load-balanced failures.
5. End ingress rules with an explicit catch-all response.
6. Validate configuration before recreation.
7. Keep tunnel health separate from application readiness; a connected tunnel can still point at a dead origin.

## Tunnel Compose Shape

```yaml
services:
  tunnel:
    image: "${CLOUDFLARED_IMAGE:?set a version-or-digest-pinned cloudflared image}"
    user: "65532:65532"
    read_only: true
    command: ["tunnel", "--no-autoupdate", "run", "--token-file", "/run/secrets/tunnel-token"]
    volumes:
      - type: bind
        source: ./secrets/tunnel-token
        target: /run/secrets/tunnel-token
        read_only: true
    networks:
      - ingress
```

Set `CLOUDFLARED_IMAGE` in the project `.env` to a tested version tag or immutable digest. Do not commit `secrets/tunnel-token`.

## Caddy Cloudflare DNS-01

The Caddy image must contain the Cloudflare DNS provider module. Verify with `caddy list-modules` before configuring labels.

Use a scoped API token with:

- `Zone:DNS:Edit` for the development zone;
- `Zone:Zone:Read` for the development zone.

Inject `CLOUDFLARE_API_TOKEN` only into the trusted Caddy ingress. Application and worktree containers do not need it.

For ephemeral development hosts, prefer a centrally managed wildcard certificate obtained by DNS-01. Follow `development-pki-and-split-dns` for TOS/Fair Usage Policy, rate limit, apex coverage, and key-scope decisions.

## Split DNS and Tunnels

A public tunnel hostname normally resolves to Cloudflare, not directly to the private origin. A private-network hostname may use split DNS and a Cloudflare private route. Decide which path each client class uses; do not let public and private paths accidentally terminate at different app versions.

When split DNS sends internal clients directly to Caddy while public clients use a tunnel, verify both paths independently, including forwarded headers, authentication, WebSocket/gRPC behavior, and edge markers when multiple origins exist.

## Common Gotchas

- Tunnel is healthy but origin service is on a project-default network invisible to `cloudflared`.
- Two connectors share one tunnel but only one can resolve a configured origin, causing intermittent failures.
- Tunnel routes directly to app while stale Caddy labels request certificates for the same hostname.
- Caddy image lacks `dns.providers.cloudflare`; config exists but cannot load.
- API token can edit every account zone instead of one delegated development zone.
- Wildcard DNS/certificate covers one label depth only.
- Cloudflare proxy status and DNS-01 TXT validation are confused; DNS-01 needs authoritative TXT writes, not an exposed origin.
- Origin HTTPS certificate name differs from the hostname `cloudflared` sends; configure origin SNI/CA correctly rather than disabling verification.
- Private network route exists, but client enrollment/policy/DNS view is missing.
- Debugger/admin endpoints are accidentally included in a tunnel wildcard.

## Verification Checklist

- [ ] Tunnel and DNS tokens are distinct, scoped, external, and redacted
- [ ] `cloudflared` runs non-root and connector image is pinned
- [ ] Every active connector reaches every configured origin
- [ ] Ingress config has deterministic route order and final catch-all
- [ ] Tunnel connection and application readiness both pass
- [ ] Caddy image contains Cloudflare DNS provider
- [ ] DNS token limited to the development zone with required permissions
- [ ] Wildcard/leaf issuance follows documented certificate policy
- [ ] Public, direct-private, and WARP/private paths return the intended version
- [ ] No debugger, Docker API, Caddy admin API, or database is tunneled
