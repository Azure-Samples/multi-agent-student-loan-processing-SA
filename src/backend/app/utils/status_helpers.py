"""Status mapping utilities for validation and loan processing workflows.

This module provides centralized status checking to avoid duplicate mapping logic
throughout the codebase. These utilities handle both current Pydantic statuses
(PASS/CONDITIONAL_PASS/FAIL) and legacy statuses (approved/needs_correction)
for backward compatibility.
"""


def is_validation_passed(status: str) -> bool:
    """Check if validation status indicates success.
    
    Centralized status mapping for Pydantic ValidationResponse statuses.
    Valid pass statuses:
    - PASS: All validations passed (current Pydantic status)
    - CONDITIONAL_PASS: Minor issues but acceptable (current Pydantic status)  
    - approved: Legacy status for backward compatibility
    
    Args:
        status: Validation status string from ValidationResponse.overall_status
        
    Returns:
        True if validation passed, False otherwise
        
    Example:
        >>> is_validation_passed("PASS")
        True
        >>> is_validation_passed("CONDITIONAL_PASS")
        True
        >>> is_validation_passed("FAIL")
        False
    """
    return status in ['PASS', 'CONDITIONAL_PASS', 'approved']


def is_validation_failed(status: str) -> bool:
    """Check if validation status indicates failure.
    
    Centralized status mapping for Pydantic ValidationResponse statuses.
    Valid fail statuses:
    - FAIL: Critical validation failures (current Pydantic status)
    - needs_correction: Legacy status for backward compatibility
    
    Note: 'incomplete' status was removed - Pydantic model only allows PASS/CONDITIONAL_PASS/FAIL
    
    Args:
        status: Validation status string from ValidationResponse.overall_status
        
    Returns:
        True if validation failed, False otherwise
        
    Example:
        >>> is_validation_failed("FAIL")
        True
        >>> is_validation_failed("needs_correction")
        True
        >>> is_validation_failed("PASS")
        False
    """
    return status in ['FAIL', 'needs_correction']
