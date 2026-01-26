## SPEC-043: Update Valid Implementation Directories

### Summary
Improves error messages in claws-gate when the "Implementation code exists" check fails, making it clearer what directories are valid and where the configuration comes from.

### Changes
- Updated error messages in claws-gate to list valid implementation directories from project.json
- Added reference to .claude/project.json configuration file in error output
- Provides helpful guidance for common scenarios (docs-only vs code changes)
- Updated both feature (IMPLEMENT-CODE_REVIEW) and bug (INVESTIGATED-FIXED) transitions
