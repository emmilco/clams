## SPEC-004: Gate Pass Verification for Phase Transitions

### Summary
Implemented commit-anchored gate pass verification to ensure phase transitions cannot happen without proof that automated gate checks actually passed.

### Changes
- Added `gate_passes` table to track successful gate checks with commit SHAs
- Modified `clams-gate check` to record passes for test-requiring transitions
- Modified `clams-task transition` to verify gate passes before allowing transitions
- Covers transitions: IMPLEMENT-CODE_REVIEW, TEST-INTEGRATE, INVESTIGATED-FIXED, REVIEWED-TESTED

### Benefits
- Gate checks cannot be skipped
- Code cannot be modified after gate passes without re-running the gate
- Clear audit trail of what code state was tested
