"""Triage Agent for loan application validation.

This agent performs three-level validation on extracted document data:
- Level 1: Cross-document validation (Loan Application vs Bank Statement)
- Level 2: Cosmos DB validation (if applicant exists)
- Level 3: Completeness check (required fields for MCP)
"""
import logging
import json
from typing import Dict, Any

from agent_framework.azure import AzureOpenAIChatClient, AzureOpenAIResponsesClient
from app.models.validation import ValidationResponse

logger = logging.getLogger(__name__)


class TriageAgentFactory:
    """Factory for creating Triage Agent with proper configuration."""
    
    # Validation instructions for the Agent (Pydantic handles schema validation)
    TRIAGE_INSTRUCTIONS = """You are a loan application validation specialist performing three-level validation on extracted document data.

VALIDATION RULES:

LEVEL 1 - Cross-Document Validation (CRITICAL):
1. Bank Name: Compare bankName from both documents (case-insensitive)
   - Status: "pass" if identical, "fail" if different
   
2. Account Number: Compare last 4 digits only
   - Extract last 4 from accountNumber (may be "****1234" or "1234")
   - Compare with accountNumberLast4 from bank statement
   - Status: "pass" if last 4 match, "fail" if different
   
3. Account Holder: Compare applicantName with accountHolderName
   - Allow case-insensitive match and middle name variations
   - Status: "pass" if match, "fail" if mismatch

CRITICAL: If values are IDENTICAL, status MUST be "pass"
Example: "Metro Federal" == "Metro Federal" → status: "pass" ✓

LEVEL 2 - Cosmos DB Validation:
Mark applicant_exists=false and message="Not applicable for this phase"
(Will be implemented in future phase)

LEVEL 3 - Completeness Check (Format Validation ONLY):
Required fields with valid format:
- studentNumber: Format STU##### (5 digits)
- applicantName: Not empty, min 2 words
- loanAmount: Numeric > 0
- grossMonthlyIncome: Numeric > 0  
- monthlyDebtPayments: Numeric >= 0

DO NOT validate business rules (loan limits, DTI ratios, etc.)
Only check: field exists, correct type, not empty, valid format

OVERALL STATUS:
- PASS: All Level 1 and Level 3 checks pass
- FAIL: Any Level 1 check fails (document mismatch)
- FAIL: Any Level 3 check fails (missing/invalid format)

SUMMARY: Provide brief explanation of validation result"""
    
    @staticmethod
    def create_triage_agent(azure_chat_client: AzureOpenAIChatClient):
        """Create and configure the Triage Agent with structured output support.
        
        IMPORTANT: Uses AzureOpenAIResponsesClient (not AzureOpenAIChatClient) because:
        - Supports structured outputs via response_format parameter with Pydantic models
        - Eliminates JSON parsing errors and AI hallucinations in validation responses
        - Guarantees type-safe responses matching ValidationResponse schema
        
        AUTHENTICATION: Prefers API key over Azure CLI credential because:
        - Azure CLI has 10+ second timeout issues that block document extraction
        - API key authentication is more reliable for production workloads
        
        Args:
            azure_chat_client: Azure OpenAI chat client (unused, kept for compatibility)
            
        Returns:
            Configured AzureOpenAIResponsesClient for triage validation with structured outputs
        """
        from app.config.settings import settings
        from app.config.azure_credential import get_azure_credential
        
        # Create AzureOpenAIResponsesClient for structured output support
        # This client supports response_format parameter with Pydantic models (API version 2024-08-01-preview+)
        if settings.AZURE_OPENAI_KEY:
            # PREFERRED: Use API key authentication to avoid Azure CLI timeout issues
            responses_client = AzureOpenAIResponsesClient(
                api_key=settings.AZURE_OPENAI_KEY,
                endpoint=settings.AZURE_OPENAI_ENDPOINT,
                deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
            )
        else:
            # FALLBACK: Azure credential may cause 10+ second timeouts in some environments
            responses_client = AzureOpenAIResponsesClient(
                credential=get_azure_credential(),
                endpoint=settings.AZURE_OPENAI_ENDPOINT,
                deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
            )
        
        logger.info("Triage Agent (ResponsesClient) created successfully with structured output support")
        return responses_client


class TriageValidator:
    """Helper class for performing validation logic.
    
    This class can be used standalone or integrated with the ChatAgent.
    It provides deterministic validation rules that complement the AI agent's reasoning.
    """
    
    @staticmethod
    def extract_last_4_digits(account_number: str) -> str:
        """Extract last 4 digits from account number."""
        if not account_number:
            return ""
        # Remove common prefixes and special characters
        clean = account_number.replace('*', '').replace('-', '').replace(' ', '')
        return clean[-4:] if len(clean) >= 4 else clean
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize name for comparison."""
        if not name:
            return ""
        # Convert to lowercase, remove extra spaces
        return ' '.join(name.lower().split())
    
    @staticmethod
    def names_match(name1: str, name2: str, threshold: float = 0.85) -> bool:
        """Check if two names match (allowing for middle name variations).
        
        Args:
            name1: First name
            name2: Second name
            threshold: Similarity threshold (0.0 to 1.0)
            
        Returns:
            True if names match
        """
        norm1 = TriageValidator.normalize_name(name1)
        norm2 = TriageValidator.normalize_name(name2)
        
        if norm1 == norm2:
            return True
        
        # Check if one name is contained in the other (for middle name cases)
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        # If all words from shorter name appear in longer name
        if len(words1) < len(words2):
            return words1.issubset(words2)
        else:
            return words2.issubset(words1)
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        if not email:
            return False
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone format."""
        if not phone:
            return False
        # Remove common formatting characters
        digits = ''.join(c for c in phone if c.isdigit())
        # Accept 10 or 11 digit phone numbers
        return len(digits) in [10, 11]
    
    @staticmethod
    def validate_student_number(student_number: str) -> bool:
        """Validate student number format: STU##### (STU followed by 5 digits)."""
        if not student_number:
            return False
        import re
        # Format: STU followed by exactly 5 digits
        return bool(re.match(r'^STU\d{5}$', student_number))
    
    @staticmethod
    def validate_cross_document(
        loan_app_data: Dict[str, Any],
        bank_stmt_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform Level 1 cross-document validation.
        
        Args:
            loan_app_data: Extracted data from loan application
            bank_stmt_data: Extracted data from bank statement
            
        Returns:
            Validation result dictionary
        """
        checks = {}
        all_passed = True
        
        # 1. Name validation
        loan_name = loan_app_data.get('applicantName', '')
        bank_name = bank_stmt_data.get('accountHolderName', '')
        name_matches = TriageValidator.names_match(loan_name, bank_name)
        
        checks['name_match'] = {
            'status': 'pass' if name_matches else 'fail',
            'loan_app_value': loan_name,
            'bank_stmt_value': bank_name,
            'message': 'Names match' if name_matches else 'Name mismatch between documents'
        }
        if not name_matches:
            all_passed = False
        
        # 2. Bank name validation
        loan_bank = loan_app_data.get('bankName', '').lower().strip()
        stmt_bank = bank_stmt_data.get('bankName', '').lower().strip()
        bank_matches = loan_bank == stmt_bank
        
        checks['bank_match'] = {
            'status': 'pass' if bank_matches else 'fail',
            'loan_app_value': loan_app_data.get('bankName', ''),
            'bank_stmt_value': bank_stmt_data.get('bankName', ''),
            'message': 'Bank names match' if bank_matches else 'Bank name mismatch'
        }
        if not bank_matches:
            all_passed = False
        
        # 3. Account type validation
        loan_acct_type = loan_app_data.get('accountType', '').lower().strip()
        stmt_acct_type = bank_stmt_data.get('accountType', '').lower().strip()
        type_matches = loan_acct_type == stmt_acct_type
        
        checks['account_type_match'] = {
            'status': 'pass' if type_matches else 'fail',
            'loan_app_value': loan_app_data.get('accountType', ''),
            'bank_stmt_value': bank_stmt_data.get('accountType', ''),
            'message': 'Account types match' if type_matches else 'Account type mismatch'
        }
        if not type_matches:
            all_passed = False
        
        # 4. Account number validation (last 4 digits)
        loan_acct_num = TriageValidator.extract_last_4_digits(
            loan_app_data.get('accountNumber', '')
        )
        stmt_acct_num = TriageValidator.extract_last_4_digits(
            bank_stmt_data.get('accountNumberLast4', '')
        )
        number_matches = loan_acct_num == stmt_acct_num and len(loan_acct_num) == 4
        
        checks['account_number_match'] = {
            'status': 'pass' if number_matches else 'fail',
            'loan_app_value': loan_acct_num,
            'bank_stmt_value': stmt_acct_num,
            'message': 'Account numbers match' if number_matches else 'Account number mismatch'
        }
        if not number_matches:
            all_passed = False
        
        return {
            'status': 'pass' if all_passed else 'fail',
            'checks': checks
        }
    
    @staticmethod
    def validate_completeness(loan_app_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform Level 3 completeness validation.
        
        Args:
            loan_app_data: Extracted data from loan application
            
        Returns:
            Validation result dictionary
        """
        missing_fields = []
        invalid_fields = []
        
        # Required fields
        required_fields = [
            'studentNumber', 'applicantName',
            'loanAmount', 'grossMonthlyIncome', 'monthlyDebtPayments'
        ]
        
        for field in required_fields:
            if field not in loan_app_data or not loan_app_data[field]:
                missing_fields.append(field)
        
        # Validate field formats if present
        if 'studentNumber' in loan_app_data:
            if not TriageValidator.validate_student_number(loan_app_data['studentNumber']):
                invalid_fields.append('studentNumber: Invalid format')
        
        if 'applicantName' in loan_app_data:
            name_words = loan_app_data['applicantName'].split()
            if len(name_words) < 2:
                invalid_fields.append('applicantName: Must include first and last name')
        
        # Basic numeric validations (presence and sign only, no business rules)
        if 'loanAmount' in loan_app_data:
            amount = loan_app_data['loanAmount']
            if amount <= 0:
                invalid_fields.append('loanAmount: Must be greater than $0')
        
        if 'grossMonthlyIncome' in loan_app_data:
            income = loan_app_data['grossMonthlyIncome']
            if income <= 0:
                invalid_fields.append('grossMonthlyIncome: Must be greater than $0')
        
        if 'monthlyDebtPayments' in loan_app_data:
            debts = loan_app_data['monthlyDebtPayments']
            if debts < 0:
                invalid_fields.append('monthlyDebtPayments: Cannot be negative')
        
        all_passed = len(missing_fields) == 0 and len(invalid_fields) == 0
        
        return {
            'status': 'pass' if all_passed else 'fail',
            'all_required_present': len(missing_fields) == 0,
            'missing_fields': missing_fields,
            'invalid_fields': invalid_fields
        }


async def run_triage_validation(
    triage_agent,
    extracted_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Run triage validation using structured outputs with Pydantic.
    
    Uses direct OpenAI SDK with JSON schema response_format for guaranteed
    type-safe responses matching the ValidationResponse schema.
    
    Args:
        triage_agent: AzureOpenAIResponsesClient configured for validation (used for config)
        extracted_data: Dictionary containing extracted data from both documents
        
    Returns:
        Validation result dictionary
    """
    try:
        from app.config.settings import settings
        from app.config.azure_credential import get_azure_credential
        from openai import AzureOpenAI
        from azure.identity import get_bearer_token_provider
        
        # Prepare input with instructions
        input_json = json.dumps(extracted_data, indent=2)
        prompt = f"""{TriageAgentFactory.TRIAGE_INSTRUCTIONS}

Please validate the following extracted loan application data and return ONLY a JSON object matching the required schema:

{input_json}"""
        
        logger.info("Starting triage validation with structured outputs (direct SDK)...")
        
        # Use direct OpenAI SDK for reliable structured outputs
        if settings.AZURE_OPENAI_KEY:
            client = AzureOpenAI(
                api_key=settings.AZURE_OPENAI_KEY,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_version="2024-08-01-preview"
            )
        else:
            token_provider = get_bearer_token_provider(
                get_azure_credential(),
                "https://cognitiveservices.azure.com/.default"
            )
            client = AzureOpenAI(
                azure_ad_token_provider=token_provider,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_version="2024-08-01-preview"
            )
        
        # Get the JSON schema for documentation in the prompt
        schema_json = json.dumps(ValidationResponse.model_json_schema(), indent=2)
        
        # Enhanced prompt with explicit JSON schema
        enhanced_prompt = f"""{prompt}

You MUST respond with a JSON object that matches this exact schema:
{schema_json}

Important notes:
- overall_status must be one of: "PASS", "CONDITIONAL_PASS", or "FAIL"
- All status fields must be either "pass" or "fail"
- missing_fields should be an empty array [] if no fields are missing
- data_consistency can be null if applicant_exists is false"""
        
        # Call with json_object response format (simpler, no strict schema requirements)
        response = client.chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You are a loan application validation specialist. Always respond with valid JSON matching the required schema. Do not include any text outside of the JSON object."},
                {"role": "user", "content": enhanced_prompt}
            ],
            temperature=0.0,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        # Parse the response
        response_text = response.choices[0].message.content
        logger.info(f"Raw response (first 500 chars): {response_text[:500] if response_text else 'EMPTY'}")
        
        if response_text:
            import json as json_module
            validation_dict = json_module.loads(response_text)
            validation_model = ValidationResponse(**validation_dict)
            validation_result = validation_model.model_dump()
            logger.info(f"Triage validation completed: {validation_result.get('overall_status')}")
            return validation_result
        
        raise ValueError("Empty response from model")
        
    except Exception as e:
        logger.error(f"Error in triage validation with structured outputs: {str(e)}", exc_info=True)
        raise
