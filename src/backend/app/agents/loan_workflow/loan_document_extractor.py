"""Document Extractor Agent for processing loan application documents.

This agent handles the upload, extraction, and validation of loan application
documents including loan applications and bank statements.
"""
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from uuid import uuid4
import asyncio

from azure.storage.blob import BlobServiceClient
from app.config.settings import settings
from app.config.azure_credential import get_azure_credential
from app.services.azure_blob_storage_client import BlobStorageProxy
from app.services.loan_document_scanner import LoanDocumentScanner

# Agent Framework imports
from agent_framework import Executor, WorkflowContext, handler
from typing_extensions import Never

logger = logging.getLogger(__name__)


class DocumentExtractorAgent(Executor):
    """Executor responsible for document upload, extraction, and validation.
    
    This executor processes uploaded documents using Azure OpenAI GPT-4o
    with structured outputs and emits extraction results to the workflow.
    """
    
    def __init__(self, id: str = "document_extractor"):
        """Initialize the Document Extractor Agent with Azure services."""
        super().__init__(id=id)
        self.credential = get_azure_credential()
        
        # Initialize Blob Storage client
        if settings.AZURE_STORAGE_ACCOUNT:
            account_url = f"https://{settings.AZURE_STORAGE_ACCOUNT}.blob.core.windows.net"
            logger.info(f"Using credential-based authentication for blob storage: {account_url}")
            
            self.blob_service_client = BlobServiceClient(
                account_url=account_url,
                credential=self.credential
            )
            
            self.blob_proxy = BlobStorageProxy(
                container_name=settings.AZURE_STORAGE_CONTAINER or "content",
                client=self.blob_service_client
            )
        else:
            logger.warning("AZURE_STORAGE_ACCOUNT not configured")
            self.blob_service_client = None
            self.blob_proxy = None
        
        # Initialize loan document scanner with OpenAI
        if self.blob_proxy:
            self.loan_scanner = LoanDocumentScanner(
                blob_storage_proxy=self.blob_proxy
            )
        else:
            logger.warning("Loan scanner not initialized - blob storage not configured")
            self.loan_scanner = None

    @handler
    async def handle_documents(
        self, 
        payload: Dict[str, Any], 
        ctx: WorkflowContext[Dict[str, Any]]
    ) -> None:
        """Handler method for processing uploaded documents.
        
        This is the Agent Framework entry point that receives document upload
        requests and emits structured extraction results to the workflow.
        
        Args:
            payload: Dict containing 'files' and 'thread_id'
            ctx: Workflow context for sending messages to downstream executors
        """
        files = payload.get('files', [])
        thread_id = payload.get('thread_id', str(uuid4()))
        
        result = await self.process_documents(files, thread_id)
        
        # Send structured result to next executor in workflow
        await ctx.send_message(result)

    async def process_documents(self, files: List[Dict[str, Any]], thread_id: str) -> Dict[str, Any]:
        """Process uploaded documents and extract relevant information.
        
        Args:
            files: List of uploaded file information
            thread_id: Thread ID for tracking the session
            
        Returns:
            Dictionary containing extracted data and processing results
        """
        try:
            # Check if services are properly configured
            if not self.loan_scanner or not self.blob_proxy:
                return {
                    "thread_id": thread_id,
                    "processing_status": "error",
                    "error": "Document processing services not configured. Please check Azure settings.",
                    "extracted_data": {},
                    "uploaded_files": [],
                    "errors": [{"general": "Loan scanner or Blob Storage not configured"}]
                }
            
            results = {
                "thread_id": thread_id,
                "processing_status": "success",
                "extracted_data": {},
                "uploaded_files": [],
                "errors": []
            }
            
            for file_info in files:
                try:
                    # Use just the filename without UUID prefix
                    blob_name = f"{thread_id}/{file_info['filename']}"
                    
                    # Upload file to blob storage
                    await self._upload_file_to_blob(file_info['content'], blob_name)
                    
                    # Extract document information
                    extracted_data = await self._extract_document_data(blob_name, file_info['filename'])
                    
                    results["uploaded_files"].append({
                        "original_name": file_info['filename'],
                        "blob_name": blob_name,
                        "extraction_status": "success"
                    })
                    
                    results["extracted_data"][file_info['filename']] = extracted_data
                    
                except Exception as e:
                    logger.error(f"Error processing file {file_info['filename']}: {str(e)}")
                    results["errors"].append({
                        "file": file_info['filename'],
                        "error": str(e)
                    })
            
            if results["errors"]:
                results["processing_status"] = "partial_success"
            
            # Store for validation access
            self._last_extraction_result = results
                
            return results
            
        except Exception as e:
            logger.error(f"Error in document processing: {str(e)}")
            return {
                "thread_id": thread_id,
                "processing_status": "error",
                "error": str(e),
                "extracted_data": {},
                "uploaded_files": [],
                "errors": [{"general": str(e)}]
            }

    async def _upload_file_to_blob(self, file_content: bytes, blob_name: str) -> None:
        """Upload file content to Azure Blob Storage.
        
        Args:
            file_content: File content as bytes
            blob_name: Name for the blob in storage
        """
        try:
            # Run blob upload in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, 
                self.blob_proxy.store_file, 
                file_content, 
                blob_name, 
                True
            )
            logger.info(f"Successfully uploaded file to blob: {blob_name}")
        except Exception as e:
            logger.error(f"Failed to upload file to blob {blob_name}: {str(e)}")
            raise

    async def _extract_document_data(self, blob_name: str, original_filename: str) -> Dict[str, Any]:
        """Extract data from a document using Azure OpenAI GPT-4o.
        
        Args:
            blob_name: Name of the blob containing the document
            original_filename: Original filename for context
            
        Returns:
            Dictionary containing extracted document data with fields for Triage Agent
        """
        try:
            # Determine document type based on filename
            doc_type = self._determine_document_type(original_filename)
            
            # Validate document type
            if doc_type not in ["loan_application", "bank_statement"]:
                raise Exception(f"Unsupported document type: {doc_type}. Expected: loan_application or bank_statement")
            
            if not self.loan_scanner:
                raise Exception("Loan document scanner not initialized")
            
            # Run document analysis with OpenAI-based scanner (synchronous in executor)
            loop = asyncio.get_event_loop()
            structured_data = await loop.run_in_executor(
                None,
                self.loan_scanner.scan,
                blob_name,
                doc_type
            )
            
            logger.info(f"Extracted {len(structured_data)} fields from {doc_type}: {original_filename}")
            
            return {
                "document_type": doc_type,
                "original_filename": original_filename,
                "blob_name": blob_name,
                "extraction_raw": {"extraction_method": "azure_openai_gpt4o"},
                "structured_data": structured_data,
                "extraction_timestamp": asyncio.get_event_loop().time()
            }
            
        except Exception as e:
            logger.error(f"Failed to extract data from {blob_name}: {str(e)}", exc_info=True)
            return {
                "document_type": "unknown",
                "original_filename": original_filename,
                "blob_name": blob_name,
                "error": str(e),
                "extraction_timestamp": asyncio.get_event_loop().time()
            }

    def _determine_document_type(self, filename: str) -> str:
        """Determine document type based on filename patterns.
        
        Args:
            filename: Original filename
            
        Returns:
            Document type string (loan_application, bank_statement, or unknown)
        """
        filename_lower = filename.lower()
        
        # Student loan application patterns
        # Check for "la-" prefix or keywords
        if (filename_lower.startswith('la-') or 
            any(keyword in filename_lower for keyword in [
                'loan', 'application', 'student-loan', 'student_loan', 
                'filled-student-loan', 'loan-application', 'loan_application'
            ])):
            return "loan_application"
        
        # Bank statement patterns
        # Check for "bs-" prefix or keywords
        elif (filename_lower.startswith('bs-') or 
              any(keyword in filename_lower for keyword in [
                  'bank', 'statement', 'account', 'fictitious-bank', 'bank_statement'
              ])):
            return "bank_statement"
        
        # Future document types can be added here
        # elif any(keyword in filename_lower for keyword in ['transcript', 'grade']):
        #     return "academic_transcript"
        # elif any(keyword in filename_lower for keyword in ['enrollment', 'acceptance']):
        #     return "enrollment_verification"
        
        else:
            return "unknown"