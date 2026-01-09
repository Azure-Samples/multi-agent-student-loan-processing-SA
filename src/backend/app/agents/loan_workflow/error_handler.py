"""Error handler executor for consistent error formatting in workflows."""
from typing import Any, Dict
from agent_framework import Executor, WorkflowContext, handler
import logging
import traceback

logger = logging.getLogger(__name__)


class ErrorHandlerExecutor(Executor):
    """Executor that provides consistent error handling and formatting.
    
    This executor wraps error responses in a user-friendly format and logs
    technical details for debugging while presenting clean messages to users.
    
    Expected payload format:
    {
        "error": Exception | str,
        "context": str (optional - describes what operation failed),
        "user_id": str (optional),
        "thread_id": str (optional)
    }
    
    Yields formatted error response:
    {
        "success": False,
        "error_message": str (user-friendly message),
        "error_type": str,
        "technical_details": str (for logging)
    }
    """
    
    def __init__(self, id: str = "error_handler"):
        """Initialize the error handler executor.
        
        Args:
            id: Unique identifier for this executor instance
        """
        super().__init__(id=id)
        self.name = "ErrorHandler"
    
    @handler
    async def handle_error(self, message: Dict[str, Any], ctx: WorkflowContext) -> None:
        """Handle and format errors consistently.
        
        Args:
            message: Error payload containing error information
            ctx: Workflow context for yielding formatted error response
        """
        try:
            payload = message
            error = payload.get("error")
            context = payload.get("context", "An operation")
            user_id = payload.get("user_id", "unknown")
            thread_id = payload.get("thread_id", "unknown")
            
            # Extract error details
            if isinstance(error, Exception):
                error_type = type(error).__name__
                error_message = str(error)
                technical_details = traceback.format_exc()
            else:
                error_type = "Error"
                error_message = str(error)
                technical_details = error_message
            
            # Log technical details for debugging
            logger.error(
                f"Error in workflow | Context: {context} | User: {user_id} | Thread: {thread_id} | "
                f"Type: {error_type} | Message: {error_message}\n{technical_details}"
            )
            
            # Format user-friendly error message
            user_friendly_message = self._format_user_message(error_type, error_message, context)
            
            # Yield formatted error response
            error_response = {
                "success": False,
                "error_message": user_friendly_message,
                "error_type": error_type,
                "technical_details": technical_details
            }
            
            await ctx.yield_output(error_response)
            
        except Exception as e:
            # Fallback error handling if error handler itself fails
            logger.critical(f"ErrorHandlerExecutor failed: {str(e)}\n{traceback.format_exc()}")
            fallback_response = {
                "success": False,
                "error_message": "An unexpected error occurred. Please try again or contact support.",
                "error_type": "CriticalError",
                "technical_details": str(e)
            }
            await ctx.yield_output(fallback_response)
    
    def _format_user_message(self, error_type: str, error_message: str, context: str) -> str:
        """Format a user-friendly error message based on error type.
        
        Args:
            error_type: Type of the exception
            error_message: Raw error message
            context: Context where error occurred
            
        Returns:
            User-friendly error message
        """
        # Map common error types to user-friendly messages
        error_templates = {
            "ValidationError": f"❌ **Validation Error**\n\n{context} failed due to invalid input. {error_message}",
            "FileNotFoundError": f"❌ **File Error**\n\n{context} failed because a required file could not be found. Please check your uploads.",
            "PermissionError": f"❌ **Permission Error**\n\n{context} failed due to insufficient permissions. Please contact support.",
            "TimeoutError": f"⏱️ **Timeout Error**\n\n{context} took too long to complete. Please try again.",
            "ConnectionError": f"🔌 **Connection Error**\n\n{context} failed due to a network issue. Please check your connection and try again.",
            "ValueError": f"❌ **Value Error**\n\n{context} received invalid data. {error_message}",
            "KeyError": f"❌ **Data Error**\n\n{context} failed because expected data was missing. Please try again or contact support.",
        }
        
        # Check if we have a template for this error type
        if error_type in error_templates:
            return error_templates[error_type]
        
        # Generic error message for unknown types
        return (
            f"❌ **Error Occurred**\n\n"
            f"{context} encountered an error. Please try again. "
            f"If the problem persists, contact support.\n\n"
            f"*Error type: {error_type}*"
        )
