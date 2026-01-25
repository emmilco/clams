## SPEC-042: Frontend Gate Check Script

### Summary
Adds a dedicated gate check script for frontend (clams-visualizer) changes that gracefully handles non-npm projects.

### Changes
- Added .claude/gates/check_frontend.sh for frontend validation
- Runs npm run lint and npm run typecheck if configured in package.json
- Handles missing npm gracefully (exit code 2)
- Handles non-npm frontend projects gracefully (skip with exit 0)
- Reads frontend_dirs from project.json for configurable paths
