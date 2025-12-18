"""Pydantic models for loan application validation.

These models define the structured output format for the Triage Agent's
three-level validation process:
- Level 1: Cross-document validation (Loan Application vs Bank Statement)
- Level 2: Cosmos DB validation (if applicant exists)
- Level 3: Completeness check (required fields for MCP)

WHY PYDANTIC MODELS:
- Eliminates JSON parsing errors (no trailing commas, wrong types, malformed syntax)
- Prevents AI hallucinations (e.g., "Metro Federal" != "Metro Federal" false mismatches)
- Enforces strict typing at API level via response_format parameter
- Auto-validates responses before returning to application code
- Reduces prompt size by ~260 lines (no need for JSON format instructions)

USAGE: Pass ValidationResponse to agent.run(response_format=ValidationResponse)
Azure OpenAI API (2024-08-01-preview+) enforces schema and returns valid Pydantic object
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class FieldValidation(BaseModel):
    """Validation result for a single field comparison.
    
    Used for cross-document validation (Level 1) to compare loan application
    and bank statement values. Status must be 'pass' or 'fail' (Literal type).
    """
    status: Literal["pass", "fail"] = Field(
        description="Validation status: 'pass' if values match, 'fail' if they don't"
    )
    loan_app_value: str = Field(
        description="Value from the loan application document"
    )
    bank_stmt_value: str = Field(
        description="Value from the bank statement document"
    )
    message: str = Field(
        description="Human-readable explanation of the validation result"
    )


class CosmosDBValidation(BaseModel):
    """Validation result for Cosmos DB checks."""
    applicant_exists: bool = Field(
        description="Whether the applicant was found in Cosmos DB"
    )
    data_consistency: Optional[Literal["consistent", "inconsistent"]] = Field(
        default=None,
        description="Whether extracted data matches Cosmos DB records"
    )
    message: str = Field(
        description="Details about the Cosmos DB validation"
    )


class CompletenessCheck(BaseModel):
    """Validation result for required fields completeness."""
    all_required_fields_present: bool = Field(
        description="Whether all required fields for MCP are present"
    )
    missing_fields: List[str] = Field(
        default_factory=list,
        description="List of missing required field names"
    )
    message: str = Field(
        description="Summary of completeness check"
    )


class ValidationResponse(BaseModel):
    """Complete validation response with all three levels of validation."""
    
    # Level 1: Cross-document validation
    bank_match: FieldValidation = Field(
        description="Bank name validation between loan app and bank statement"
    )
    account_number_match: FieldValidation = Field(
        description="Account number validation between loan app and bank statement"
    )
    account_holder_match: FieldValidation = Field(
        description="Account holder name validation between loan app and bank statement"
    )
    
    # Level 2: Cosmos DB validation
    cosmos_db_validation: CosmosDBValidation = Field(
        description="Results from Cosmos DB applicant lookup"
    )
    
    # Level 3: Completeness check
    completeness_check: CompletenessCheck = Field(
        description="Check for all required fields needed by MCP"
    )
    
    # Overall status (CRITICAL: Only these 3 values allowed via Literal type)
    overall_status: Literal["PASS", "CONDITIONAL_PASS", "FAIL"] = Field(
        description="Overall validation result: PASS (all validations passed), CONDITIONAL_PASS (minor issues), FAIL (critical issues)"
    )
    summary: str = Field(
        description="Executive summary of the validation results"
    )
    
    # Note: Legacy status values 'approved', 'needs_correction', 'incomplete' are NO LONGER VALID
    # Orchestrator uses is_validation_passed() and is_validation_failed() utilities to check status
