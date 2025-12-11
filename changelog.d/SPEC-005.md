## SPEC-005: Portable installation for CLAMS

### Summary
Add one-command installation scripts for setting up CLAMS with Qdrant vector database and Claude Code integration.

### Changes
- Added docker-compose.yml for Qdrant vector database service
- Added scripts/install.sh for automated setup (Docker, Python deps, Claude config)
- Added scripts/uninstall.sh for clean removal
- Added scripts/json_merge.py for safe JSON configuration merging
- Added scripts/verify_install.py for installation verification
- Updated README.md with installation instructions
- Updated GETTING_STARTED.md with configuration guide
- Added tests for json_merge.py
