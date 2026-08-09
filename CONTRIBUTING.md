# Contributing

Thank you for improving Brotal Agent Skills.

## Development workflow

1. Branch from `main`.
2. Add a failing unit, contract, or regression test for the behavior.
3. Implement the smallest coherent change.
4. Run `python scripts/check_repo.py`.
5. Exercise any Docker/Caddy path the change affects; mocked prose is not runtime evidence.
6. Review the complete diff for secrets and private infrastructure identifiers.
7. Open a pull request; never push directly to `main` without repository-owner approval.

## Skill rules

- Follow the current specification at <https://agentskills.io/>.
- Keep the skill directory name identical to frontmatter `name`.
- Use only portable top-level frontmatter fields. Put author/version/client hints in string-valued `metadata`.
- Keep the main body below 500 lines and use focused `references/` files.
- Prefer standard-library, cross-platform scripts. State any dependency in `compatibility` and setup instructions.
- Scripts must refuse destructive overwrites/deletes by default and return non-zero on validation failure.
- Examples use reserved domains such as `example.com`, no live internal endpoints.
- Templates must contain placeholders, not credentials.

## Commit messages

Use `type(scope): summary`, for example:

```text
feat(collision-free-dev): add Kubernetes ingress alternative
fix(devstack): preserve existing env without force
```
