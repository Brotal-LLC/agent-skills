# Tunnels and DNS Challenge

## Separate Credentials by Capability

| Credential | Used by | Capability |
|---|---|---|
| Tunnel connector token | `cloudflared` | Connect a specific named tunnel |
| Cloudflare DNS API token | Caddy DNS provider | Read zone and edit DNS validation records |
| Account/API provisioning token | Controlled administrative workflow | Create/manage tunnels or DNS resources |

A runtime connector should not receive the administrative token used to create it. A Caddy DNS token should not be mounted into every application. Rotate each independently and keep files out of source control.

## Named Tunnel Configuration

Locally managed configuration illustrates deterministic ingress order:

```yaml
tunnel: "00000000-0000-0000-0000-000000000000"
credentials-file: /run/secrets/tunnel-credentials.json
ingress:
  - hostname: app.dev.example.com
    service: https://caddy:443
    originRequest:
      originServerName: app.dev.example.com
      httpHostHeader: app.dev.example.com
  - hostname: api.dev.example.com
    service: http://api:8080
  - service: http_status:404
```

Remotely managed tunnels store ingress configuration in Cloudflare and commonly run from a connector token. The same routing invariants apply. Validate the configuration with the installed `cloudflared` version before deployment.

Use Docker service DNS names only when `cloudflared` and the origin share a network. `localhost` inside the connector is the connector itself.

The Caddy route above is one complete **verified HTTPS origin profile**:

- Caddy must serve a certificate whose SAN covers `app.dev.example.com`.
- `originServerName` supplies the certificate-verification name and TLS SNI even though Docker resolves the origin as `caddy`.
- `httpHostHeader` selects the same Caddy virtual host after TLS is established.
- A public/wildcard certificate uses the connector image's normal CA bundle. For Caddy internal PKI, mount the internal root read-only into `cloudflared` and set `caPool` to that file:

  ```yaml
  originRequest:
    originServerName: app.dev.example.com
    httpHostHeader: app.dev.example.com
    caPool: /run/caddy-pki/root.crt
  ```

  Mount only the public root certificate, never Caddy's CA private key. A Compose bind mount can use `target: /run/caddy-pki/root.crt` with `read_only: true`; keep the root path outside application source and distribute it through the development trust workflow.
- Do not replace trust configuration with `noTLSVerify`.

Do not send a normal hostname-based Caddy site to `http://caddy:80`: Caddy's automatic HTTPS redirects it back to the same public HTTPS hostname, whose next request re-enters the tunnel and repeats the HTTP origin hop. An HTTP private hop is valid only with a separately scoped Caddy site that is explicitly HTTP/no-redirect; it is not interchangeable with the profile above.

## Origin Choice

### Tunnel to Caddy

Benefits:

- one host/path routing policy;
- consistent auth/security headers;
- one place for upstream protocol and observability;
- direct and tunneled access can converge.

Use the complete verified HTTPS profile above unless the deployment deliberately owns an explicit HTTP/no-redirect Caddy site. Do not mix the HTTPS public hostname with an HTTP origin and hope automatic HTTPS understands the topology; it understands redirects, enthusiastically.

### Tunnel directly to application

Benefits:

- fewer hops;
- useful for a single intentionally isolated service.

Costs:

- bypasses Caddy auth/headers/routing/logging;
- hostname must not also be claimed by unnecessary CDP labels;
- application must trust forwarded headers only from the connector path;
- protocol support must be verified directly.

Document this as a security-boundary decision, not an optimization discovered by accident.

## Connector High Availability

Multiple connectors for one named tunnel are active capacity, not passive standby. Cloudflare can send traffic through any healthy connection. Therefore every connector location must reach every origin in the shared ingress configuration.

Safe patterns:

- identical origin topology on every connector host;
- each local Caddy can forward missing routes to the correct private origin;
- separate tunnels for connector groups with different reachable origins.

Unsafe pattern: start a second connector that cannot resolve half the Docker service names and hope traffic prefers the first. Hope remains unsupported as a load-balancing policy.

## Connector Transport and Firewall

`cloudflared` connects outbound to Cloudflare on port `7844`: UDP for QUIC or TCP for HTTP/2. A positive security model can block unsolicited ingress while allowing only the documented connector egress destinations/protocols.

Leave protocol selection on `auto` unless measured firewall/network behavior requires an explicit choice. Repeated QUIC handshake timeouts followed by HTTP/2 success indicate an egress-policy or UDP-path issue, not an application-origin defect. Verify connector transport logs before changing Caddy or the app.

## Private Network Routes

Private network routing requires:

- route advertised by the tunnel;
- client connected through supported Zero Trust/WARP mode;
- device/user policy authorizing access;
- DNS resolution path for private hostnames when hostname routing is used;
- private firewall allowing connector-to-origin traffic.

Test from an enrolled authorized client and an unauthorized client. A route in the dashboard alone proves control-plane configuration, not packet delivery.

## DNS-01 with Caddy

A Caddy build needs `github.com/caddy-dns/cloudflare`. Verify:

```bash
caddy list-modules | grep dns.providers.cloudflare
```

Provide the token through Caddy's environment/secret boundary and reference it from the Caddy TLS issuer configuration. Required zone-scoped permissions are commonly `Zone:DNS:Edit` and `Zone:Zone:Read`; use the narrow development zone resource.

DNS-01 creates `_acme-challenge` TXT records. Public A/AAAA reachability is not required. Wildcard certificates require DNS-01.

When delegating `_acme-challenge` through CNAME/NS records, confirm the ACME client/provider follows the selected delegation and scope tokens only to the validation zone. Test with CA staging first.

## Wildcard Certificate Policy

For a large number of ephemeral services:

- issue `*.dev.example.com` centrally;
- add `dev.example.com` separately if the base is served;
- keep the private key only on trusted ingress;
- flatten hostnames or issue another depth when multiple labels are required;
- verify Caddy actually serves the wildcard rather than requesting leaf certificates;
- preserve Caddy state across recreation;
- monitor renewal and failure logs.

Wildcard certificates reduce ACME churn but increase key impact. Refer to `development-pki-and-split-dns` before choosing them.

## Protocol and Header Verification

For every tunnel route, verify:

- HTTP status/body/version marker;
- `Host` received by origin;
- client-IP/header trust chain;
- WebSocket `101` and data frames where used;
- native gRPC where used;
- upload/stream timeout behavior;
- direct/internal path separately from tunnel path.

For a known health route, make redirects fail the tunnel-path probe rather than silently following a loop:

```bash
curl --fail-with-body --show-error --silent --location --max-redirs 0 https://app.dev.example.com/health
```

Then verify Caddy logs show an HTTPS origin request with the intended host. A successful connector status does not prove origin TLS, route selection, or redirect safety.

Do not trust all forwarded headers from arbitrary Docker peers. Limit trusted proxies to the connector/Caddy boundary and sanitize at the first trusted hop.

## Operations

After changing token, image, command, networks, or ingress config:

```bash
docker compose config --quiet
docker compose up --detach --force-recreate tunnel
```

Then inspect bounded logs and Cloudflare connection state. A connected connector plus a 502 means transport succeeded only as far as the connector.

## Sources

- Cloudflare Tunnel overview: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
- Cloudflare Tunnel configuration: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/local-management/configuration-file/
- cloudflared origin-request configuration fields: https://github.com/cloudflare/cloudflared/blob/master/ingress/config.go
- Cloudflare Tunnel private networks: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/private-net/
- Cloudflare Tunnel firewall/connector transport: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/tunnel-with-firewall/
- Cloudflare tunnel permissions and tokens: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/remote-management/
- Caddy Cloudflare DNS provider: https://github.com/caddy-dns/cloudflare
- Caddy DNS challenge: https://caddyserver.com/docs/automatic-https#dns-challenge
- Cloudflare API token permissions: https://developers.cloudflare.com/fundamentals/api/reference/permissions/
