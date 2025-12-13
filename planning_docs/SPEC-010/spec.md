# SPEC-010: Move CLAMS files out of .claude directory

## Problem Statement

Currently, CLAMS installation files (hooks, config, MCP client) live in `./.claude/` alongside CLAWS orchestration files. This creates confusion because:

1. **Muddled concerns**: `.claude/` contains both:
   - CLAWS files (orchestration tools for this repo): `bin/`, `roles/`, `claws.db`
   - CLAMS files (learning system installation): `hooks/`, `hooks/config.yaml`, `hooks/mcp_client.py`

2. **Active vs installation**: When running Claude in this folder, `.claude/` becomes part of the working environment. CLAMS files are meant to be installation artifacts, not repo-specific tooling.

3. **Portability**: CLAMS is designed to be installed in any repo. Having its files in `.claude/` implies they're repo-specific.

## Proposed Solution

Move CLAMS files to a new top-level directory: `clams/` (or `installation/` or similar)

### Current Structure
```
.claude/
├── bin/                    # CLAWS (keep)
├── roles/                  # CLAWS (keep)
├── claws.db               # CLAWS (keep)
├── hooks/                  # CLAMS (move)
│   ├── config.yaml
│   ├── session_start.sh
│   ├── user_prompt_submit.sh
│   ├── ghap_checkin.sh
│   ├── outcome_capture.sh
│   ├── session_end.sh
│   └── mcp_client.py
└── settings.local.json    # CLAWS (keep)
```

### Proposed Structure
```
.claude/
├── bin/                    # CLAWS only
├── roles/                  # CLAWS only
├── claws.db               # CLAWS only
└── settings.local.json    # CLAWS only

clams/
├── hooks/                  # CLAMS hooks
│   ├── config.yaml
│   ├── session_start.sh
│   ├── user_prompt_submit.sh
│   ├── ghap_checkin.sh
│   ├── outcome_capture.sh
│   └── session_end.sh
└── mcp_client.py          # CLAMS MCP client
```

## Acceptance Criteria

1. [ ] CLAMS files moved to new `clams/` directory
2. [ ] All references updated:
   - [ ] `scripts/install.sh` - hook registration paths
   - [ ] `scripts/uninstall.sh` - hook removal paths
   - [ ] `~/.claude/settings.json` - hook command paths (via installer)
   - [ ] Hook scripts internal references (SCRIPT_DIR, REPO_ROOT calculations)
   - [ ] Any imports in `mcp_client.py`
3. [ ] Install script works correctly with new paths
4. [ ] Uninstall script works correctly with new paths
5. [ ] Hooks execute correctly from new location
6. [ ] MCP client works correctly from new location
7. [ ] CLAWS functionality unaffected (bin/, roles/, db all still work)
8. [ ] Triple-check audit: grep for any remaining `.claude/hooks` references

## Files to Move

| Current Path | New Path |
|-------------|----------|
| `.claude/hooks/config.yaml` | `clams/hooks/config.yaml` |
| `.claude/hooks/session_start.sh` | `clams/hooks/session_start.sh` |
| `.claude/hooks/user_prompt_submit.sh` | `clams/hooks/user_prompt_submit.sh` |
| `.claude/hooks/ghap_checkin.sh` | `clams/hooks/ghap_checkin.sh` |
| `.claude/hooks/outcome_capture.sh` | `clams/hooks/outcome_capture.sh` |
| `.claude/hooks/session_end.sh` | `clams/hooks/session_end.sh` |
| `.claude/hooks/mcp_client.py` | `clams/mcp_client.py` |

## Files to Update

| File | Changes Needed |
|------|---------------|
| `scripts/install.sh` | Update hook paths in registration |
| `scripts/uninstall.sh` | Update hook paths in removal |
| `clams/hooks/*.sh` | Update SCRIPT_DIR/REPO_ROOT if needed |
| `clams/mcp_client.py` | Verify no path assumptions |
| `tests/hooks/test_mcp_client.py` | Update import paths |

## Verification Steps

1. Run `./scripts/uninstall.sh --force` to clean existing installation
2. Run `./scripts/install.sh` with new paths
3. Verify `~/.claude/settings.json` has correct hook paths
4. Start new Claude session, verify hooks fire
5. Test MCP tools work
6. Run `grep -r ".claude/hooks" .` to find any missed references
7. Run full test suite

## Out of Scope

- Renaming the `clams` package in `src/` (already correct)
- Moving CLAWS files (they belong in `.claude/`)
- Changing the `~/.clams/` data directory (user data, separate concern)
