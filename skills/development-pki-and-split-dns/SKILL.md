---
name: development-pki-and-split-dns
description: Use when choosing certificates and DNS for local, isolated, firewalled, or multi-worktree development environments, including internal CAs, public wildcard certificates, and split-horizon resolution.
license: MIT
compatibility: Requires control of the relevant client trust stores or DNS zones. Public certificate flows require a CA-supported registered domain; private-only names should use internal PKI.
metadata:
  author: "Brotal LLC"
  version: "1.0.0"
  platforms: "linux,macos,windows"
  parent: "collision-free-agentic-development"
  companions: "cloudflare-tunnels-and-caddy-dns,caddy-docker-proxy-routing,compose-development-environments"
---

# Development PKI and Split DNS

## When to Use

Load this skill when deciding between Caddy's internal CA and public ACME, designing wildcard certificate policy for ephemeral development hosts, or resolving the same test hostname differently inside an isolated/private network.

## Decision Table

| Environment | DNS | Certificate |
|---|---|---|
| `localhost` or invented private-only name | local resolver/hosts for tiny scope | Caddy `tls internal` / internal CA |
| Private address using a real controlled domain | split-horizon DNS | Internal CA, or public wildcard obtained by DNS-01 |
| Publicly reachable stable hostname | public DNS | Public automatic HTTPS via HTTP-01/TLS-ALPN-01 or DNS-01 |
| Many ephemeral worktree hosts | wildcard/split DNS | Prefer one deliberately managed wildcard via DNS-01 over leaf issuance per stack |

Public HTTP-01 is not valid for bare `localhost`, and wildcard certificates require DNS-01. DNS-01 can issue for a name whose application origin remains private because validation proves DNS control rather than reachability.

## Certificate Policy

1. Use the internal CA for local/private development when every client can trust the root.
2. Use public certificates only for controlled registered domains and policy-compliant use.
3. For high-churn worktrees, centralize a wildcard such as `*.dev.example.com` rather than requesting a leaf certificate for every branch and recreation.
4. Remember that `*.dev.example.com` does not cover `dev.example.com`; include the apex/base SAN separately when needed.
5. Do not assume leaf-host Caddy labels automatically reuse a wildcard. Configure certificate automation/route ownership centrally and verify the served certificate.
6. Preserve Caddy `/data`; deleting it discards account/certificate state and can trigger needless reissuance.
7. Respect CA subscriber agreements, TOS/Fair Usage Policy, and current rate limit documentation. Use staging while testing automation.
8. Never commit private keys, internal root keys, ACME account state, or DNS API tokens.

See [certificate-and-resolution-policy.md](references/certificate-and-resolution-policy.md) for wildcard topology, trust distribution, and split DNS.

## Internal CA Workflow

- Persist the Caddy data directory.
- Export only the root certificate needed for trust distribution; protect the root private key in Caddy state.
- Install the root into each host OS/browser trust store and any container/client trust bundle that validates the service.
- Restart applications that cache trust stores.
- Verify hostname SAN, chain, and client trust without `-k`/insecure flags.

Internal CA trust is an administrative act. Do not silently modify a machine-wide trust store in a reusable script.

## Split-Horizon DNS

Split DNS returns private addresses to authorized internal clients while public resolvers return a public address or no application address. Use it for firewalled environments where hairpin NAT, public routing, or exposing origins would be wrong.

Design explicitly:

- authoritative zone and ownership;
- internal resolver views/zones;
- wildcard versus application-specific records;
- TTL and negative-cache behavior;
- VPN/container resolver paths;
- firewall policy from each client segment to ingress;
- behavior for unauthorized/off-network clients.

An internal record pointing at a private address does not grant network reachability. DNS and firewall acceptance must both be tested.

## Wildcard versus Application-Specific Records

- Wildcard DNS reduces per-worktree record churn but explicit records override it.
- Wildcard certificates reduce issuance churn and CA load, but broaden private-key impact.
- Application-specific certificates narrow key scope and improve per-host revocation, but high-churn automated issuance can violate reasonable-use expectations or hit rate limits.
- A shared wildcard key belongs only on the trusted ingress tier, never copied into application worktrees.

Use separate development subzones to keep wildcard and token scope away from production names.

## Verification

```bash
dig app.dev.example.com A
dig app.dev.example.com AAAA
openssl s_client -connect app.dev.example.com:443 -servername app.dev.example.com
curl --fail --show-error https://app.dev.example.com/health
```

Run equivalent DNS and TLS checks from:

- host;
- container network;
- VPN/private client;
- public/off-network resolver where applicable.

Do not use `curl -k` as acceptance evidence.

## Common Gotchas

- Internal DNS returns an RFC1918/private address, but the VPN lacks a route or firewall permission.
- Public resolver cached NXDOMAIN before the record existed; negative caching outlives the fix.
- Browser trusts the internal CA while a CLI/container uses a different trust store.
- Wildcard covers one label only; `api.feature.dev.example.com` is not covered by `*.dev.example.com`.
- Public and internal zones drift, producing a certificate for one name and routing another.
- Recreating Caddy without persistent state causes avoidable ACME churn.
- Split DNS is replaced by enormous `/etc/hosts` files that cannot serve containers or teams consistently.
- Public wildcard key is mounted into every app container, multiplying compromise scope.

## Verification Checklist

- [ ] Certificate mode matches name reachability and trust model
- [ ] Wildcard/apex/SAN coverage tested explicitly
- [ ] CA policy and current rate limit guidance reviewed
- [ ] Caddy certificate/account state persists
- [ ] Root CA certificate distributed deliberately; private key remains protected
- [ ] Internal/public DNS answers match the intended client view
- [ ] VPN routes and firewall permit only intended private clients
- [ ] TLS succeeds without insecure bypass from every supported client class
