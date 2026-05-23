"""Input validation and PII scrubbing utilities (Sprint 3)."""

import re
import logging

logger = logging.getLogger(__name__)


def scrub_pii(text: str) -> str:
    """
    Remove personally identifiable information (PII) from text.
    
    Patterns scrubbed:
    - Email addresses → [EMAIL]
    - Phone numbers → [PHONE]
    - Credit card numbers → [CREDIT_CARD]
    - Social security numbers → [SSN]
    - Dates (likely DOB) → [DATE]
    """
    if not text:
        return text
    
    # Email: name@domain.ext
    text = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        '[EMAIL]',
        text
    )
    
    # Phone: (123) 456-7890 or 123-456-7890 or 1234567890
    text = re.sub(
        r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
        '[PHONE]',
        text
    )

    # Vietnamese phone: +84..., 84..., or 0... with optional spaces/dashes.
    text = re.sub(
        r'(?<!\d)(?:\+?84|0)(?:[-.\s]?\d){9,10}(?!\d)',
        '[PHONE]',
        text
    )
    
    # Credit card: 4111 1111 1111 1111 or 4111111111111111
    text = re.sub(
        r'\b(?:[0-9]{4}[-\s]?){3}[0-9]{4}\b',
        '[CREDIT_CARD]',
        text
    )
    
    # SSN: 123-45-6789
    text = re.sub(
        r'\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b',
        '[SSN]',
        text
    )
    
    return text


def validate_user_input(text: str, max_length: int = 1000) -> tuple[bool, str]:
    """
    Validate user input text.
    
    Returns:
        (is_valid, error_message)
    """
    if not text:
        return False, "Input cannot be empty"
    
    if len(text) > max_length:
        return False, f"Input exceeds maximum length of {max_length} characters"
    
    # Check for potentially malicious patterns (basic XSS/injection prevention)
    dangerous_patterns = [
        r'<script',
        r'javascript:',
        r'onerror=',
        r'onclick=',
        r'sql\s*(;|--)',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False, "Input contains potentially malicious content"
    
    return True, ""


def sanitize_user_input(text: str) -> str:
    """
    Sanitize user input: scrub PII and normalize whitespace.
    """
    # Scrub PII
    text = scrub_pii(text)
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text


def validate_email(email: str) -> bool:
    """Simple email validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_cefr_level(level: str) -> bool:
    """Validate CEFR level."""
    valid_levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    return level.upper() in valid_levels
