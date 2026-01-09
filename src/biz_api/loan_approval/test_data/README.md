# Test Data for Loan Approval API

This folder contains input/output JSON pairs for testing the loan approval business logic.

## File Structure

Each test case has two files:
- `*_input.json` - Request payload to send to the API
- `*_output.json` - Expected response from the API

## Test Cases

### 1. REJECTED - High DTI (> 45%)

**Input:** `rejected_high_dti_input.json`
```json
{
  "studentNumber": "STU78901",
  "applicantName": "Robert Wilson",
  "loanAmount": 20000.0,
  "grossMonthlyIncome": 4000.0,
  "monthlyDebtPayments": 2000.0
}
```

**Output:** `rejected_high_dti_output.json`
- **DTI:** 50% (2000 / 4000 × 100)
- **Status:** REJECTED
- **APR:** null
- **Reason:** "High debt-to-income ratio. DTI must be 45% or lower to qualify."

---

### 2. APPROVED - Standard Rate (40% ≤ DTI ≤ 45%)

**Input:** `approved_standard_rate_input.json`
```json
{
  "studentNumber": "STU45678",
  "applicantName": "Jane Smith",
  "loanAmount": 30000.0,
  "grossMonthlyIncome": 5000.0,
  "monthlyDebtPayments": 2200.0
}
```

**Output:** `approved_standard_rate_output.json`
- **DTI:** 44% (2200 / 5000 × 100)
- **Status:** APPROVED
- **APR:** 7.5%
- **Reason:** "Approved with standard rate due to moderate debt-to-income ratio."

---

### 3. APPROVED - Preferred Rate (DTI < 40%)

**Input:** `approved_preferred_rate_input.json`
```json
{
  "studentNumber": "STU12345",
  "applicantName": "John Doe",
  "loanAmount": 25000.0,
  "grossMonthlyIncome": 6000.0,
  "monthlyDebtPayments": 2000.0
}
```

**Output:** `approved_preferred_rate_output.json`
- **DTI:** 33.33% (2000 / 6000 × 100)
- **Status:** APPROVED
- **APR:** 5.5%
- **Reason:** "Approved with preferred rate due to excellent debt-to-income ratio."

---

### 4. Using Loan Application ID

**Input:** `loan_application_id_input.json`
```json
{
  "loanApplicationId": "APP-2025-001",
  "applicantName": "Sarah Johnson",
  "loanAmount": 35000.0,
  "grossMonthlyIncome": 7500.0,
  "monthlyDebtPayments": 2400.0
}
```

**Output:** `loan_application_id_output.json`
- **DTI:** 32% (2400 / 7500 × 100)
- **Status:** APPROVED
- **APR:** 5.5%
- **Uses:** `loanApplicationId` instead of `studentNumber`

---

## How to Use

### 1. Manual Testing with curl

**Test Rejected Case:**
```bash
curl -X POST http://localhost:8080/evaluateLoanApplication \
  -H "Content-Type: application/json" \
  -d @test_data/rejected_high_dti_input.json
```

**Test Standard Rate Approval:**
```bash
curl -X POST http://localhost:8080/evaluateLoanApplication \
  -H "Content-Type: application/json" \
  -d @test_data/approved_standard_rate_input.json
```

**Test Preferred Rate Approval:**
```bash
curl -X POST http://localhost:8080/evaluateLoanApplication \
  -H "Content-Type: application/json" \
  -d @test_data/approved_preferred_rate_input.json
```

**Test with Loan Application ID:**
```bash
curl -X POST http://localhost:8080/evaluateLoanApplication \
  -H "Content-Type: application/json" \
  -d @test_data/loan_application_id_input.json
```

### 2. Automated Testing Script

```python
import json
import requests

def test_loan_approval(input_file, output_file):
    # Load input and expected output
    with open(input_file) as f:
        input_data = json.load(f)
    with open(output_file) as f:
        expected_output = json.load(f)
    
    # Call API
    response = requests.post(
        'http://localhost:8080/evaluateLoanApplication',
        json=input_data
    )
    
    actual_output = response.json()
    
    # Validate response
    print(f"Testing: {input_file}")
    print(f"  Status: {'✓' if actual_output['status'] == expected_output['status'] else '✗'}")
    print(f"  APR: {'✓' if actual_output['aprRate'] == expected_output['aprRate'] else '✗'}")
    print(f"  DTI: {actual_output['dti']}%")
    print(f"  Reason: {actual_output['reason']}")
    
    # Assert equality
    assert actual_output == expected_output, "Output mismatch!"
    print("  ✓ PASSED\n")

# Run all tests
test_loan_approval('test_data/rejected_high_dti_input.json', 
                   'test_data/rejected_high_dti_output.json')
test_loan_approval('test_data/approved_standard_rate_input.json',
                   'test_data/approved_standard_rate_output.json')
test_loan_approval('test_data/approved_preferred_rate_input.json',
                   'test_data/approved_preferred_rate_output.json')
test_loan_approval('test_data/loan_application_id_input.json',
                   'test_data/loan_application_id_output.json')
```

### 3. Simple Test with jq

```bash
# Test and compare output
curl -s -X POST http://localhost:8080/evaluateLoanApplication \
  -H "Content-Type: application/json" \
  -d @test_data/rejected_high_dti_input.json | \
  jq '.' > actual_output.json

# Compare with expected
diff test_data/rejected_high_dti_output.json actual_output.json
```

### 4. Using Provided Test Scripts

**Python Test (Direct Service Testing - No Server Required):**
```bash
# Run tests directly without starting the MCP server
cd src/biz_api/loan_approval
python test_loan_approval.py
```

This tests the loan approval logic directly by importing the service classes.

**Bash Test (HTTP API Testing - Server Must Be Running):**
```bash
# First, start the MCP server in one terminal
cd src/biz_api/loan_approval
python main.py

# Then, in another terminal, run the HTTP tests
cd src/biz_api/loan_approval
bash test_http.sh
```

This tests the actual HTTP endpoints of the running MCP server.

## DTI Business Rules Summary

| DTI Range | Status | APR | Test File |
|-----------|--------|-----|-----------|
| > 45% | REJECTED | N/A | `rejected_high_dti.json` |
| 40% - 45% | APPROVED | 7.5% | `approved_standard_rate.json` |
| < 40% | APPROVED | 5.5% | `approved_preferred_rate.json` |

## Test Coverage

✅ **Rejected Scenario** - DTI > 45%  
✅ **Standard Rate Approval** - 40% ≤ DTI ≤ 45%  
✅ **Preferred Rate Approval** - DTI < 40%  
✅ **Student Number Identifier** - Using `studentNumber`  
✅ **Loan Application ID Identifier** - Using `loanApplicationId`  
✅ **Edge Cases** - Boundary values (40%, 45%, 39.9%, 0%)  

## Notes

- All monetary values are in USD
- DTI is calculated as: `(monthlyDebtPayments / grossMonthlyIncome) × 100`
- Either `studentNumber` or `loanApplicationId` must be provided
- The `keyId` field in responses is auto-generated from the identifier type
