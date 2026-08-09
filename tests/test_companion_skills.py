from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "skills"
PARENT = "collision-free-agentic-development"
COMPANIONS = {
    "caddy-docker-proxy-routing": {
        "reference": "references/upstream-protocols-and-routing.md",
        "terms": (
            "CADDY_INGRESS_NETWORKS",
            "CADDY_DOCKER_LABEL_PREFIX",
            "does not scope discovery",
            "{{upstreams h2c 8080}}",
            "tls_server_name",
            "WebSocket",
            "gRPC",
            "one route owner",
        ),
    },
    "compose-development-environments": {
        "reference": "references/merge-lifecycle-and-debugging.md",
        "terms": (
            "COMPOSE_PROJECT_NAME",
            "COMPOSE_FILE",
            "docker compose config",
            "--force-recreate",
            "profiles",
            "container_name",
        ),
    },
    "rootless-dev-container-filesystems": {
        "reference": "references/mount-ownership-patterns.md",
        "terms": (
            "UID",
            "GID",
            "read-only source",
            "named volume",
            "tmpfs",
            "root-owned",
            "/workspace",
        ),
    },
    "dev-container-package-caches": {
        "reference": "references/package-cache-matrix.md",
        "terms": (
            "NUGET_PACKAGES",
            "npm_config_cache",
            "pnpm",
            "Yarn",
            "Maven",
            "Gradle",
            "CARGO_HOME",
            "lockfile",
        ),
    },
    "containerized-development-tooling": {
        "reference": "references/lsp-logs-and-debugging.md",
        "terms": (
            "LSP",
            "devcontainer",
            "docker compose logs",
            "docker inspect",
            "healthcheck",
            "readiness",
            "watcher",
        ),
    },
    "development-pki-and-split-dns": {
        "reference": "references/certificate-and-resolution-policy.md",
        "terms": (
            "internal CA",
            "split-horizon",
            "wildcard",
            "DNS-01",
            "HTTP-01",
            "rate limit",
            "trust store",
            "NXDOMAIN",
        ),
    },
    "cloudflare-tunnels-and-caddy-dns": {
        "reference": "references/tunnels-and-dns-challenge.md",
        "terms": (
            "cloudflared",
            "named tunnel",
            "CLOUDFLARE_API_TOKEN",
            "Zone:DNS:Edit",
            "Zone:Zone:Read",
            "DNS-01",
            "wildcard",
            "private network",
        ),
    },
}


def skill_text(slug: str) -> str:
    return (SKILLS / slug / "SKILL.md").read_text(encoding="utf-8")


class CompanionSkillCatalogTests(unittest.TestCase):
    def test_companion_packages_and_focused_references_exist(self) -> None:
        missing: list[str] = []
        for slug, contract in COMPANIONS.items():
            for relative in ("SKILL.md", contract["reference"]):
                if not (SKILLS / slug / relative).is_file():
                    missing.append(f"{slug}/{relative}")
        self.assertEqual([], missing)

    def test_companion_frontmatter_declares_parent_and_portable_metadata(self) -> None:
        for slug in COMPANIONS:
            with self.subTest(skill=slug):
                text = skill_text(slug)
                self.assertTrue(text.startswith("---\n"))
                frontmatter = text.split("---\n", 2)[1]
                self.assertRegex(frontmatter, rf"(?m)^name: {re.escape(slug)}$")
                self.assertRegex(frontmatter, r"(?m)^description: Use when .+")
                self.assertIn("license: MIT", frontmatter)
                self.assertIn(f'parent: "{PARENT}"', frontmatter)
                self.assertNotRegex(frontmatter, r"(?m)^(?:author|version|platforms):")

    def test_each_companion_documents_its_required_gotchas_and_sources(self) -> None:
        for slug, contract in COMPANIONS.items():
            with self.subTest(skill=slug):
                root = SKILLS / slug
                combined = skill_text(slug) + (root / contract["reference"]).read_text(
                    encoding="utf-8"
                )
                for term in contract["terms"]:
                    self.assertIn(term, combined)
                self.assertIn("## Sources", combined)
                self.assertRegex(combined, r"https://")
                self.assertIn(contract["reference"], skill_text(slug))

    def test_parent_routes_to_every_companion_without_embedding_absolute_paths(self) -> None:
        text = skill_text(PARENT)
        for slug in COMPANIONS:
            self.assertIn(slug, text)
        self.assertNotRegex(text, r"/home/[^\s]+/skills/")

    def test_relationship_metadata_has_no_dangling_skills(self) -> None:
        installed = {path.parent.name for path in SKILLS.glob("*/SKILL.md")}
        parent_frontmatter = skill_text(PARENT).split("---\n", 2)[1]
        children = re.search(r'(?m)^  children: "([^"]+)"$', parent_frontmatter)
        if children is None:
            self.fail("parent metadata is missing children")
        self.assertEqual(set(COMPANIONS), set(children.group(1).split(",")))

        for slug in COMPANIONS:
            with self.subTest(skill=slug):
                frontmatter = skill_text(slug).split("---\n", 2)[1]
                companions = re.search(r'(?m)^  companions: "([^"]+)"$', frontmatter)
                if companions is None:
                    self.fail(f"{slug} metadata is missing companions")
                related = set(companions.group(1).split(","))
                self.assertNotIn(slug, related)
                self.assertLessEqual(related, installed)

    def test_all_bash_snippets_avoid_redirection_shaped_placeholders(self) -> None:
        for path in SKILLS.glob("**/*.md"):
            text = path.read_text(encoding="utf-8")
            for block in re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL):
                self.assertNotRegex(
                    block,
                    r"<[A-Za-z][A-Za-z0-9_-]*>",
                    f"shell redirection-shaped placeholder in {path.relative_to(REPO)}",
                )

    def test_tunnel_to_caddy_uses_verified_https_and_rejects_redirects(self) -> None:
        reference = (
            SKILLS
            / "cloudflare-tunnels-and-caddy-dns"
            / "references"
            / "tunnels-and-dns-challenge.md"
        ).read_text(encoding="utf-8")
        self.assertIn("service: https://caddy:443", reference)
        self.assertIn("originServerName: app.dev.example.com", reference)
        self.assertIn("httpHostHeader: app.dev.example.com", reference)
        self.assertIn("caPool: /run/caddy-pki/root.crt", reference)
        self.assertIn("mount the internal root read-only", reference)
        self.assertIn("--location --max-redirs 0", reference)
        self.assertNotIn("service: http://caddy:80", reference)
        self.assertNotRegex(reference, r"(?m)^\s+noTLSVerify:")

    def test_debugging_guidance_is_secret_safe_and_ingress_isolated(self) -> None:
        compose_reference = (
            SKILLS
            / "compose-development-environments"
            / "references"
            / "merge-lifecycle-and-debugging.md"
        ).read_text(encoding="utf-8")
        tooling = skill_text("containerized-development-tooling")
        combined = compose_reference + tooling
        self.assertIn("docker inspect --format", combined)
        self.assertIn(".Config.Env", combined)
        self.assertIn("container loopback", tooling)
        self.assertIn("shared ingress network", tooling)
        self.assertIn("debug sidecar", tooling)
        self.assertIn("`0.0.0.0`", tooling)
        self.assertIn(
            "Do not attach that sidecar to the shared ingress network.",
            tooling,
        )
        self.assertIn(
            "no app-service debugger is bound to a wildcard address",
            tooling,
        )
        self.assertIn("must fail", tooling)

        for path in sorted(REPO.rglob("*.md")):
            lines = path.read_text(encoding="utf-8").splitlines()
            line_number = 0
            while line_number < len(lines):
                stripped = lines[line_number].strip()
                if not stripped.startswith("docker inspect"):
                    line_number += 1
                    continue

                command = stripped
                while command.rstrip().endswith("\\"):
                    line_number += 1
                    self.assertLess(
                        line_number,
                        len(lines),
                        f"unterminated docker inspect command in {path.relative_to(REPO)}",
                    )
                    command += " " + lines[line_number].strip()

                self.assertIn(
                    "--format",
                    command,
                    f"unbounded docker inspect in {path.relative_to(REPO)}",
                )
                self.assertNotIn(
                    ".Config.Env",
                    command,
                    f"environment dump in {path.relative_to(REPO)}",
                )
                line_number += 1

    def test_copyable_compose_examples_do_not_add_unapproved_latest_tags(self) -> None:
        # This organization-maintained ingress image is a deliberate policy exception.
        allowed = "ghcr.io/skb50bd/caddy:latest"
        offenders: list[str] = []
        image_line = re.compile(r"^\s*image:\s*[\"']?([^\s\"']+)", re.MULTILINE)
        for markdown in sorted(SKILLS.rglob("*.md")):
            for image in image_line.findall(markdown.read_text(encoding="utf-8")):
                if image.endswith(":latest") and image != allowed:
                    offenders.append(f"{markdown.relative_to(REPO)}: {image}")
        self.assertEqual([], offenders)

    def test_readme_documents_installable_hermes_identifier_and_caddy_exception(self) -> None:
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        expected = (
            'hermes skills install "https://raw.githubusercontent.com/'
            "Brotal-LLC/agent-skills/f086090c462324457086777c6501cab1781fda42/"
            'skills/collision-free-agentic-development/SKILL.md" --yes --force'
        )
        self.assertIn(expected, readme)
        self.assertRegex(
            readme,
            r"https://raw\.githubusercontent\.com/Brotal-LLC/agent-skills/"
            r"[0-9a-f]{40}/skills/collision-free-agentic-development/SKILL\.md",
        )
        self.assertIn("community-source CAUTION", readme)
        self.assertIn("inspect the immutable source", readme)
        self.assertNotIn(
            "hermes skills install "
            "Brotal-LLC/agent-skills/skills/collision-free-agentic-development",
            readme,
        )
        self.assertNotIn("hermes skills tap add Brotal-LLC/agent-skills", readme)
        self.assertIn("deliberate project-policy exception", readme)
        self.assertIn("ghcr.io/skb50bd/caddy:latest", readme)

    def test_parent_support_references_are_file_complete_for_hermes_bundles(self) -> None:
        package = SKILLS / PARENT
        skill = (package / "SKILL.md").read_text(encoding="utf-8")
        # Mirrors Hermes UrlSource/GitHubSource allowlisted local-reference extraction.
        reference_pattern = re.compile(
            r"(?:\]\(|`|(?:^|[\s\"\']))"
            r"((?:references|templates|scripts|assets|examples)/"
            r"[^\s)`\"'<>]+)",
            re.MULTILINE,
        )
        referenced = {
            match.group(1).rstrip(".,;:")
            for match in reference_pattern.finditer(skill.replace("\\", "/"))
        }
        for relative in referenced:
            self.assertTrue(
                (package / relative).is_file(),
                f"Hermes bundle reference is not a regular file: {relative}",
            )

        support_files = {
            path.relative_to(package).as_posix()
            for directory in ("references", "templates", "scripts", "assets", "examples")
            if (package / directory).exists()
            for path in (package / directory).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        }
        self.assertEqual(support_files, referenced)

    def test_readme_catalog_and_skills_sh_group_every_installable_skill(self) -> None:
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        expected = {PARENT, *COMPANIONS}
        for slug in expected:
            self.assertIn(f"skills/{slug}/", readme)

        catalog_path = REPO / "skills.sh.json"
        self.assertTrue(catalog_path.is_file())
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        grouped = {slug for grouping in catalog["groupings"] for slug in grouping.get("skills", [])}
        directories = {path.parent.name for path in SKILLS.glob("*/SKILL.md")}
        self.assertEqual(directories, grouped)
        self.assertEqual(expected, grouped)

    def test_ci_validates_the_entire_dynamic_catalog(self) -> None:
        workflow = (REPO / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
        validator = REPO / "scripts" / "validate_skills.py"
        self.assertTrue(validator.is_file())
        self.assertIn("python scripts/validate_skills.py", workflow)
        self.assertNotIn("agentskills validate skills/collision-free-agentic-development", workflow)

    def test_relative_markdown_links_resolve(self) -> None:
        broken: list[str] = []
        for markdown in REPO.rglob("*.md"):
            if ".git" in markdown.parts:
                continue
            text = markdown.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^]]*\]\(([^)]+)\)", text):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                path_part = target.split("#", 1)[0]
                if path_part and not (markdown.parent / path_part).exists():
                    broken.append(f"{markdown.relative_to(REPO)} -> {target}")
        self.assertEqual([], broken)


if __name__ == "__main__":
    unittest.main()
