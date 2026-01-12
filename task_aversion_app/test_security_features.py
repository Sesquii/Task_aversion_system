#!/usr/bin/env python3
"""
Security Features Test Script
Tests HTML escaping, input validation, and error handling for Phase 2B security features.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.security_utils import (
    sanitize_html, sanitize_for_storage,
    validate_task_name, validate_description, validate_note,
    validate_survey_response, validate_comment, validate_blocker,
    ValidationError, escape_for_display,
    handle_error, record_error_report
)


def test_html_escaping():
    """Test HTML escaping to prevent XSS attacks."""
    print("\n" + "="*60)
    print("TEST 1: HTML Escaping (XSS Prevention)")
    print("="*60)
    
    test_cases = [
        # (input, expected_output, description)
        ("<script>alert('XSS')</script>", "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;", "Script tag"),
        ("<img src=x onerror=alert('XSS')>", "&lt;img src=x onerror=alert(&#x27;XSS&#x27;)&gt;", "Image with onerror"),
        ("javascript:alert('XSS')", "javascript:alert(&#x27;XSS&#x27;)", "JavaScript protocol"),
        ("<div onclick='alert(1)'>Click</div>", "&lt;div onclick=&#x27;alert(1)&#x27;&gt;Click&lt;/div&gt;", "Div with onclick"),
        ("<svg><script>alert('XSS')</script></svg>", "&lt;svg&gt;&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;&lt;/svg&gt;", "SVG with script"),
        ("'quotes' and \"double quotes\"", "&#x27;quotes&#x27; and &quot;double quotes&quot;", "Quotes escaping"),
        ("Normal text", "Normal text", "Normal text (no escaping needed)"),
        ("", "", "Empty string"),
        (None, "", "None value"),
    ]
    
    passed = 0
    failed = 0
    
    for input_text, expected, description in test_cases:
        result = sanitize_html(input_text)
        if result == expected:
            input_display = str(input_text)[:50] if input_text is not None else 'None'
            result_display = result[:50] if result else ''
            print(f"[PASS] {description}: '{input_display}' -> '{result_display}'")
            passed += 1
        else:
            print(f"[FAIL] {description}")
            print(f"  Input:    '{input_text}'")
            print(f"  Expected: '{expected}'")
            print(f"  Got:      '{result}'")
            failed += 1
    
    print(f"\nResult: {passed} passed, {failed} failed")
    return failed == 0


def test_input_validation():
    """Test input validation with length limits."""
    print("\n" + "="*60)
    print("TEST 2: Input Validation (Length Limits)")
    print("="*60)
    
    test_cases = [
        # (function, input, should_pass, description)
        (validate_task_name, "Valid Task Name", True, "Valid task name"),
        (validate_task_name, "", False, "Empty task name"),
        (validate_task_name, None, False, "None task name"),
        (validate_task_name, "a" * 200, True, "Task name at max length (200)"),
        (validate_task_name, "a" * 201, False, "Task name over max length (201)"),
        (validate_description, "Valid description", True, "Valid description"),
        (validate_description, "a" * 5000, True, "Description at max length (5000)"),
        (validate_description, "a" * 5001, False, "Description over max length (5001)"),
        (validate_note, "Valid note", True, "Valid note"),
        (validate_note, "a" * 10000, True, "Note at max length (10000)"),
        (validate_note, "a" * 10001, False, "Note over max length (10001)"),
        (validate_survey_response, "Valid response", True, "Valid survey response"),
        (validate_survey_response, "a" * 2000, True, "Survey response at max length (2000)"),
        (validate_survey_response, "a" * 2001, False, "Survey response over max length (2001)"),
    ]
    
    passed = 0
    failed = 0
    
    for func, input_text, should_pass, description in test_cases:
        try:
            result = func(input_text)
            if should_pass:
                print(f"[PASS] {description}: Validation passed")
                passed += 1
            else:
                print(f"[FAIL] {description}: Should have failed but passed")
                failed += 1
        except ValidationError as e:
            if not should_pass:
                print(f"[PASS] {description}: Validation correctly failed - {str(e)[:50]}")
                passed += 1
            else:
                print(f"[FAIL] {description}: Should have passed but failed - {str(e)}")
                failed += 1
        except Exception as e:
            print(f"[FAIL] {description}: Unexpected error - {type(e).__name__}: {e}")
            failed += 1
    
    print(f"\nResult: {passed} passed, {failed} failed")
    return failed == 0


def test_xss_in_validation():
    """Test that XSS attempts are sanitized during validation."""
    print("\n" + "="*60)
    print("TEST 3: XSS Sanitization in Validation")
    print("="*60)
    
    xss_payloads = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "javascript:alert('XSS')",
        "<div onclick='alert(1)'>Click</div>",
        "<svg><script>alert('XSS')</script></svg>",
    ]
    
    passed = 0
    failed = 0
    
    for payload in xss_payloads:
        try:
            # Try to validate a task name with XSS payload
            result = validate_task_name(payload)
            # Check that HTML tags are escaped (should contain &lt; and &gt;)
            # The key is that < and > are escaped, so the HTML won't execute
            has_unescaped_tags = "<script>" in result or "<img" in result or "<div" in result or "<svg" in result
            
            if not has_unescaped_tags:
                # Check that escaping happened (should contain &lt; or &gt; for HTML tags, or &#x27; for quotes)
                # For payloads with HTML tags, should have &lt; or &gt;
                # For payloads without HTML tags (like javascript:), quotes should be escaped
                has_escaping = "&lt;" in result or "&gt;" in result or "&#x27;" in result or "&quot;" in result
                if has_escaping or payload == result:  # If payload has no special chars, result can be same
                    print(f"[PASS] XSS payload sanitized: '{payload[:40]}...' -> '{result[:40]}...'")
                    passed += 1
                else:
                    print(f"[FAIL] XSS payload not properly escaped: '{result}'")
                    failed += 1
            else:
                print(f"[FAIL] XSS payload contains unescaped HTML tags: '{result}'")
                failed += 1
        except ValidationError:
            # If validation fails for other reasons (e.g., empty after stripping), that's OK
            print(f"[PASS] XSS payload rejected by validation: '{payload[:40]}...'")
            passed += 1
        except Exception as e:
            print(f"[FAIL] Unexpected error: {type(e).__name__}: {e}")
            failed += 1
    
    print(f"\nResult: {passed} passed, {failed} failed")
    return failed == 0


def test_error_handling():
    """Test error handling system."""
    print("\n" + "="*60)
    print("TEST 4: Error Handling System")
    print("="*60)
    
    try:
        # Test error ID generation
        test_error = ValueError("Test error message")
        error_id = handle_error("test_operation", test_error, user_id=1, context={"test": "value"})
        
        if error_id and len(error_id) == 8:
            print(f"[PASS] Error ID generated: {error_id}")
        else:
            print(f"[FAIL] Invalid error ID: {error_id}")
            return False
        
        # Test error report recording
        success = record_error_report(error_id, user_id=1, user_context="User was testing")
        if success:
            print(f"[PASS] Error report recorded successfully")
        else:
            print(f"[FAIL] Error report recording failed")
            return False
        
        print(f"[PASS] Error handling system works correctly")
        return True
        
    except Exception as e:
        print(f"[FAIL] Error handling test failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_output_escaping():
    """Test output escaping for display."""
    print("\n" + "="*60)
    print("TEST 5: Output Escaping for Display")
    print("="*60)
    
    test_cases = [
        ("<script>alert('XSS')</script>", "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;"),
        ("Normal text", "Normal text"),
        ("", ""),
        (None, ""),
    ]
    
    passed = 0
    failed = 0
    
    for input_text, expected in test_cases:
        result = escape_for_display(input_text)
        if result == expected:
            print(f"[PASS] Output escaping: '{input_text[:40] if input_text else 'None'}...'")
            passed += 1
        else:
            print(f"[FAIL] Output escaping failed")
            print(f"  Input:    '{input_text}'")
            print(f"  Expected: '{expected}'")
            print(f"  Got:      '{result}'")
            failed += 1
    
    print(f"\nResult: {passed} passed, {failed} failed")
    return failed == 0


def test_sanitize_for_storage():
    """Test sanitize_for_storage function."""
    print("\n" + "="*60)
    print("TEST 6: Sanitize for Storage")
    print("="*60)
    
    test_cases = [
        ("  <script>alert('XSS')</script>  ", "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;", "XSS with whitespace"),
        ("  Normal text  ", "Normal text", "Normal text with whitespace"),
        ("", "", "Empty string"),
        (None, "", "None value"),
    ]
    
    passed = 0
    failed = 0
    
    for input_text, expected, description in test_cases:
        result = sanitize_for_storage(input_text)
        if result == expected:
            print(f"[PASS] {description}: '{input_text[:40] if input_text else 'None'}...'")
            passed += 1
        else:
            print(f"[FAIL] {description}")
            print(f"  Input:    '{input_text}'")
            print(f"  Expected: '{expected}'")
            print(f"  Got:      '{result}'")
            failed += 1
    
    print(f"\nResult: {passed} passed, {failed} failed")
    return failed == 0


def run_all_tests():
    """Run all security tests."""
    print("\n" + "="*60)
    print("SECURITY FEATURES TEST SUITE")
    print("="*60)
    
    results = []
    
    results.append(("HTML Escaping", test_html_escaping()))
    results.append(("Input Validation", test_input_validation()))
    results.append(("XSS in Validation", test_xss_in_validation()))
    results.append(("Error Handling", test_error_handling()))
    results.append(("Output Escaping", test_output_escaping()))
    results.append(("Sanitize for Storage", test_sanitize_for_storage()))
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed_count = sum(1 for _, result in results if result)
    total_count = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n[SUCCESS] All security tests passed!")
        return 0
    else:
        print(f"\n[FAILURE] {total_count - passed_count} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
