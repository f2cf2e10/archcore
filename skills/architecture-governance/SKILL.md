---
name: architecture-governance
description: Interpret a project's ArchCore architecture contract, independently selected methodologies, and change policy before code edits.
---

# ArchCore architecture governance

1. Look for the repository-root `architecture.yaml`. Without it, do not assume an ArchCore architectural profile.
2. Read both the selected architecture `.yaml` rules and its companion `.md` explanation (including diagrams, when applicable) from the installed plugin’s `catalog/architectures/` and selected definitions in `catalog/methodologies/`, `catalog/principles/`, and `catalog/patterns/`. Never infer methodology from architecture.
3. Classify every proposed changed path, including new or removed paths, by the contract's layer mappings and unclassified fallback.
4. Respect protection floors and allowed dependency directions. An Architect's design and a Guardian's advisory clearance are not human authorization.
5. For code-changing requests, follow the Governed Implementation Workflow below by default; delegate to the three installed agents when supported. A review-only request must not edit files.
6. Resolve the installed plugin root from this skill location (`../../` from `skills/architecture-governance/`); run `python3 <plugin-root>/tools/archcore_contract.py validate architecture.yaml --catalog <plugin-root>/catalog` and optionally `python3 <plugin-root>/tools/archguard.py check --project . --catalog <plugin-root>/catalog`. Run the contract validator if available and distinguish its configuration validation from actual diff/dependency enforcement.
7. Do not edit protected paths or governance configuration under an unverified approval. Report blocked scope and missing trusted mechanisms clearly.

Methodologies, principles, and design patterns are guidance unless explicit mechanically checkable rules exist. Avoid unnecessary abstractions.

Selecting a pattern (including DTO) enables informed review, not mandatory implementation. Require a concrete reason for any extra representation, interface, or adapter.

## Deterministic scan before architectural review

When ArchGuard is installed and a participating project has `architecture.yaml`, run its read-only `scan` or `check` on the project and inspect the JSON graph when making dependency claims. Distinguish mechanically detected violations from issues requiring semantic review. Never claim complete dependency coverage: the current Python AST scanner does not resolve dynamic dependencies, external frameworks, or runtime dependency injection.

The three TOML files bundled under `agents/` are optional Codex custom agent definitions; installing the plugin does not itself register them. No project-local agent files are required.

## Deterministic Phase 4 review

Run `archguard scan --project . --format json` to build the project graph and `archguard check --project .` for dependency and framework rules. If reviewing modifications in a Git repository, run `archguard check --project . --changed` and optionally provide `--scope` for the intended paths. Treat dynamic imports and undecidable semantic quality as unresolved, not passes. Do not interpret `--scope` or an agent recommendation as trusted human approval. Protected paths remain blocked by ArchGuard pending external approval integration.


## Default Governed Implementation Workflow

When a participating project has `architecture.yaml` and the user requests implementation, **automatically** use the workflow below. The user should only have to say what to build; do not require a special invocation phrase. If native delegation is unavailable, execute the same stages sequentially and transparently; do not falsely claim independent review.

1. **Architect — plan (read-only):** inspect the requested behavior, project contract, knowledge catalog and existing architecture graph. Run the contract validator and baseline `archguard check`. Produce the minimal design, exact proposed paths, layer classifications, design rationale, expected tests, and any blocking baseline violations. Do not treat an existing unrelated violation as newly introduced.
2. **Guardian — preflight (read-only):** review the plan against actual architecture definitions, dependencies, selected methodologies/principles/patterns, requested scope and protection policy. Return `CLEAR`, `REVISE`, `BLOCKED`, or `UNKNOWN`, with concrete evidence. `CLEAR` means advisory scope clearance, never trusted approval. If `REVISE`, send findings to Architect, then recheck. If `BLOCKED`/`UNKNOWN` for required edits, stop and report. Do not edit governance configuration to bypass policy.
3. **Implementer — edit permitted files only:** follow the reviewed scope and project conventions. Add/update **pytest** tests for behavior where appropriate; avoid automatic DTOs, excess abstractions or patterns without justification. Never touch protected, forbidden or unclassified paths requiring authorization. Run targeted pytest and ArchGuard checks after implementation. Inspect the real Git diff including untracked files.
4. **Guardian — independent post-implementation review (read-only):** inspect actual changed files rather than trusting the Implementer report. Run available contract/ArchGuard checks and examine tests, architectural correctness, contract compliance, unnecessary complexity, and pattern misuse. Return `PASS`, `REWORK`, `BLOCKED`, or `UNKNOWN` with file-specific findings and evidence. Do not represent an AI review as trusted human approval.
5. **Correction loop:** on `REWORK`, hand the concrete issues to Implementer, run tests/checks again, and re-review. Allow at most **three correction attempts** to avoid an infinite loop. If the design itself is unsound, return it to Architect and repeat Guardian preflight. On unresolved violations, blocked paths, or inability to verify critical checks, stop and report; do not declare success.
6. **Completion:** report files changed, pytest results, ArchGuard outcomes, Guardian verdict, and open limitations. Only call the governed implementation compliant if Guardian reports PASS and applicable tests/checks passed, with no blocking violations. A pre-existing or unverifiable issue must be disclosed, not silently treated as a pass.

For trivial low-risk changes, a shorter sequential path is acceptable if it preserves preflight, scope enforcement, deterministic checks and final review. Independent Guardian review is preferred where available; do not infer that custom agent TOML presence proves the client actually delegated.

### Testing convention

Use `python3 -m pytest` for ArchCore and prefer project-native **pytest** tests for Python changes. If the target project does not have pytest available, report that limitation instead of claiming the tests passed. Tests cannot override protected-layer policies; stop and request trusted authorization if writing tests would violate the contract. Never change the contract to permit otherwise blocked tests.
