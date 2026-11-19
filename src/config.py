import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
RAW_CSV = RAW_DIR / "BasicCompanyDataAsOneFile-2026-11-01.csv"
SAMPLE_CSV = DATA_DIR / "sample_companies.csv"
CANDIDATES_CSV = DATA_DIR / "candidates_extracted.csv"
RESULTS_CSV = DATA_DIR / "results_verified.csv"
HMRC_QUEUE_CSV = DATA_DIR / "hmrc_manual_queue.csv"
AUDIT_JSON = DATA_DIR / "part1_source_audit.json"

SAMPLE_SIZE = 150
RANDOM_SEED = 42

TARGET_SIC_PREFIXES = (
    tuple(str(i) for i in range(10, 34)) +  
    tuple(str(i) for i in range(41, 44)) +  
    ("46", "47", "62")                     
)

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

VAT_REGEX_PATTERNS = [
    re.compile(
        r'(?:VAT|Value\s+Added\s+Tax|V\.A\.T\.)(?:\s+(?:Number|Registration|Reg|No\.?|#)?)?\s*[:\-–]?\s*(?:GB)?\s*([0-9]{3}\s*[0-9]{4}\s*[0-9]{2}|[0-9]{9})\b',
        re.IGNORECASE
    ),
    re.compile(
        r'\bEORI(?:\s+(?:Number|No\.?|#))?\s*[:\-–]?\s*GB\s*([0-9]{9})(?:000)?\b',
        re.IGNORECASE
    ),
    re.compile(
        r'\bGB\s*([0-9]{3}\s*[0-9]{4}\s*[0-9]{2}|[0-9]{9})\b'
    ),
]

MODULO_97_WEIGHTS = [8, 7, 6, 5, 4, 3, 2]

NAME_SIMILARITY_THRESHOLD = 70.0
POSTCODE_SIMILARITY_THRESHOLD = 80.0
