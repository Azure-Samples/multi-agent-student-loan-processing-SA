from typing import Any, AsyncGenerator, Dict
from enum import Enum
from agent_framework import WorkflowBuilder, Workflow, InMemoryCheckpointStorage, Case, Default, ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from uuid import uuid4
import logging
from datetime import datetime

from .loan_document_extractor import DocumentExtractorAgent
from .extraction_result_formatter import ResponseFormatterExecutor
from .user_intent_classifier import IntentClassifierExecutor, IntentType
from .error_handler import ErrorHandlerExecutor
from .loan_application_instructions_provider import LoanApplicationExecutor
from .loan_application_validator import run_triage_validation
from .loan_approval_decision_maker import DecisionMakerAgent, run_decision_maker
from app.utils.status_helpers import is_validation_passed, is_validation_failed

logger = logging.getLogger(__name__)

class ThreadState(Enum):
    """Enum for tracking loan application process states"""
    INITIAL = "initial"  # New conversation
    DOCUMENTS_UPLOADED = "documents_uploaded"  # Documents have been uploaded
    EXTRACTING = "extracting"  # Extracting data from documents
    VALIDATING = "validating"  # Running triage validation
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # Validation passed, waiting for user confirmation
    EVALUATING = "evaluating"  # Running decision maker evaluation
    COMPLETED = "completed"  # Loan decision provided
    ERROR = "error"  # Error state


class OrchestrationAgent:
    """Orchestration agent for student loan processing.
    
    This agent coordinates multiple workflows:
    - Document processing workflow (doc_extractor -> response_formatter)
    - Intent classification for routing
    - General chat responses
    
    Note: Uses WorkflowBuilder (not SequentialBuilder) because our executors
    work with structured data payloads, not conversation context. SequentialBuilder
    is designed for agent workflows with list[ChatMessage] threading.
    """
    
    # Class-level dictionaries to store state by thread_id
    # This persists across OrchestrationAgent instances (which are created per-request)
    _validation_results_by_thread: Dict[str, Dict[str, Any]] = {}
    _thread_states: Dict[str, Dict[str, Any]] = {}  # Stores {thread_id: {state, timestamp, message}}
   
    instructions = """
      You are a helpful and professional student loan advisor assistant for a banking institution.
      Your role is to assist students and families with STUDENT LOAN inquiries ONLY.
      
      🚨 CRITICAL SCOPE RESTRICTION:
      - You ONLY handle STUDENT LOANS (for education/tuition purposes)
      - You do NOT provide assistance for:
        • Home mortgages or mortgage loans
        • Auto loans or car financing
        • Personal loans
        • Business loans
        • Credit cards
        • Any other non-student loan financial products
      
      If a user asks about non-student loan topics, politely decline with:
      "I apologize, but I specialize exclusively in student loans for educational purposes. For questions about [topic], please contact our general banking department or visit our main website for assistance with other loan products."
      
      You specialize in:
      - Student loan information and product options (federal and private student loans only)
      - Student loan eligibility requirements and criteria
      - Interest rates and repayment options for student loans
      - Student loan application procedures and required documentation
      - FAFSA (Free Application for Federal Student Aid) guidance
      - Processing student loan application documents
      
      IMPORTANT STUDENT LOAN DOCUMENT PROCESSING WORKFLOW:
      When a user expresses intent to apply for a student loan (phrases like "I want to apply for a student loan", 
      "I need help with student loans", "How do I get financial aid", etc.), you should:
      
      1. Acknowledge their student loan intent
      2. Explain the required student loan documents (loan application and bank statement)
      3. Ask them to upload the necessary documents using the upload button
      4. Use the process_loan_documents tool when they confirm they want to upload documents
      
      CORE REQUIRED DOCUMENTS (Phase 1):
      - **Student Loan Application Form** (completed and signed)
      - **Bank Statement** (most recent month for financial verification)
      
      NOTE: Additional documents will be supported in future phases.
      
      FORMATTING GUIDELINES:
      “When responding, write in a structured, professional, and visually clear format.
        Use short sections with clear headings, bullet points, and tables when appropriate.
        Highlight key ideas with **bold text** or emojis for readability.
        Include concise explanations and examples for technical concepts.

        The tone should be:
        - Confident and explanatory (like a senior consultant’s report)
        - Easy to read at a glance
        - Well-organized with Markdown styling
        When applicable, format the response with:
        - Headings (##) for major sections
        - Bullets (–) for lists
        - Tables for comparisons
        - Callouts (📌 / ⚙️ / 🧠 / 🚀) to emphasize key ideas.
        Always end with a short Summary or Action Recommendation section.”
    """
    name = "StudentLoanAdvisorAgent"
    description = "A student loan advisor assistant that helps students and families with student loan applications and inquiries."

    def __init__(self, 
                 azure_chat_client: AzureOpenAIChatClient,
                 doc_extractor: DocumentExtractorAgent,
                 response_formatter: ResponseFormatterExecutor,
                 intent_classifier: IntentClassifierExecutor,
                 error_handler: ErrorHandlerExecutor,
                 checkpoint_storage: InMemoryCheckpointStorage,
                 loan_application: 'LoanApplicationExecutor',
                 triage_agent: Any = None,
        decision_maker_agent: DecisionMakerAgent = None,
                ):
      self.azure_chat_client = azure_chat_client
      self.doc_extractor = doc_extractor
      self.response_formatter = response_formatter
      self.intent_classifier = intent_classifier
      self.error_handler = error_handler
      self.checkpoint_storage = checkpoint_storage
      self.loan_application = loan_application
      self.triage_agent = triage_agent
      self.decision_maker_agent = decision_maker_agent
      
      # Create ChatAgent for general Q&A conversations using Agent Framework pattern
      self.chat_agent = ChatAgent(
          chat_client=azure_chat_client,
          name=self.name,
          description=self.description,
          instructions=self.instructions
      )
      
      # Create ChatResponseExecutor that wraps the ChatAgent
      # Lazy import to avoid circular dependency
      from app.agents.loan_workflow.general_chat_handler import ChatResponseExecutor
      self.chat_response = ChatResponseExecutor(
          chat_agent=self.chat_agent,
          id="chat_response"
      )
    
    @classmethod
    def update_thread_state(cls, thread_id: str, state: ThreadState, message: str = ""):
        """Update the state for a given thread"""
        if thread_id:
            cls._thread_states[thread_id] = {
                "state": state.value,
                "timestamp": datetime.utcnow().isoformat(),
                "message": message
            }
            logger.info(f"Thread {thread_id} state updated to: {state.value}")
    
    @classmethod
    def get_thread_state(cls, thread_id: str) -> Dict[str, Any]:
        """Get the current state for a given thread"""
        return cls._thread_states.get(thread_id, {
            "state": ThreadState.INITIAL.value,
            "timestamp": datetime.utcnow().isoformat(),
            "message": ""
        })
    
    def get_thread_status_message(self, thread_id: str) -> str:
        """Get a formatted status message for the current thread state"""
        state_info = OrchestrationAgent.get_thread_state(thread_id)
        state = state_info.get('state', 'initial')
        message = state_info.get('message', '')
        
        status_icons = {
            ThreadState.INITIAL.value: "💬",
            ThreadState.DOCUMENTS_UPLOADED.value: "📄",
            ThreadState.EXTRACTING.value: "🔍",
            ThreadState.VALIDATING.value: "✓",
            ThreadState.AWAITING_CONFIRMATION.value: "⏳",
            ThreadState.EVALUATING.value: "⚙️",
            ThreadState.COMPLETED.value: "✅",
            ThreadState.ERROR.value: "❌"
        }
        
        status_labels = {
            ThreadState.INITIAL.value: "Ready",
            ThreadState.DOCUMENTS_UPLOADED.value: "Documents Uploaded",
            ThreadState.EXTRACTING.value: "Extracting Data",
            ThreadState.VALIDATING.value: "Validating",
            ThreadState.AWAITING_CONFIRMATION.value: "Awaiting Confirmation",
            ThreadState.EVALUATING.value: "Evaluating Application",
            ThreadState.COMPLETED.value: "Completed",
            ThreadState.ERROR.value: "Error"
        }
        
        icon = status_icons.get(state, "💬")
        label = status_labels.get(state, "Unknown")
        
        return f"{icon} **Status**: {label}" + (f" - {message}" if message else "")
    
    def get_loan_application_status(self, thread_id: str) -> Dict[str, Any]:
        """Get structured loan application status for UI display.
        
        Maps internal ThreadState to UI stages:
        - Application Initiated: INITIAL, DOCUMENTS_UPLOADED, EXTRACTING
        - Identity Verification: VALIDATING, AWAITING_CONFIRMATION
        - Financial Assessment: EVALUATING
        - Underwriting Review: (future - not yet implemented)
        - Approval & Disbursement: COMPLETED, ERROR
        
        Returns:
            Dict with applicationId, currentStage, stages list with status/description
        """
        state_info = OrchestrationAgent.get_thread_state(thread_id)
        current_state = state_info.get('state', 'initial')
        
        # Define the stages for the UI
        stages = [
            {
                "id": "application_initiated",
                "title": "Application Initiated",
                "description": "Documents received",
                "status": "pending",  # pending, active, completed
                "icon": "document"
            },
            {
                "id": "identity_verification",
                "title": "Identity Verification",
                "description": "Document validation",
                "status": "pending",
                "icon": "shield-check"
            },
            {
                "id": "financial_assessment",
                "title": "Financial Assessment",
                "description": "Credit & income review",
                "status": "pending",
                "icon": "currency-dollar"
            },
            {
                "id": "underwriting_review",
                "title": "Underwriting Review",
                "description": "Risk evaluation",
                "status": "pending",
                "icon": "clipboard-check"
            },
            {
                "id": "approval_disbursement",
                "title": "Approval & Disbursement",
                "description": "Final decision",
                "status": "pending",
                "icon": "check-circle"
            }
        ]
        
        # Map current state to stage status
        if current_state in [ThreadState.DOCUMENTS_UPLOADED.value, ThreadState.EXTRACTING.value]:
            stages[0]["status"] = "completed"
            stages[1]["status"] = "active"
            current_stage = "identity_verification"
            
        elif current_state in [ThreadState.VALIDATING.value, ThreadState.AWAITING_CONFIRMATION.value]:
            stages[0]["status"] = "completed"
            stages[1]["status"] = "active"
            current_stage = "identity_verification"
            
        elif current_state == ThreadState.EVALUATING.value:
            stages[0]["status"] = "completed"
            stages[1]["status"] = "completed"
            stages[2]["status"] = "active"
            current_stage = "financial_assessment"
            
        elif current_state == ThreadState.COMPLETED.value:
            stages[0]["status"] = "completed"
            stages[1]["status"] = "completed"
            stages[2]["status"] = "completed"
            stages[3]["status"] = "completed"
            stages[4]["status"] = "completed"
            current_stage = "approval_disbursement"
            
        elif current_state == ThreadState.ERROR.value:
            # Mark current stage as error
            stages[0]["status"] = "completed"
            stages[1]["status"] = "error"
            current_stage = "identity_verification"
            
        else:  # INITIAL
            stages[0]["status"] = "active"
            current_stage = "application_initiated"
        
        return {
            "applicationId": f"#LA-2025-{thread_id[:8].upper()}",
            "currentStage": current_stage,
            "currentState": current_state,
            "timestamp": state_info.get('timestamp', ''),
            "message": state_info.get('message', ''),
            "stages": stages,
            "note": "Processing time is typically 3-5 business days. We'll notify you of any updates."
        }
      
    def _build_document_workflow(self) -> Workflow:
        """Build the document processing workflow using Agent Framework patterns.
        
        Returns:
            Workflow configured with doc_extractor -> formatter pipeline and checkpointing
        """
        # Build the workflow using fluent API:
        # 1) add_edge(from_node, to_node) defines sequential edge
        # 2) set_start_executor(node) declares the entry point
        # 3) with_checkpointing(storage) enables state persistence
        # 4) build() finalizes and returns an immutable Workflow object
        workflow = (
            WorkflowBuilder()
            .add_edge(self.doc_extractor, self.response_formatter)
            .set_start_executor(self.doc_extractor)
            .with_checkpointing(self.checkpoint_storage)
            .build()
        )
        
        return workflow
    
    async def _run_triage_validation(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run Triage Agent validation on extracted data.
        
        Args:
            extracted_data: Dict containing extracted document data
            
        Returns:
            Dict with validation_result, consolidated_data, overall_status, discrepancies
        """
        if not self.triage_agent:
            logger.warning("Triage Agent not configured, skipping validation")
            return {
                "overall_status": "approved",
                "validation_result": {"level1_cross_document": {"status": "skipped"}},
                "consolidated_data": extracted_data,
                "discrepancies": [],
                "user_notification": None
            }
        
        try:
            # Prepare input for triage validation
            triage_input = {"extracted_data": extracted_data}
            
            # Run validation
            validation_result = await run_triage_validation(self.triage_agent, triage_input)
            
            logger.info(f"Triage validation completed with status: {validation_result.get('overall_status')}")
            return validation_result
            
        except Exception as e:
            logger.error(f"Error in triage validation: {str(e)}", exc_info=True)
            return {
                "overall_status": "error",
                "validation_result": {},
                "consolidated_data": extracted_data,
                "discrepancies": [{"field": "validation", "issue": f"Validation error: {str(e)}"}],
                "user_notification": f"Validation encountered an error: {str(e)}"
            }
    
    async def _run_decision_maker(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run Decision Maker Agent to evaluate loan application.
        
        Args:
            validated_data: Consolidated validated data from Triage Agent
            
        Returns:
            Loan decision result from Decision Maker Agent
        """
        if not self.decision_maker_agent:
            logger.warning("Decision Maker Agent not configured, skipping evaluation")
            return {
                "status": "error",
                "reason": "Loan decision service not available",
                "error": "Decision Maker Agent not configured"
            }
        
        try:
            logger.info("Running Decision Maker Agent for loan evaluation...")
            decision_result = await run_decision_maker(self.decision_maker_agent, validated_data)
            logger.info(f"Decision Maker completed with status: {decision_result.get('status')}")
            return decision_result
            
        except Exception as e:
            logger.error(f"Error in Decision Maker: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "reason": f"Failed to evaluate loan application: {str(e)}",
                "error": str(e)
            }
    
    def get_thread_status_message(self, thread_id: str) -> str:
        """Get a formatted status message for the current thread state"""
        state_info = OrchestrationAgent.get_thread_state(thread_id)
        state = state_info.get('state', 'initial')
        message = state_info.get('message', '')
        
        status_icons = {
            ThreadState.INITIAL.value: "💬",
            ThreadState.DOCUMENTS_UPLOADED.value: "📄",
            ThreadState.EXTRACTING.value: "🔍",
            ThreadState.VALIDATING.value: "✓",
            ThreadState.AWAITING_CONFIRMATION.value: "⏳",
            ThreadState.EVALUATING.value: "⚙️",
            ThreadState.COMPLETED.value: "✅",
            ThreadState.ERROR.value: "❌"
        }
        
        status_labels = {
            ThreadState.INITIAL.value: "Ready",
            ThreadState.DOCUMENTS_UPLOADED.value: "Documents Uploaded",
            ThreadState.EXTRACTING.value: "Extracting Data",
            ThreadState.VALIDATING.value: "Validating",
            ThreadState.AWAITING_CONFIRMATION.value: "Awaiting Confirmation",
            ThreadState.EVALUATING.value: "Evaluating Application",
            ThreadState.COMPLETED.value: "Completed",
            ThreadState.ERROR.value: "Error"
        }
        
        icon = status_icons.get(state, "💬")
        label = status_labels.get(state, "Unknown")
        
        return f"{icon} **Status**: {label}" + (f" - {message}" if message else "")
    
    def _format_decision_result(self, decision_result: Dict[str, Any]) -> str:
        """Format decision result for user display.
        
        Args:
            decision_result: Result from Decision Maker Agent
            
        Returns:
            Formatted string message for user
        """
        status = decision_result.get('status', 'unknown')
        
        if status == 'error':
            # Error occurred during evaluation
            msg = ["❌ **Loan Evaluation Error**\n"]
            msg.append(f"**Error**: {decision_result.get('reason', 'Unknown error occurred')}\n")
            msg.append("\n**📌 Next Steps:**")
            msg.append("Please try again or contact support if the issue persists.")
            return "\n".join(msg)
        
        elif status == 'APPROVED':
            # Loan approved - show APR and details
            apr_rate = decision_result.get('aprRate', 0)
            loan_amount = decision_result.get('loanAmount', 0)
            dti = decision_result.get('dti', 0)
            reason = decision_result.get('reason', '')
            loan_app_id = decision_result.get('loanApplicationId', 'N/A')
            applicant_name = decision_result.get('applicantName', '')
            
            msg = ["🎉 **Loan Application APPROVED!**\n"]
            msg.append("📋 **Decision Status: APPROVED**\n")
            msg.append(f"Congratulations {applicant_name}! Your student loan application has been approved.\n")
            
            msg.append("**💰 Loan Details:**")
            msg.append(f"  • **Loan Amount:** ${loan_amount:,.2f}")
            msg.append(f"  • **APR Rate:** {apr_rate}%")
            msg.append(f"  • **Application ID:** {loan_app_id}")
            msg.append(f"  • **Your DTI Ratio:** {dti:.1f}%\n")
            
            msg.append(f"**📝 Decision Reason:**")
            msg.append(f"{reason}\n")
            
            msg.append("**🚀 Next Steps:**")
            msg.append("1. Review the loan terms and APR rate")
            msg.append("2. Sign the loan agreement documents")
            msg.append("3. Complete identity verification")
            msg.append("4. Funds will be disbursed after final approval\n")
            
            msg.append("Would you like more information about the loan terms or repayment options?")
            
            return "\n".join(msg)
        
        elif status == 'REJECTED':
            # Loan rejected - show reason and guidance
            reason = decision_result.get('reason', '')
            dti = decision_result.get('dti', 0)
            loan_amount = decision_result.get('loanAmount', 0)
            applicant_name = decision_result.get('applicantName', '')
            
            msg = ["❌ **Loan Application Not Approved**\n"]
            msg.append("📋 **Decision Status: REJECTED**\n")
            msg.append(f"We regret to inform you that your loan application has not been approved at this time.\n")
            
            msg.append("**📊 Application Details:**")
            msg.append(f"  • **Applicant:** {applicant_name}")
            msg.append(f"  • **Requested Amount:** ${loan_amount:,.2f}")
            msg.append(f"  • **Your DTI Ratio:** {dti:.1f}%\n")
            
            msg.append(f"**❌ Reason for Rejection:**")
            msg.append(f"{reason}\n")
            
            msg.append("**💡 Recommendations:**")
            msg.append("  • Reduce your monthly debt payments")
            msg.append("  • Increase your monthly income")
            msg.append("  • Consider applying with a co-signer")
            msg.append("  • Apply for a smaller loan amount")
            msg.append("  • Reapply after improving your debt-to-income ratio\n")
            
            msg.append("**📌 Next Steps:**")
            msg.append("You may reapply once your financial situation improves.")
            msg.append("Our financial advisors are available to help you understand your options.")
            
            return "\n".join(msg)
        
        else:
            # Unknown status
            return f"⚠️ **Unknown Decision Status**\n\nReceived unexpected status: {status}\n\nPlease contact support."
    
    def _format_validation_result(self, validation_result: Dict[str, Any], extracted_data: Dict[str, Any]) -> str:
        """Format validation result for user display.
        
        Args:
            validation_result: Result from triage validation
            extracted_data: Original extracted data
            
        Returns:
            Formatted string message for user
        """
        overall_status = validation_result.get('overall_status', 'unknown')
        
        if is_validation_passed(overall_status):
            # Validation passed - show success message
            # Use consolidated data from validation_result (already flattened and stored during validation)
            # Falls back to extracting from extracted_data if not available (backward compatibility)
            consolidated = validation_result.get('consolidated_data', {})
            if not consolidated:
                # Fallback: Extract consolidated data from extracted_data (flatten nested structure)
                for file_data in extracted_data.values():
                    if isinstance(file_data, dict):
                        consolidated.update(file_data)
            
            msg = ["✅ **Documents Processed Successfully**\n"]
            msg.append("📋 **Validation Status: PASSED**\n")
            msg.append("All your data has been successfully validated and is ready for processing.\n")
            
            # Show key extracted fields
            msg.append("**📝 Validated Information:**")
            if consolidated.get('applicantName'):
                msg.append(f"  • **Applicant:** {consolidated['applicantName']}")
            if consolidated.get('studentNumber'):
                msg.append(f"  • **Student Number:** {consolidated['studentNumber']}")
            if consolidated.get('loanAmount'):
                msg.append(f"  • **Loan Amount:** ${consolidated['loanAmount']:,.2f}")
            if consolidated.get('grossMonthlyIncome'):
                msg.append(f"  • **Monthly Income:** ${consolidated['grossMonthlyIncome']:,.2f}")
            if consolidated.get('bankName'):
                msg.append(f"  • **Bank:** {consolidated['bankName']}")
            if consolidated.get('accountType'):
                msg.append(f"  • **Account Type:** {consolidated['accountType']}")
            
            msg.append("\n**🚀 Ready to Proceed**")
            msg.append("Please confirm to proceed with loan evaluation.")
            
            return "\n".join(msg)
            
        elif is_validation_failed(overall_status):
            # Validation failed - extract failure reasons from field validations
            msg = ["⚠️ **Document Validation Issues Found**\n"]
            msg.append("📋 **Validation Status: FAILED**\n")
            
            # Collect failed validations
            issues = []
            
            # Check each validation field
            bank_match = validation_result.get('bank_match', {})
            if isinstance(bank_match, dict) and bank_match.get('status') == 'fail':
                issues.append(f"**Bank Name Mismatch**: {bank_match.get('message', 'Bank names do not match')}")
            
            account_match = validation_result.get('account_number_match', {})
            if isinstance(account_match, dict) and account_match.get('status') == 'fail':
                issues.append(f"**Account Number Mismatch**: {account_match.get('message', 'Account numbers do not match')}")
            
            holder_match = validation_result.get('account_holder_match', {})
            if isinstance(holder_match, dict) and holder_match.get('status') == 'fail':
                issues.append(f"**Account Holder Mismatch**: {holder_match.get('message', 'Account holder names do not match')}")
            
            # Add summary if available
            summary = validation_result.get('summary', '')
            if summary:
                msg.append(f"_{summary}_\n")
            
            # List specific issues
            if issues:
                msg.append("**❌ Issues Found:**")
                for idx, issue in enumerate(issues, 1):
                    msg.append(f"  {idx}. {issue}")
            else:
                msg.append("**❌ Issue:** Validation checks did not pass. Please verify your documents contain matching information.")
            
            msg.append("\n**📌 Next Steps:**")
            msg.append("Please review and correct the issues above, then upload the corrected documents.")
            
            return "\n".join(msg)
        
        else:
            # Unknown status or error
            return "⚠️ **Validation Status Unknown**\n\nPlease try uploading your documents again."
    
    def create_loan_application_workflow(self) -> Workflow:
        """Factory method: Create workflow for providing loan application instructions.
        
        Returns:
            Workflow configured with loan_application executor and checkpointing
        """
        workflow = (
            WorkflowBuilder()
            .set_start_executor(self.loan_application)
            .with_checkpointing(self.checkpoint_storage)
            .build()
        )
        
        return workflow
    
    def create_intent_classification_workflow(self) -> Workflow:
        """Factory method: Create workflow for classifying user intent.
        
        Returns:
            Workflow configured with intent_classifier executor and checkpointing
        """
        workflow = (
            WorkflowBuilder()
            .set_start_executor(self.intent_classifier)
            .with_checkpointing(self.checkpoint_storage)
            .build()
        )
        
        return workflow

    async def process_loan_documents(self) -> str:
        """
        Provide student loan application document instructions using LoanApplicationExecutor.
        
        Returns:
            Formatted response with upload instructions
        """
        try:
            # Use factory method to create workflow
            workflow = self.create_loan_application_workflow()
            
            # Execute with minimal payload
            events = await workflow.run({})
            outputs = events.get_outputs()
            
            return outputs[0] if outputs else "Please upload your loan application documents."
            
        except Exception as e:
            logger.error(f"Error in process_loan_documents: {str(e)}")
            return f"Error: {str(e)}. Please try again."

    async def _classify_intent(self, message: str, has_files: bool) -> str:
        """Classify user intent using the IntentClassifierExecutor.
        
        Args:
            message: User's message
            has_files: Whether files are attached
            
        Returns:
            Intent type string
        """
        payload = {
            'message': message,
            'has_files': has_files
        }
        
        # Use factory method to create intent classification workflow
        intent_workflow = self.create_intent_classification_workflow()
        
        events = await intent_workflow.run(payload)
        outputs = events.get_outputs()
        
        return outputs[0] if outputs else IntentType.GENERAL_CHAT

    async def process_uploaded_documents(self, user_message: str, thread_id: str | None = None) -> tuple[str, str]:
        """
        Process uploaded documents using Agent Framework workflow.
        
        Args:
            user_message: User's message
            thread_id: Session thread ID
            
        Returns:
            tuple[str, str]: (formatted response, thread_id)
        """
        uploaded_files = getattr(self, '_uploaded_files', None)
        if uploaded_files:
            try:
                # Generate thread_id if not provided
                if not thread_id:
                    thread_id = str(uuid4())
                
                # Update state to EXTRACTING
                OrchestrationAgent.update_thread_state(
                    thread_id, 
                    ThreadState.EXTRACTING, 
                    "Extracting data from uploaded documents"
                )
                
                # Build the workflow
                workflow = self._build_document_workflow()
                
                # Prepare the initial payload for DocumentExtractorAgent
                payload = {
                    'files': uploaded_files,
                    'thread_id': thread_id
                }
                
                # Execute the workflow and get the final output
                # workflow.run() returns events, and get_outputs() retrieves the yielded outputs
                events = await workflow.run(payload)
                outputs = events.get_outputs()
                
                # Get the formatted extraction result
                if not outputs:
                    return "Documents processed but no output was generated."
                
                # Extract the raw data from workflow context for validation
                # The workflow stores extraction_result in context
                extraction_result = None
                if hasattr(workflow, '_last_extraction_result'):
                    extraction_result = workflow._last_extraction_result
                else:
                    # Try to extract from payload if available
                    logger.warning("Could not find extraction_result in workflow context")
                    # For now, we'll need to store this in the doc_extractor
                    # Let's get it from the doc_extractor's last result
                    if hasattr(self.doc_extractor, '_last_extraction_result'):
                        extraction_result = self.doc_extractor._last_extraction_result
                
                # Run Triage validation if we have extraction data
                if extraction_result and extraction_result.get('extracted_data'):
                    # Update state to VALIDATING
                    OrchestrationAgent.update_thread_state(
                        thread_id,
                        ThreadState.VALIDATING,
                        "Validating extracted data"
                    )
                    
                    # Flatten the structure for Triage Agent
                    # Document Extractor returns: {filename: {document_type, structured_data, ...}}
                    # Triage Agent expects: {filename: {field1, field2, ...}}
                    flattened_data = {}
                    for filename, doc_data in extraction_result['extracted_data'].items():
                        # Extract the structured_data or use doc_data directly
                        if isinstance(doc_data, dict) and 'structured_data' in doc_data:
                            flattened_data[filename] = doc_data['structured_data']
                        else:
                            flattened_data[filename] = doc_data
                    
                    validation_result = await self._run_triage_validation(flattened_data)
                    
                    # Add consolidated data to validation result
                    # Extract consolidated data from flattened_data (flatten nested structure)
                    consolidated = {}
                    for file_data in flattened_data.values():
                        if isinstance(file_data, dict):
                            consolidated.update(file_data)
                    validation_result['consolidated_data'] = consolidated
                    
                    # Store validation result in class-level dictionary by thread_id
                    # This persists across requests for the same conversation
                    if thread_id:
                        OrchestrationAgent._validation_results_by_thread[thread_id] = validation_result
                        logger.debug(f"Stored validation result for thread_id: {thread_id}")
                    
                    # Check if validation passed - return result and wait for user confirmation
                    overall_status = validation_result.get('overall_status')
                    if is_validation_passed(overall_status):
                        # Update state to AWAITING_CONFIRMATION
                        OrchestrationAgent.update_thread_state(
                            thread_id,
                            ThreadState.AWAITING_CONFIRMATION,
                            "Validation passed - awaiting user confirmation"
                        )
                        logger.info(f"Validation passed ({overall_status}) - awaiting user confirmation")
                        
                        # Return formatted validation result
                        # User will need to confirm before Decision Maker proceeds
                        return (self._format_validation_result(validation_result, flattened_data), thread_id)
                    elif is_validation_failed(overall_status):
                        # Update state to ERROR for failed validation
                        OrchestrationAgent.update_thread_state(
                            thread_id,
                            ThreadState.ERROR,
                            "Document validation failed - corrections needed"
                        )
                        logger.info(f"Validation failed ({overall_status}) - corrections required")
                        
                        # Return formatted validation result with errors
                        return (self._format_validation_result(validation_result, flattened_data), thread_id)
                    else:
                        # Unknown status (should not happen with Pydantic validation)
                        OrchestrationAgent.update_thread_state(
                            thread_id,
                            ThreadState.ERROR,
                            f"Unexpected validation status: {overall_status}"
                        )
                        logger.warning(f"Unexpected validation status received: {overall_status}")
                        
                        # Return validation result
                        return (self._format_validation_result(validation_result, flattened_data), thread_id)
                else:
                    # No extraction data - return original formatted output
                    return (outputs[0], thread_id)
                    
            except Exception as e:
                logger.error(f"Error processing documents with workflow: {str(e)}", exc_info=True)
                
                # Use error handler workflow for consistent error formatting
                error_workflow = (
                    WorkflowBuilder()
                    .set_start_executor(self.error_handler)
                    .with_checkpointing(self.checkpoint_storage)
                    .build()
                )
                
                error_payload = {
                    "error": e,
                    "context": "Document processing",
                    "user_id": "user",
                    "thread_id": thread_id
                }
                
                error_events = await error_workflow.run(error_payload)
                error_outputs = error_events.get_outputs()
                
                if error_outputs and isinstance(error_outputs[0], dict):
                    return (error_outputs[0].get("error_message", str(e)), thread_id)
                return (f"❌ **Error Processing Documents**\n\n{str(e)}\n\nPlease try again.", thread_id)
            finally:
                if hasattr(self, '_uploaded_files'):
                    delattr(self, '_uploaded_files')
        else:
            return ("No files uploaded yet. Please use the + button to attach your student loan application and bank statement.", thread_id if thread_id else str(uuid4()))

    async def processMessage(self, user_message: str , thread_id : str | None) -> tuple[str, str | None]:
        """
        Process a message and return a complete response.
        """
        # Check if files were uploaded
        if hasattr(self, '_uploaded_files') and self._uploaded_files:
            doc_response = await self.process_uploaded_documents(user_message)
            return (doc_response, thread_id)
        
        # Otherwise handle as a regular chat message
        # For now, use a simple response - this can be enhanced with Azure OpenAI chat later
        response = f"You said: {user_message}\n\nI'm your student loan advisor. How can I help you today?"
        return (response, thread_id)

    async def processMessageStream(self, user_message: str, thread_id: str | None) -> AsyncGenerator[tuple[str, bool, str | None], None]:
        """
        Process a message and stream the response in chunks.
        
        Yields:
            tuple[str, bool, str | None]: (content_chunk, is_final, thread_id)
        """
        has_files = hasattr(self, '_uploaded_files') and bool(self._uploaded_files)
        
        # Check if user is confirming to proceed with Decision Maker
        # Validation results are stored per thread_id in class-level dictionary
        logger.debug(f"processMessageStream - thread_id: {thread_id}")
        logger.debug(f"Stored validation thread_ids: {list(OrchestrationAgent._validation_results_by_thread.keys())}")
        
        validation_result = None
        if thread_id and thread_id in OrchestrationAgent._validation_results_by_thread:
            validation_result = OrchestrationAgent._validation_results_by_thread[thread_id]
            logger.debug(f"Found validation result for thread_id {thread_id} with status: {validation_result.get('overall_status')}")
        else:
            logger.debug(f"No validation result found for thread_id: {thread_id}")
        
        if validation_result:
            validation_status = validation_result.get('overall_status')
            # Accept PASS, CONDITIONAL_PASS, or approved status
            if is_validation_passed(validation_status):
                logger.debug(f"Checking user message for confirmation keywords: '{user_message}'")
                # Check if message is a confirmation
                confirmation_keywords = ['confirm', 'yes', 'proceed', 'go ahead', 'continue', 'ok', 'okay', 'approve']
                user_message_lower = user_message.lower()
                if any(keyword in user_message_lower for keyword in confirmation_keywords):
                    logger.info("User confirmed - proceeding to loan decision evaluation")
                    
                    # Extract consolidated data from validation result
                    consolidated_data = validation_result.get('consolidated_data', {})
                    
                    if consolidated_data:
                        # Update state to EVALUATING
                        OrchestrationAgent.update_thread_state(
                            thread_id,
                            ThreadState.EVALUATING,
                            "Evaluating loan application"
                        )
                        
                        # Clear validation state from class-level dictionary
                        del OrchestrationAgent._validation_results_by_thread[thread_id]
                        logger.debug(f"Cleared validation result for thread_id: {thread_id}")
                        
                        # Run Decision Maker to evaluate loan application
                        try:
                            decision_result = await self._run_decision_maker(consolidated_data)
                            decision_response = self._format_decision_result(decision_result)
                            
                            # Update state to COMPLETED
                            OrchestrationAgent.update_thread_state(
                                thread_id,
                                ThreadState.COMPLETED,
                                "Loan evaluation completed"
                            )
                            
                            yield (decision_response, False, thread_id)
                            yield ("", True, thread_id)
                            return
                        except Exception as e:
                            logger.error(f"Error running Decision Maker: {str(e)}", exc_info=True)
                            # Update state to ERROR
                            OrchestrationAgent.update_thread_state(
                                thread_id,
                                ThreadState.ERROR,
                                f"Error during loan evaluation: {str(e)}"
                            )
                            error_response = f"❌ **Loan Evaluation Error**\n\nError: Failed to evaluate loan application: {str(e)}\n\nPlease try again or contact support."
                            yield (error_response, False, thread_id)
                            yield ("", True, thread_id)
                            return
                    else:
                        logger.error("No consolidated data available for Decision Maker")
                        error_response = "❌ **Error**: No application data found. Please upload your documents again."
                        yield (error_response, False, thread_id)
                        yield ("", True, thread_id)
                        return
        
        # Classify intent using IntentClassifierExecutor
        intent = await self._classify_intent(user_message, has_files)
        
        # Route based on intent
        if intent == IntentType.DOCUMENT_UPLOAD and has_files:
            doc_response, actual_thread_id = await self.process_uploaded_documents(user_message, thread_id)
            # Use the actual thread_id returned from document processing (may be newly generated)
            logger.debug(f"Document upload completed - thread_id: {actual_thread_id}")
            yield (doc_response, False, actual_thread_id)
            yield ("", True, actual_thread_id)
            return
        
        if intent == IntentType.LOAN_APPLICATION:
            response = await self.process_loan_documents()
            yield (response, False, thread_id)
            yield ("", True, thread_id)
            return
        
        # General chat - use ChatAgent for conversational responses
        try:
            # Use ChatAgent to generate response
            agent_response = await self.chat_agent.run([user_message])
            
            # Extract response text from agent
            if hasattr(agent_response, 'messages') and agent_response.messages:
                # ChatMessage uses .text attribute, not .content
                last_message = agent_response.messages[-1]
                response = last_message.text if hasattr(last_message, 'text') else str(last_message)
            else:
                response = "I'm your student loan advisor. How can I help you today?"
                
            yield (response, False, thread_id)
            yield ("", True, thread_id)
            
        except Exception as e:
            logger.error(f"Error in general chat with ChatAgent: {str(e)}", exc_info=True)
            error_response = f"I encountered an error: {str(e)}. Please try again."
            yield (error_response, False, thread_id)
            yield ("", True, thread_id)    
