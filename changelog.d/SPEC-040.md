## SPEC-040: Gate Type-Specific Routing

### Summary
Refactors gate checks to use a registry-based dispatcher that routes to type-specific check scripts based on project type detection.

### Changes
- Added `.claude/gates/registry.json` defining check script mappings for all categories and project types
- Added `.claude/bin/claws-gate-dispatch` routing script using jq for JSON parsing
- Created type-specific check scripts for Python, JavaScript, Rust, Go, and shell
- Simplified `claws-gate` to use the dispatcher instead of inline case statements
- Supports composite projects via `gate_config.composite_types` in project.json
- Provides graceful fallbacks with generic scripts for unknown project types
- Aggregates failures across all detected project types in composite projects

### References
- Unblocks: SPEC-041 (shell/hooks gate), SPEC-042 (frontend gate)
