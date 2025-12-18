# DTI-Based Loan Approval Implementation

## Overview
This implementation adds **Debt-to-Income (DTI) ratio** based loan approval business logic to the loan processing system.

## Business Rules

### DTI Thresholds
- **DTI > 45%**: ❌ **REJECTED** - "High debt-to-income ratio"
- **40% ≤ DTI ≤ 45%**: ✅ **APPROVED** at **7.5% APR** - Standard rate
- **DTI < 40%**: ✅ **APPROVED** at **5.5% APR** - Preferred rate

### DTI Calculation
```
DTI (%) = (Monthly Debt Payments / Gross Monthly Income) × 100
```

## Implementation Details

### Modified Files

#### 1. `models.py` - New Data Models
Added the following Pydantic models:

- **`LoanDecisionStatus`**: Enum for decision status (APPROVED, REJECTED, CONDITIONAL)
- **`ApplicantFinancials`**: Financial data extracted from documents
  - `grossMonthlyIncome`: float
  - `monthlyDebtPayments`: float
  - `dti`: Optional[float] (calculated if not provided)

- **`LoanApplication`**: Loan application request
  - `applicantId`: str
  - `applicantName`: str
  - `loanAmount`: float
  - `financials`: ApplicantFinancials

- **`LoanDecision`**: Loan approval/rejection response
  - `status`: LoanDecisionStatus
  - `aprRate`: Optional[float]
  - `reason`: str
  - `dti`: float
  - `applicantId`: str
  - `applicantName`: str
  - `loanAmount`: float

#### 2. `services.py` - Business Logic
Added **`LoanApprovalService`** class with two main methods:

**`calculate_dti(financials: ApplicantFinancials) -> float`**
- Calculates DTI percentage from financial data
- Validates that gross monthly income > 0
- Returns DTI as percentage (0-100+)

**`evaluate_loan_application(application: LoanApplication) -> LoanDecision`**
- Applies DTI-based business rules
- Returns structured decision with status, APR, and reason
- Logs decisions for audit trail

#### 3. `mcp_tools.py` - MCP Tool Endpoints
Added two new MCP tools for the agent workflow:

**`calculateDTI`**
- **Input**: `grossMonthlyIncome`, `monthlyDebtPayments`
- **Output**: DTI percentage with financial summary
- **Use Case**: Triage Agent computes and persists DTI

**`evaluateLoanApplication`**
- **Input**: Applicant info + financials (with optional pre-calculated DTI)
- **Output**: Full loan decision with approval status, APR, and reason
- **Use Case**: Financial Analyzer Agent applies business rules

## Agent Workflow Integration

Based on the guidance, the DTI logic integrates with agents as follows:

```
┌─────────────────────────────────────────────────────────────┐
│  1. Document Extractor Agent                                │
│     └─→ Extracts: grossMonthlyIncome, monthlyDebtPayments  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Triage Agent                                            │
│     └─→ Calls: calculateDTI()                              │
│     └─→ Computes: dti = (debt / income) × 100              │
│     └─→ Persists: DTI value for downstream agents          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Financial Analyzer Agent                                │
│     └─→ Calls: evaluateLoanApplication()                   │
│     └─→ Applies: DTI-based business rules                  │
│     └─→ Returns: Decision (APPROVED/REJECTED) + APR + Reason│
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Decision Maker Agent                                    │
│     └─→ Echoes: Final decision and rationale to user       │
└─────────────────────────────────────────────────────────────┘
```

## Example Usage

### Example 1: Low DTI (Approved at 5.5%)
```python
from services import LoanApprovalService
from models import LoanApplication, ApplicantFinancials

service = LoanApprovalService()

application = LoanApplication(
    applicantId="APP-001",
    applicantName="John Doe",
    loanAmount=25000.0,
    financials=ApplicantFinancials(
        grossMonthlyIncome=6000.0,
        monthlyDebtPayments=1800.0  # DTI = 30%
    )
)

decision = service.evaluate_loan_application(application)
# Result:
# - status: APPROVED
# - aprRate: 5.5%
# - reason: "Approved with preferred rate due to excellent debt-to-income ratio."
# - dti: 30.0
```

### Example 2: Moderate DTI (Approved at 7.5%)
```python
application = LoanApplication(
    applicantId="APP-002",
    applicantName="Jane Smith",
    loanAmount=30000.0,
    financials=ApplicantFinancials(
        grossMonthlyIncome=5000.0,
        monthlyDebtPayments=2200.0  # DTI = 44%
    )
)

decision = service.evaluate_loan_application(application)
# Result:
# - status: APPROVED
# - aprRate: 7.5%
# - reason: "Approved with standard rate due to moderate debt-to-income ratio."
# - dti: 44.0
```

### Example 3: High DTI (Rejected)
```python
application = LoanApplication(
    applicantId="APP-003",
    applicantName="Bob Wilson",
    loanAmount=20000.0,
    financials=ApplicantFinancials(
        grossMonthlyIncome=4000.0,
        monthlyDebtPayments=2000.0  # DTI = 50%
    )
)

decision = service.evaluate_loan_application(application)
# Result:
# - status: REJECTED
# - aprRate: None
# - reason: "High debt-to-income ratio. DTI must be 45% or lower to qualify."
# - dti: 50.0
```

## MCP Tool Testing

You can test the MCP tools via HTTP requests once the server is running:

```bash
# Start the MCP server
cd src/biz_api/loan_approval
python main.py

# Test calculateDTI
curl -X POST http://localhost:8080/calculateDTI \
  -H "Content-Type: application/json" \
  -d '{
    "grossMonthlyIncome": 5000,
    "monthlyDebtPayments": 1500
  }'

# Test evaluateLoanApplication
curl -X POST http://localhost:8080/evaluateLoanApplication \
  -H "Content-Type: application/json" \
  -d '{
    "applicantId": "APP-123",
    "applicantName": "Test User",
    "loanAmount": 25000,
    "grossMonthlyIncome": 6000,
    "monthlyDebtPayments": 2000
  }'
```

## Logging
All operations are logged with structured information:
- DTI calculations with input values
- Loan approval decisions with thresholds
- Applicant information for audit trails

Example log output:
```
INFO: Calculating DTI: monthly_debt=2000.0, monthly_income=6000.0
INFO: Calculated DTI: 33.33%
INFO: Evaluating loan application for John Doe (ID: APP-001), amount: $25000.00
INFO: Loan APPROVED at 5.5% APR: DTI=33.33%
```

## Next Steps

To complete the agent integration:

1. **Document Extractor Agent**: Modify to extract `grossMonthlyIncome` and `monthlyDebtPayments`
2. **Triage Agent**: Create/modify to call `calculateDTI` MCP tool
3. **Financial Analyzer Agent**: Create/modify to call `evaluateLoanApplication` MCP tool
4. **Decision Maker Agent**: Create/modify to format and present the final decision

## Dependencies
- `pydantic`: For data validation and models
- `fastmcp`: For MCP tool integration
- Standard logging for audit trails
