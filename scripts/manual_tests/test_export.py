#!/usr/bin/env python3
"""
Test script for PTVault export functionality
Tests JSON export, Markdown export, and template system
"""

import requests
import json
import sys

BASE_URL = "http://localhost:5000"

def test_setup():
    """Setup test data: master password, engagement, and evidence"""
    print("=" * 60)
    print("SETUP: Creating test data")
    print("=" * 60)

    # 1. Setup master password
    print("\n1. Setting up master password...")
    response = requests.post(f"{BASE_URL}/api/auth/setup", json={
        "master_password": "TestPassword123!"
    })

    if response.status_code in [200, 201]:
        print(f"   ✓ Master password set")
        token = response.cookies.get('auth_token')
        cookies = {'auth_token': token}
    else:
        print(f"   ✗ Setup failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return None

    # 2. Login
    print("\n2. Logging in...")
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "master_password": "TestPassword123!"
    })

    if response.status_code == 200:
        print(f"   ✓ Logged in")
        cookies = {'auth_token': response.cookies.get('auth_token')}
    else:
        print(f"   ✗ Login failed: {response.status_code}")
        return None

    # 3. Create engagement
    print("\n3. Creating test engagement...")
    response = requests.post(f"{BASE_URL}/api/engagements",
        cookies=cookies,
        json={
            "name": "ACME Corp Penetration Test",
            "client": "ACME Corporation",
            "start_date": "2025-12-01",
            "end_date": "2025-12-15",
            "status": "completed",
            "scope": "External network penetration test of 192.168.1.0/24",
            "contact_name": "John Smith",
            "contact_email": "john.smith@acme.com",
            "notes": "Comprehensive security assessment identified multiple critical vulnerabilities requiring immediate remediation."
        })

    if response.status_code == 201:
        engagement = response.json()
        engagement_id = engagement['id']
        print(f"   ✓ Engagement created (ID: {engagement_id})")
    else:
        print(f"   ✗ Engagement creation failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return None

    # 4. Set active engagement
    print(f"\n4. Setting active engagement to {engagement_id}...")
    response = requests.post(f"{BASE_URL}/api/engagements/active",
        cookies=cookies,
        json={"engagement_id": engagement_id})

    if response.status_code == 200:
        print(f"   ✓ Active engagement set")
    else:
        print(f"   ✗ Failed to set active engagement: {response.status_code}")
        return None

    # 5. Create evidence entries
    print("\n5. Creating evidence entries...")

    evidence_data = [
        {
            "type": "note",
            "title": "SQL Injection in Login Form",
            "content": "The login form at /admin/login is vulnerable to SQL injection. Using payload ' OR '1'='1 bypasses authentication.",
            "tags": "critical,sql-injection,authentication",
            "metadata": json.dumps({
                "severity_level": "critical",
                "cvss": 9.8,
                "cve": "N/A"
            })
        },
        {
            "type": "command_output",
            "title": "Open Ports Discovered",
            "content": "nmap scan results:\n22/tcp   open  ssh\n80/tcp   open  http\n443/tcp  open  https\n3306/tcp open  mysql",
            "tags": "high,reconnaissance,nmap",
            "metadata": json.dumps({
                "tool_name": "nmap",
                "severity_level": "high"
            })
        },
        {
            "type": "note",
            "title": "Weak Password Policy",
            "content": "Password policy allows simple passwords like 'password123'. No complexity requirements enforced.",
            "tags": "medium,password-policy",
            "metadata": json.dumps({
                "severity_level": "medium"
            })
        },
        {
            "type": "note",
            "title": "Missing Security Headers",
            "content": "Web application missing CSP, X-Frame-Options, and X-Content-Type-Options headers.",
            "tags": "low,headers,web",
            "metadata": json.dumps({
                "severity_level": "low"
            })
        },
        {
            "type": "tool_output",
            "title": "Nmap Full Scan Results",
            "content": "See attached XML file for complete scan results",
            "tags": "nmap,scan",
            "metadata": json.dumps({
                "tool_name": "nmap",
                "severity_level": "high",
                "summary": {
                    "hosts_up": 15,
                    "ports_found": 42
                }
            })
        }
    ]

    created_count = 0
    for evidence in evidence_data:
        response = requests.post(f"{BASE_URL}/api/evidence",
            cookies=cookies,
            json=evidence)

        if response.status_code == 201:
            created_count += 1
        else:
            print(f"   ✗ Failed to create evidence: {response.status_code}")

    print(f"   ✓ Created {created_count}/{len(evidence_data)} evidence entries")

    return {
        'cookies': cookies,
        'engagement_id': engagement_id
    }

def test_json_export(context):
    """Test JSON export endpoint"""
    print("\n" + "=" * 60)
    print("TEST 1: JSON Export")
    print("=" * 60)

    engagement_id = context['engagement_id']
    cookies = context['cookies']

    print(f"\nExporting engagement {engagement_id} to JSON...")
    response = requests.get(f"{BASE_URL}/api/engagements/{engagement_id}/export/json",
        cookies=cookies)

    if response.status_code == 200:
        print("✓ Export successful (HTTP 200)")

        # Parse JSON
        try:
            data = response.json()

            # Validate structure
            print("\nValidating JSON structure...")

            assert 'engagement' in data, "Missing 'engagement' key"
            assert 'evidence' in data, "Missing 'evidence' key"
            assert 'statistics' in data, "Missing 'statistics' key"
            assert 'export_metadata' in data, "Missing 'export_metadata' key"
            print("  ✓ Top-level structure valid")

            # Check engagement data
            eng = data['engagement']
            assert eng['name'] == "ACME Corp Penetration Test"
            assert eng['client'] == "ACME Corporation"
            print(f"  ✓ Engagement: {eng['name']}")

            # Check evidence
            evidence_list = data['evidence']
            print(f"  ✓ Evidence entries: {len(evidence_list)}")

            # Check tags are arrays
            for e in evidence_list:
                assert isinstance(e.get('tags', []), list), "Tags should be array"
            print(f"  ✓ Tags format: arrays")

            # Check statistics
            stats = data['statistics']
            print(f"  ✓ Total evidence: {stats['total_evidence']}")
            print(f"  ✓ By severity: Critical={stats['evidence_by_severity'].get('critical', 0)}, "
                  f"High={stats['evidence_by_severity'].get('high', 0)}, "
                  f"Medium={stats['evidence_by_severity'].get('medium', 0)}, "
                  f"Low={stats['evidence_by_severity'].get('low', 0)}")

            # Save to file
            with open('export_test.json', 'w') as f:
                json.dump(data, f, indent=2)
            print("\n  ✓ Saved to: export_test.json")

            print("\n✓ JSON EXPORT TEST PASSED")
            return True

        except Exception as e:
            print(f"\n✗ JSON validation failed: {e}")
            return False
    else:
        print(f"✗ Export failed: HTTP {response.status_code}")
        print(f"Response: {response.text}")
        return False

def test_markdown_export(context):
    """Test Markdown export endpoint"""
    print("\n" + "=" * 60)
    print("TEST 2: Markdown Export")
    print("=" * 60)

    engagement_id = context['engagement_id']
    cookies = context['cookies']

    print(f"\nExporting engagement {engagement_id} to Markdown...")
    response = requests.get(f"{BASE_URL}/api/engagements/{engagement_id}/export/markdown",
        cookies=cookies)

    if response.status_code == 200:
        print("✓ Export successful (HTTP 200)")

        markdown = response.text

        # Validate content
        print("\nValidating Markdown content...")

        assert "# Penetration Test Report:" in markdown, "Missing title"
        print("  ✓ Title present")

        assert "ACME Corporation" in markdown, "Missing client name"
        print("  ✓ Client name present")

        assert "## Findings Summary" in markdown or "## Executive Summary" in markdown, "Missing sections"
        print("  ✓ Section headers present")

        assert "Critical" in markdown or "critical" in markdown, "Missing severity levels"
        print("  ✓ Severity information present")

        # Check length
        lines = markdown.split('\n')
        print(f"  ✓ Total lines: {len(lines)}")

        # Save to file
        with open('export_test.md', 'w') as f:
            f.write(markdown)
        print("\n  ✓ Saved to: export_test.md")

        # Show preview
        print("\nMarkdown preview (first 20 lines):")
        print("-" * 60)
        for line in lines[:20]:
            print(line)
        print("-" * 60)

        print("\n✓ MARKDOWN EXPORT TEST PASSED")
        return True

    else:
        print(f"✗ Export failed: HTTP {response.status_code}")
        print(f"Response: {response.text}")
        return False

def test_template_system(context):
    """Test template system endpoints"""
    print("\n" + "=" * 60)
    print("TEST 3: Template System")
    print("=" * 60)

    engagement_id = context['engagement_id']
    cookies = context['cookies']

    # Test 1: List templates
    print("\n3a. Listing available templates...")
    response = requests.get(f"{BASE_URL}/api/templates", cookies=cookies)

    if response.status_code == 200:
        templates = response.json().get('templates', [])
        print(f"  ✓ Found {len(templates)} templates:")
        for t in templates:
            print(f"     - {t['name']}")
    else:
        print(f"  ✗ Failed to list templates: HTTP {response.status_code}")
        return False

    # Test 2: Get template content
    print("\n3b. Getting 'default' template content...")
    response = requests.get(f"{BASE_URL}/api/templates/default", cookies=cookies)

    if response.status_code == 200:
        template_content = response.text
        print(f"  ✓ Template loaded ({len(template_content)} bytes)")

        # Check for Jinja2 syntax
        if "{{" in template_content and "}}" in template_content:
            print("  ✓ Contains Jinja2 variables")
    else:
        print(f"  ✗ Failed to get template: HTTP {response.status_code}")
        return False

    # Test 3: Render template with engagement data
    for template_name in ['default', 'executive', 'findings']:
        print(f"\n3c. Rendering '{template_name}' template with engagement data...")
        response = requests.get(
            f"{BASE_URL}/api/engagements/{engagement_id}/export/template/{template_name}",
            cookies=cookies)

        if response.status_code == 200:
            rendered = response.text
            print(f"  ✓ Template rendered ({len(rendered)} bytes)")

            # Validate rendering (should NOT contain {{ }} anymore)
            if "{{" in rendered or "}}" in rendered:
                print("  ⚠ Warning: Unrendered variables found")
            else:
                print("  ✓ All variables rendered")

            # Check content
            if "ACME Corporation" in rendered:
                print("  ✓ Engagement data interpolated")

            # Save to file
            with open(f'export_test_{template_name}.md', 'w') as f:
                f.write(rendered)
            print(f"  ✓ Saved to: export_test_{template_name}.md")

        else:
            print(f"  ✗ Failed to render template: HTTP {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False

    print("\n✓ TEMPLATE SYSTEM TEST PASSED")
    return True

def test_security(context):
    """Test security: engagement isolation"""
    print("\n" + "=" * 60)
    print("TEST 4: Security - Engagement Isolation")
    print("=" * 60)

    cookies = context['cookies']

    # Try to export engagement ID that doesn't match active engagement
    print("\nAttempting to export engagement ID 999 (should fail)...")
    response = requests.get(f"{BASE_URL}/api/engagements/999/export/json",
        cookies=cookies)

    if response.status_code == 403 or response.status_code == 404:
        print(f"  ✓ Correctly rejected (HTTP {response.status_code})")
        print("\n✓ SECURITY TEST PASSED")
        return True
    else:
        print(f"  ✗ Security issue: got HTTP {response.status_code}, expected 403 or 404")
        return False

def main():
    print("\n" + "=" * 60)
    print("PTVault Export Functionality Test Suite")
    print("=" * 60)

    # Setup
    context = test_setup()
    if not context:
        print("\n✗ SETUP FAILED - Aborting tests")
        sys.exit(1)

    # Run tests
    results = []
    results.append(("JSON Export", test_json_export(context)))
    results.append(("Markdown Export", test_markdown_export(context)))
    results.append(("Template System", test_template_system(context)))
    results.append(("Security", test_security(context)))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nExported files created:")
        print("  - export_test.json")
        print("  - export_test.md")
        print("  - export_test_default.md")
        print("  - export_test_executive.md")
        print("  - export_test_findings.md")
        sys.exit(0)
    else:
        print("\n⚠ SOME TESTS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
