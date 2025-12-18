"""Intent Classifier Executor for detecting user intents.

This executor analyzes user messages to determine their intent,
enabling conditional routing in the workflow.
"""
import logging
import re
from typing import Dict, Any
from agent_framework import Executor, WorkflowContext, handler
from typing_extensions import Never

logger = logging.getLogger(__name__)


class IntentType:
    """Intent types for the loan processing application."""
    LOAN_APPLICATION = "loan_application"
    DOCUMENT_UPLOAD = "document_upload"
    GENERAL_CHAT = "general_chat"


class IntentClassifierExecutor(Executor):
    """Executor that classifies user intent for routing decisions.
    
    This executor analyzes the user's message and determines whether they want to:
    - Apply for a loan (initial request)
    - Upload documents (completion of document upload)
    - Have a general conversation
    """
    
    def __init__(self, id: str = "intent_classifier"):
        """Initialize the Intent Classifier Executor."""
        super().__init__(id=id)
        
        # Intent patterns
        self.loan_application_patterns = [
            r'\b(apply|applying|appl)\s*(for|the)?\s*(a\s+)?(student\s+)?loan\b',
            r'\bwant\s+to\s+apply\b',
            r'\bneed\s+(a\s+)?(student\s+)?loan\b',
            r'\bhow\s+do\s+i\s+(apply\s+for\s+)?(student\s+)?loan\b',
            r'\b(student\s+)?loan\s+application\b',
            r'\bstart\s+my\s+(student\s+)?loan\s+application\b',
            r'\bfafsa\b',
            r'\bfinancial\s+aid\b',
            r'\bcollege\s+(funding|loan)\b',
            r'\btuition\s+(help|loan|assistance)\b',
            r'\bget\s+a\s+(student\s+)?loan\b'
        ]
        
        self.document_upload_patterns = [
            r'\bhere\s+(is|are)\s+(the\s+)?(documents?|files?)\b',
            r'\buploaded\s+(the\s+)?(documents?|files?)\b',
            r'\b(i\s+)?(have\s+)?uploaded\b',
            r'\bready\s+to\s+proceed\b',
            r'\bprocess\s+(these|them|my\s+documents?)\b',
            r'\bhere\s+is\s+go\b',
            r'\bgo\s+ahead\b',
            r'\blet\'s\s+proceed\b',
            r'\bstart\s+processing\b',
            r'\banalyze\s+(these|my)\s+(documents?|files?)\b',
            r'\bi\'m\s+ready\b'
        ]
    
    @handler
    async def classify_intent(
        self, 
        payload: Dict[str, Any],
        ctx: WorkflowContext[Never, str]
    ) -> None:
        """Classify the user's intent based on their message.
        
        Args:
            payload: Dict containing 'message' and optionally 'has_files'
            ctx: Workflow context for yielding the classified intent
        """
        message = payload.get('message', '')
        has_files = payload.get('has_files', False)
        
        # Determine intent
        intent = self._classify(message, has_files)
        
        logger.info(f"Classified intent: {intent} for message: {message[:50]}...")
        
        # Yield the intent for conditional routing
        await ctx.yield_output(intent)
    
    def _classify(self, message: str, has_files: bool) -> str:
        """Classify the user's intent.
        
        Args:
            message: User's message
            has_files: Whether files are attached
            
        Returns:
            Intent type string
        """
        message_lower = message.lower()
        
        # Check document upload intent first (more specific)
        if has_files or self._matches_patterns(message_lower, self.document_upload_patterns):
            return IntentType.DOCUMENT_UPLOAD
        
        # Check loan application intent
        if self._matches_patterns(message_lower, self.loan_application_patterns):
            return IntentType.LOAN_APPLICATION
        
        # Default to general chat
        return IntentType.GENERAL_CHAT
    
    def _matches_patterns(self, text: str, patterns: list) -> bool:
        """Check if text matches any of the given patterns.
        
        Args:
            text: Text to check
            patterns: List of regex patterns
            
        Returns:
            True if any pattern matches
        """
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False
