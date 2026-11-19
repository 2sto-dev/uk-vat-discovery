import re
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from .config import (
        CANDIDATES_CSV,
        RESULTS_CSV,
        NAME_SIMILARITY_THRESHOLD,
        POSTCODE_SIMILARITY_THRESHOLD,
        HMRC_QUEUE_CSV,
    )
    from .validators import clean_vat_string
except ImportError:
    from config import (
        CANDIDATES_CSV,
        RESULTS_CSV,
        NAME_SIMILARITY_THRESHOLD,
        POSTCODE_SIMILARITY_THRESHOLD,
        HMRC_QUEUE_CSV,
    )
    from validators import clean_vat_string

LEGAL_SUFFIXES = re.compile(
    r'\b(LIMITED|LTD|PLC|LLP|CIC|COMPANY|CORP|CORPORATION|SERVICES|HOLDINGS|GROUP|UK)\b',
    re.IGNORECASE
)

def normalize_company_name(name: str) -> str:
    if not name:
        return ""
    name_clean = LEGAL_SUFFIXES.sub("", name.upper())
    name_clean = re.sub(r'[^A-Z0-9\s]', ' ', name_clean)
    return " ".join(name_clean.split())

def normalize_postcode(pc: str) -> str:
    if not pc:
        return ""
    return re.sub(r'[^A-Z0-9]', '', pc.upper())

class HMRCVerifier:
    def __init__(self):
        self.base_url = "https://www.tax.service.gov.uk/check-vat-number/enter-vat-details"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        })

    def _get_csrf_token(self) -> Optional[str]:
        try:
            r = self.session.get(self.base_url, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                csrf = soup.find("input", {"name": "csrfToken"})
                if csrf and csrf.get("value"):
                    return csrf["value"]
        except Exception as e:
            print(f"[-] Error fetching HMRC CSRF token: {e}")
        return None

    def query_vat_number(self, vat_number: str) -> Dict[str, Any]:
        cleaned_vat = clean_vat_string(vat_number)
        result = {
            "vat_number": cleaned_vat,
            "hmrc_status": "ERROR",
            "registered_name": "",
            "registered_address": "",
            "error_message": "",
        }

        if len(cleaned_vat) != 9 or not cleaned_vat.isdigit():
            result["hmrc_status"] = "INVALID_FORMAT"
            return result

        csrf = self._get_csrf_token()
        if not csrf:
            result["hmrc_status"] = "RATE_LIMITED_OR_BLOCKED"
            result["error_message"] = "Could not obtain CSRF token from HMRC checker"
            return result

        payload = {
            "csrfToken": csrf,
            "target": cleaned_vat,
        }

        try:
            r = self.session.post(self.base_url, data=payload, timeout=15)
            if "/check-vat-number/known" in r.url:
                result["hmrc_status"] = "REGISTERED"
                soup = BeautifulSoup(r.text, "html.parser")
                
                headings = soup.find_all(class_="govuk-heading-s")
                for h in headings:
                    htext = h.get_text(strip=True).lower()
                    sibling = h.find_next_sibling(class_="govuk-body")
                    if sibling:
                        val = sibling.get_text(" ", strip=True)
                        if "name" in htext:
                            result["registered_name"] = val
                        elif "address" in htext:
                            result["registered_address"] = val
            elif "/check-vat-number/unknown" in r.url:
                result["hmrc_status"] = "NOT_REGISTERED"
            else:
                result["hmrc_status"] = "UNEXPECTED_RESPONSE"
                result["error_message"] = f"Final URL: {r.url}, Status: {r.status_code}"
        except Exception as e:
            result["hmrc_status"] = "NETWORK_ERROR"
            result["error_message"] = str(e)

        return result

    def match_entity(
        self,
        ch_name: str,
        ch_postcode: str,
        hmrc_name: str,
        hmrc_address: str
    ) -> Tuple[float, float, str]:
        if not hmrc_name:
            return 0.0, 0.0, "NO_HMRC_DATA"

        norm_ch_name = normalize_company_name(ch_name)
        norm_hmrc_name = normalize_company_name(hmrc_name)
        
        score_token_set = fuzz.token_set_ratio(norm_ch_name, norm_hmrc_name)
        score_partial = fuzz.partial_ratio(norm_ch_name, norm_hmrc_name)
        name_score = round(max(score_token_set, score_partial), 1)

        norm_ch_pc = normalize_postcode(ch_postcode)
        norm_hmrc_pc = normalize_postcode(hmrc_address)
        
        postcode_score = 0.0
        if norm_ch_pc and norm_ch_pc in norm_hmrc_pc:
            postcode_score = 100.0
        elif norm_ch_pc and len(norm_ch_pc) >= 3:
            outward_ch = norm_ch_pc[:-3] if len(norm_ch_pc) > 3 else norm_ch_pc
            if outward_ch and outward_ch in norm_hmrc_pc:
                postcode_score = 75.0
            else:
                postcode_score = round(fuzz.partial_ratio(norm_ch_pc, norm_hmrc_pc), 1)

        if name_score >= NAME_SIMILARITY_THRESHOLD:
            if postcode_score >= POSTCODE_SIMILARITY_THRESHOLD:
                status = "VERIFIED_EXACT_MATCH"
            else:
                status = "VERIFIED_NAME_MATCH_TRADING_ADDRESS"
        else:
            status = "MISMATCH_FALSE_POSITIVE"

        return name_score, postcode_score, status


def run_verification_pipeline(candidates_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    if candidates_df is None:
        if not CANDIDATES_CSV.exists():
            raise FileNotFoundError(f"Candidates file not found at {CANDIDATES_CSV}")
        candidates_df = pd.read_csv(CANDIDATES_CSV)

    # Filter to checksum-valid candidates
    valid_cands = candidates_df[candidates_df["is_checksum_valid"] == True].copy()
    print(f"[*] Starting HMRC verification for {len(valid_cands)} checksum-valid candidates...")

    verifier = HMRCVerifier()
    results = []
    manual_queue = []

    for idx, (_, row) in enumerate(valid_cands.iterrows()):
        vat = str(row.get("candidate_vat", "")).strip()
        ch_name = str(row.get("CompanyName", "")).strip()
        ch_postcode = str(row.get("RegAddress.PostCode", "")).strip()
        company_num = str(row.get("CompanyNumber", "")).strip()

        print(f"    [{idx+1}/{len(valid_cands)}] Checking VAT {vat} for '{ch_name}'...")
        
        hmrc_res = verifier.query_vat_number(vat)
        time.sleep(1.0)

        if hmrc_res["hmrc_status"] == "REGISTERED":
            name_score, pc_score, resolution = verifier.match_entity(
                ch_name=ch_name,
                ch_postcode=ch_postcode,
                hmrc_name=hmrc_res["registered_name"],
                hmrc_address=hmrc_res["registered_address"]
            )
            print(f"        -> HMRC Name: {hmrc_res['registered_name']} (Name match: {name_score}%, Res: {resolution})")
        elif hmrc_res["hmrc_status"] == "NOT_REGISTERED":
            name_score, pc_score, resolution = 0.0, 0.0, "DEREGISTERED_OR_INVALID"
            print("        -> HMRC: Not Registered / Deregistered")
        else:
            name_score, pc_score, resolution = 0.0, 0.0, "VERIFICATION_FAILED"
            print(f"        -> HMRC check error: {hmrc_res['error_message']}")
            manual_queue.append({
                "CompanyNumber": company_num,
                "CompanyName": ch_name,
                "CandidateVAT": vat,
                "Error": hmrc_res["error_message"]
            })

        results.append({
            "CompanyNumber": company_num,
            "CompanyName": ch_name,
            "CH_PostCode": ch_postcode,
            "CandidateVAT": vat,
            "HMRC_Status": hmrc_res["hmrc_status"],
            "HMRC_RegisteredName": hmrc_res["registered_name"],
            "HMRC_RegisteredAddress": hmrc_res["registered_address"],
            "NameSimilarityScore": name_score,
            "PostCodeSimilarityScore": pc_score,
            "EntityResolution": resolution,
            "SourcePage": row.get("source_page", ""),
        })

    res_df = pd.DataFrame(results)
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    res_df.to_csv(RESULTS_CSV, index=False)

    if manual_queue:
        pd.DataFrame(manual_queue).to_csv(HMRC_QUEUE_CSV, index=False)
        print(f"[!] Saved {len(manual_queue)} rate-limited items to {HMRC_QUEUE_CSV}")

    print(f"\n[+] HMRC Verification complete. Verified {len(res_df)} candidates. Saved to {RESULTS_CSV}")
    return res_df

if __name__ == "__main__":
    run_verification_pipeline()
