"""Enhanced document scanner for loan application documents using Azure OpenAI.

Provides helpers to scan loan applications and bank statements using Azure OpenAI GPT-4o
with structured outputs for accurate field extraction from PDF documents.
"""
import logging
import re
from typing import Dict, Optional, Any
from pathlib import Path
import pymupdf4llm
import openai
import azure.identity
from app.services.azure_blob_storage_client import BlobStorageProxy
from app.config.settings import settings
from app.config.azure_credential import get_azure_credential
from app.models.documents import StudentLoanApplication, BankStatement

logger = logging.getLogger(__name__)


class LoanDocumentScanner:
    """Enhanced scanner for loan application and bank statement documents.
    
    Uses Azure OpenAI GPT-4o with structured outputs to extract
    all required fields from loan documents with high accuracy.
    """

    def __init__(
        self,
        blob_storage_proxy: BlobStorageProxy,
        openai_client: Optional[openai.AzureOpenAI] = None
    ) -> None:
        """Initialize the loan document scanner.
        
        Args:
            blob_storage_proxy: Blob storage proxy for file operations
            openai_client: Azure OpenAI client (optional, will create if not provided)
        """
        self._blob_storage_proxy = blob_storage_proxy
        
        # Initialize Azure OpenAI client
        # Use API key if available, otherwise fall back to Azure credential
        if openai_client:
            self._openai_client = openai_client
            logger.debug("Using provided OpenAI client")
        elif settings.AZURE_OPENAI_KEY:
            # Use API key authentication (more reliable than Azure CLI)
            logger.info(f"✓ Using API key authentication for OpenAI client (key length: {len(settings.AZURE_OPENAI_KEY)} chars)")
            self._openai_client = openai.AzureOpenAI(
                api_version="2024-08-01-preview",
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=settings.AZURE_OPENAI_KEY
            )
        else:
            # Fall back to Azure credential
            logger.warning(f"AZURE_OPENAI_KEY not found in settings (value: {settings.AZURE_OPENAI_KEY}), falling back to Azure CLI credential")
            logger.debug("Using Azure credential authentication for OpenAI client")
            credential = get_azure_credential()
            token_provider = azure.identity.get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            self._openai_client = openai.AzureOpenAI(
                api_version="2024-08-01-preview",
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                azure_ad_token_provider=token_provider
            )
        
        self._model_name = settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME

    def scan(
        self,
        blob_name: str,
        doc_type: str
    ) -> Dict[str, Any]:
        """Scan a document from blob storage and extract structured data.

        Args:
            blob_name: Name of the blob to scan
            doc_type: Type of document (loan_application or bank_statement)

        Returns:
            Dictionary containing extracted structured data
        """
        logger.debug(f"Scanning document: {blob_name}")

        try:
            # Download blob data using synchronous method
            file_data = self._blob_storage_proxy.get_file_as_bytes(blob_name)
            
            # Extract data using Azure OpenAI
            extracted_data = self._internal_scan(file_data, doc_type)
            
            # Data is already structured from Pydantic models
            logger.debug(f"Successfully scanned document: {blob_name}")
            return extracted_data

        except Exception as e:
            logger.error(f"Error scanning document {blob_name}: {str(e)}", exc_info=True)
            raise

    def scan_file(self, file_path: Path, doc_type: str) -> Dict[str, Any]:
        """Scan a document from local file.

        Args:
            file_path: Path to the local file
            doc_type: Type of document (loan_application or bank_statement)

        Returns:
            Dictionary containing extracted structured data

        Raises:
            FileNotFoundError if file doesn't exist
        """
        with open(file_path, "rb") as file:
            file_data = file.read()

        return self._internal_scan(file_data, doc_type)

    def _internal_scan(self, file_data: bytes, doc_type: str) -> Dict[str, Any]:
        """Internal method to scan document data using Azure OpenAI.

        Args:
            file_data: Binary data of the document
            doc_type: Type of document (loan_application or bank_statement)

        Returns:
            Dictionary containing extracted structured fields
        """
        logger.info(f"Extracting data from {doc_type}...")
        logger.debug(f"File data size: {len(file_data)} bytes")

        try:
            # Convert PDF to markdown using pymupdf4llm
            import io
            import pymupdf
            logger.debug("Converting PDF to markdown...")
            
            # Open PDF from bytes using pymupdf with stream parameter
            doc = pymupdf.open(stream=file_data, filetype="pdf")
            md_text = pymupdf4llm.to_markdown(doc)
            doc.close()
            
            logger.debug(f"Markdown conversion complete. Length: {len(md_text)} chars")
            
            # Choose the appropriate model based on document type
            if doc_type == "loan_application":
                response_format = StudentLoanApplication
                system_message = "Extract all information from this student loan application form exactly as it appears in the document. Focus on financial information, student details, and banking information."
            else:  # bank_statement
                response_format = BankStatement
                system_message = "Extract all information from this bank statement exactly as it appears in the document. Focus on account holder, bank details, account information, and balance."
            
            # Call Azure OpenAI with structured outputs
            logger.debug(f"Calling Azure OpenAI model: {self._model_name}")
            completion = self._openai_client.beta.chat.completions.parse(
                model=self._model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": md_text},
                ],
                response_format=response_format,
            )
            logger.debug("OpenAI API call completed")
            
            message = completion.choices[0].message
            if message.refusal:
                logger.error(f"OpenAI refused to extract: {message.refusal}")
                return {}
            
            # Convert Pydantic model to dict
            extracted_data = message.parsed.model_dump()
            logger.info(f"Successfully extracted {len(extracted_data)} fields from {doc_type}")
            logger.debug(f"Extracted data: {extracted_data}")
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error extracting data from {doc_type}: {str(e)}", exc_info=True)
            logger.debug(f"Failed extraction - Doc type: {doc_type}, File size: {len(file_data)} bytes")
            return {}
