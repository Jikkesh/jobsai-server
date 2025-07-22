import os
import pandas as pd

# List your CSV paths here:
csv_files = [
    './scrapper/freshers_final.csv',
    './scrapper/internships_final.csv',
    './services/temp/remote_jobs.csv'
]

# The exact error HTML to look for
ERROR_HTML = (
    '<p>Error generating content: 400 Client Error: '
    'Bad Request for url: https://api.groq.com/openai/v1/chat/completions</p>'
)

# Columns to inspect
CHECK_COLS = [
    'job_description',
    'qualification',
    'key_responsibility',
    'about_company',
    'selection_process',
]

def clean_error_rows(df: pd.DataFrame, cols: list, error_str: str) -> pd.DataFrame:
    """
    Return a DataFrame with any row removed if ANY of the given cols exactly equals error_str.
    """
    return df.loc[~df[cols].eq(error_str).any(axis=1)]

def process_file(path: str):
    print(f"\nProcessing: {path}")
    # 1) Read CSV (all as strings)
    df = pd.read_csv(path, dtype=str)

    before = len(df)
    # 2) Clean
    df_clean = clean_error_rows(df, CHECK_COLS, ERROR_HTML)
    after = len(df_clean)

    removed = before - after
    print(f"  Rows before: {before:,} | Rows after: {after:,} | Removed: {removed:,}")

    # 3) Write cleaned CSV next to original
    base, ext = os.path.splitext(path)
    out_path = f"{base}{ext}"
    df_clean.to_csv(out_path, index=False)
    print(f"  Cleaned file written to: {out_path}")

def main():
    for csv_path in csv_files:
        if os.path.isfile(csv_path):
            process_file(csv_path)
        else:
            print(f"\n⚠️  File not found: {csv_path}")

if __name__ == "__main__":
    main()
