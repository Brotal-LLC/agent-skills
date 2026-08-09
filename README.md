# Brotal Agent Skills

Portable [Agent Skills](https://agentskills.io/) for reliable software-development and infrastructure workflows.

## Catalog

### Development environment orchestration

| Skill | Purpose | Platforms |
|---|---|---|
| [`collision-free-agentic-development`](skills/collision-free-agentic-development/) | Parent workflow for parallel Docker Compose hot-reload environments across branches, clones, worktrees, humans, and coding agents. | Linux, macOS Docker Desktop, Windows Docker Desktop/WSL2 |
| [`compose-development-environments`](skills/compose-development-environments/) | Compose layering, profiles, project isolation, merge semantics, lifecycle, and evidence-first debugging. | Linux, macOS Docker Desktop, Windows Docker Desktop/WSL2 |

### Development containers and tooling

| Skill | Purpose | Platforms |
|---|---|---|
| [`rootless-dev-container-filesystems`](skills/rootless-dev-container-filesystems/) | Non-root UID/GID, read-only source, writable workspaces, named volumes, tmpfs, and mount ownership. | Linux, macOS Docker Desktop, Windows Docker Desktop/WSL2 |
| [`dev-container-package-caches`](skills/dev-container-package-caches/) | Safe NuGet, npm, pnpm, Yarn, Maven, Gradle, Cargo, pip, and uv cache topology and invalidation. | Linux, macOS Docker Desktop, Windows Docker Desktop/WSL2 |
| [`containerized-development-tooling`](skills/containerized-development-tooling/) | Container-resident LSPs, devcontainer setup, watchers, logs, health/readiness, and secure debugger attachment. | Linux, macOS Docker Desktop, Windows Docker Desktop/WSL2 |

### Ingress, PKI, and private networking

| Skill | Purpose | Platforms |
|---|---|---|
| [`caddy-docker-proxy-routing`](skills/caddy-docker-proxy-routing/) | CDP labels, route ownership, network selection, and HTTP/HTTPS/h2c/gRPC/WebSocket/FastCGI upstream gotchas. | Linux containers on supported Docker hosts |
| [`development-pki-and-split-dns`](skills/development-pki-and-split-dns/) | Internal CA, public/wildcard certificate policy, CA fair use, trust distribution, and split-horizon DNS. | Linux, macOS, Windows/WSL2 clients |
| [`cloudflare-tunnels-and-caddy-dns`](skills/cloudflare-tunnels-and-caddy-dns/) | Named Cloudflare tunnels, private routes, connector topology, and scoped Cloudflare DNS-01 for Caddy. | Linux containers on supported Docker hosts |

The parent skill routes agents to the focused companions. Each companion is also independently installable; use the smallest set that owns the task instead of loading the entire catalog for sport.

## Installation

### Agent Skills clients

Browse/select skills through the open skills CLI:

```bash
npx skills add Brotal-LLC/agent-skills
```

Install the parent directly:

```bash
npx skills add Brotal-LLC/agent-skills --skill collision-free-agentic-development
```

Install a focused companion by replacing the skill name, for example:

```bash
npx skills add Brotal-LLC/agent-skills --skill caddy-docker-proxy-routing
```

The CLI prompts for supported target agents and project/global scope. Add `-g` for a global install or `--copy` when symlinks are unsuitable.

Manual fallback:

```bash
git clone https://github.com/Brotal-LLC/agent-skills.git
```

Each `skills/<skill-name>/` directory is an installable unit; the repository root is the catalog.

### Hermes Agent

Install a direct GitHub skill identifier. Hermes reports a community-source CAUTION because this skill intentionally contains container networking, subprocess-based Docker checks, and platform CA trust commands. First inspect the immutable source and every scanner finding; after approving that exact bundle, make the override explicit:

```bash
hermes skills install Brotal-LLC/agent-skills/skills/collision-free-agentic-development --yes --force
```

Or add the catalog as a tap:

```bash
hermes skills tap add Brotal-LLC/agent-skills
```

Then browse/install through `hermes skills browse`. See the current Hermes documentation if CLI behavior changes: <https://hermes-agent.nousresearch.com/docs/>.

## Quality and compatibility

Every skill follows the open Agent Skills frontmatter contract. `skills.sh.json` groups the catalog for compatible discovery clients. The repository gate checks all text files, compiles Python, validates portable top-level metadata, rejects private infrastructure identifiers and secret-shaped values, and runs unit/contract tests.

Install pinned development tools and tracked pre-commit hooks:

```bash
python -m pip install -r requirements-dev.txt
pre-commit install
pre-commit run --all-files
python scripts/validate_skills.py
```

The dynamic validator discovers every `skills/*/SKILL.md`; CI does not keep a hand-maintained one-skill allowlist.

The organization-maintained `ghcr.io/skb50bd/caddy:latest` ingress image is the catalog's one deliberate project-policy exception to the no-floating-tags rule. Contract tests permit that exact image and reject every other newly copied `:latest` image; Cloudflared and application examples remain version- or digest-pinned.

The parent skill's templates additionally receive all-mode Compose render tests, a real non-root Node dev-container runtime and same-container restart smoke, and live per-worktree PostgreSQL/Redis isolation smoke on Linux. Helper path separators, identity, environment generation, and safety checks run in CI on Linux, macOS, and Windows.

```bash
python tests/smoke_compose.py
python tests/smoke_node_runtime.py
python tests/smoke_data_runtime.py
```

## Repository layout

```text
skills.sh.json
skills/<skill-name>/
├── SKILL.md
├── references/
├── scripts/
└── templates/

tests/
scripts/check_repo.py
scripts/validate_skills.py
```

Only directories needed by a skill are present; reference-only companions do not carry ornamental empty folders.

## Contributing

1. Create a branch; do not work directly on `main`.
2. Write or update contract tests first and confirm the relevant test fails.
3. Keep `SKILL.md` concise; move protocol matrices and deep gotchas into focused references.
4. Keep parent/companion boundaries explicit and avoid duplicating long procedures.
5. Use standard-library helpers where practical and make destructive operations explicit.
6. Run `python scripts/check_repo.py`, `python scripts/validate_skills.py`, and relevant live smoke tests.
7. Open a pull request with verification evidence and no private URLs, IPs, tokens, certificates, or conversation identifiers.

## Security

Treat bundled scripts as code: review them before execution. Never commit real `.env` files, certificates or private keys, API/tunnel tokens, passwords, or private infrastructure identifiers.

DNS-provider credentials belong only at trusted ingress. Wildcard private keys remain on that ingress rather than being copied into application worktrees. Debuggers, Docker APIs, Caddy admin APIs, databases, and package-registry credentials must not be exposed through shared ingress or tunnels.

## License

MIT — see [LICENSE](LICENSE).
