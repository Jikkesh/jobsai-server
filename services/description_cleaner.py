import re
import unicodedata
from typing import Dict, List
import requests
import os
from dotenv import load_dotenv

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
    # if word_count > max_words:
    #     print(f"📊 Text too long ({word_count} words), summarizing to ~{max_words} words...")
    #     text = summarize_with_llm(text, max_words)
    #     print(f"📝 After summarization: {len(text)} characters, {len(text.split())} words")
    
    return text


def preprocess_with_section_extraction(raw_description: str) -> Dict[str, str]:
    """
    Alternative preprocessing that extracts sections separately.
    Useful if you want to process different parts differently.
    """
    if not raw_description:
        return {"processed_description": ""}
    
    # Clean the text first
    cleaned = clean_encoding_issues(raw_description)
    cleaned = remove_noise_content(cleaned)
    cleaned = clean_whitespace_and_formatting(cleaned)
    
    # Extract sections
    sections = extract_job_sections(cleaned)
    
    # Combine the most important sections for processing
    important_parts = []
    
    if sections["role_description"]:
        important_parts.append(f"Role: {sections['role_description']}")
    
    if sections["responsibilities"]:
        important_parts.append(f"Responsibilities: {sections['responsibilities']}")
    
    if sections["requirements"]:
        important_parts.append(f"Requirements: {sections['requirements']}")
    
    if sections["about_company"]:
        # Limit company info to avoid overwhelming the description
        company_info = sections["about_company"][:500] + "..." if len(sections["about_company"]) > 500 else sections["about_company"]
        important_parts.append(f"About Company: {company_info}")
    
    # If no sections found, use main content
    if not important_parts and sections["main_content"]:
        important_parts.append(sections["main_content"])
    
    processed_text = "\n\n".join(important_parts)
    
    # Final summarization if still too long
    if len(processed_text.split()) > 400:
        processed_text = summarize_with_llm(processed_text, 400)
    
    return {
        "processed_description": processed_text,
        "sections": sections  # Return sections in case you want to use them separately
    }


# Test function to demonstrate the preprocessing
def test_preprocessing():
    """Test the preprocessing with your example data"""
    sample_text = """ð\x9f\x98\x8e \nOur Culture\nQuantum Metric's number one objective is happy people, diverse and inclusive culture.\xa0 Weâ\x80\x99re passionate about empowering our people to become the best version of themselves, offering coaching and training programs designed to accelerate their career in whatever direction they choose.\xa0\xa0\nAs a remote-first company, we understand the importance of building an engaged, diverse, and fun place to work. We hold regular company-wide events, seasonal challenges, and Quantum Metric sponsored local outings when Zoom becomes too much. We also have a number of Employee Resource Groups that provide spaces to discuss, share, and reflect on topics that impact us both inside and outside of work - from being new to SaaS or navigating it as a first-time parent, to overcoming the barriers faced as Black, Hispanic, Asian American and Native Hawaiian/Pacific Islander, LGBTQIA or other underrepresented backgrounds.\n\xa0\xa0\nWe are also passionate about the connections we build with our customers. Youâ\x80\x99ll not only work with some of the worldâ\x80\x99s most recognized brands, but build lasting relationships.\nAt Quantum Metric we value all types of experience and education and donâ\x80\x99t expect you to meet every qualification for this position. We are most interested in the unique perspective you can bring and your ability to uphold our values of passion, persistence, and integrity.\nð\x9f\x9a\x80 About the Role\nAs an Account Executive at Quantum Metric, you will spearhead full life-cycle sales within a greenfield territory, focusing on acquiring and expanding enterprise-level accounts. We seek a highly motivated and results-oriented individual with a passion for continuous learning and significant earning potential. You will build trust and credibility with diverse stakeholders, including Product Managers, Business Analysts, CX Insights Leaders, and DevOps teams across web, iOS, and Android platforms, as well as technology ecosystem partners.\xa0\nAs a key member of our team, you'll leverage your experience in full-cycle enterprise SaaS sales to develop compelling business cases and drive growth. We foster a supportive and collaborative startup culture where you can thrive and make a significant impact.\n\\n\nð\x9f\x94§ Responsibilities\nDriving Enterprise Growth:\n Proactively identify, qualify, and close new enterprise-level accounts\nStrategic Account Development:\n Craft and execute strategic account plans and build a sustainable revenue pipeline\nSolution-Focused Engagement:\n Conduct in-depth discovery sessions to understand customer needs and position our SaaS solutions to achieve their strategic objectives\nNavigating Complex Sales:\n Skillfully manage intricate sales cycles involving multiple stakeholders, adeptly navigating organizational structures and decision-making processes to drive deals to closure\nValue-Driven Partnerships:\n Collaborate with prospective clients to build compelling business cases that demonstrate the tangible ROI and strategic advantages of our SaaS investment\nTrusted Advisor Role: \nCultivate and maintain strong, long-term relationships with key stakeholders, positioning yourself as a trusted advisor and partner committed to their success\nMarket and Product Intelligence:\n Maintain a strong understanding of our evolving SaaS platform, the competitive landscape, and emerging industry trends to effectively communicate our value proposition\nð\x9f\x92¡ Requirements\nProven track record of exceeding sales quotas and closing complex deals\nExperience selling solutions involving multiple stakeholders and long sales cycles\nExperience developing business cases and demonstrating ROI\nStrong understanding of enterprise SaaS sales methodologies\nExcellent communication, presentation, and negotiation skills\nAbility to build and maintain strong relationships with C-level executive\nStrong business acumen and strategic thinking\nAbility to adapt to a rapidly evolving product and market\nProficient with CRM systems (e.g., Salesforce)\nCompensation: Base $130,000-155,000 (OTE is double base, commissions are uncapped)\n\\n\nð\x9f\x8f\x86 \nPerks and Benefits\nThis will be the best group that you ever work with! We support one another through obstacles and succeed as a team. Your hard work will be well rewarded. Most importantly, you'll be strapped to a technology rocket ship bound for greatness! Your success at Quantum Metric will be a milestone in your career.\xa0\nGroup benefits\nMedical, Dental, Vision Insurance (99% Medical base plan paid by the Company)\nFSA, DCFSA, and HSA accounts\nEmployee Assistance Programs (EAP)\nTelehealth options\nVoluntary Life & AD&D, STD, LTD, Critical Illness and Accident\nHealthy Rewards â\x80\x93 Discount Programs\nDiscounts on Pet Insurance\n401k (with employer match) and Options / Equity\xa0\n13 company holidays\nUnlimited Paid Time Off\xa0\nSick leave\nParental/Adoption Leave\xa0\nIn addition to our more traditional benefits, we also offer great perks, a flexible work environment, and numerous resources for professional development and team building.\nPromotional opportunities\xa0\nRewards and recognition programs\xa0\nRobust onboarding and training program\nOne-time stipend for work-at-home employees\nMonthly business expense stipend\nFlexible work environments\nEmployee Discount Program (Perks at Work)\nEmployee Referral Program\xa0\nLead Referral Program\nMacBook and awesome swag delivered to your door\nEncouraging and collaborative culture\xa0\nRECHARGE PROGRAM (after 3 years, disconnect for 3 weeks, no email/slack)\n\xa0\nð\x9f\x90\x89 About Quantum Metric\nAs the leader in Continuous Product Design, Quantum Metric helps organizations put customers at the heart of everything they do. The Quantum Metric platform provides a structured approach to understanding the digital customer journey, enabling organizations to recognize customer needs, quantify the financial impact and prioritize based on the impact to the customer and business'\x80\x99 bottom line.\xa0\nToday, Quantum Metric captures insights from 40 percent of the world'\x80\x99s internet users, supporting nationally recognized brands in ecommerce and retail, travel, financial services and telecommunications. Our customer retention rate is 98%.\xa0\nQuantum Metric has been named to the Inc 5000 and the Deloitte 500 for the last five-consecutive years, and has made the Best Places to Work lists by Glassdoor, BuiltIn, Fast Company and Forbes.\xa0\nIf the above role seems like a match and you're interested in joining a team of people with exceptional potential from diverse backgrounds, perspectives, and life experiences, we want to hear from you!\nThe job description is not designed to cover or contain a comprehensive listing of activities, duties or responsibilities that are required of the employee. Quantum Metric reserves the right to change, edit, and add duties and responsibilities of all job descriptions at any time, at its sole discretion, and to notify the respective employee accordingly.\xa0\nQuantum Metric will only provide offers of employment and all communications regarding employment from an official @quantummetric.com\xa0email address and/or LinkedIn inMail. Quantum does not recruit via channels such as WhatsApp or Telegram, and will not ask for a candidate'\x80\x99s sensitive information and/or any upfront fees/costs during the job application process. Quantum asks that any candidates report any suspicious recruitment efforts to\xa0security@quantummetric.com.\nQuantum Metric is an E-Verify employer: \nhttps://e-verify.uscis.gov/web/media/resourcesContents/E-Verify_Participation_Poster_ES.pdf\nApplicant Privacy Policy: \n\xa0https://www.quantummetric.com/legal/applicant-privacy-policy/\n#LI-REMOTE #BI-Remote\nPlease mention the word **FAME** and tag RMzguNjguMTM0LjE5NA== when applying to show you read the job post completely (#RMzguNjguMTM0LjE5NA==). This is a beta feature to avoid spam applicants. Companies can search these words to find applicants that read this and see they're human."""
    
    print("=" * 80)
    print("TESTING JOB DESCRIPTION PREPROCESSING")
    print("=" * 80)
    
    # Test simple preprocessing
    processed = preprocess_job_description(sample_text)
    
    print("\n" + "=" * 40)
    print("FINAL PROCESSED TEXT:")
    print("=" * 40)
    print(processed)
    print(f"\nFinal length: {len(processed)} characters, {len(processed.split())} words")


if __name__ == "__main__":
    test_preprocessing()