from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "collision-free-agentic-development"
SCRIPT = SKILL / "scripts" / "devstack.py"


def read(relative: str) -> str:
    return (SKILL / relative).read_text(encoding="utf-8")


def load_devstack():
    spec = importlib.util.spec_from_file_location("devstack", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SkillPackageContractTests(unittest.TestCase):
    def test_required_package_files_exist(self) -> None:
        required = {
            "SKILL.md",
            "references/architecture.md",
            "references/cross-platform.md",
            "references/data-isolation.md",
            "references/tls-and-dns.md",
            "references/troubleshooting.md",
            "scripts/devstack.py",
            "templates/app/.env.example",
            "templates/app/compose.yaml",
            "templates/app/compose.dev.yaml",
            "templates/app/compose.shared-data.yaml",
            "templates/app/compose.worktree-data.yaml",
            "templates/app/compose.tls-cloudflare.yaml",
            "templates/app/compose.tls-internal.yaml",
            "templates/app/Dockerfile.dotnet.dev",
            "templates/app/Dockerfile.node.dev",
            "templates/ingress/.env.example",
            "templates/ingress/compose.yaml",
        }
        missing = sorted(path for path in required if not (SKILL / path).is_file())
        self.assertEqual([], missing)

    def test_skill_frontmatter_is_open_standard_compatible(self) -> None:
        text = read("SKILL.md")
        self.assertTrue(text.startswith("---\n"))
        frontmatter = text.split("---\n", 2)[1]
        self.assertRegex(frontmatter, r"(?m)^name: collision-free-agentic-development$")
        self.assertRegex(frontmatter, r"(?m)^description: .+")
        self.assertIn("license: MIT", frontmatter)
        self.assertIn("compatibility:", frontmatter)
        self.assertIn('platforms: "linux,macos,windows"', frontmatter)
        for forbidden in ("\nversion:", "\nauthor:", "\nplatforms:"):
            self.assertNotIn(forbidden, frontmatter)

    def test_skill_covers_every_collision_domain(self) -> None:
        text = (
            read("SKILL.md")
            + read("references/architecture.md")
            + read("references/data-isolation.md")
        )
        for term in (
            "COMPOSE_PROJECT_NAME",
            "STACK_ID",
            "container_name",
            "published ports",
            "ingress network",
            "database",
            "Redis",
            "volume",
            "worktree",
        ):
            self.assertIn(term, text)

    def test_skill_documents_compose_file_separator_and_recreate_semantics(
        self,
    ) -> None:
        text = (
            read("SKILL.md")
            + read("references/cross-platform.md")
            + read("references/troubleshooting.md")
        )
        self.assertIn("COMPOSE_PATH_SEPARATOR", text)
        self.assertIn("Linux and macOS", text)
        self.assertIn("Windows", text)
        self.assertIn("docker compose up --detach --force-recreate", text)
        self.assertIn("docker compose restart", text)
        self.assertIn("docker compose config --quiet", text)

    def test_bash_snippets_are_copy_safe(self) -> None:
        for path in SKILL.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for block in re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL):
                self.assertNotRegex(
                    block,
                    r"<[A-Za-z][A-Za-z0-9_-]*>",
                    f"shell redirection-shaped placeholder in {path.relative_to(REPO)}",
                )

    def test_tls_reference_covers_all_requested_certificate_modes(self) -> None:
        text = read("references/tls-and-dns.md")
        for term in (
            "HTTP-01",
            "DNS-01",
            "Cloudflare",
            "internal CA",
            "tls internal",
            "CLOUDFLARE_API_TOKEN",
            "port 80",
            "port 443",
            "split-horizon",
        ):
            self.assertIn(term, text)
        self.assertIn("Zone:DNS:Edit", text)
        self.assertIn("Zone:Zone:Read", text)

    def test_public_files_contain_no_private_infrastructure_identifiers(self) -> None:
        forbidden = re.compile(
            r"(?:aamar\.cloud|shakib\.io|skb\.bd|10\.(?:\d{1,3}\.){2}\d{1,3}|discord\.com/channels)",
            re.IGNORECASE,
        )
        offenders: list[str] = []
        for path in REPO.rglob("*"):
            if not path.is_file() or ".git" in path.parts or path.suffix in {".pyc"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if forbidden.search(text):
                offenders.append(str(path.relative_to(REPO)))
        self.assertEqual([], offenders)


class ComposeTemplateContractTests(unittest.TestCase):
    def test_app_templates_avoid_global_docker_collisions(self) -> None:
        compose_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SKILL / "templates" / "app").glob("compose*.yaml")
        )
        self.assertNotIn("container_name:", compose_text)
        self.assertNotRegex(compose_text, r"(?m)^\s+ports:\s*$")
        self.assertNotRegex(compose_text, r"(?m)^\s+name:\s+(?!\$\{)")

    def test_dev_services_are_non_root_hot_reload_and_ingress_attached(self) -> None:
        text = read("templates/app/compose.dev.yaml")
        self.assertNotIn('user: "0', text)
        self.assertGreaterEqual(text.count("user:"), 2)
        self.assertRegex(text, r"(?m)^\s+- dotnet\s*$[\s\S]*?^\s+- watch\s*$")
        self.assertRegex(text, r"npm run (?:dev|start:dev)")
        self.assertGreaterEqual(text.count("ingress"), 3)
        self.assertIn("caddy.reverse_proxy", text)
        self.assertRegex(text, r"caddy:\s+\$\{[A-Z_]+_HOST:\?")

    def test_node_workspace_avoids_root_owned_nested_bind_mountpoints(self) -> None:
        text = read("templates/app/compose.dev.yaml")
        web = text.split("\n  web:\n", 1)[1]
        self.assertIn("./web:/source", web)
        self.assertIn("node_modules:/workspace/web/node_modules", web)
        self.assertIn("/workspace/web/.next", web)
        self.assertIn("ln -sfn", web)
        self.assertNotRegex(web, r"\bln -s (?!-)")
        self.assertNotIn("- .:/workspace", web)

    def test_dev_dependencies_and_build_outputs_do_not_pollute_host(self) -> None:
        text = read("templates/app/compose.dev.yaml") + read("templates/app/Dockerfile.dotnet.dev")
        self.assertIn("NUGET_PACKAGES", text)
        self.assertIn("CONTAINER_BUILD_ROOT", text)
        self.assertIn("node_modules", text)
        self.assertIn("tmpfs", text)
        self.assertIn("USER", text)

    def test_tls_overlays_do_not_embed_secrets(self) -> None:
        cloudflare = read("templates/app/compose.tls-cloudflare.yaml")
        internal = read("templates/app/compose.tls-internal.yaml")
        self.assertIn("{env.CLOUDFLARE_API_TOKEN}", cloudflare)
        self.assertNotRegex(cloudflare, r"CLOUDFLARE_API_TOKEN\s*[:=]\s*[A-Za-z0-9_-]{20,}")
        self.assertIn("caddy.tls: internal", internal)

    def test_data_templates_support_shared_and_per_worktree_state(self) -> None:
        shared = read("templates/app/compose.shared-data.yaml")
        isolated = read("templates/app/compose.worktree-data.yaml")
        self.assertIn("external: true", shared)
        self.assertIn("${POSTGRES_DB", shared + isolated)
        self.assertIn("${REDIS_PREFIX", shared + isolated)
        self.assertIn("profiles:", isolated)
        self.assertIn("/var/lib/postgresql", isolated)
        self.assertNotIn("/var/lib/postgresql/data", isolated)
        self.assertNotIn("external: true", isolated)

    def test_ingress_template_persists_certs_and_declares_ingress_network(self) -> None:
        text = read("templates/ingress/compose.yaml")
        self.assertIn("ghcr.io/skb50bd/caddy", text)
        self.assertIn("CADDY_INGRESS_NETWORKS", text)
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock:ro", text)
        self.assertIn("caddy_data:/data", text)
        self.assertIn("attachable: true", text)
        self.assertIn("${INGRESS_NETWORK:-agent-ingress}", text)


class DevstackHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.devstack = load_devstack()

    def test_identity_is_deterministic_valid_and_path_specific(self) -> None:
        first = self.devstack.derive_identity(Path("/tmp/acme/app-feature"), "app")
        again = self.devstack.derive_identity(Path("/tmp/acme/app-feature"), "app")
        second = self.devstack.derive_identity(Path("/tmp/acme/app-other"), "app")
        self.assertEqual(first, again)
        self.assertNotEqual(first.stack_id, second.stack_id)
        self.assertRegex(first.stack_id, r"^[a-z0-9][a-z0-9-]{0,62}$")
        self.assertRegex(first.postgres_db, r"^[a-z][a-z0-9_]{0,62}$")
        self.assertTrue(first.redis_prefix.endswith(":"))

    def test_root_host_uid_is_never_propagated_to_dev_containers(self) -> None:
        with (
            mock.patch.object(self.devstack.os, "getuid", return_value=0, create=True),
            mock.patch.object(self.devstack.os, "getgid", return_value=0, create=True),
        ):
            self.assertEqual((1000, 1000), self.devstack.default_uid_gid("linux"))

    def test_compose_file_separator_is_cross_platform(self) -> None:
        self.assertEqual(":", self.devstack.compose_separator("linux"))
        self.assertEqual(":", self.devstack.compose_separator("darwin"))
        self.assertEqual(";", self.devstack.compose_separator("windows"))

    def test_init_generates_mode_specific_collision_free_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "feature one"
            project.mkdir()
            output = project / ".env"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "init",
                    "--project-dir",
                    str(project),
                    "--domain",
                    "dev.example.com",
                    "--tls",
                    "internal",
                    "--data-mode",
                    "worktree",
                    "--platform",
                    "windows",
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            env = output.read_text(encoding="utf-8")
            self.assertIn(
                "COMPOSE_FILE=compose.yaml;compose.dev.yaml;compose.worktree-data.yaml;compose.tls-internal.yaml",
                env,
            )
            self.assertIn("COMPOSE_PROFILES=worktree-data", env)
            self.assertRegex(env, r"(?m)^COMPOSE_PROJECT_NAME=[a-z0-9-]+$")
            self.assertRegex(env, r"(?m)^WEB_HOST=[a-z0-9-]+\.dev\.example\.com$")
            self.assertNotIn("CLOUDFLARE_API_TOKEN=", env)

    def test_init_rejects_invalid_dns_network_and_multiline_env_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for domain in ("bad..example", "-bad.example", f"{'a' * 64}.example"):
                with self.subTest(domain=domain), self.assertRaises(ValueError):
                    self.devstack.build_env(
                        root,
                        project_name="app",
                        domain=domain,
                        tls_mode="internal",
                        data_mode="worktree",
                        platform_name="linux",
                    )
            with self.assertRaises(ValueError):
                self.devstack.build_env(
                    root,
                    project_name="app",
                    domain="localhost",
                    tls_mode="internal",
                    data_mode="worktree",
                    platform_name="linux",
                    ingress_network="ingress\nINJECTED=value",
                )
            with self.assertRaises(ValueError):
                self.devstack.render_env({"ONLY": "line1\nline2"})
            for tls_mode in ("http", "cloudflare"):
                with self.subTest(tls_mode=tls_mode), self.assertRaises(ValueError):
                    self.devstack.build_env(
                        root,
                        project_name="app",
                        domain="localhost",
                        tls_mode=tls_mode,
                        data_mode="worktree",
                        platform_name="linux",
                    )

    def test_scaffold_collision_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            marker = target / "compose.yaml"
            marker.write_text("existing\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.devstack.copy_templates(target)
            self.assertEqual(marker.read_text(encoding="utf-8"), "existing\n")
            self.assertEqual([marker], list(target.iterdir()))

    def test_init_refuses_to_overwrite_env_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / ".env"
            output.write_text("KEEP_ME=1\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "init", "--output", str(output)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("KEEP_ME=1\n", output.read_text(encoding="utf-8"))

    def test_doctor_infers_custom_ingress_name_from_rendered_compose(self) -> None:
        config = {
            "services": {
                "api": {
                    "user": "1000:1000",
                    "labels": {
                        "dev.agent-skills.hot-reload": "true",
                        "caddy": "api.example.test",
                        "caddy.reverse_proxy": "{{upstreams 8080}}",
                    },
                    "networks": {"ingress": None},
                }
            },
            "networks": {"ingress": {"external": True, "name": "team-proxy"}},
        }
        ingress = self.devstack.infer_ingress_network(config)
        self.assertEqual("team-proxy", ingress)
        self.assertEqual([], self.devstack.audit_compose_config(config, ingress))

    def test_compose_audit_rejects_root_fixed_names_ports_and_missing_ingress(
        self,
    ) -> None:
        config = {
            "services": {
                "api": {
                    "user": "0:0",
                    "container_name": "api",
                    "ports": [{"published": "8080", "target": 8080}],
                    "labels": {"dev.agent-skills.hot-reload": "true"},
                    "networks": {"default": None},
                }
            },
            "networks": {"default": {}},
        }
        issues = "\n".join(self.devstack.audit_compose_config(config, "agent-ingress"))
        self.assertIn("root", issues)
        self.assertIn("container_name", issues)
        self.assertIn("published port", issues)
        self.assertIn("ingress", issues)


class RepositoryQualityGateTests(unittest.TestCase):
    def test_repo_has_ci_precommit_and_catalog_readme(self) -> None:
        for relative in (
            ".gitattributes",
            ".github/workflows/ci.yaml",
            ".pre-commit-config.yaml",
            "README.md",
            "scripts/check_repo.py",
        ):
            self.assertTrue((REPO / relative).is_file(), relative)
        attributes = (REPO / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("* text=auto eol=lf", attributes)
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        self.assertIn("collision-free-agentic-development", readme)
        self.assertIn("Agent Skills", readme)
        self.assertIn("installation", readme.lower())


if __name__ == "__main__":
    unittest.main()
