"""Tests for schema generation utilities.

Tests that schema generators correctly extract enum values, generate valid
JSON Schema definitions, and validate schemas against Python Enum classes.
"""

from enum import Enum

import pytest

from clams.utils.schema import (
    enum_schema,
    enum_schema_from_list,
    get_enum_diff,
    get_enum_values,
    validate_enum_schema,
)


class Status(Enum):
    """Test enum for status values."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


class Priority(Enum):
    """Test enum for priority values."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IntEnum(Enum):
    """Test enum with non-string values (invalid for schemas)."""

    ONE = 1
    TWO = 2


class TestGetEnumValues:
    """Tests for get_enum_values function."""

    def test_extracts_values_from_enum(self) -> None:
        """Correctly extracts string values from Enum class."""
        values = get_enum_values(Status)
        assert values == ["pending", "active", "completed"]

    def test_extracts_single_value_enum(self) -> None:
        """Works with single-value enums."""

        class SingleValue(Enum):
            ONLY = "only"

        values = get_enum_values(SingleValue)
        assert values == ["only"]

    def test_raises_on_non_enum_class(self) -> None:
        """Raises TypeError for non-Enum types."""
        with pytest.raises(TypeError, match="Expected Enum class"):
            get_enum_values(str)  # type: ignore[arg-type]

    def test_raises_on_instance(self) -> None:
        """Raises TypeError for Enum instances (not classes)."""
        with pytest.raises(TypeError, match="Expected Enum class"):
            get_enum_values(Status.PENDING)  # type: ignore[arg-type]

    def test_raises_on_non_string_values(self) -> None:
        """Raises ValueError for enums with non-string values."""
        with pytest.raises(ValueError, match="non-string value"):
            get_enum_values(IntEnum)

    def test_preserves_order(self) -> None:
        """Values are returned in definition order."""

        class Ordered(Enum):
            FIRST = "first"
            SECOND = "second"
            THIRD = "third"

        values = get_enum_values(Ordered)
        assert values == ["first", "second", "third"]


class TestEnumSchema:
    """Tests for enum_schema function."""

    def test_generates_basic_schema(self) -> None:
        """Generates schema with type and enum."""
        schema = enum_schema(Status)
        assert schema["type"] == "string"
        assert schema["enum"] == ["pending", "active", "completed"]
        assert "description" not in schema
        assert "default" not in schema

    def test_includes_description(self) -> None:
        """Includes description when provided."""
        schema = enum_schema(Status, description="Task status")
        assert schema["description"] == "Task status"

    def test_includes_default(self) -> None:
        """Includes default when provided."""
        schema = enum_schema(Status, default="pending")
        assert schema["default"] == "pending"

    def test_includes_all_options(self) -> None:
        """Can include both description and default."""
        schema = enum_schema(
            Priority,
            description="Task priority level",
            default="medium",
        )
        assert schema == {
            "type": "string",
            "description": "Task priority level",
            "enum": ["low", "medium", "high"],
            "default": "medium",
        }

    def test_raises_on_invalid_default(self) -> None:
        """Raises ValueError if default is not a valid enum value."""
        with pytest.raises(ValueError, match="not a valid value"):
            enum_schema(Status, default="invalid")

    def test_raises_on_non_enum_class(self) -> None:
        """Raises TypeError for non-Enum types."""
        with pytest.raises(TypeError, match="Expected Enum class"):
            enum_schema(dict)  # type: ignore[arg-type]


class TestValidateEnumSchema:
    """Tests for validate_enum_schema function."""

    def test_valid_schema_matches(self) -> None:
        """Returns True when schema values match enum."""
        schema = {"type": "string", "enum": ["pending", "active", "completed"]}
        assert validate_enum_schema(Status, schema) is True

    def test_valid_schema_different_order(self) -> None:
        """Returns True even if order is different."""
        schema = {"type": "string", "enum": ["completed", "pending", "active"]}
        assert validate_enum_schema(Status, schema) is True

    def test_missing_value_fails(self) -> None:
        """Returns False if schema is missing an enum value."""
        schema = {"type": "string", "enum": ["pending", "active"]}
        assert validate_enum_schema(Status, schema) is False

    def test_extra_value_fails(self) -> None:
        """Returns False if schema has extra enum value."""
        schema = {"type": "string", "enum": ["pending", "active", "completed", "extra"]}
        assert validate_enum_schema(Status, schema) is False

    def test_no_enum_key_fails(self) -> None:
        """Returns False if schema lacks enum key."""
        schema = {"type": "string"}
        assert validate_enum_schema(Status, schema) is False

    def test_empty_enum_fails(self) -> None:
        """Returns False if schema has empty enum."""
        schema = {"type": "string", "enum": []}
        assert validate_enum_schema(Status, schema) is False


class TestGetEnumDiff:
    """Tests for get_enum_diff function."""

    def test_no_diff_when_matching(self) -> None:
        """Returns empty lists when schema matches enum."""
        schema = {"type": "string", "enum": ["pending", "active", "completed"]}
        diff = get_enum_diff(Status, schema)
        assert diff["missing_in_schema"] == []
        assert diff["extra_in_schema"] == []

    def test_missing_values_detected(self) -> None:
        """Detects values in enum but not in schema."""
        schema = {"type": "string", "enum": ["pending"]}
        diff = get_enum_diff(Status, schema)
        assert diff["missing_in_schema"] == ["active", "completed"]
        assert diff["extra_in_schema"] == []

    def test_extra_values_detected(self) -> None:
        """Detects values in schema but not in enum."""
        schema = {
            "type": "string",
            "enum": ["pending", "active", "completed", "archived", "deleted"],
        }
        diff = get_enum_diff(Status, schema)
        assert diff["missing_in_schema"] == []
        assert diff["extra_in_schema"] == ["archived", "deleted"]

    def test_both_differences_detected(self) -> None:
        """Detects both missing and extra values."""
        schema = {"type": "string", "enum": ["pending", "unknown"]}
        diff = get_enum_diff(Status, schema)
        assert diff["missing_in_schema"] == ["active", "completed"]
        assert diff["extra_in_schema"] == ["unknown"]

    def test_raises_on_missing_enum_key(self) -> None:
        """Raises KeyError if schema lacks enum key."""
        schema = {"type": "string"}
        with pytest.raises(KeyError, match="enum"):
            get_enum_diff(Status, schema)

    def test_results_are_sorted(self) -> None:
        """Diff results are sorted alphabetically."""

        class Letters(Enum):
            C = "c"
            A = "a"
            B = "b"

        schema = {"type": "string", "enum": ["z", "x", "y"]}
        diff = get_enum_diff(Letters, schema)
        assert diff["missing_in_schema"] == ["a", "b", "c"]
        assert diff["extra_in_schema"] == ["x", "y", "z"]


class TestEnumSchemaFromList:
    """Tests for enum_schema_from_list function."""

    def test_generates_schema_from_list(self) -> None:
        """Generates schema from list of values."""
        values = ["one", "two", "three"]
        schema = enum_schema_from_list(values)
        assert schema == {"type": "string", "enum": ["one", "two", "three"]}

    def test_includes_description(self) -> None:
        """Includes description when provided."""
        schema = enum_schema_from_list(["a", "b"], description="Letter choice")
        assert schema["description"] == "Letter choice"

    def test_includes_default(self) -> None:
        """Includes default when provided."""
        schema = enum_schema_from_list(["a", "b"], default="a")
        assert schema["default"] == "a"

    def test_raises_on_empty_list(self) -> None:
        """Raises ValueError for empty list."""
        with pytest.raises(ValueError, match="cannot be empty"):
            enum_schema_from_list([])

    def test_raises_on_invalid_default(self) -> None:
        """Raises ValueError if default not in list."""
        with pytest.raises(ValueError, match="not in values list"):
            enum_schema_from_list(["a", "b"], default="c")

    def test_raises_on_non_string_values(self) -> None:
        """Raises TypeError for non-string values."""
        with pytest.raises(TypeError, match="must be strings"):
            enum_schema_from_list([1, 2, 3])  # type: ignore[list-item]

    def test_does_not_mutate_input(self) -> None:
        """Does not mutate the input list."""
        values = ["a", "b"]
        schema = enum_schema_from_list(values)
        schema["enum"].append("c")
        assert values == ["a", "b"]


class TestIntegrationWithRealEnums:
    """Integration tests using real enums from the codebase."""

    def test_domain_enum(self) -> None:
        """Works with Domain enum from observation models."""
        from clams.observation.models import Domain

        schema = enum_schema(Domain, description="Task domain")
        assert schema["type"] == "string"
        assert "debugging" in schema["enum"]
        assert "refactoring" in schema["enum"]
        assert schema["description"] == "Task domain"

    def test_strategy_enum(self) -> None:
        """Works with Strategy enum from observation models."""
        from clams.observation.models import Strategy

        schema = enum_schema(Strategy, description="Problem-solving strategy")
        assert schema["type"] == "string"
        assert "systematic-elimination" in schema["enum"]
        assert "trial-and-error" in schema["enum"]
        assert len(schema["enum"]) == 9

    def test_outcome_status_enum(self) -> None:
        """Works with OutcomeStatus enum from observation models."""
        from clams.observation.models import OutcomeStatus

        schema = enum_schema(OutcomeStatus, description="Resolution status")
        assert schema["enum"] == ["confirmed", "falsified", "abandoned"]

    def test_unit_type_enum(self) -> None:
        """Works with UnitType enum from indexers."""
        from clams.indexers.base import UnitType

        schema = enum_schema(UnitType, description="Type of code unit")
        assert schema["type"] == "string"
        assert "function" in schema["enum"]
        assert "class" in schema["enum"]
        assert "method" in schema["enum"]

    def test_validate_domain_enum_against_enums_py(self) -> None:
        """Domain Enum values match list-based DOMAINS in enums.py."""
        from clams.observation.models import Domain
        from clams.server.tools.enums import DOMAINS

        enum_values = set(get_enum_values(Domain))
        list_values = set(DOMAINS)
        assert enum_values == list_values, f"Diff: {enum_values ^ list_values}"

    def test_validate_strategy_enum_against_enums_py(self) -> None:
        """Strategy Enum values match list-based STRATEGIES in enums.py."""
        from clams.observation.models import Strategy
        from clams.server.tools.enums import STRATEGIES

        enum_values = set(get_enum_values(Strategy))
        list_values = set(STRATEGIES)
        assert enum_values == list_values, f"Diff: {enum_values ^ list_values}"

    def test_validate_outcome_status_enum_against_enums_py(self) -> None:
        """OutcomeStatus Enum values match list-based values in enums.py."""
        from clams.observation.models import OutcomeStatus
        from clams.server.tools.enums import OUTCOME_STATUS_VALUES

        enum_values = set(get_enum_values(OutcomeStatus))
        list_values = set(OUTCOME_STATUS_VALUES)
        assert enum_values == list_values, f"Diff: {enum_values ^ list_values}"
