"""Test script for Triage Agent validation.

This script demonstrates the Triage Agent's three-level validation capabilities.
"""
import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.agents.loan_workflow.loan_application_validator import (
    TriageAgentFactory,
    TriageValidator,
    run_triage_validation
)
from app.config.azure_credential import get_azure_credential
from app.config.settings import settings
from agent_framework.azure import AzureOpenAIChatClient


# Sample extracted data (simulating output from Document Extractor)
SAMPLE_MATCHING_DATA = {
    "extracted_data": {
        "la-JaneSmith-standard_rate-02.pdf": {
            "studentNumber": "STU123456",
            "applicantName": "Jane Smith",
            "email": "jane.smith@university.edu",
            "phone": "+1-555-0123",
            "loanAmount": 25000.00,
            "loanPurpose": "Tuition fees for Fall 2025",
            "grossMonthlyIncome": 4500.00,
            "monthlyDebtPayments": 800.00,
            "bankName": "First National Bank",
            "accountType": "Checking",
            "accountNumber": "****5678"
        },
        "bs-JaneSmith_BankStatement.pdf": {
            "accountHolderName": "Jane Smith",
            "bankName": "First National Bank",
            "accountType": "Checking",
            "accountNumberLast4": "5678",
            "currentBalance": 12500.00,
            "statementPeriod": "January 2025 - March 2025"
        }
    }
}

SAMPLE_MISMATCHED_DATA = {
    "extracted_data": {
        "la-JaneSmith-standard_rate-02.pdf": {
            "studentNumber": "STU123456",
            "applicantName": "Jane Smith",
            "email": "jane.smith@university.edu",
            "phone": "+1-555-0123",
            "loanAmount": 25000.00,
            "loanPurpose": "Tuition fees",
            "grossMonthlyIncome": 4500.00,
            "monthlyDebtPayments": 800.00,
            "bankName": "First National Bank",
            "accountType": "Checking",
            "accountNumber": "****5678"
        },
        "bs-JohnDoe_BankStatement.pdf": {
            "accountHolderName": "John Doe",  # Mismatch!
            "bankName": "Second National Bank",  # Mismatch!
            "accountType": "Savings",  # Mismatch!
            "accountNumberLast4": "1234",  # Mismatch!
            "currentBalance": 8000.00,
            "statementPeriod": "January 2025 - March 2025"
        }
    }
}


async def test_validator_helper_functions():
    """Test the TriageValidator helper functions."""
    print("="*80)
    print("Testing TriageValidator Helper Functions")
    print("="*80)
    
    # Test name matching
    print("\n1. Name Matching Tests:")
    test_cases = [
        ("Jane Smith", "Jane Smith", True),
        ("Jane Smith", "Jane M. Smith", True),
        ("Jane Smith", "John Smith", False),
        ("Jane Marie Smith", "Jane Smith", True),
    ]
    
    for name1, name2, expected in test_cases:
        result = TriageValidator.names_match(name1, name2)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{name1}' vs '{name2}': {result} (expected: {expected})")
    
    # Test last 4 digits extraction
    print("\n2. Account Number Last 4 Digits Extraction:")
    test_numbers = ["****5678", "1234-5678", "Account: 12345678", "5678"]
    for num in test_numbers:
        result = TriageValidator.extract_last_4_digits(num)
        print(f"  '{num}' → '{result}'")
    
    # Test validation functions
    print("\n3. Field Validation Tests:")
    print(f"  Email 'jane@example.com': {TriageValidator.validate_email('jane@example.com')}")
    print(f"  Email 'invalid': {TriageValidator.validate_email('invalid')}")
    print(f"  Phone '+1-555-0123': {TriageValidator.validate_phone('+1-555-0123')}")
    print(f"  Phone '123': {TriageValidator.validate_phone('123')}")
    print(f"  Student# 'STU123456': {TriageValidator.validate_student_number('STU123456')}")
    print(f"  Student# '123456': {TriageValidator.validate_student_number('123456')}")


async def test_cross_document_validation():
    """Test Level 1 cross-document validation."""
    print("\n" + "="*80)
    print("Testing Level 1: Cross-Document Validation")
    print("="*80)
    
    # Get data from sample
    loan_app = SAMPLE_MATCHING_DATA["extracted_data"]["la-JaneSmith-standard_rate-02.pdf"]
    bank_stmt = SAMPLE_MATCHING_DATA["extracted_data"]["bs-JaneSmith_BankStatement.pdf"]
    
    print("\n✓ Testing MATCHING documents:")
    result = TriageValidator.validate_cross_document(loan_app, bank_stmt)
    print(f"  Overall Status: {result['status']}")
    for check_name, check_result in result['checks'].items():
        status_icon = "✓" if check_result['status'] == 'pass' else "✗"
        print(f"  {status_icon} {check_name}: {check_result['message']}")
    
    # Test with mismatched data
    loan_app_mismatch = SAMPLE_MISMATCHED_DATA["extracted_data"]["la-JaneSmith-standard_rate-02.pdf"]
    bank_stmt_mismatch = SAMPLE_MISMATCHED_DATA["extracted_data"]["bs-JohnDoe_BankStatement.pdf"]
    
    print("\n✗ Testing MISMATCHED documents:")
    result = TriageValidator.validate_cross_document(loan_app_mismatch, bank_stmt_mismatch)
    print(f"  Overall Status: {result['status']}")
    for check_name, check_result in result['checks'].items():
        status_icon = "✓" if check_result['status'] == 'pass' else "✗"
        print(f"  {status_icon} {check_name}: {check_result['message']}")
        if check_result['status'] == 'fail':
            print(f"      Loan App: '{check_result['loan_app_value']}'")
            print(f"      Bank Stmt: '{check_result['bank_stmt_value']}'")


async def test_completeness_validation():
    """Test Level 3 completeness validation."""
    print("\n" + "="*80)
    print("Testing Level 3: Completeness Validation")
    print("="*80)
    
    # Complete data
    complete_data = SAMPLE_MATCHING_DATA["extracted_data"]["la-JaneSmith-standard_rate-02.pdf"]
    
    print("\n✓ Testing COMPLETE data:")
    result = TriageValidator.validate_completeness(complete_data)
    print(f"  Overall Status: {result['status']}")
    print(f"  All Required Present: {result['all_required_present']}")
    print(f"  Missing Fields: {result['missing_fields'] if result['missing_fields'] else 'None'}")
    print(f"  Invalid Fields: {result['invalid_fields'] if result['invalid_fields'] else 'None'}")
    
    # Incomplete data
    incomplete_data = {
        "studentNumber": "STU123456",
        "applicantName": "Jane",  # Only first name
        "email": "invalid-email",  # Invalid format
        "loanAmount": 500,  # Too low
        "grossMonthlyIncome": 100000,  # Too high
    }
    
    print("\n✗ Testing INCOMPLETE data:")
    result = TriageValidator.validate_completeness(incomplete_data)
    print(f"  Overall Status: {result['status']}")
    print(f"  All Required Present: {result['all_required_present']}")
    if result['missing_fields']:
        print(f"  Missing Fields:")
        for field in result['missing_fields']:
            print(f"    - {field}")
    if result['invalid_fields']:
        print(f"  Invalid Fields:")
        for field in result['invalid_fields']:
            print(f"    - {field}")


async def test_triage_agent_with_ai():
    """Test the full Triage Agent with AI-powered validation."""
    print("\n" + "="*80)
    print("Testing Full Triage Agent (AI-Powered)")
    print("="*80)
    
    try:
        # Create Azure chat client
        if settings.AZURE_OPENAI_KEY:
            chat_client = AzureOpenAIChatClient(
                api_key=settings.AZURE_OPENAI_KEY,
                endpoint=settings.AZURE_OPENAI_ENDPOINT,
                deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
            )
        else:
            chat_client = AzureOpenAIChatClient(
                credential=get_azure_credential(),
                endpoint=settings.AZURE_OPENAI_ENDPOINT,
                deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
            )
        
        # Create Triage Agent
        triage_agent = TriageAgentFactory.create_triage_agent(chat_client)
        
        print("\n✓ Testing with MATCHING documents:")
        print("-" * 80)
        result = await run_triage_validation(triage_agent, SAMPLE_MATCHING_DATA)
        
        print(f"\nOverall Status: {result.get('overall_status')}")
        print(f"Ready for Decision: {result.get('ready_for_decision')}")
        
        if result.get('discrepancies'):
            print("\nDiscrepancies Found:")
            for disc in result['discrepancies']:
                print(f"  • {disc['field']}: {disc['message']}")
        else:
            print("\n✓ No discrepancies found!")
        
        print("\nConsolidated Data:")
        consolidated = result.get('consolidated_data', {})
        print(f"  Student: {consolidated.get('applicantName')} ({consolidated.get('studentNumber')})")
        print(f"  Loan Amount: ${consolidated.get('loanAmount'):,.2f}")
        print(f"  Monthly Income: ${consolidated.get('grossMonthlyIncome'):,.2f}")
        print(f"  Monthly Debts: ${consolidated.get('monthlyDebtPayments'):,.2f}")
        print(f"  Bank: {consolidated.get('bankName')} - {consolidated.get('accountType')}")
        
        # Test with mismatched data
        print("\n\n✗ Testing with MISMATCHED documents:")
        print("-" * 80)
        result = await run_triage_validation(triage_agent, SAMPLE_MISMATCHED_DATA)
        
        print(f"\nOverall Status: {result.get('overall_status')}")
        print(f"Ready for Decision: {result.get('ready_for_decision')}")
        
        if result.get('discrepancies'):
            print("\nDiscrepancies Found:")
            for disc in result['discrepancies']:
                print(f"  • Level {disc['level']} - {disc['field']}:")
                print(f"    Expected: {disc['expected']}")
                print(f"    Actual: {disc['actual']}")
                print(f"    Message: {disc['message']}")
        
        if result.get('user_notification'):
            print(f"\nUser Notification:\n{result['user_notification']}")
        
    except Exception as e:
        print(f"\n✗ Error testing Triage Agent: {str(e)}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("TRIAGE AGENT TEST SUITE")
    print("="*80)
    
    # Run helper function tests
    await test_validator_helper_functions()
    
    # Run cross-document validation tests
    await test_cross_document_validation()
    
    # Run completeness validation tests
    await test_completeness_validation()
    
    # Run full AI-powered Triage Agent test
    await test_triage_agent_with_ai()
    
    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
