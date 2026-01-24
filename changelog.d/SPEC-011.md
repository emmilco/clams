## SPEC-011: Strengthen Bug Investigation Protocol

### Summary
Enhanced bug investigation gate checks to require rigorous differential diagnosis with evidence-based hypothesis elimination.

### Changes
- Added `.claude/gates/check_bug_investigation.sh` gate script validating:
  - At least 3 hypotheses considered
  - Exactly 1 CONFIRMED hypothesis
  - Evidence documented for eliminated hypotheses
  - Evidentiary scaffold code present
  - Captured output from scaffold
  - Fix plan references in bug report
- Updated `.claude/templates/bug-report.md` with requirements callout, example differential diagnosis, and evidentiary scaffold examples
- Enhanced `.claude/roles/bug-investigator.md` with evidence thresholds, anti-patterns, and self-review checklist
- Added 13 test cases in `tests/gates/test_check_bug_investigation.py`
