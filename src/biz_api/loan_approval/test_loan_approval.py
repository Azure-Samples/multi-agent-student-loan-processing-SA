#!/usr/bin/env python3
"""
Test script for Loan Approval MCP Server
Runs test cases using the sample JSON files
"""

import json
import sys
import os
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from services import LoanApprovalService
from models import LoanApplication, ApplicantFinancials


def load_test_case(input_file, output_file):
    """Load input and expected output from JSON files"""
    with open(input_file, 'r') as f:
        input_data = json.load(f)
    with open(output_file, 'r') as f:
        expected_output = json.load(f)
    return input_data, expected_output


def run_test(test_name, input_file, output_file):
    """Run a single test case"""
    print(f"\n{'='*70}")
    print(f"Testing: {test_name}")
    print(f"{'='*70}")
    
    # Load test data
    input_data, expected_output = load_test_case(input_file, output_file)
    
    print(f"\n📥 INPUT:")
    print(f"  Student Number: {input_data['studentNumber']}")
    print(f"  Applicant: {input_data['applicantName']}")
    print(f"  Loan Amount: ${input_data['loanAmount']:,.2f}")
    print(f"  Monthly Income: ${input_data['grossMonthlyIncome']:,.2f}")
    print(f"  Monthly Debt: ${input_data['monthlyDebtPayments']:,.2f}")
    
    # Create loan application
    financials = ApplicantFinancials(
        grossMonthlyIncome=input_data['grossMonthlyIncome'],
        monthlyDebtPayments=input_data['monthlyDebtPayments']
    )
    
    application = LoanApplication(
        studentNumber=input_data['studentNumber'],
        applicantName=input_data['applicantName'],
        loanAmount=input_data['loanAmount'],
        financials=financials
    )
    
    # Evaluate loan application
    service = LoanApprovalService()
    decision = service.evaluate_loan_application(application)
    actual_output = decision.model_dump()
    
    print(f"\n📤 OUTPUT:")
    print(f"  Status: {actual_output['status']}")
    print(f"  APR Rate: {actual_output['aprRate']}%" if actual_output['aprRate'] else "  APR Rate: N/A")
    print(f"  DTI: {actual_output['dti']:.2f}%")
    print(f"  Loan Application ID: {actual_output['loanApplicationId']}")
    print(f"  Reason: {actual_output['reason']}")
    
    # Validate results
    print(f"\n✅ VALIDATION:")
    passed = True
    
    if actual_output['status'] != expected_output['status']:
        print(f"  ❌ Status mismatch: got '{actual_output['status']}', expected '{expected_output['status']}'")
        passed = False
    else:
        print(f"  ✓ Status: {actual_output['status']}")
    
    if actual_output['aprRate'] != expected_output['aprRate']:
        print(f"  ❌ APR mismatch: got {actual_output['aprRate']}, expected {expected_output['aprRate']}")
        passed = False
    else:
        print(f"  ✓ APR: {actual_output['aprRate']}%")
    
    # DTI might have slight floating point differences
    if abs(actual_output['dti'] - expected_output['dti']) > 0.1:
        print(f"  ❌ DTI mismatch: got {actual_output['dti']:.2f}%, expected {expected_output['dti']:.2f}%")
        passed = False
    else:
        print(f"  ✓ DTI: {actual_output['dti']:.2f}%")
    
    if actual_output['loanApplicationId'] != expected_output['loanApplicationId']:
        print(f"  ❌ Loan Application ID mismatch: got '{actual_output['loanApplicationId']}', expected '{expected_output['loanApplicationId']}'")
        passed = False
    else:
        print(f"  ✓ Loan Application ID: {actual_output['loanApplicationId']}")
    
    if passed:
        print(f"\n🎉 TEST PASSED!")
    else:
        print(f"\n❌ TEST FAILED!")
    
    return passed


def main():
    """Run all test cases"""
    print("="*70)
    print("Loan Approval MCP Server - Test Suite")
    print("="*70)
    
    test_dir = Path(__file__).parent / "test_data"
    
    test_cases = [
        ("REJECTED - High DTI (> 45%)", 
         "rejected_high_dti_input.json", 
         "rejected_high_dti_output.json"),
        
        ("APPROVED - Standard Rate (40% ≤ DTI ≤ 45%)", 
         "approved_standard_rate_input.json", 
         "approved_standard_rate_output.json"),
        
        ("APPROVED - Preferred Rate (DTI < 40%)", 
         "approved_preferred_rate_input.json", 
         "approved_preferred_rate_output.json"),
    ]
    
    results = []
    for test_name, input_file, output_file in test_cases:
        input_path = test_dir / input_file
        output_path = test_dir / output_file
        
        if not input_path.exists() or not output_path.exists():
            print(f"\n⚠️  Skipping {test_name} - files not found")
            continue
        
        passed = run_test(test_name, input_path, output_path)
        results.append((test_name, passed))
    
    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    
    total = len(results)
    passed_count = sum(1 for _, passed in results if passed)
    failed_count = total - passed_count
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {status}: {test_name}")
    
    print(f"\nTotal: {total} | Passed: {passed_count} | Failed: {failed_count}")
    
    if failed_count == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {failed_count} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
