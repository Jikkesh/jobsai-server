import os
import pandas as pd
import markdown

# your existing converter
def markdown_to_html(markdown_content: str) -> str:
    """Convert Markdown to HTML using python-markdown"""
    md = markdown.Markdown(extensions=[
        'markdown.extensions.extra',      # Tables, fenced code blocks, etc.
        'markdown.extensions.nl2br',      # Convert newlines to <br>
        'markdown.extensions.sane_lists', # Better list handling
        'markdown.extensions.toc'         # Table of contents
    ])
    return md.convert(markdown_content or "")

# paths
INPUT_CSV = os.path.join('temp', 'remote_jobs.csv')
OUTPUT_CSV = os.path.join('temp', 'remote_jobs_html.csv')

# columns to convert
MD_COLUMNS = [
    'job_description',
    'key_responsibility',
    'about_company',
    'selection_process',
    'qualification'
]

def convert_markdown_columns(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Apply markdown_to_html to each cell in the given list of columns."""
    for col in cols:
        if col in df.columns:
            df[col] = df[col].apply(markdown_to_html)
        else:
            print(f"Warning: column '{col}' not found in input CSV.")
    return df

def main():
    # 1. Read the original CSV
    df = pd.read_csv(INPUT_CSV, dtype=str)  # read everything as string

    # 2. Convert markdown columns to HTML
    df_html = convert_markdown_columns(df, MD_COLUMNS)

    # 3. Write out the new CSV
    df_html.to_csv(OUTPUT_CSV, index=False)
    print(f"Written HTML‑converted CSV to: {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
