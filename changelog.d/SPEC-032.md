## SPEC-032: Type-Safe Datetime and Numeric Handling

### Summary
Added type-safe utilities for datetime serialization and numeric validation with comprehensive error handling.

### Changes
- Extended `src/clams/utils/datetime.py` with:
  - `is_valid_datetime_format()` - validate ISO8601 format strings
  - `serialize_datetime_optional()` - safe optional datetime serialization
  - `deserialize_datetime_optional()` - safe optional datetime deserialization
- Added `src/clams/utils/numeric.py` with:
  - `safe_int()` - safe integer conversion with validation
  - `clamp()` - value clamping with bounds
  - `is_positive()` - positive number validation
- Added `src/clams/utils/validation.py` with:
  - `@validate_datetime_params()` - decorator for datetime parameter validation
  - `@validate_numeric_range()` - decorator for numeric range validation
- Added 139 new tests covering edge cases, error messages, and timezone handling
