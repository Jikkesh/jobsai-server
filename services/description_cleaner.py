import re
import unicodedata
from typing import Dict, List
import requests
import os
from dotenv import load_dotenv

from services.text_extraction import advanced_rate_limiter

load_dotenv()

def clean_encoding_issues(text: str) -> str:
    """Clean various encoding and unicode issues from text"""
    if not text:
        return ""
    
    # Replace common problematic unicode characters
    replacements = {
        '\u2019': "'",  # right single quotation mark
        '\u2018': "'",  # left single quotation mark
        '\u201c': '"',  # left double quotation mark
        '\u201d': '"',  # right double quotation mark
        '\u2013': '-',  # en dash
        '\u2014': '--', # em dash
        '\u00a0': ' ',  # non-breaking space
        '\u2022': '•',  # bullet point
        '\u00e2\u0080\u0099': "'",  # encoded apostrophe
        '\u00e2\u0080\u009d': '"',  # encoded quote
        '\u00e2\u0080\u009c': '"',  # encoded quote
        'â\x80\x99': "'",
        'â\x80\x9d': '"',
        'â\x80\x9c': '"',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Remove hex-encoded characters like \x9f\x98\x8e
    text = re.sub(r'\\x[0-9a-fA-F]{2}', '', text)
    
    # Remove other problematic unicode patterns
    text = re.sub(r'[\u200b-\u200d\ufeff]', '', text)  # zero-width characters
    
    # Normalize unicode
    try:
        text = unicodedata.normalize('NFKD', text)
    except:
        pass
    
    # Remove emoji patterns (optional - might want to keep some)
    text = re.sub(r'ð[^\s]*', '', text)  # Remove emoji patterns starting with ð
    
    return text


def extract_job_sections(text: str) -> Dict[str, str]:
    """Extract specific sections from job description text"""
    if not text:
        return {"main_content": ""}
    
    sections = {
        "role_description": "",
        "responsibilities": "",
        "requirements": "",
        "benefits": "",
        "about_company": "",
        "main_content": ""
    }
    
    # Define section patterns (case insensitive)
    patterns = {
        "role_description": [
            r"(?:about the role|job description|role overview|position summary)(.*?)(?=responsibilities|requirements|qualifications|benefits|about|$)",
            r"(?:🚀|📋).*?(?:about the role|role)(.*?)(?=responsibilities|requirements|🔧|💡|$)"
        ],
        "responsibilities": [
            r"(?:responsibilities|duties|what you'll do|key tasks)(.*?)(?=requirements|qualifications|benefits|compensation|about|$)",
            r"(?:🔧|📋).*?responsibilities(.*?)(?=💡|requirements|qualifications|$)"
        ],
        "requirements": [
            r"(?:requirements|qualifications|what we're looking for|skills needed)(.*?)(?=benefits|compensation|perks|about|$)",
            r"(?:💡|📋).*?requirements(.*?)(?=🏆|benefits|compensation|$)"
        ],
        "benefits": [
            r"(?:benefits|perks|what we offer|compensation)(.*?)(?=about|equal opportunity|$)",
            r"(?:🏆|💰).*?(?:benefits|perks)(.*?)(?=about|🐉|$)"
        ],
        "about_company": [
            r"(?:about|company|who we are|our company)(.*?)(?=equal opportunity|privacy|applicant|e-verify|$)",
            r"(?:🐉|🏢).*?about(.*?)(?=equal opportunity|privacy|$)"
        ]
    }
    
    # Try to extract each section
    for section_name, section_patterns in patterns.items():
        for pattern in section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match and match.group(1).strip():
                sections[section_name] = match.group(1).strip()
                break
    
    # If no sections found, use the whole text as main content
    if not any(sections[key] for key in sections if key != "main_content"):
        sections["main_content"] = text
    
    return sections


def remove_noise_content(text: str) -> str:
    """Remove common noise patterns from job descriptions"""
    if not text:
        return ""
    
    # Patterns to remove (things that don't add value to job understanding)
    noise_patterns = [
        r'please mention.*?when applying.*?$',  # Application instructions
        r'#[A-Z0-9-_]+',  # Hashtags like #LI-REMOTE
        r'this is a beta feature.*?human\.',  # Beta feature mentions
        r'companies can search.*?$',  # Search instructions
        r'quantum metric will only provide.*?security@quantummetric\.com\.',  # Security warnings
        r'quantum metric is an e-verify.*?$',  # Legal boilerplate
        r'applicant privacy policy.*?$',  # Privacy policy links
        r'https?://[^\s]+',  # URLs (optional - you might want to keep some)
        r'equal opportunity employer.*?$',  # EEO statements
        r'the job description is not designed.*?accordingly\.',  # Job description disclaimers
        r'we are an equal opportunity.*?$',  # More EEO content
    ]
    
    for pattern in noise_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    
    return text.strip()


def clean_whitespace_and_formatting(text: str) -> str:
    """Clean excessive whitespace and formatting issues"""
    if not text:
        return ""
    
    # Remove excessive newlines
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    
    # Remove excessive spaces
    text = re.sub(r' {3,}', ' ', text)
    
    # Clean up line breaks with spaces
    text = re.sub(r'\n +', '\n', text)
    text = re.sub(r' +\n', '\n', text)
    
    # Remove trailing/leading whitespace on each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(line for line in lines if line)
    
    return text.strip()

@advanced_rate_limiter
def summarize_with_llm(text: str, max_words: int = 100) -> str:
    """Use GROQ API to summarize lengthy job descriptions"""
    if not text or len(text.split()) <= max_words:
        return text
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        # Fallback to simple truncation if no API key
        words = text.split()
        if len(words) > max_words:
            return ' '.join(words[:max_words]) + "..."
        return text
    
    system_prompt = (
        f"You are an expert at summarizing job descriptions. "
        f"Extract and summarize the most important information from the job posting in {max_words} words or less. "
        f"Focus on: job title, key responsibilities, required skills, company info, and compensation if mentioned. "
        f"Remove fluff, legal boilerplate, and excessive company culture details. "
        f"Keep the essential information that a job seeker needs to know."
    )
    
    user_prompt = f"Summarize this job description concisely:\n\n{text}"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 500  # Ensure we don't get too long a response
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Warning: LLM summarization failed: {e}")
        # Fallback to truncation
        words = text.split()
        if len(words) > max_words:
            return ' '.join(words[:max_words]) + "..."
        return text


def preprocess_job_description(raw_description: str, max_words: int = 400) -> str:
    """
    Main preprocessing function to clean and prepare job description text.
    
    Args:
        raw_description (str): Raw job description from API
        max_words (int): Maximum words to keep (will summarize if longer)
    
    Returns:
        str: Cleaned and processed job description
    """
    if not raw_description:
        return ""
    
    print(f"📝 Original text length: {len(raw_description)} characters, {len(raw_description.split())} words")
    
    # Step 1: Clean encoding issues
    text = clean_encoding_issues(raw_description)
    print(f"🧹 After encoding cleanup: {len(text)} characters")
    
    # Step 2: Remove noise content  
    text = remove_noise_content(text)
    print(f"🗑️  After noise removal: {len(text)} characters")
    
    # Step 3: Clean whitespace and formatting
    text = clean_whitespace_and_formatting(text)
    print(f"✨ After formatting cleanup: {len(text)} characters")
    
    # Step 4: Check if summarization is needed
    word_count = len(text.split())
    if word_count > max_words:
        print(f"📊 Text too long ({word_count} words), summarizing to ~{max_words} words...")
        text = summarize_with_llm(text, max_words)
        print(f"📝 After summarization: {len(text)} characters, {len(text.split())} words")
    
    return text
