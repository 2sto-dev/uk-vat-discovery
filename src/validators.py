import re
import sys
from pathlib import Path
from typing import Optional, Tuple

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from .config import MODULO_97_WEIGHTS
except ImportError:
    from config import MODULO_97_WEIGHTS

def clean_vat_string(vat_raw: str) -> str:
    """Normalize VAT string by stripping 'GB', spaces, punctuation, and leading zeros if malformed."""
    if not vat_raw:
        return ""
    cleaned = re.sub(r'[^0-9A-Za-z]', '', vat_raw).upper()
    if cleaned.startswith("GB"):
        cleaned = cleaned[2:]
    return cleaned

def validate_uk_vat_checksum(vat_candidate: str) -> Tuple[bool, str]:
    """
    Validates a 9-digit UK VAT registration number using HMRC Modulo-97 algorithms.
    
    Returns:
        (is_valid: bool, rule_matched: str)
        rule_matched can be: 'STANDARD', 'POST_2009', 'BRANCH_TRADER', 'SPECIAL', or 'INVALID'
    """
    cleaned = clean_vat_string(vat_candidate)
    
    # Check for branch trader (12 digits: 9-digit VAT + 3-digit branch)
    is_branch = False
    if len(cleaned) == 12 and cleaned.isdigit():
        is_branch = True
        cleaned = cleaned[:9]
        
    # Standard UK VAT must be exactly 9 digits
    if len(cleaned) != 9 or not cleaned.isdigit():
        # Special government / health authority cases
        if len(cleaned) == 5:
            prefix = cleaned[:2]
            num = cleaned[2:]
            if prefix == "GD" and num.isdigit() and int(num) < 500:
                return True, "SPECIAL_GOV_DEPT"
            if prefix == "HA" and num.isdigit() and int(num) >= 500:
                return True, "SPECIAL_HEALTH_AUTH"
        return False, "INVALID_FORMAT"
    
    # Reject trivial invalid numbers like 000000000
    if int(cleaned) == 0:
        return False, "INVALID_ZERO"
        
    digits = [int(d) for d in cleaned]
    weighted_sum = sum(d * w for d, w in zip(digits[:7], MODULO_97_WEIGHTS))
    check_digits = digits[7] * 10 + digits[8]
    
    # Rule 1: Standard pre/post HMRC rule
    # (weighted_sum + check_digits) % 97 == 0
    if (weighted_sum + check_digits) % 97 == 0:
        return True, "BRANCH_TRADER" if is_branch else "STANDARD"
        
    # Rule 2: Post-November 2009 rule (+55 offset)
    # (weighted_sum + check_digits + 55) % 97 == 0
    if (weighted_sum + check_digits + 55) % 97 == 0:
        return True, "BRANCH_TRADER_POST_2009" if is_branch else "POST_2009"
        
    return False, "INVALID_CHECKSUM"


def extract_vat_from_eori(eori_str: str) -> Optional[str]:
    """
    Extracts 9-digit VAT number from a UK EORI number.
    UK EORI format for VAT registered entities is typically GB + 9-digit VAT + optional 3-digit suffix (e.g. 000).
    """
    cleaned = clean_vat_string(eori_str)
    if len(cleaned) == 9 and cleaned.isdigit():
        is_valid, _ = validate_uk_vat_checksum(cleaned)
        return cleaned if is_valid else None
    elif len(cleaned) == 12 and cleaned.isdigit():
        vat_part = cleaned[:9]
        is_valid, _ = validate_uk_vat_checksum(vat_part)
        return vat_part if is_valid else None
    return None


if __name__ == "__main__":
    test_cases = [
        ("GB 220 4302 31", True, "STANDARD"),       # Tesco
        ("232 1288 92", True, "STANDARD"),          # Marks & Spencer
        ("GB232128892000", True, "BRANCH_TRADER"),  # M&S EORI/Branch
        ("GB 000 0000 00", False, "INVALID_ZERO"),
        ("123456789", False, "INVALID_CHECKSUM"),
    ]
    for vat, expected_valid, expected_rule in test_cases:
        valid, rule = validate_uk_vat_checksum(vat)
        print(f"VAT: {vat:<18} -> Valid: {valid!s:<6} Rule: {rule} (Expected: {expected_valid}, {expected_rule})")
