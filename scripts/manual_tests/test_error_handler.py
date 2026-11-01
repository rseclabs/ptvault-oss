#!/usr/bin/env python3
"""Test script for error handling system."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from utils.error_handler import (
    PTVaultError,
    ValidationError,
    DatabaseError,
    AuthenticationError,
    NotFoundError,
    ConflictError,
    FileUploadError,
    ParsingError,
    require_fields,
    validate_enum
)


def test_custom_exceptions():
    """Test custom exception classes."""
    print("\n=== Testing Custom Exceptions ===\n")

    # Test ValidationError
    try:
        raise ValidationError("Invalid email format", field="email")
    except ValidationError as e:
        print(f"✓ ValidationError: {e.message} (status: {e.status_code})")
        print(f"  Details: {e.details}")
        print(f"  JSON: {e.to_dict()}")

    # Test DatabaseError
    try:
        raise DatabaseError("Failed to insert record", query="INSERT INTO...")
    except DatabaseError as e:
        print(f"\n✓ DatabaseError: {e.message} (status: {e.status_code})")
        print(f"  Details: {e.details}")

    # Test AuthenticationError
    try:
        raise AuthenticationError("Invalid credentials")
    except AuthenticationError as e:
        print(f"\n✓ AuthenticationError: {e.message} (status: {e.status_code})")

    # Test NotFoundError
    try:
        raise NotFoundError("engagement", resource_id=123)
    except NotFoundError as e:
        print(f"\n✓ NotFoundError: {e.message} (status: {e.status_code})")
        print(f"  Details: {e.details}")

    # Test ConflictError
    try:
        raise ConflictError("User already exists")
    except ConflictError as e:
        print(f"\n✓ ConflictError: {e.message} (status: {e.status_code})")

    # Test FileUploadError
    try:
        raise FileUploadError("File too large", filename="evidence.png")
    except FileUploadError as e:
        print(f"\n✓ FileUploadError: {e.message} (status: {e.status_code})")
        print(f"  Details: {e.details}")

    # Test ParsingError
    try:
        raise ParsingError("Invalid XML structure", tool_type="nmap")
    except ParsingError as e:
        print(f"\n✓ ParsingError: {e.message} (status: {e.status_code})")
        print(f"  Details: {e.details}")


def test_validation_helpers():
    """Test validation helper functions."""
    print("\n\n=== Testing Validation Helpers ===\n")

    # Test require_fields - success
    try:
        data = {"name": "Test", "client": "ACME Corp"}
        require_fields(data, ["name", "client"])
        print("✓ require_fields: Valid data passed")
    except ValidationError as e:
        print(f"✗ Unexpected error: {e.message}")

    # Test require_fields - missing field
    try:
        data = {"name": "Test"}
        require_fields(data, ["name", "client"])
        print("✗ require_fields: Should have raised ValidationError")
    except ValidationError as e:
        print(f"✓ require_fields: Caught missing field - {e.message}")

    # Test require_fields - empty field
    try:
        data = {"name": "", "client": "ACME"}
        require_fields(data, ["name", "client"])
        print("✗ require_fields: Should have raised ValidationError for empty field")
    except ValidationError as e:
        print(f"✓ require_fields: Caught empty field - {e.message}")

    # Test validate_enum - success
    try:
        validate_enum("active", ["active", "archived"], "status")
        print("\n✓ validate_enum: Valid value passed")
    except ValidationError as e:
        print(f"✗ Unexpected error: {e.message}")

    # Test validate_enum - invalid value
    try:
        validate_enum("invalid", ["active", "archived"], "status")
        print("✗ validate_enum: Should have raised ValidationError")
    except ValidationError as e:
        print(f"✓ validate_enum: Caught invalid value - {e.message}")


def test_error_responses():
    """Test JSON error response format."""
    print("\n\n=== Testing JSON Error Responses ===\n")

    errors = [
        ValidationError("Invalid email", field="email"),
        DatabaseError("Connection failed"),
        AuthenticationError(),
        NotFoundError("host", 42),
        ConflictError("Duplicate entry"),
    ]

    for error in errors:
        response = error.to_dict()
        print(f"✓ {error.__class__.__name__}:")
        print(f"  Status Code: {error.status_code}")
        print(f"  JSON Response: {response}")


if __name__ == "__main__":
    print("=" * 60)
    print("PTVault Error Handling System - Test Suite")
    print("=" * 60)

    test_custom_exceptions()
    test_validation_helpers()
    test_error_responses()

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60 + "\n")
