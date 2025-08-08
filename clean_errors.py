import os
import pandas as pd

# List your CSV paths here:
csv_files = [
    './scrapper/freshers_final.csv',
    './scrapper/internships_final.csv',
    './services/temp/remote_jobs.csv'
]

# Define both error types to check for
ERROR_TYPES = [
    '<p>Error generating content: 400 Client Error: Bad Request for url: https://api.groq.com/openai/v1/chat/completions</p>',
    'Error: random.Random.uniform() argument after * must be an iterable, not int',
    'Not specified'
]

# Columns to inspect
CHECK_COLS = [
    'job_description',
    'qualification',
    'key_responsibility',
    'about_company',
    'selection_process',
    'company_name',
    'job_role',
    'website_link'
]

def clean_error_rows(df: pd.DataFrame, cols: list, error_strings: list) -> pd.DataFrame:
    """
    Return a DataFrame with any row removed if ANY of the given cols 
    exactly equals any of the error strings.
    """
    # Create a mask for rows that contain any error in any of the specified columns
    error_mask = pd.DataFrame(False, index=df.index, columns=[0])
    
    for error_str in error_strings:
        # Check if any of the specified columns contain this error
        current_error_mask = df[cols].eq(error_str).any(axis=1)
        error_mask[0] = error_mask[0] | current_error_mask
    
    # Return rows that DON'T have errors
    return df.loc[~error_mask[0]]

def analyze_errors(df: pd.DataFrame, cols: list, error_strings: list) -> dict:
    """
    Analyze what types of errors exist in the DataFrame
    """
    error_analysis = {}
    
    for error_str in error_strings:
        error_count = 0
        error_details = {}
        
        for col in cols:
            if col in df.columns:
                col_errors = (df[col] == error_str).sum()
                if col_errors > 0:
                    error_details[col] = col_errors
                    error_count += col_errors
        
        if error_count > 0:
            error_analysis[error_str[:50] + "..."] = {
                'total_occurrences': error_count,
                'columns_affected': error_details
            }
    
    return error_analysis

def process_file(path: str):
    print(f"\nProcessing: {path}")
    
    try:
        # 1) Read CSV (all as strings, handle missing values)
        df = pd.read_csv(path, dtype=str, na_filter=False)
        
        # Check if required columns exist
        missing_cols = [col for col in CHECK_COLS if col not in df.columns]
        if missing_cols:
            print(f"  ⚠️  Missing columns: {missing_cols}")
            available_cols = [col for col in CHECK_COLS if col in df.columns]
            if not available_cols:
                print(f"  ❌ No target columns found. Skipping file.")
                return
            print(f"  ✅ Will check available columns: {available_cols}")
            check_cols = available_cols
        else:
            check_cols = CHECK_COLS

        before = len(df)
        
        # 2) Analyze errors before cleaning
        print(f"  📊 Error Analysis:")
        error_analysis = analyze_errors(df, check_cols, ERROR_TYPES)
        if error_analysis:
            for error_type, details in error_analysis.items():
                print(f"    • {error_type}")
                print(f"      Total occurrences: {details['total_occurrences']}")
                for col, count in details['columns_affected'].items():
                    print(f"        - {col}: {count} rows")
        else:
            print(f"    ✅ No errors found!")
        
        # 3) Clean the data
        df_clean = clean_error_rows(df, check_cols, ERROR_TYPES)
        after = len(df_clean)

        removed = before - after
        print(f"  📈 Results: {before:,} → {after:,} rows (removed {removed:,})")

        # 4) Write cleaned CSV (overwrite original or create new file)
        if removed > 0:
            # Create backup of original
            base, ext = os.path.splitext(path)
            backup_path = f"{base}_backup{ext}"
            if not os.path.exists(backup_path):
                df.to_csv(backup_path, index=False)
                print(f"  💾 Backup created: {backup_path}")
            
            # Write cleaned file
            df_clean.to_csv(path, index=False)
            print(f"  ✅ Cleaned file written to: {path}")
        else:
            print(f"  ✅ No changes needed")
            
    except Exception as e:
        print(f"  ❌ Error processing file: {str(e)}")

def main():
    print("🧹 CSV Error Cleaner")
    print("=" * 50)
    print(f"Looking for these error types:")
    for i, error in enumerate(ERROR_TYPES, 1):
        print(f"  {i}. {error[:80]}{'...' if len(error) > 80 else ''}")
    print(f"In these columns: {', '.join(CHECK_COLS)}")
    
    total_processed = 0
    for csv_path in csv_files:
        if os.path.isfile(csv_path):
            process_file(csv_path)
            total_processed += 1
        else:
            print(f"\n⚠️  File not found: {csv_path}")
    
    print(f"\n🎉 Processing complete! {total_processed} files processed.")

if __name__ == "__main__":
    main()