# Loan Approval Business API

## Overview

This MCP (Model Context Protocol) server provides loan approval business logic based on **Debt-to-Income (DTI)** ratio calculations. It exposes tools for calculating DTI and evaluating loan applications using predefined business rules.

## Business Rules

### DTI-Based Approval Logic

The loan approval decision is based on the applicant's Debt-to-Income ratio:

| DTI Range | Decision | APR Rate | Description |
|-----------|----------|----------|-------------|
| **DTI > 45%** | ❌ **REJECTED** | N/A | High debt-to-income ratio |
| **40% ≤ DTI ≤ 45%** | ✅ **APPROVED** | **7.5%** | Standard rate for moderate DTI |
| **DTI < 40%** | ✅ **APPROVED** | **5.5%** | Preferred rate for excellent DTI |

### DTI Calculation Formula

```
DTI (%) = (Monthly Debt Payments / Gross Monthly Income) × 100
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server (FastMCP)                     │
│                   Port: 8080 (prod) / 8070 (dev)            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      MCP Tools (mcp_tools.py)               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  • calculateDTI                                       │  │
│  │  • evaluateLoanApplication                            │  │
│  │  • getAccountsByUserName                              │  │
│  │  • getAccountDetails                                  │  │
│  │  • getPaymentMethodDetails                            │  │
│  │  • getRegisteredBeneficiary                           │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Services (services.py)                    │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  LoanApprovalService                                  │  │
│  │    • calculate_dti()                                  │  │
│  │    • evaluate_loan_application()                      │  │
│  │                                                        │  │
│  │  AccountService                                       │  │
│  │    • get_account_details()                            │  │
│  │    • get_payment_method_details()                     │  │
│  │    • get_registered_beneficiary()                     │  │
│  │                                                        │  │
│  │  UserService                                          │  │
│  │    • get_accounts_by_user_name()                      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     Models (models.py)                      │
│  • LoanApplication, LoanDecision, LoanDecisionStatus       │
│  • ApplicantFinancials                                      │
│  • Account, PaymentMethod, Beneficiary                      │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
loan_approval/
├── README.md                    # This file
├── DTI_IMPLEMENTATION.md        # Detailed implementation guide
├── main.py                      # MCP server entry point
├── models.py                    # Pydantic data models
├── services.py                  # Business logic services
├── mcp_tools.py                 # MCP tool definitions
├── logging_config.py            # Logging configuration
├── pyproject.toml               # Python project dependencies
└── Dockerfile                   # Container image definition
```

## API Reference

### 🔧 MCP Tools

#### 1. `calculateDTI`

Calculate the debt-to-income ratio from financial information.

**Parameters:**
- `grossMonthlyIncome` (float): Gross monthly income in dollars
- `monthlyDebtPayments` (float): Total monthly debt payments in dollars

**Returns:**
```json
{
  "dti": 33.33,
  "grossMonthlyIncome": 6000.0,
  "monthlyDebtPayments": 2000.0
}
```

**Example:**
```python
calculateDTI(
    grossMonthlyIncome=6000.0,
    monthlyDebtPayments=2000.0
)
# Returns: {"dti": 33.33, ...}
```

---

#### 2. `evaluateLoanApplication`

Evaluate a loan application and return approval decision based on DTI.

**Parameters:**
- `applicantName` (str): Full name of the applicant
- `loanAmount` (float): Requested loan amount in dollars
- `grossMonthlyIncome` (float): Gross monthly income in dollars
- `monthlyDebtPayments` (float): Total monthly debt payments in dollars
- `studentNumber` (str, optional): Student number (unique identifier)
- `loanApplicationId` (str, optional): Loan application ID (unique identifier)
- `dti` (float, optional): Pre-calculated DTI (will calculate if not provided)

**Note:** Either `studentNumber` or `loanApplicationId` must be provided as the primary identifier.

**Returns:**
```json
{
  "status": "APPROVED",
  "aprRate": 5.5,
  "reason": "Approved with preferred rate due to excellent debt-to-income ratio.",
  "dti": 33.33,
  "studentNumber": "STU12345",
  "loanApplicationId": null,
  "keyId": "STU-STU12345",
  "applicantName": "John Doe",
  "loanAmount": 25000.0
}
```

**Example:**
```python
# Using student number
evaluateLoanApplication(
    studentNumber="STU12345",
    applicantName="John Doe",
    loanAmount=25000.0,
    grossMonthlyIncome=6000.0,
    monthlyDebtPayments=2000.0
)

# Using loan application ID
evaluateLoanApplication(
    loanApplicationId="APP-2025-001",
    applicantName="Jane Smith",
    loanAmount=30000.0,
    grossMonthlyIncome=5000.0,
    monthlyDebtPayments=2200.0
)
```

---

#### 3. `getAccountsByUserName`

Get the list of all accounts for a specific user.

**Parameters:**
- `userName` (str): Username of logged user

**Returns:** List of Account objects

---

#### 4. `getAccountDetails`

Get account details and available payment methods.

**Parameters:**
- `accountId` (str): Unique identifier for the user account

**Returns:** Account object with payment methods

---

#### 5. `getPaymentMethodDetails`

Get payment method details with available balance.

**Parameters:**
- `paymentMethodId` (str): Unique identifier for the payment method

**Returns:** PaymentMethod object

---

#### 6. `getRegisteredBeneficiary`

Get list of registered beneficiaries for a specific account.

**Parameters:**
- `accountId` (str): Unique identifier for the user account

**Returns:** List of Beneficiary objects

## Running the Server

### Prerequisites

- Python 3.10+
- Dependencies listed in `pyproject.toml`

### Installation

```bash
cd src/biz_api/loan_approval
pip install -e .
```

### Start Server

**Development Mode (Port 8070):**
```bash
export PROFILE=dev
python main.py
```

**Production Mode (Port 8080):**
```bash
export PROFILE=prod
python main.py
```

Or simply:
```bash
python main.py  # Defaults to production mode
```

### Docker Deployment

```bash
# Build image
docker build -t loan-approval-api .

# Run container
docker run -p 8080:8080 -e PROFILE=prod loan-approval-api
```

## Testing

### Manual Testing via HTTP

Once the server is running, you can test the endpoints:

```bash
# Calculate DTI
curl -X POST http://localhost:8080/calculateDTI \
  -H "Content-Type: application/json" \
  -d '{
    "grossMonthlyIncome": 5000,
    "monthlyDebtPayments": 1500
  }'

# Evaluate Loan Application
curl -X POST http://localhost:8080/evaluateLoanApplication \
  -H "Content-Type: application/json" \
  -d '{
    "studentNumber": "STU12345",
    "applicantName": "John Doe",
    "loanAmount": 25000,
    "grossMonthlyIncome": 6000,
    "monthlyDebtPayments": 2000
  }'
```

### Test Scenarios

| Scenario | Monthly Income | Monthly Debt | DTI | Expected Result |
|----------|---------------|--------------|-----|-----------------|
| Excellent Credit | $6,000 | $1,800 | 30% | APPROVED at 5.5% |
| Good Credit | $5,000 | $2,100 | 42% | APPROVED at 7.5% |
| High Debt | $4,000 | $2,000 | 50% | REJECTED |

## Integration with Agent Workflow

This MCP server is designed to integrate with the loan processing agent workflow:

```
┌─────────────────────────────────────────────────────────────┐
│  1. Document Extractor Agent                                │
│     └─→ Extracts: grossMonthlyIncome, monthlyDebtPayments  │
│     └─→ Extracts: studentNumber or loanApplicationId       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Triage Agent                                            │
│     └─→ Calls: calculateDTI()                              │
│     └─→ Computes and persists DTI value                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Financial Analyzer Agent                                │
│     └─→ Calls: evaluateLoanApplication()                   │
│     └─→ Applies DTI-based business rules                   │
│     └─→ Returns decision, APR, and reason                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Decision Maker Agent                                    │
│     └─→ Presents final decision to user                    │
└─────────────────────────────────────────────────────────────┘
```

## Data Models

### LoanApplication

```python
{
    "studentNumber": "STU12345",           # Optional: Student number
    "loanApplicationId": "APP-2025-001",   # Optional: Loan application ID
    "applicantName": "John Doe",           # Required
    "loanAmount": 25000.0,                 # Required
    "financials": {                        # Required
        "grossMonthlyIncome": 6000.0,
        "monthlyDebtPayments": 2000.0,
    }
}
```

**Note:** Must provide either `studentNumber` or `loanApplicationId`.

### LoanDecision

```python
{
    "status": "APPROVED",                  # APPROVED | REJECTED | CONDITIONAL
    "aprRate": 5.5,                        # Null if rejected
    "reason": "Approved with preferred rate...",
    "dti": 33.33,
    "studentNumber": "STU12345",
    "loanApplicationId": null,
    "keyId": "STU-STU12345",
    "applicantName": "John Doe",
    "loanAmount": 25000.0
}
```

## Logging

All operations are logged with structured information for audit trails:

```
INFO: Calculating DTI: monthly_debt=2000.0, monthly_income=6000.0
INFO: Calculated DTI: 33.33%
INFO: Evaluating loan application for John Doe (ID: STU-STU12345), amount: $25000.00
INFO: Loan APPROVED at 5.5% APR: DTI=33.33%
```

## Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `PROFILE` | `dev` \| `prod` | `prod` | Server profile for port selection |

## Error Handling

The service includes validation for:
- ✅ Gross monthly income must be > 0
- ✅ Either `studentNumber` or `loanApplicationId` must be provided
- ✅ Account IDs must be numeric
- ✅ Payment method IDs must be numeric

## Dependencies

See `pyproject.toml` for full dependency list:
- `fastmcp` - MCP server framework
- `pydantic` - Data validation
- Standard library: `logging`, `typing`, `enum`

## Support

For issues or questions:
1. Check `DTI_IMPLEMENTATION.md` for detailed implementation guide
2. Review logs for error messages
3. Verify input parameters match expected types

## License

See LICENSE file in project root.
