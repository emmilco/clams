#!/usr/bin/env bash
# clams/hooks/validate_config.sh
# Validate hook configuration consistency
#
# Usage: ./validate_config.sh
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASS=true
CHECKS_RUN=0
CHECKS_FAILED=0

# Color output if terminal supports it
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' NC=''
fi

pass() { echo -e "${GREEN}PASS${NC}: $1"; ((CHECKS_RUN++)) || true; }
fail() { echo -e "${RED}FAIL${NC}: $1"; PASS=false; ((CHECKS_RUN++)) || true; ((CHECKS_FAILED++)) || true; }
warn() { echo -e "${YELLOW}WARN${NC}: $1"; }

echo "=== CLAMS Hook Configuration Validation ==="
echo

# 1. Check each registered hook exists and is executable
echo "--- Hook Script Checks ---"
HOOKS=(session_start.sh session_end.sh user_prompt_submit.sh ghap_checkin.sh outcome_capture.sh)

for hook in "${HOOKS[@]}"; do
    hook_path="$SCRIPT_DIR/$hook"
    if [[ ! -f "$hook_path" ]]; then
        fail "$hook not found"
        continue
    fi

    if [[ ! -x "$hook_path" ]]; then
        fail "$hook not executable (run: chmod +x $hook_path)"
        continue
    fi

    # Check bash syntax
    syntax_errors=$(bash -n "$hook_path" 2>&1)
    if [[ $? -ne 0 ]]; then
        fail "$hook has syntax errors: $syntax_errors"
        continue
    fi

    pass "$hook"
done
echo

# 2. Check dependencies
echo "--- Dependency Checks ---"
DEPS=(curl jq bash)
for dep in "${DEPS[@]}"; do
    if command -v "$dep" &>/dev/null; then
        version=$("$dep" --version 2>/dev/null | head -1 || echo "version unknown")
        pass "$dep available ($version)"
    else
        fail "$dep not found in PATH"
    fi
done
echo

# 3. Check config.yaml exists (optional - legacy)
echo "--- Configuration Checks ---"
if [[ -f "$SCRIPT_DIR/config.yaml" ]]; then
    pass "config.yaml present (legacy)"
    # Check config.yaml syntax if yq or python available
    if command -v python3 &>/dev/null; then
        yaml_check=$(python3 -c "
import yaml
import sys
try:
    with open('$SCRIPT_DIR/config.yaml') as f:
        yaml.safe_load(f)
    print('valid')
except Exception as e:
    print(f'invalid: {e}')
" 2>/dev/null)
        if [[ "$yaml_check" == "valid" ]]; then
            pass "config.yaml syntax valid"
        else
            fail "config.yaml syntax error: $yaml_check"
        fi
    fi
else
    warn "config.yaml not found (using defaults)"
fi
echo

# 4. Check documented env vars are used in scripts
echo "--- Environment Variable Documentation ---"
# These are the env vars documented in README.md
ENV_VARS=(CLAMS_HTTP_HOST CLAMS_HTTP_PORT CLAMS_PID_FILE CLAMS_STORAGE_PATH CLAMS_GHAP_CHECK_FREQUENCY)
for var in "${ENV_VARS[@]}"; do
    # Check if variable is referenced in any hook
    if grep -q "$var" "$SCRIPT_DIR"/*.sh 2>/dev/null; then
        pass "$var documented and used"
    else
        warn "$var documented but not found in hooks"
    fi
done
echo

# 5. Check README exists and documents all hooks
echo "--- Documentation Checks ---"
if [[ -f "$SCRIPT_DIR/README.md" ]]; then
    pass "README.md exists"
    # Check that README documents all hooks
    for hook in "${HOOKS[@]}"; do
        if grep -q "$hook" "$SCRIPT_DIR/README.md"; then
            pass "README documents $hook"
        else
            fail "README missing documentation for $hook"
        fi
    done

    # Check that README documents all env vars
    for var in "${ENV_VARS[@]}"; do
        if grep -q "$var" "$SCRIPT_DIR/README.md"; then
            pass "README documents $var"
        else
            fail "README missing documentation for $var"
        fi
    done
else
    fail "README.md not found"
fi
echo

# 6. Cross-reference: check that all .sh files in directory are documented
echo "--- Cross-Reference Checks ---"
for script in "$SCRIPT_DIR"/*.sh; do
    if [[ -f "$script" ]]; then
        script_name=$(basename "$script")
        # Skip this validation script itself
        if [[ "$script_name" == "validate_config.sh" ]]; then
            continue
        fi
        # Check if it's in our HOOKS array
        found=false
        for hook in "${HOOKS[@]}"; do
            if [[ "$hook" == "$script_name" ]]; then
                found=true
                break
            fi
        done
        if [[ "$found" == "true" ]]; then
            pass "$script_name is a known hook"
        else
            warn "$script_name is in hooks/ but not in validation list"
        fi
    fi
done
echo

# Summary
echo "=== Summary ==="
echo "Checks run: $CHECKS_RUN"
echo "Checks failed: $CHECKS_FAILED"

if $PASS; then
    echo -e "${GREEN}All checks passed${NC}"
    exit 0
else
    echo -e "${RED}Some checks failed${NC}"
    exit 1
fi
