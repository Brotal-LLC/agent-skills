# Brotal Agent Skills

Portable [Agent Skills](https://agentskills.io/) for reliable software-development and infrastructure workflows.

## Catalog

| Skill | Purpose | Platforms |
|---|---|---|
| [`collision-free-agentic-development`](skills/collision-free-agentic-development/) | Run parallel Docker Compose hot-reload environments for branches, clones, worktrees, humans, and coding agents without hostname, port, container, volume, database, cache, or certificate collisions. | Linux, macOS Docker Desktop, Windows Docker Desktop/WSL2 |

## Installation

### Agent Skills clients (Claude Code, Codex, Cursor, OpenCode, and others)

Install through the open skills CLI:

```bash
npx skills add Brotal-LLC/agent-skills --skill collision-free-agentic-development
```

The CLI prompts for target agents and project/global scope. Add `-g` for a global install or `--copy` when symlinks are unsuitable.

Manual fallback: clone this repository, then copy or link the skill folder according to the client's skill-directory convention.

```bash
git clone https://github.com/Brotal-LLC/agent-skills.git
```

The installable unit is `skills/collision-free-agentic-development/`, not the repository root.

### Hermes Agent

Hermes can install a direct GitHub skill identifier:

```bash
hermes skills install Brotal-LLC/agent-skills/collision-free-agentic-development
```

Or add the catalog as a tap:

```bash
hermes skills tap add Brotal-LLC/agent-skills
```

Then browse/install through `hermes skills browse`. See the current Hermes documentation if CLI behavior changes: <https://hermes-agent.nousresearch.com/docs/>.

## Quality and compatibility

Every skill follows the open Agent Skills frontmatter contract. The repository gate checks all text files, compiles Python, validates portable top-level metadata, rejects private infrastructure identifiers and secret-shaped values, and runs unit/contract tests.

```bash
python scripts/check_repo.py
```

Compose templates receive all-mode render tests, a real non-root Node dev-container runtime and same-container restart smoke test, and a live per-worktree PostgreSQL/Redis isolation smoke test on Linux. The helper's path separator, identity, environment generation, and safety checks run in CI on Linux, macOS, and Windows.

Install pinned development tools and the tracked pre-commit hooks:

```bash
python -m pip install -r requirements-dev.txt
pre-commit install
pre-commit run --all-files
agentskills validate skills/collision-free-agentic-development
python tests/smoke_compose.py
python tests/smoke_node_runtime.py
python tests/smoke_data_runtime.py
```

## Repository layout

```text
skills/<skill-name>/
├── SKILL.md
├── references/
├── scripts/
└── templates/

tests/
scripts/check_repo.py
```

## Contributing

1. Create a branch; do not work directly on `main`.
2. Write or update contract tests first and confirm the relevant test fails.
3. Keep `SKILL.md` concise; move detailed material into focused references.
4. Use standard-library helpers where practical and make destructive operations explicit.
5. Run `python scripts/check_repo.py` and any skill-specific live smoke tests.
6. Open a pull request with verification evidence and no private URLs, IPs, tokens, or conversation identifiers.

## Security

Treat bundled scripts as code: review them before execution. Never commit real `.env` files, certificates with private keys, API tokens, passwords, or private infrastructure identifiers. The collision-free development skill deliberately keeps DNS-provider credentials in the shared ingress environment rather than application worktrees.

## License

MIT — see [LICENSE](LICENSE).
