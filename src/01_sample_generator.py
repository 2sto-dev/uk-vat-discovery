import os
import sys
import random
import time
from pathlib import Path
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from .config import RAW_CSV, SAMPLE_CSV, SAMPLE_SIZE, RANDOM_SEED, TARGET_SIC_PREFIXES
except ImportError:
    from config import RAW_CSV, SAMPLE_CSV, SAMPLE_SIZE, RANDOM_SEED, TARGET_SIC_PREFIXES

def matches_commercial_sic(sic_text: str) -> bool:
    if not isinstance(sic_text, str) or not sic_text.strip():
        return False
    code = sic_text.strip().split()[0]
    return code.startswith(TARGET_SIC_PREFIXES)

def generate_sample():
    print(f"[*] Starting unbiased sampling from {RAW_CSV}...")
    if not RAW_CSV.exists():
        raise FileNotFoundError(f"Raw CSV not found at {RAW_CSV}")
        
    random.seed(RANDOM_SEED)
    
    cols_to_use = [
        "CompanyName",
        " CompanyNumber",
        "RegAddress.AddressLine1",
        " RegAddress.AddressLine2",
        "RegAddress.PostTown",
        "RegAddress.County",
        "RegAddress.Country",
        "RegAddress.PostCode",
        "CompanyCategory",
        "CompanyStatus",
        "DissolutionDate",
        "IncorporationDate",
        "Accounts.AccountCategory",
        "SICCode.SicText_1",
        "SICCode.SicText_2",
    ]
    
    reservoir = []
    total_scanned = 0
    active_count = 0
    eligible_count = 0
    start_time = time.time()
    
    chunk_size = 50000
    reader = pd.read_csv(
        RAW_CSV,
        chunksize=chunk_size,
        usecols=lambda c: c.strip() in [col.strip() for col in cols_to_use],
        dtype=str,
        low_memory=False,
        encoding="utf-8",
        on_bad_lines="skip"
    )
    
    for chunk_idx, chunk in enumerate(reader):
        chunk.columns = [c.strip() for c in chunk.columns]
        total_scanned += len(chunk)
        
        status_mask = (chunk["CompanyStatus"].str.strip().str.lower() == "active")
        if "DissolutionDate" in chunk.columns:
            status_mask &= chunk["DissolutionDate"].isna() | (chunk["DissolutionDate"].str.strip() == "")
        active_chunk = chunk[status_mask]
        active_count += len(active_chunk)
        
        non_dormant = active_chunk[
            active_chunk["Accounts.AccountCategory"].fillna("").str.strip().str.upper() != "DORMANT"
        ]
        
        has_metadata = non_dormant[
            non_dormant["CompanyName"].fillna("").str.strip().ne("") &
            non_dormant["RegAddress.PostCode"].fillna("").str.strip().ne("")
        ]
        
        sic1_match = has_metadata["SICCode.SicText_1"].apply(matches_commercial_sic)
        sic2_match = has_metadata["SICCode.SicText_2"].apply(matches_commercial_sic)
        eligible = has_metadata[sic1_match | sic2_match]
        
        for _, row in eligible.iterrows():
            eligible_count += 1
            if len(reservoir) < SAMPLE_SIZE:
                reservoir.append(row.to_dict())
            else:
                j = random.randint(0, eligible_count - 1)
                if j < SAMPLE_SIZE:
                    reservoir[j] = row.to_dict()
                    
        if (chunk_idx + 1) % 10 == 0:
            elapsed = time.time() - start_time
            print(f"    Processed {total_scanned:,} rows ({eligible_count:,} eligible) in {elapsed:.1f}s...")
            
    df_sample = pd.DataFrame(reservoir)
    
    for col in df_sample.columns:
        if df_sample[col].dtype == object:
            df_sample[col] = df_sample[col].fillna("").str.strip()
            
    SAMPLE_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_sample.to_csv(SAMPLE_CSV, index=False)
    
    elapsed = time.time() - start_time
    print(f"\n[+] Successfully generated sample of {len(df_sample)} companies in {elapsed:.1f}s!")
    print(f"    - Total records scanned: {total_scanned:,}")
    print(f"    - Total active companies: {active_count:,}")
    print(f"    - Total eligible commercial B2B companies: {eligible_count:,}")
    print(f"    - Saved to: {SAMPLE_CSV}")
    
    return df_sample

if __name__ == "__main__":
    generate_sample()
