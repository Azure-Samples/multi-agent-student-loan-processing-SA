"""Response Formatter Agent for presenting extraction results.

This agent handles the presentation logic, formatting structured data
from document extraction into user-friendly markdown output.
"""
import logging
import re
from typing import Dict, Any, List
from agent_framework import Executor, WorkflowContext, handler
from typing_extensions import Never

logger = logging.getLogger(__name__)


class ResponseFormatterExecutor(Executor):
    """Executor that formats extracted document data for user presentation.
    
    This executor receives structured extraction results and produces
    formatted markdown output for the UI.
    """
    
    def __init__(self, id: str = "response_formatter"):
        """Initialize the Response Formatter Executor."""
        super().__init__(id=id)
    
    @handler
    async def format_extraction_result(
        self,
        extraction_result: Dict[str, Any],
        ctx: WorkflowContext[Never, str]
    ) -> None:
        """Format extraction results into user-friendly markdown.
        
        Args:
            extraction_result: Structured data from DocumentExtractorAgent
            ctx: Workflow context for yielding final output
        """
        formatted = self._format_for_display(extraction_result)
        # Yield as final workflow output
        await ctx.yield_output(formatted)
    
    def _format_for_display(self, data: Dict[str, Any]) -> str:
        """Format structured extraction data into markdown.
        
        Args:
            data: Dict containing extracted_data, uploaded_files, errors
            
        Returns:
            Formatted markdown string
        """
        lines = ["✅ **Documents Processed Successfully**\n"]
        lines.append("**Extracted Information:**")
        
        for filename, doc_data in data.get('extracted_data', {}).items():
            lines.append(f"\n📄 **{filename}**")
            
            if isinstance(doc_data, dict):
                formatted_fields = self._format_extracted_data(doc_data)
                lines.extend(formatted_fields)
            else:
                lines.append(f"  {doc_data}")
        
        # Add errors if any
        if data.get('errors'):
            lines.append("\n**⚠️ Errors:**")
            for error in data['errors']:
                lines.append(f"  • {error.get('file', 'Unknown')}: {error.get('error', 'Unknown error')}")
        
        return "\n".join(lines)
    
    def _format_field_name(self, key: str) -> str:
        """Convert snake_case or camelCase to Title Case."""
        key = key.replace('_', ' ')
        # Add space before capital letters in camelCase
        key = re.sub(r'(?<!^)(?=[A-Z])', ' ', key)
        return key.title()
    
    def _extract_value_from_nested(self, value: Any) -> str:
        """Recursively extract string values from nested dictionaries."""
        if isinstance(value, dict):
            # Check if it's a currency object
            if 'amount' in value and 'currencySymbol' in value:
                symbol = value.get('currencySymbol', '$')
                amount = value.get('amount', 0)
                if isinstance(amount, (int, float)):
                    return f"{symbol}{amount:,.2f}"
                return f"{symbol}{amount}"
            
            # For other dicts, try to extract meaningful values
            for key in ['content', 'value', 'text', 'name']:
                if key in value and value[key]:
                    return str(value[key])
            
            # If no common fields, return concatenated non-empty values
            values = [str(v) for v in value.values() if v and not isinstance(v, (dict, list))]
            if values:
                return ', '.join(values[:3])
            
            # Last resort: truncate dict representation
            dict_str = str(value)
            return dict_str[:80] + "..." if len(dict_str) > 80 else dict_str
        
        elif isinstance(value, list):
            if not value:
                return ""
            # If list of simple values, join them
            if all(not isinstance(item, (dict, list)) for item in value):
                return ', '.join(str(item) for item in value[:5])
            # Otherwise truncate
            list_str = str(value)
            return list_str[:80] + "..." if len(list_str) > 80 else list_str
        
        return str(value) if value else ""
    
    def _format_extracted_data(self, doc_data: Dict[str, Any]) -> List[str]:
        """Format extracted document data into readable bullet points."""
        formatted_lines = []
        
        # Priority fields to display first
        priority_fields = [
            'document_type', 'VendorName', 'CustomerName', 'InvoiceTotal',
            'InvoiceDate', 'account_number', 'current_balance', 
            'available_balance', 'statement_date', 'VendorAddress'
        ]
        
        # Fields to skip
        skip_fields = {'blob_name', 'extraction_raw', 'raw_data', 'extraction_timestamp', 
                      'confidence', 'page_number', 'bounding_box'}
        
        displayed_count = 0
        max_fields = 7
        
        # First show priority fields
        for key in priority_fields:
            if displayed_count >= max_fields:
                break
            if key in doc_data and doc_data[key]:
                value = self._extract_value_from_nested(doc_data[key])
                if value:
                    formatted_lines.append(f"  • **{self._format_field_name(key)}:** {value}")
                    displayed_count += 1
        
        # Then show other fields if we haven't reached the limit
        if displayed_count < max_fields:
            for key, value in doc_data.items():
                if displayed_count >= max_fields:
                    break
                if key not in priority_fields and key not in skip_fields and value:
                    extracted_value = self._extract_value_from_nested(value)
                    if extracted_value:
                        formatted_lines.append(f"  • **{self._format_field_name(key)}:** {extracted_value}")
                        displayed_count += 1
        
        return formatted_lines
