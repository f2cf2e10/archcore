---
name: archcore-setup
description: Help install and verify ArchCore in Codex without copying files into every repository.
---

# ArchCore setup

1. Locate this installed plugin's root (the directory containing `plugin.json`, `catalog/`, and `tools/`).
2. For a project containing `architecture.yaml`, run `python3 <plugin-root>/tools/archcore_contract.py validate architecture.yaml --catalog <plugin-root>/catalog` to validate its contract.
3. For a deterministic Python project graph, run `python3 <plugin-root>/tools/archguard.py scan --project . --catalog <plugin-root>/catalog --format json`.
4. Install PyYAML into the Python environment executing these commands if it is missing. Do not install Python dependencies without permission.
5. Subagent definitions live under `agents/` but plugin installation alone does not register them globally. If the user explicitly requests registration, guide them through `python3 <plugin-root>/scripts/register_global.py` and ask them to review modifications before proceeding.
6. There is no automatic privileged approval mechanism. Protected paths require trusted human authorization outside the agents.
