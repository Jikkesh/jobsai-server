import os
import time
import re
from typing import Dict
import requests
import markdown
import mistune
from dotenv import load_dotenv
import random
from functools import wraps

load_dotenv()

DEFAULT_MODEL = "gemma2-9b-it"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Rate limiting configuration
RATE_LIMIT_CONFIG = {
    'base_delay': 5,      # Base delay between requests (seconds)
    'max_retries': 5,      # Maximum number of retries
    'backoff_factor': 2,   # Exponential backoff multiplier
    'jitter_range': (1, 3) # Random jitter to avoid thundering herd
}

def rate_limited_retry(func):
    """Decorator to handle rate limiting with exponential backoff and jitter"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        config = RATE_LIMIT_CONFIG
        last_exception = None
        
        for attempt in range(config['max_retries']):
            try:
                # Add base delay before each attempt (except first)
                if attempt > 0:
                    # Calculate exponential backoff with jitter
                    delay = config['base_delay'] * (config['backoff_factor'] ** (attempt - 1))
                    jitter = random.uniform(*config['jitter_range'])
                    total_delay = delay + jitter
                    
                    print(f"🔄 Rate limited. Waiting {total_delay:.1f}s before retry {attempt}/{config['max_retries']-1}...")
                    time.sleep(total_delay)
                
                return func(*args, **kwargs)
                
            except requests.exceptions.HTTPError as e:
                last_exception = e
                if e.response.status_code == 429:
                    print(f"⚠️  Rate limit hit (attempt {attempt + 1}/{config['max_retries']})")
                    
                    # Check if response has Retry-After header
                    retry_after = e.response.headers.get('Retry-After')
                    if retry_after and attempt < config['max_retries'] - 1:
                        wait_time = int(retry_after) + random.uniform(1, 3)
                        print(f"🕐 Server requested {retry_after}s wait. Waiting {wait_time:.1f}s...")
                        time.sleep(wait_time)
                    continue
                else:
                    # For non-rate-limit errors, re-raise immediately
                    raise e
            except Exception as e:
                # For other exceptions, re-raise immediately
                raise e
        
        # If all retries exhausted, raise the last exception
        print(f"❌ All {config['max_retries']} attempts failed due to rate limiting")
        raise last_exception
    
    return wrapper


SYSTEM_PROMPTS = {
    "job_description": (
        "You are an AI Agent specializing in writing comprehensive job descriptions for job portals. "
        "Generate a detailed, thorough job description based on the provided information up to 200 words long. "
        "If some details are missing, supplement extensively with relevant industry-standard information. "
        "Structure your response with multiple clear headings and well-organized sections."
        "Use professional, objective tone and third-person voice. Provide specific examples and context where relevant. "
        "Format your response in Markdown with proper headings, bullet points, and detailed explanations. "
        "Do not include any direct calls-to-action or first-person phrasing. Make the content rich and informative."
    ),

    "key_responsibility": (
        "You are an AI Agent specializing in creating detailed key responsibilities sections for job portals. "
        "Generate a comprehensive list of duties and responsibilities that is up to 200 words long. "
        "Extract and expand upon the key duties based on the provided text. "
        "If limited information is provided, generate extensive typical tasks for the role based on industry standards. "
        "Structure your response with multiple clear headings and well-organized sections."
        "For each responsibility, provide detailed explanations, context, and expected outcomes. "
        "Use objective, third-person voice with specific examples and measurable objectives where possible. "
        "Format your response in Markdown with detailed bullet points and explanations."
    ),
    
    "about_company": (
        "You are an AI Agent crafting comprehensive 'About the Company' sections for job portals. "
        "Create a detailed company profile that is up to 200 words long. "
        "Use the provided information and expand with relevant industry knowledge and best practices. "
        "If minimal details are supplied, create a comprehensive company profile using general best practices. "
        "Structure your response with multiple clear headings and well-organized sections."
        "Write in third-person, objective tone with rich details about mission, culture, market position, and growth trajectory. "
        "Format your response in Markdown with appropriate headings and comprehensive paragraphs."
    ),
    
    "selection_process": (
        "You are an AI Agent creating detailed selection processes for job portals. "
        "Generate a comprehensive, multi-stage hiring workflow that is up to 200 words long. "
        "Outline a realistic and thorough selection process typical for the role and industry. "
        "Structure your response with multiple clear headings and well-organized sections."
        "For each stage, provide detailed explanations of: what happens, who's involved, duration, evaluation criteria, and candidate expectations. "
        "Use third-person, objective voice with specific timelines and processes. "
        "If no specifics are given, describe comprehensive best-practice steps with industry-standard procedures. "
        "Format your response in Markdown with numbered steps, detailed explanations, and timelines."
    ),
    
    "qualification": (
        "You are an AI Agent creating comprehensive qualifications sections for job portals. "
        "Generate a detailed breakdown of qualifications and requirements that is up to 200 words long. "
        "Extract and extensively elaborate on required skills and criteria from the provided text. "
        "If minimal qualifications are listed, generate comprehensive typical requirements for the role. "
        "Structure your response with multiple clear headings and well-organized sections."
        "For each qualification, provide detailed explanations of why it's important, how it applies to the role, and what level of proficiency is expected. "
        "Maintain a neutral, third-person tone with specific examples and contexts. "
        "Format your response in Markdown with clear sections and comprehensive explanations."
    )
}


def construct_prompt(topic: str, job_description: str, company_name: str, job_title: str, qualifications: str) -> str:
    """Construct topic-specific prompts with relevant information"""
    base_info = f"Company Name: {company_name}\nJob Title: {job_title}\n"

    if topic == "job_description":
        return f"""{base_info}
Job Description Information:
{job_description or 'No detailed description provided'}

Task: Create a complete job description based on the above information, using industry-standard details where needed."""

    elif topic == "key_responsibility":
        return f"""{base_info}
Job Description Information:
{job_description or 'No responsibilities listed'}

Task: Extract or generate key responsibilities for this position. Group similar tasks under subheadings."""

    elif topic == "about_company":
        return f"""{base_info}

Task: Create an 'About the Company' section. Use provided info or general company profile conventions if missing."""

    elif topic == "selection_process":
        return f"""{base_info}
Job Description Information:
{job_description or 'No selection details provided'}

Task: Outline a multi-stage selection process appropriate for this role and industry."""

    elif topic == "qualification":
        return f"""{base_info}Qualifications & Requirements: {qualifications or 'Not specified'}

Task: List and categorize necessary qualifications. Use typical criteria if none supplied."""

    else:
        return f"""{base_info}
Job Description Information:
{job_description}

Task: Process the above information for the topic: {topic}"""


def markdown_to_html(markdown_content: str) -> str:
    """Convert Markdown to HTML using python-markdown"""
    md = markdown.Markdown(extensions=[
        'markdown.extensions.extra',      # Tables, fenced code blocks, etc.
        'markdown.extensions.nl2br',      # Convert newlines to <br>
        'markdown.extensions.sane_lists', # Better list handling
        'markdown.extensions.toc'         # Table of contents
    ])
    return md.convert(markdown_content)


def mistune_to_html(markdown_content: str) -> str:
    """Convert Markdown to HTML using mistune"""
    renderer = mistune.HTMLRenderer()
    md = mistune.Markdown(renderer=renderer)
    return md(markdown_content)


def simple_text_to_html(text_content: str) -> str:
    """Convert simple structured text to HTML"""
    lines = text_content.split('\n')
    html_lines = []
    in_list = False
    in_ordered_list = False
    
    for line in lines:
        line = line.strip()
        if not line:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if in_ordered_list:
                html_lines.append('</ol>')
                in_ordered_list = False
            html_lines.append('<br>')
            continue
            
        # Handle headings
        if line.startswith('# '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if in_ordered_list:
                html_lines.append('</ol>')
                in_ordered_list = False
            html_lines.append(f'<h1>{line[2:].strip()}</h1>')
        elif line.startswith('## '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if in_ordered_list:
                html_lines.append('</ol>')
                in_ordered_list = False
            html_lines.append(f'<h2>{line[3:].strip()}</h2>')
        elif line.startswith('### '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if in_ordered_list:
                html_lines.append('</ol>')
                in_ordered_list = False
            html_lines.append(f'<h3>{line[4:].strip()}</h3>')
        # Handle bullet points
        elif line.startswith('- ') or line.startswith('* '):
            if in_ordered_list:
                html_lines.append('</ol>')
                in_ordered_list = False
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            html_lines.append(f'<li>{line[2:].strip()}</li>')
        # Handle numbered lists
        elif re.match(r'^\d+\.\s', line):
            content = re.sub(r'^\d+\.\s', '', line)
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if not in_ordered_list:
                html_lines.append('<ol>')
                in_ordered_list = True
            html_lines.append(f'<li>{content}</li>')
        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if in_ordered_list:
                html_lines.append('</ol>')
                in_ordered_list = False
            if line:
                html_lines.append(f'<p>{line}</p>')
    
    if in_list:
        html_lines.append('</ul>')
    if in_ordered_list:
        html_lines.append('</ol>')
    
    return '\n'.join(html_lines)


@rate_limited_retry
def call_groq_api(prompt: str, system_prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Make a call to the GROQ API to generate content with rate limiting"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "AI enhancement not available - missing GROQ_API_KEY"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "top_p": 0.95,
        "temperature": 0.1
    }
    
    print(f"🌐 Making API call to GROQ...")
    response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=60)
    response.raise_for_status()  # This will raise HTTPError for 4xx/5xx responses
    
    result = response.json()["choices"][0]["message"]["content"]
    print(f"✅ API call successful, received {len(result)} characters")
    return result


def generate_ai_enhanced_content(job_description: str, company_name: str, job_title: str, 
                                qualifications: str = "", converter: str = "markdown") -> Dict[str, str]:
    """
    Main function to generate all five job content sections in HTML format with rate limiting.
    
    Args:
        job_description (str): Basic job description or role information
        company_name (str): Name of the company
        job_title (str): Job title/position name
        qualifications (str, optional): Specific qualifications if any. Defaults to "".
        converter (str, optional): HTML converter to use ('markdown', 'mistune', 'simple'). Defaults to "markdown".
    
    Returns:
        Dict[str, str]: Dictionary containing all five sections with HTML content
    """
    
    print(f"🚀 Starting content generation for: {job_title} at {company_name}")
    print("=" * 60)
    
    results = {}
    total_sections = len(SYSTEM_PROMPTS)
    
    # Process each section with enhanced rate limiting
    for i, (topic, system_prompt) in enumerate(SYSTEM_PROMPTS.items(), 1):
        print(f"📝 Generating {topic.replace('_', ' ').title()} ({i}/{total_sections})...")
        
        try:
            # Get content from LLM with rate limiting
            dynamic_prompt = construct_prompt(topic, job_description, company_name, job_title, qualifications)
            raw_content = call_groq_api(dynamic_prompt, system_prompt)
            
            # Convert to HTML based on chosen converter
            if converter == "markdown":
                html_content = markdown_to_html(raw_content)
            elif converter == "mistune":
                html_content = mistune_to_html(raw_content)
            elif converter == "simple":
                html_content = simple_text_to_html(raw_content)
            else:
                html_content = raw_content  # Keep as-is
                
            results[topic] = html_content
            print(f"✅ {topic.replace('_', ' ').title()} completed ({len(html_content)} characters)")
            
            # Enhanced inter-request delay with progress indication
            if i < total_sections:  # Don't wait after the last request
                base_delay = RATE_LIMIT_CONFIG['base_delay']
                jitter = random.uniform(1, 3)
                total_delay = base_delay + jitter
                
                print(f"⏳ Waiting {total_delay:.1f}s before next section to respect rate limits...")
                print(f"📊 Progress: {i}/{total_sections} sections completed ({(i/total_sections)*100:.1f}%)")
                time.sleep(total_delay)
                print("-" * 60)
            
        except Exception as e:
            error_msg = f"❌ Error generating {topic}: {str(e)}"
            print(error_msg)
            results[topic] = f"<p>Error generating content: {str(e)}</p>"
            
            # Continue to next section even if one fails
            print("⚠️  Continuing with next section...")
    
    print("=" * 60)
    print(f"🎉 Content generation completed! Generated {len(results)} sections.")
    
    return results


def batch_generate_with_smart_delays(jobs_data: list) -> list:
    """
    Generate content for multiple jobs with intelligent delay management
    
    Args:
        jobs_data: List of job dictionaries with keys: job_description, company_name, job_title, qualifications
        
    Returns:
        List of enhanced job dictionaries with generated content
    """
    print(f"🎯 Starting batch generation for {len(jobs_data)} jobs")
    enhanced_jobs = []
    
    for idx, job in enumerate(jobs_data, 1):
        print(f"\n{'='*80}")
        print(f"🏢 PROCESSING JOB {idx}/{len(jobs_data)}")
        print(f"Company: {job.get('company_name', 'Unknown')}")
        print(f"Role: {job.get('job_title', 'Unknown')}")
        print(f"{'='*80}")
        
        try:
            enhanced_content = generate_ai_enhanced_content(
                job_description=job.get('job_description', ''),
                company_name=job.get('company_name', ''),
                job_title=job.get('job_title', ''),
                qualifications=job.get('qualifications', '')
            )
            
            # Merge original job data with enhanced content
            enhanced_job = {**job, **enhanced_content}
            enhanced_jobs.append(enhanced_job)
            
            print(f"✅ Job {idx} completed successfully")
            
            # Add longer delay between jobs to be extra safe
            if idx < len(jobs_data):
                inter_job_delay = 15 + random.uniform(3, 7)  # 15-22 seconds between jobs
                print(f"🕐 Waiting {inter_job_delay:.1f}s before next job...")
                time.sleep(inter_job_delay)
                
        except Exception as e:
            print(f"❌ Failed to process job {idx}: {str(e)}")
            # Add the original job data even if enhancement failed
            enhanced_jobs.append(job)
    
    print(f"\n🎊 BATCH PROCESSING COMPLETE!")
    print(f"✅ Successfully processed: {len(enhanced_jobs)} jobs")
    return enhanced_jobs


def save_content_to_files(content_dict: Dict[str, str], output_dir: str = "job_content_output"):
    """Save each content section to separate HTML files."""
    import os
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    for section_name, content in content_dict.items():
        filename = f"{section_name}.html"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"💾 Saved {section_name} to {filepath}")


def display_content_summary(content_dict: Dict[str, str]):
    """Display a summary of generated content."""
    print("\n" + "=" * 60)
    print("📊 CONTENT GENERATION SUMMARY")
    print("=" * 60)
    
    total_chars = 0
    for section_name, content in content_dict.items():
        char_count = len(content)
        word_count = len(content.split())
        total_chars += char_count
        
        print(f"📄 {section_name.replace('_', ' ').title():<25} {char_count:>6} chars | {word_count:>4} words")
    
    print("-" * 60)
    print(f"📈 Total Content Generated: {total_chars:,} characters")
    print("=" * 60)


# Example usage and testing
if __name__ == "__main__":
    # Example: Basic usage with enhanced rate limiting
    print("🔥 ENHANCED JOB CONTENT GENERATION WITH RATE LIMITING")
    job_desc = (
        "Join Heard as a Sales Development Representative (SDR) and help connect mental health professionals "
        "with resources to grow their practices. This role involves prospecting, lead generation, and "
        "supporting the sales team in building relationships with potential clients."
    )
    
    content = generate_ai_enhanced_content(
        job_description=job_desc,
        company_name="Heard",
        job_title="Sales Development Representative",
        qualifications="Bachelor's degree in Business, Marketing, or related field. 1-2 years sales experience preferred.",
    )
    
    # Display summary
    display_content_summary(content)