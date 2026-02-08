"""Input validation test suite for MCP tools.

This package contains comprehensive tests for validating all MCP tool inputs.
It ensures consistent error handling and informative error messages across
all tools.

Test categories covered:
- Missing required fields
- Wrong type inputs
- Invalid enum values
- Out of range values
- String length limits
- Format validation
- Conditional requirements
- Empty/whitespace strings

References bugs:
- BUG-019: validate_value returns internal server error
- BUG-020: store_value returns internal server error
- BUG-024: Error message mismatch between stores
"""
