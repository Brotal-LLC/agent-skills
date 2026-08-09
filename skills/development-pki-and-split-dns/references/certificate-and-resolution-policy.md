# Certificate and Resolution Policy

## Public versus Private Trust

### Internal CA

Choose internal PKI when names are local/private and all clients are administratively controlled. Caddy's local HTTPS issues from its internal CA. Persist Caddy's data directory and distribute the root certificate deliberately.

Advantages:

- no public DNS or CA dependency;
- works for local/private names;
- no public issuance churn.

Costs:

- every client trust store must be managed;
- unmanaged browsers/devices show warnings;
- root private key protection and rotation are your responsibility.

### Public CA

Choose public trust for registered domains used by unmanaged clients. HTTP-01/TLS-ALPN-01 require public validation reachability. DNS-01 proves DNS control and supports wildcard issuance without exposing the application origin.

Use the CA's staging endpoint while developing automation. Consult current production rate limits and subscriber agreement rather than copying old numeric limits into scripts.

## Wildcard Strategy for Development

A deliberate development hierarchy:

```text
dev.example.com               optional base portal
*.dev.example.com             one-label application/worktree hosts
```

If hosts require another label (`api.feature.dev.example.com`), a `*.dev.example.com` certificate does not match. Either flatten naming (`feature-api.dev.example.com`) or manage a separate wildcard at the correct depth.

Central wildcard policy:

1. Delegate or isolate a development DNS zone.
2. Give the trusted ingress a token limited to that zone.
3. Obtain both wildcard and base SAN if both are served.
4. Keep key material only in persisted ingress certificate storage.
5. Route leaf hosts through that ingress.
6. Inspect the served certificate for representative hosts.
7. Renew centrally and alert before expiry.

For Caddy 2.10 and newer, configure the wildcard site before/listed alongside leaf sites. Caddy then prefers the applicable wildcard certificate instead of requesting separate leaf certificates:

```caddyfile
*.dev.example.com {
	tls {
		dns cloudflare {env.CLOUDFLARE_API_TOKEN}
	}
	abort
}

app.dev.example.com {
	reverse_proxy app:8080
}
```

The wildcard site's `abort` prevents unknown development hosts from falling through to an application. In a CDP deployment, the wildcard certificate policy belongs on the trusted singleton ingress while application labels declare their leaf hosts/routes. Pin Caddy/CDP versions and inspect live certificate selection.

Before Caddy 2.10, or when the deployed adapter does not preserve wildcard preference, define one wildcard site and route leaf hosts with explicit `host` matchers/`handle` blocks. Do not assume that independent leaf site addresses consume the wildcard: older behavior can request leaf certificates anyway, defeating the issuance policy.

## Fair Usage and CA Policy

Avoid automation patterns that repeatedly:

- delete ACME account/certificate storage;
- issue on every container recreation;
- generate unique random public names for disposable tests;
- retry failed orders without backoff;
- use production ACME while debugging configuration.

A wildcard reduces order count but increases key blast radius. Balance CA load, rate limit risk, and private-key scope. Follow current CA TOS/Fair Usage Policy and rate limit docs; they can change independently of this skill.

## Internal Trust Distribution

Export the root certificate, not its private key. Install it in each relevant store:

- Linux system CA store;
- macOS Keychain;
- Windows certificate store;
- browser-specific stores when they do not use the OS;
- language runtimes/containers with custom CA bundles;
- WSL distribution separately from Windows when required.

Use the platform's supported trust tooling and obtain user/admin approval before machine-wide changes. Verify using the actual application client, not only OpenSSL.

## Split-Horizon Resolution

### Zone model

An internal DNS server can host an authoritative override for `dev.example.com` and return private ingress addresses. Public DNS can retain only the records needed for DNS-01 and optionally omit A/AAAA records.

Avoid accidentally shadowing the entire parent zone when only one development subzone is intended. An internal authoritative `example.com` zone without all public records makes unrelated public names disappear.

### Resolver paths

Test every path:

- host OS;
- WSL distribution;
- Docker embedded DNS;
- VPN clients;
- LAN clients;
- CI runners;
- public resolver.

Docker containers usually query Docker's embedded resolver, which forwards according to daemon/host configuration. A host resolving correctly does not prove a container sees the same view.

### TTL and NXDOMAIN

Use bounded TTLs during migration, then raise them for stability. Negative answers can be cached according to the zone's SOA negative TTL; flushing only the browser may not clear OS, VPN, or recursive-resolver caches.

### Firewall and routing

DNS answers are not routes. Verify:

- route to the private ingress subnet;
- firewall allows intended client segments to 443 (and 80 only if required);
- ingress does not expose backend service ports;
- off-network clients cannot reach private origin addresses;
- IPv6 policy matches IPv4 rather than accidentally bypassing it.

## Host Validation and Rebinding

Applications and dev servers may reject unknown `Host`/origin values. Configure exact development suffixes/hosts rather than disabling host validation globally. Treat DNS rebinding protections as security controls, especially when a public name resolves to private addresses.

## Acceptance Matrix

| Client | Expected DNS | Expected route | Expected trust |
|---|---|---|---|
| Local host | private ingress | allowed | system/internal or public CA |
| Dev container | private ingress | allowed | container trust bundle |
| VPN client | private ingress | allowed | managed trust/public CA |
| Public client | public edge or no address | policy-specific | public CA if served |
| Unauthorized LAN | no route or denied | denied | irrelevant |

## Sources

- Caddy automatic HTTPS and local HTTPS: https://caddyserver.com/docs/automatic-https
- Caddy wildcard certificate patterns: https://caddyserver.com/docs/caddyfile/patterns#wildcard-certificates
- Caddy local CA command: https://caddyserver.com/docs/command-line#caddy-trust
- Let's Encrypt challenge types: https://letsencrypt.org/docs/challenge-types/
- Let's Encrypt rate limits: https://letsencrypt.org/docs/rate-limits/
- Let's Encrypt integration guidance: https://letsencrypt.org/docs/integration-guide/
- RFC 6762 `.local` considerations: https://www.rfc-editor.org/rfc/rfc6762
- DNS negative caching: https://www.rfc-editor.org/rfc/rfc2308
