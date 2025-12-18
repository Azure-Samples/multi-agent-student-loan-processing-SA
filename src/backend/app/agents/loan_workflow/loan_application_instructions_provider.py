"""LoanApplicationExecutor - Provides loan application instructions.

This executor handles LOAN_APPLICATION intent by providing users
with instructions on required documents for student loan applications.
"""

from agent_framework import Executor, WorkflowContext, handler
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class LoanApplicationExecutor(Executor):
    """Executor that provides student loan application instructions.
    
    This executor returns formatted instructions on required documents
    for the student loan application process.
    """
    
    def __init__(self, id: str = "loan_application"):
        """Initialize the loan application executor.
        
        Args:
            id: Executor identifier
        """
        super().__init__(id=id)
    
    @handler
    async def provide_instructions(
        self, 
        message: Dict[str, Any], 
        ctx: WorkflowContext[str, str]
    ) -> None:
        """Provide loan application instructions to the user.
        
        Args:
            message: Dict containing request information
            ctx: Workflow context for yielding outputs
        """
        try:
            response = """
📄 **Student Loan Application**

To process your student loan application, please upload these 2 documents:

**Required Documents:**
- ✅ **Loan Application Form** (completed and signed)
- ✅ **Bank Statement** (most recent month)

**Next Step:**
Click the "+" button below to upload your documents.
"""
            
            await ctx.yield_output(response.strip())
            
        except Exception as e:
            logger.error(f"Error in LoanApplicationExecutor: {str(e)}", exc_info=True)
            await ctx.yield_output(f"Error: {str(e)}. Please try again.")
