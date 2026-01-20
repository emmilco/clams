# SPEC-056: Hook Configuration Consolidation

## Problem Statement

Claude Code hooks are currently configured in multiple places:
- `.claude/settings.json` - defines hook scripts
- Individual hook scripts in `clams/hooks/` - contain logic
- Environment variables - configure behavior

This fragmentation makes it hard to:
1. Understand what hooks are active
2. Configure hook behavior consistently
3. Debug hook issues
4. Add new hooks following existing patterns

**Reference**: Unblocked by SPEC-029 (per spec cross-references)

## Proposed Solution

Consolidate hook configuration into a single, well-documented structure:
1. Central config file documenting all hooks
2. Consistent environment variable naming
3. Hook registry for programmatic access

## Acceptance Criteria

- [ ] Central hook documentation at `clams/hooks/README.md`
- [ ] Documentation includes:
  - Each hook's purpose and trigger event
  - Expected input (environment variables, stdin)
  - Expected output (JSON schema, exit codes)
  - Environment variables that control behavior
- [ ] Environment variables follow consistent naming: `CLAMS_HOOK_*`
- [ ] Hook enable/disable via `CLAMS_HOOK_<NAME>_ENABLED=0|1`
- [ ] Hook configuration validation script: `clams/hooks/validate_config.sh`
- [ ] Validation script checks:
  - All referenced scripts exist
  - Scripts are executable
  - Required environment variables are documented
- [ ] `.claude/settings.json` hook definitions match documentation

## Implementation Notes

Current hooks (from codebase):
- `session_start.sh` - SessionStart event
- `session_end.sh` - SessionEnd event
- `user_prompt_submit.sh` - UserPromptSubmit event
- `ghap_checkin.sh` - PreToolCall event (for GHAP reminders)
- `outcome_capture.sh` - PostToolCall event (for GHAP resolution capture)

Documentation structure for `clams/hooks/README.md`:
```markdown
# CLAMS Hooks

## Overview
Hooks integrate CLAMS with Claude Code's event system.

## Available Hooks

### session_start.sh
- **Event**: SessionStart
- **Purpose**: Initialize CLAMS session, check for orphaned GHAPs
- **Output**: JSON with `hookSpecificOutput.additionalContext`
- **Environment**:
  - `CLAMS_DIR`: Path to CLAMS installation
  - `CLAMS_HOOK_SESSION_START_ENABLED`: Set to 0 to disable

### session_end.sh
...
```

## Testing Requirements

- Validation script passes on current configuration
- Validation script fails when script is missing
- Validation script fails when script is not executable
- Documentation matches actual hook implementations
- Environment variable naming is consistent

## Out of Scope

- Hook behavior changes (this is configuration only)
- New hooks (create separate specs)
- Hook testing infrastructure (covered by SPEC-020)
