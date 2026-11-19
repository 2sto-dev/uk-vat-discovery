import os
import re
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
RAW_CSV = RAW_DIR / "BasicCompanyDataAsOneFile-2026-11-01.csv"
SAMPLE_CSV = DATA_DIR / "sample_companies.csv"
CANDIDATES_CSV = DATA_DIR / "candidates_extracted.csv"
RESULTS_CSV = DATA_DIR / "results_verified.csv"
HMRC_QUEUE_CSV = DATA_DIR / "hmrc_manual_queue.csv"
AUDIT_JSON = DATA_DIR / "part1_source_audit.json"

# Sampling Parameters
SAMPLE_SIZE = 150
RANDOM_SEED = 42

# SIC Code filter criteria (Active commercial / B2B sectors)
# Manufacturing (10-33), Construction (41-43), Wholesale (46), Retail (47), Tech/Services (62)
TARGET_SIC_PREFIXES = (
    tuple(str(i) for i in range(10, 34)) +  # 10xxx - 33xxx
    tuple(str(i) for i in range(41, 44)) +  # 41xxx - 43xxx
    ("46", "47", "62")                     # 46xxx, 47xxx, 62xxx
)

# Crawling configuration
MAX_CONCURRENT_REQUESTS = 5
REQUEST_TIMEOUT_SECONDS = 10
MAX_PAGES_PER_DOMAIN = 6

HIGH_YIELD_PATHS = [
    "",
    "/contact",
    "/contact-us",
    "/terms",
    "/terms-and-conditions",
    "/terms-conditions",
    "/privacy",
    "/privacy-policy",
    "/legal",
    "/about",
    "/about-us",
    "/imprint",
]

# Regex patterns for VAT candidate discovery
# Matches standard UK 9-digit VAT, with or without 'GB' prefix and various space patterns
VAT_REGEX_PATTERNS = [
    # Explicit context: VAT / Value Added Tax followed by 9 digits
    re.compile(
        r'(?:VAT|Value\s+Added\s+Tax|V\.A\.T\.)(?:\s+(?:Number|Registration|Reg|No\.?|#)?)?\s*[:\-–]?\s*(?:GB)?\s*([0-9]{3}\s*[0-9]{4}\s*[0-9]{2}|[0-9]{9})\b',
        re.IGNORECASE
    ),
    # EORI GB + 9 digits or GB + 9 digits + 000
    re.compile(
        r'\bEORI(?:\s+(?:Number|No\.?|#))?\s*[:\-–]?\s*GB\s*([0-9]{9})(?:000)?\b',
        re.IGNORECASE
    ),
    # Standalone GB prefix + 9 digits with standard grouping
    re.compile(
        r'\bGB\s*([0-9]{3}\s*[0-9]{4}\s*[0-9]{2}|[0-9]{9})\b'
    ),
]

# Modulo-97 Weights for 9-digit standard UK VAT
MODULO_97_WEIGHTS = [8, 7, 6, 5, 4, 3, 2]

# Fuzzy entity resolution thresholds
NAME_SIMILARITY_THRESHOLD = 70.0
POSTCODE_SIMILARITY_THRESHOLD = 80.0
