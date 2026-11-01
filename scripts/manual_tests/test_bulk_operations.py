#!/usr/bin/env python3
"""
Test script for bulk evidence operations.
Tests the /api/evidence/bulk endpoint.
"""

import requests
import json

BASE_URL = "http://localhost:5001"
session = requests.Session()

def login():
    """Login with master password"""
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"master_password": "test123"}
    )
    if response.status_code == 200:
        print("✓ Logged in successfully")
        return True
    else:
        print(f"✗ Login failed: {response.text}")
        return False

def get_engagements():
    """Get list of engagements"""
    response = session.get(f"{BASE_URL}/api/engagements")
    if response.status_code == 200:
        engagements = response.json()
        print(f"✓ Found {len(engagements)} engagement(s)")
        return engagements
    else:
        print(f"✗ Failed to get engagements: {response.text}")
        return []

def set_active_engagement(engagement_id):
    """Set active engagement"""
    response = session.post(
        f"{BASE_URL}/api/engagements/active",
        json={"engagement_id": engagement_id}
    )
    if response.status_code == 200:
        print(f"✓ Set active engagement: {engagement_id}")
        return True
    else:
        print(f"✗ Failed to set active engagement: {response.text}")
        return False

def create_test_evidence():
    """Create some test evidence items"""
    evidence_ids = []

    for i in range(3):
        response = session.post(
            f"{BASE_URL}/api/evidence",
            json={
                "title": f"Test Evidence {i+1}",
                "evidence_type": "note",
                "content": f"This is test evidence item {i+1}",
                "tags": "test,bulk-test"
            }
        )
        if response.status_code == 201:
            evidence = response.json()
            evidence_ids.append(evidence['id'])
            print(f"✓ Created evidence {evidence['id']}: {evidence['title']}")
        else:
            print(f"✗ Failed to create evidence: {response.text}")

    return evidence_ids

def test_bulk_tag(evidence_ids):
    """Test bulk tag operation"""
    print("\n--- Testing Bulk Tag Operation ---")
    response = session.post(
        f"{BASE_URL}/api/evidence/bulk",
        json={
            "operation": "tag",
            "evidence_ids": evidence_ids,
            "params": {
                "tags": "bulk-tagged,reviewed"
            }
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✓ Bulk tag successful: {result['message']}")
        print(f"  Success: {result['success']}, Failed: {result['failed']}")
        return True
    else:
        print(f"✗ Bulk tag failed: {response.text}")
        return False

def test_bulk_export(evidence_ids):
    """Test bulk export operation"""
    print("\n--- Testing Bulk Export Operation ---")
    response = session.post(
        f"{BASE_URL}/api/evidence/bulk",
        json={
            "operation": "export",
            "evidence_ids": evidence_ids,
            "params": {}
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✓ Bulk export successful: {result['message']}")
        print(f"  Exported {len(result.get('data', []))} items")
        return True
    else:
        print(f"✗ Bulk export failed: {response.text}")
        return False

def test_bulk_delete(evidence_ids):
    """Test bulk delete operation"""
    print("\n--- Testing Bulk Delete Operation ---")
    response = session.post(
        f"{BASE_URL}/api/evidence/bulk",
        json={
            "operation": "delete",
            "evidence_ids": evidence_ids,
            "params": {}
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✓ Bulk delete successful: {result['message']}")
        print(f"  Success: {result['success']}, Failed: {result['failed']}")
        return True
    else:
        print(f"✗ Bulk delete failed: {response.text}")
        return False

def main():
    """Main test function"""
    print("=== PTVault Bulk Operations Test ===\n")

    # Login
    if not login():
        return

    # Get engagements
    engagements = get_engagements()
    if not engagements:
        print("\n✗ No engagements found. Please create an engagement first.")
        return

    # Set active engagement
    engagement_id = engagements[0]['id']
    if not set_active_engagement(engagement_id):
        return

    # Create test evidence
    print("\n--- Creating Test Evidence ---")
    evidence_ids = create_test_evidence()
    if not evidence_ids:
        print("\n✗ Failed to create test evidence")
        return

    # Test bulk operations
    test_bulk_tag(evidence_ids)
    test_bulk_export(evidence_ids)

    # Note: Commenting out delete test to preserve evidence
    # Uncomment to test delete functionality
    # test_bulk_delete(evidence_ids)

    print("\n=== All Tests Completed ===")
    print(f"\nNote: Created {len(evidence_ids)} test evidence items.")
    print("You can manually test the UI by selecting these items and using the bulk action toolbar.")

if __name__ == "__main__":
    main()
