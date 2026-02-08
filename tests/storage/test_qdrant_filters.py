"""Tests for QdrantVectorStore filter operators."""

from qdrant_client.http import models as qmodels

from calm.storage.qdrant import QdrantVectorStore


class TestQdrantFilterBuilding:
    """Tests for _build_filter method with new operators."""

    def test_simple_equality_filter(self):
        """Test simple equality filter."""
        store = QdrantVectorStore()
        filters = {"category": "preference"}
        qdrant_filter = store._build_filter(filters)

        assert isinstance(qdrant_filter, qmodels.Filter)
        assert len(qdrant_filter.must) == 1
        condition = qdrant_filter.must[0]
        assert isinstance(condition, qmodels.FieldCondition)
        assert condition.key == "category"
        assert condition.match.value == "preference"

    def test_multiple_equality_filters(self):
        """Test multiple equality filters (AND logic)."""
        store = QdrantVectorStore()
        filters = {
            "project": "clams",
            "language": "python",
        }
        qdrant_filter = store._build_filter(filters)

        assert len(qdrant_filter.must) == 2
        conditions = qdrant_filter.must
        keys = [c.key for c in conditions]
        assert "project" in keys
        assert "language" in keys

    def test_in_operator_filter(self):
        """Test $in operator for multi-value match."""
        store = QdrantVectorStore()
        filters = {
            "language": {"$in": ["python", "typescript", "rust"]}
        }
        qdrant_filter = store._build_filter(filters)

        assert len(qdrant_filter.must) == 1
        condition = qdrant_filter.must[0]
        assert isinstance(condition, qmodels.FieldCondition)
        assert condition.key == "language"
        assert isinstance(condition.match, qmodels.MatchAny)
        assert condition.match.any == ["python", "typescript", "rust"]

    def test_gte_operator_filter(self):
        """Test $gte operator for range filter with numeric values."""
        store = QdrantVectorStore()
        filters = {
            "score": {"$gte": 0.5}
        }
        qdrant_filter = store._build_filter(filters)

        assert len(qdrant_filter.must) == 1
        condition = qdrant_filter.must[0]
        assert isinstance(condition, qmodels.FieldCondition)
        assert condition.key == "score"
        assert condition.range.gte == 0.5

    def test_lte_operator_filter(self):
        """Test $lte operator for range filter."""
        store = QdrantVectorStore()
        filters = {
            "importance": {"$lte": 0.5}
        }
        qdrant_filter = store._build_filter(filters)

        assert len(qdrant_filter.must) == 1
        condition = qdrant_filter.must[0]
        assert isinstance(condition, qmodels.FieldCondition)
        assert condition.key == "importance"
        assert condition.range.lte == 0.5

    def test_gte_and_lte_combined(self):
        """Test combined $gte and $lte for range filter."""
        store = QdrantVectorStore()
        filters = {
            "score": {"$gte": 0.3, "$lte": 0.7}
        }
        qdrant_filter = store._build_filter(filters)

        assert len(qdrant_filter.must) == 1
        condition = qdrant_filter.must[0]
        assert isinstance(condition, qmodels.FieldCondition)
        assert condition.key == "score"
        assert condition.range.gte == 0.3
        assert condition.range.lte == 0.7

    def test_mixed_operators_in_single_query(self):
        """Test multiple different operators in one filter."""
        store = QdrantVectorStore()
        filters = {
            "project": "clams",  # equality
            "language": {"$in": ["python", "rust"]},  # $in
            "importance": {"$gte": 0.3},  # $gte
        }
        qdrant_filter = store._build_filter(filters)

        assert len(qdrant_filter.must) == 3
        conditions = {c.key: c for c in qdrant_filter.must}

        # Check equality filter
        assert conditions["project"].match.value == "clams"

        # Check $in filter
        assert isinstance(conditions["language"].match, qmodels.MatchAny)
        assert conditions["language"].match.any == ["python", "rust"]

        # Check $gte filter
        assert conditions["importance"].range.gte == 0.3
