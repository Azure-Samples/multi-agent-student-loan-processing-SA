# Triage Agent

The Triage Agent performs comprehensive three-level validation on loan application documents before they are sent for approval decision.

## Overview

The Triage Agent is a **ChatAgent** (AI-powered) that validates extracted document data through three validation levels:

1. **Level 1: Cross-Document Validation** - Compares data between Loan Application and Bank Statement
2. **Level 2: Cosmos DB Validation** - Compares with historical applicant data (if exists)
3. **Level 3: Completeness Check** - Ensures all required fields are present and valid

## Architecture

```
Document Extractor (Executor)
      ↓
  [Extracted Data]
      ↓
Triage Agent (ChatAgent) ← Cosmos DB Query Tool (future)
      ↓
  [Validation Result]
      ↓
├─ Pass → Decision Maker Agent
└─ Fail → Return to User for Correction
```

## Components

### 1. TriageAgentFactory

Factory class for creating configured Triage ChatAgent instances.

```python
from app.agents.loan_workflow.loan_application_validator import TriageAgentFactory
from agent_framework.azure import AzureOpenAIChatClient

chat_client = AzureOpenAIChatClient(...)
triage_agent = TriageAgentFactory.create_triage_agent(chat_client)
```

### 2. TriageValidator

Helper class with deterministic validation rules.

```python
from app.agents.loan_workflow.loan_application_validator import TriageValidator

# Validate cross-document consistency
result = TriageValidator.validate_cross_document(loan_app_data, bank_stmt_data)

# Validate completeness
result = TriageValidator.validate_completeness(loan_app_data)

# Helper functions
TriageValidator.names_match("Jane Smith", "Jane M. Smith")  # True
TriageValidator.extract_last_4_digits("****5678")  # "5678"
TriageValidator.validate_email("jane@example.com")  # True
```

### 3. run_triage_validation

Async function to run complete validation.

```python
from app.agents.loan_workflow.loan_application_validator import run_triage_validation

extracted_data = {
    "extracted_data": {
        "loan_application.pdf": {...},
        "bank_statement.pdf": {...}
    }
}

validation_result = await run_triage_validation(triage_agent, extracted_data)
```

## Validation Levels

### Level 1: Cross-Document Validation (CRITICAL)

Compares these fields between Loan Application and Bank Statement:

| Field | Validation Rule | Error Type |
|-------|----------------|------------|
| **Name** | Must match (allows middle name variations) | FAIL |
| **Bank Name** | Must be identical | FAIL |
| **Account Type** | Must match (Checking/Savings) | FAIL |
| **Last 4 Digits** | Account number last 4 must match | FAIL |

**Example:**
- ✅ "Jane Smith" matches "Jane M. Smith"
- ✅ "First National Bank" == "First National Bank"
- ❌ "Checking" ≠ "Savings"
- ❌ "5678" ≠ "1234"

### Level 2: Cosmos DB Validation (WARNING)

Compares current application with historical data (if applicant exists):

- Personal info changes (name, email, phone)
- Financial data trends (income significantly different?)
- Account changes (different bank or account?)
- Previous application history (multiple recent applications?)

**Status:** Currently returns "not_applicable" (to be implemented in Phase 7)

### Level 3: Completeness Check (CRITICAL)

Validates required fields for MCP system:

**Required Fields:**
- `studentNumber` - Format: STU######
- `applicantName` - Min 2 words (first + last name)
- `email` - Valid email format
- `phone` - Valid phone format (10-11 digits)
- `loanAmount` - Range: $1,000 - $100,000
- `grossMonthlyIncome` - Range: $1,000 - $50,000
- `monthlyDebtPayments` - >= 0 and < grossMonthlyIncome

## Input Format

The Triage Agent expects extracted data in this structure:

```json
{
  "extracted_data": {
    "la-JaneSmith-standard_rate-02.pdf": {
      "studentNumber": "STU123456",
      "applicantName": "Jane Smith",
      "email": "jane.smith@example.com",
      "phone": "+1-555-0123",
      "loanAmount": 25000.00,
      "loanPurpose": "Tuition fees",
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
```

## Output Format

The Triage Agent returns structured JSON:

```json
{
  "validation_result": {
    "level1_cross_document": {
      "status": "pass",
      "checks": {
        "name_match": {
          "status": "pass",
          "loan_app_value": "Jane Smith",
          "bank_stmt_value": "Jane Smith",
          "message": "Names match"
        },
        "bank_match": {...},
        "account_type_match": {...},
        "account_number_match": {...}
      }
    },
    "level2_cosmos_db": {
      "status": "not_applicable",
      "applicant_exists": false
    },
    "level3_completeness": {
      "status": "pass",
      "all_required_present": true,
      "missing_fields": [],
      "invalid_fields": []
    }
  },
  "consolidated_data": {
    "studentNumber": "STU123456",
    "applicantName": "Jane Smith",
    "email": "jane.smith@example.com",
    "loanAmount": 25000.00,
    "grossMonthlyIncome": 4500.00,
    "monthlyDebtPayments": 800.00,
    "bankName": "First National Bank",
    "accountType": "Checking",
    "accountNumberLast4": "5678",
    "currentBalance": 12500.00
  },
  "discrepancies": [],
  "overall_status": "approved",
  "ready_for_decision": true,
  "user_notification": null
}
```

### Overall Status Values

- **`approved`** - All validations passed, ready for Decision Maker
- **`needs_correction`** - Validation failures found, user must correct
- **`incomplete`** - Missing required fields, user must provide data

## Usage in Orchestration Agent

```python
from app.agents.loan_workflow.loan_application_validator import run_triage_validation
import json

async def process_loan_application(self, extracted_data, thread_id):
    """Process loan application with Triage validation."""
    
    # Run Triage validation
    validation_result = await run_triage_validation(
        self.triage_agent, 
        {"extracted_data": extracted_data}
    )
    
    # Check validation status
    if validation_result['overall_status'] == 'needs_correction':
        # Return discrepancies to user
        discrepancies = validation_result['discrepancies']
        notification = validation_result['user_notification']
        return self._format_correction_request(discrepancies, notification)
    
    if validation_result['overall_status'] == 'incomplete':
        # Request missing information
        missing = validation_result['validation_result']['level3_completeness']['missing_fields']
        return self._request_missing_fields(missing)
    
    # Validation passed - continue to Decision Maker
    consolidated_data = validation_result['consolidated_data']
    return await self.decision_maker.run(consolidated_data)
```

## Testing

Run the test suite:

```bash
cd src/backend
python -m app.agents.loan_workflow.test_triage_agent
```

The test suite covers:
1. ✅ Helper function tests (name matching, field validation)
2. ✅ Cross-document validation (matching and mismatched scenarios)
3. ✅ Completeness validation (complete and incomplete data)
4. ✅ Full AI-powered Triage Agent (end-to-end validation)

## Error Handling

The Triage Agent includes comprehensive error handling:

```python
try:
    result = await run_triage_validation(triage_agent, extracted_data)
except json.JSONDecodeError as e:
    # Agent response was not valid JSON
    logger.error(f"Invalid JSON from Triage Agent: {e}")
except ValueError as e:
    # Validation error
    logger.error(f"Validation error: {e}")
except Exception as e:
    # General error
    logger.error(f"Error in triage validation: {e}")
```

## Integration Points

### Current Integration
- ✅ Receives extracted data from **Document Extractor Agent**
- ✅ Returns validation result to **Orchestration Agent**
- ✅ Uses **AzureOpenAIChatClient** for AI-powered validation

### Future Integration (Phase 7)
- 🔄 **Cosmos DB Query Tool** for Level 2 validation
- 🔄 Query historical applicant data by studentNumber
- 🔄 Compare with previous applications and account history

## Configuration

The Triage Agent is configured in `container_azure_chat.py`:

```python
from app.agents.loan_workflow.loan_application_validator import TriageAgentFactory

# Triage Agent (ChatAgent for validation)
triage_agent = providers.Singleton(
    lambda: TriageAgentFactory.create_triage_agent(_azure_chat_client())
)

# Pass to Orchestration Agent
orchestration_agent = providers.Factory(
    OrchestrationAgent,
    ...,
    triage_agent=triage_agent
)
```

## Best Practices

1. **Always validate before decision making** - Never skip Triage validation
2. **Store validation results** - Keep audit trail of validation attempts
3. **Clear user feedback** - Provide specific correction instructions
4. **Handle corrections gracefully** - Allow re-upload and re-validation
5. **Log all validations** - Track validation failures for analysis

## Next Steps

- [ ] Phase 7: Implement Cosmos DB Query Tool for Level 2 validation
- [ ] Phase 6: Add user correction workflow in Orchestration Agent
- [ ] Phase 4: Integrate into Sequential Pipeline (Doc Extractor → Triage → Decision Maker)

## See Also

- [Document Extractor Agent](./doc_extractor_agent.py) - Provides input data
- [Decision Maker Agent](./decision_maker_agent.py) - Consumes validated data (Phase 3)
- [Orchestration Agent](./orchestration_agent.py) - Coordinates the pipeline
