# TLS, DNS, and Shared Caddy Ingress

## Shared ingress bootstrap

Copy `templates/ingress/` to one machine-level infrastructure directory, copy `.env.example` to gitignored `.env`, then start it once:

```bash
docker compose config --quiet
docker compose up --detach
```

The template uses `ghcr.io/skb50bd/caddy`, a custom Caddy image that includes `github.com/lucaslorentz/caddy-docker-proxy/plugin/v2` and the Cloudflare DNS module. The generic contract is Caddy Docker Proxy; operators may substitute a compatible, pinned image. In durable environments, pin a release or OCI digest rather than floating `latest`.

Only the ingress publishes port 80 and port 443. It persists `/data` and `/config`; `/data` contains ACME certificates and the internal CA. Never casually run `docker compose down --volumes` against ingress.

The direct Docker socket mount is simple but security-sensitive: access to the Docker API is effectively host control. On multi-user or less-trusted machines, put a least-privilege Docker socket proxy in front of Caddy and expose only the read endpoints Caddy Docker Proxy needs.

Caddy Docker Proxy network discovery is best-effort. Set `CADDY_INGRESS_NETWORKS` explicitly and attach every routed app service to that same network. Source: <https://github.com/lucaslorentz/caddy-docker-proxy>.

## Choose one certificate mode

### 1. Internal CA (`tls internal`)

Best default for private workstations, offline development, and `*.localhost`. Select `compose.tls-internal.yaml`. Caddy issues certificates from its internal CA; clients must trust the CA root.

Export and print platform-specific trust commands:

```bash
python "$SKILL_DIR/scripts/devstack.py" export-ca \
  --container agent-ingress-caddy \
  --output ./agent-ingress-root.crt
```

The root normally lives at `/data/caddy/pki/authorities/local/root.crt`. Trust it deliberately:

- Linux Debian/Ubuntu: copy it to `/usr/local/share/ca-certificates/` and run `update-ca-certificates`.
- Linux Fedora/RHEL: copy it under `/etc/pki/ca-trust/source/anchors/` and run `update-ca-trust`.
- macOS: use `security add-trusted-cert` against the System keychain.
- Windows: use elevated PowerShell `Import-Certificate` into `Cert:\\LocalMachine\\Root`.

Some browsers maintain a separate trust store; verify the actual browser, not only `curl`. Never distribute Caddy's internal CA private key. Back up the Caddy data volume if stable trust across host rebuilds matters.

Caddy reference: <https://caddyserver.com/docs/caddyfile/directives/tls>.

### 2. Public ACME with HTTP-01/TLS-ALPN-01

Select no TLS overlay (`--tls http`). A normal `caddy` site label enables Automatic HTTPS. Requirements:

- Every exact hostname resolves publicly to the ingress host.
- Inbound port 80 and port 443 reach Caddy without another process intercepting challenges.
- NAT/firewall rules permit the validation path.
- The hostname is not an internal-only split-horizon address from the CA's perspective.

HTTP-01 validates via port 80 and cannot issue wildcard certificates. Caddy may also use TLS-ALPN-01 on 443. If a CDN proxy sits in front, DNS-only mode during issuance is the least surprising path; otherwise verify that challenge traffic reaches this Caddy instance. Do not open public ports merely to satisfy local development when internal CA or DNS-01 fits better.

Automatic HTTPS reference: <https://caddyserver.com/docs/automatic-https>.

### 3. Public ACME with Cloudflare DNS-01

Select `compose.tls-cloudflare.yaml`. DNS-01 works without exposing the ingress host to the public internet and is required for wildcard certificates. The Cloudflare token belongs only in the ingress stack's gitignored `.env`; application containers do not need it. App labels reference `{env.CLOUDFLARE_API_TOKEN}`, which Caddy resolves inside the ingress container.

Use a narrowly scoped API token:

- Permissions: `Zone:DNS:Edit` and `Zone:Zone:Read`.
- Resources: only the required zone or zones.
- No global API key.

DNS-01 creates temporary `_acme-challenge` TXT records; it does not make application hostnames resolve. Add one of:

- Public exact/wildcard A and AAAA records pointing to the ingress host.
- Private split-horizon DNS records pointing to the LAN/VPN address.
- Exact hosts-file entries for a small local-only set.

A wildcard DNS record routes names; it is not a certificate. A wildcard certificate proves names; it does not route them. Confusing those two has funded many fine debugging sessions.

For local-only public names, split-horizon DNS is usually cleanest: the authoritative public zone permits DNS-01 TXT updates while local clients resolve application names to the private ingress address.

## Label overlays

Base dev labels own routing only:

```yaml
labels:
  caddy: ${WEB_HOST:?WEB_HOST required}
  caddy.reverse_proxy: "{{upstreams 3000}}"
```

TLS overlays merge one issuer choice into each routed service. Do not activate both internal and Cloudflare overlays. After changing hostname, issuer labels, token exposure, or ingress networks, apply by recreation:

```bash
docker compose config --quiet
docker compose up --detach --force-recreate
```

`docker compose restart` retains the old labels, environment, and networks.

## Verification

1. Inspect rendered labels: `docker compose config --format json`.
2. Inspect running labels and ingress attachment with `docker inspect`.
3. Check Caddy logs for config-adaptation and ACME errors.
4. Resolve each hostname from the client that will use it.
5. Request every hostname over HTTPS and inspect issuer/SAN/expiry.
6. Open the app in a browser and verify HMR/WebSocket reconnection; an HTTP 200 alone does not prove hot reload survives the proxy.
