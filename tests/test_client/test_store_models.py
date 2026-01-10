"""Unit tests for store models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from cl_client.store_models import (
    Entity,
    EntityListResponse,
    EntityPagination,
    EntityVersion,
    StoreConfig,
    StoreOperationResult,
)


class TestEntity:
    """Tests for Entity model."""

    def test_entity_creation(self):
        """Test creating an entity with all fields."""
        entity = Entity(
            id=1,
            label="Test Entity",
            description="Test description",
            is_collection=False,
            parent_id=None,
            added_date=1704067200000,  # 2024-01-01 00:00:00
            updated_date=1704153600000,  # 2024-01-02 00:00:00
            create_date=1704067200000,
            file_size=1024,
            height=800,
            width=600,
            mime_type="image/jpeg",
            md5="abc123",
        )

        assert entity.id == 1
        assert entity.label == "Test Entity"
        assert entity.description == "Test description"
        assert entity.is_collection is False
        assert entity.file_size == 1024

    def test_entity_datetime_conversion(self):
        """Test datetime conversion properties."""
        entity = Entity(
            id=1,
            added_date=1704067200000,  # 2024-01-01 00:00:00 UTC
            updated_date=1704153600000,  # 2024-01-02 00:00:00 UTC
            create_date=1704067200000,
        )

        # Check datetime conversions
        assert entity.added_date_datetime is not None
        assert isinstance(entity.added_date_datetime, datetime)
        assert entity.added_date_datetime.year == 2024
        assert entity.added_date_datetime.month == 1
        assert entity.added_date_datetime.day == 1

        assert entity.updated_date_datetime is not None
        assert entity.updated_date_datetime.year == 2024
        assert entity.updated_date_datetime.month == 1
        assert entity.updated_date_datetime.day == 2

    def test_entity_none_datetime(self):
        """Test datetime conversion with None values."""
        entity = Entity(
            id=1,
            added_date=None,
            updated_date=None,
            create_date=None,
        )

        assert entity.added_date_datetime is None
        assert entity.updated_date_datetime is None
        assert entity.create_date_datetime is None

    def test_entity_optional_fields(self):
        """Test entity with minimal fields."""
        entity = Entity(id=1)

        assert entity.id == 1
        assert entity.label is None
        assert entity.description is None
        assert entity.is_collection is None


class TestEntityPagination:
    """Tests for EntityPagination model."""

    def test_pagination_creation(self):
        """Test creating pagination info."""
        pagination = EntityPagination(
            page=1,
            page_size=20,
            total_items=100,
            total_pages=5,
            has_next=True,
            has_prev=False,
        )

        assert pagination.page == 1
        assert pagination.page_size == 20
        assert pagination.total_items == 100
        assert pagination.total_pages == 5
        assert pagination.has_next is True
        assert pagination.has_prev is False


class TestEntityListResponse:
    """Tests for EntityListResponse model."""

    def test_entity_list_response(self):
        """Test creating entity list response."""
        entities = [
            Entity(id=1, label="Entity 1"),
            Entity(id=2, label="Entity 2"),
        ]
        pagination = EntityPagination(
            page=1,
            page_size=20,
            total_items=2,
            total_pages=1,
            has_next=False,
            has_prev=False,
        )

        response = EntityListResponse(items=entities, pagination=pagination)

        assert len(response.items) == 2
        assert response.items[0].id == 1
        assert response.pagination.total_items == 2


class TestEntityVersion:
    """Tests for EntityVersion model."""

    def test_entity_version_creation(self):
        """Test creating entity version."""
        version = EntityVersion(
            version=1,
            transaction_id=100,
            end_transaction_id=200,
            operation_type="INSERT",
            label="Original Label",
            description="Original description",
        )

        assert version.version == 1
        assert version.transaction_id == 100
        assert version.end_transaction_id == 200
        assert version.operation_type == "INSERT"
        assert version.label == "Original Label"


class TestStoreConfig:
    """Tests for StoreConfig model."""

    def test_store_config_creation(self):
        """Test creating store config."""
        config = StoreConfig(
            guest_mode=False,
            updated_at=1704067200000,
            updated_by="admin",
        )

        assert config.guest_mode is False
        assert config.updated_at == 1704067200000
        assert config.updated_by == "admin"

    def test_store_config_datetime(self):
        """Test datetime conversion."""
        config = StoreConfig(
            guest_mode=True,
            updated_at=1704067200000,
        )

        assert config.updated_at_datetime is not None
        assert isinstance(config.updated_at_datetime, datetime)
        assert config.updated_at_datetime.year == 2024


class TestStoreOperationResult:
    """Tests for StoreOperationResult wrapper."""

    def test_success_result(self):
        """Test successful operation result."""
        entity = Entity(id=1, label="Test")
        result = StoreOperationResult[Entity](
            success="Entity created successfully",
            data=entity,
        )

        assert result.is_success is True
        assert result.is_error is False
        assert result.data is not None
        assert result.data.id == 1
        assert result.success == "Entity created successfully"
        assert result.error is None

    def test_error_result(self):
        """Test error operation result."""
        result = StoreOperationResult[Entity](
            error="Unauthorized: Invalid token",
        )

        assert result.is_success is False
        assert result.is_error is True
        assert result.data is None
        assert result.error == "Unauthorized: Invalid token"
        assert result.success is None

    def test_value_or_throw_success(self):
        """Test value_or_throw on success."""
        entity = Entity(id=1, label="Test")
        result = StoreOperationResult[Entity](
            success="Success",
            data=entity,
        )

        value = result.value_or_throw()
        assert value.id == 1
        assert value.label == "Test"

    def test_value_or_throw_error(self):
        """Test value_or_throw on error."""
        result = StoreOperationResult[Entity](
            error="Operation failed",
        )

        with pytest.raises(RuntimeError, match="Operation failed"):
            result.value_or_throw()

    def test_value_or_throw_no_data(self):
        """Test value_or_throw when success but no data."""
        result = StoreOperationResult[Entity](
            success="Success",
            data=None,
        )

        with pytest.raises(RuntimeError, match="succeeded but data is None"):
            result.value_or_throw()

    def test_result_with_list_type(self):
        """Test result wrapper with list type."""
        versions = [
            EntityVersion(version=1, transaction_id=100),
            EntityVersion(version=2, transaction_id=101),
        ]
        result = StoreOperationResult[list[EntityVersion]](
            success="Versions retrieved",
            data=versions,
        )

        assert result.is_success is True
        assert len(result.data) == 2
        assert result.data[0].version == 1

    def test_result_json_serialization(self):
        """Test JSON serialization."""
        entity = Entity(id=1, label="Test")
        result = StoreOperationResult[Entity](
            success="Success",
            data=entity,
        )

        # Should be able to convert to dict
        result_dict = result.model_dump()
        assert result_dict["success"] == "Success"
        assert result_dict["data"]["id"] == 1
        assert result_dict["error"] is None
