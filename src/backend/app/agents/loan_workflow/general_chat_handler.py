"""ChatResponseExecutor - Handles general chat conversations using ChatAgent.

This executor wraps a ChatAgent to handle GENERAL_CHAT intent,
providing conversational responses for Q&A about student loans.
"""

from agent_framework import Executor, WorkflowContext, handler
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class ChatResponseExecutor(Executor):
    """Executor that handles general chat using a ChatAgent.
    
    This executor takes user messages and returns conversational responses
    using a ChatAgent configured with student loan advisor instructions.
    """
    
    def __init__(self, chat_agent: Any, id: str = "chat_response"):
        """Initialize the chat response executor.
        
        Args:
            chat_agent: ChatAgent instance (from azure_chat_client.create_agent())
            id: Executor identifier
        """
        super().__init__(id=id)
        self.chat_agent = chat_agent
    
    @handler
    async def handle_chat(
        self, 
        message: Dict[str, Any], 
        ctx: WorkflowContext[str, str]
    ) -> None:
        """Handle general chat messages using the ChatAgent.
        
        Args:
            message: Dict containing 'user_message' key
            ctx: Workflow context for yielding outputs
        """
        try:
            user_message = message.get('user_message', '')
            
            # Run the ChatAgent to get conversational response
            agent_response = await self.chat_agent.run([user_message])
            
            # Extract the response text
            if hasattr(agent_response, 'messages') and agent_response.messages:
                # ChatMessage uses .text attribute, not .content
                last_message = agent_response.messages[-1]
                response_text = last_message.text if hasattr(last_message, 'text') else str(last_message)
            else:
                response_text = "I'm your student loan advisor. How can I help you today?"
            
            # Yield the response
            await ctx.yield_output(response_text)
            
        except Exception as e:
            logger.error(f"Error in ChatResponseExecutor: {str(e)}", exc_info=True)
            await ctx.yield_output(f"I encountered an error: {str(e)}. Please try again.")
