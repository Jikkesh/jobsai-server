import os
import time
import re
from typing import Dict, Optional, Tuple
import requests
import markdown
from dotenv import load_dotenv
import random
from functools import wraps
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

load_dotenv()

DEFAULT_MODEL = "gemma2-9b-it"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

@dataclass
class RateLimitTracker:
    """Track API usage to respect Groq limits"""
    requests_per_minute: int = 0
    requests_per_day: int = 0
    tokens_per_minute: int = 0
    tokens_per_day: int = 0
    minute_window_start: datetime = None
    day_window_start: datetime = None
    
    # Server-reported limits (updated from headers)
    server_rpm_limit: Optional[int] = None
    server_rpd_limit: Optional[int] = None
    server_tpm_limit: Optional[int] = None
    server_tpd_limit: Optional[int] = None
    
    # Server-reported remaining (updated from headers)
    server_remaining_requests: Optional[int] = None
    server_remaining_tokens: Optional[int] = None
    
    # Conservative fallback limits
    MAX_RPM: int = 30
    MAX_RPD: int = 500
    MAX_TPM: int = 15000
    MAX_TPD: int = 100000

# Global rate limit tracker
rate_tracker = RateLimitTracker()

def parse_rate_limit_headers(response) -> Dict[str, Optional[int]]:
    """
    Parse all possible Groq rate limit headers
    Different APIs use different header names
    """
    headers = response.headers
    parsed = {}
    
    # Common rate limit header patterns
    header_patterns = {
        'requests_remaining': [
            'x-ratelimit-remaining-requests',
            'x-ratelimit-remaining',
            'ratelimit-remaining',
            'x-rate-limit-remaining'
        ],
        'tokens_remaining': [
            'x-ratelimit-remaining-tokens', 
            'x-ratelimit-remaining-input-tokens',
            'x-ratelimit-remaining-output-tokens'
        ],
        'requests_limit': [
            'x-ratelimit-limit-requests',
            'x-ratelimit-limit',
            'ratelimit-limit'
        ],
        'tokens_limit': [
            'x-ratelimit-limit-tokens',
            'x-ratelimit-limit-input-tokens', 
            'x-ratelimit-limit-output-tokens'
        ],
        'reset_time': [
            'x-ratelimit-reset-requests',
            'x-ratelimit-reset-tokens',
            'x-ratelimit-reset',
            'ratelimit-reset'
        ],
        'retry_after': [
            'retry-after'
        ]
    }
    
    for category, header_names in header_patterns.items():
        for header_name in header_names:
            if header_name.lower() in [h.lower() for h in headers.keys()]:
                try:
                    # Find the actual header with correct case
                    actual_header = next(h for h in headers.keys() 
                                       if h.lower() == header_name.lower())
                    parsed[category] = int(headers[actual_header])
                    break
                except (ValueError, StopIteration):
                    continue
        
        if category not in parsed:
            parsed[category] = None
    
    return parsed

def update_from_server_headers(response):
    """Update rate limit tracker with server-reported values"""
    global rate_tracker
    
    headers_data = parse_rate_limit_headers(response)
    
    # Update server limits if provided
    if headers_data['requests_limit']:
        rate_tracker.server_rpm_limit = headers_data['requests_limit']
    if headers_data['tokens_limit']:
        rate_tracker.server_tpm_limit = headers_data['tokens_limit']
    
    # Update remaining counts
    if headers_data['requests_remaining'] is not None:
        rate_tracker.server_remaining_requests = headers_data['requests_remaining']
    if headers_data['tokens_remaining'] is not None:
        rate_tracker.server_remaining_tokens = headers_data['tokens_remaining']
    
    # Log comprehensive rate limit info
    print(f"\n📊 RATE LIMIT STATUS FROM SERVER:")
    print(f"  🔢 Remaining Requests: {headers_data['requests_remaining'] or 'Unknown'}")
    print(f"  🎯 Remaining Tokens: {headers_data['tokens_remaining'] or 'Unknown'}")
    print(f"  📝 Request Limit: {headers_data['requests_limit'] or 'Unknown'}")
    print(f"  📊 Token Limit: {headers_data['tokens_limit'] or 'Unknown'}")
    
    if headers_data['reset_time']:
        reset_datetime = datetime.fromtimestamp(headers_data['reset_time'])
        print(f"  🔄 Resets at: {reset_datetime.strftime('%H:%M:%S')}")
    
    if headers_data['retry_after']:
        print(f"  ⏳ Retry after: {headers_data['retry_after']} seconds")

def get_effective_limits() -> Tuple[int, int, int, int]:
    """
    Get effective rate limits, preferring server-reported values
    Returns: (rpm, rpd, tpm, tpd)
    """
    global rate_tracker
    
    # Use server limits if available, otherwise fallback to conservative defaults
    effective_rpm = rate_tracker.server_rpm_limit or rate_tracker.MAX_RPM
    effective_rpd = rate_tracker.server_rpd_limit or rate_tracker.MAX_RPD
    effective_tpm = rate_tracker.server_tpm_limit or rate_tracker.MAX_TPM
    effective_tpd = rate_tracker.server_tpd_limit or rate_tracker.MAX_TPD
    
    return effective_rpm, effective_rpd, effective_tpm, effective_tpd

def smart_rate_limit_check(estimated_tokens: int = 1000) -> Optional[float]:
    """
    Intelligent rate limit checking using both local tracking and server data
    """
    global rate_tracker
    reset_windows_if_needed()
    
    effective_rpm, effective_rpd, effective_tpm, effective_tpd = get_effective_limits()
    delays = []
    
    # If we have server-reported remaining counts, use those for more accurate checks
    if rate_tracker.server_remaining_requests is not None:
        if rate_tracker.server_remaining_requests <= 0:
            print("⚠️ Server reports no remaining requests!")
            delays.append(60)  # Wait a minute
    else:
        # Fallback to local tracking
        if rate_tracker.requests_per_minute >= effective_rpm:
            time_until_reset = 60 - (datetime.now() - rate_tracker.minute_window_start).seconds
            delays.append(time_until_reset)
    
    if rate_tracker.server_remaining_tokens is not None:
        if rate_tracker.server_remaining_tokens < estimated_tokens:
            print(f"⚠️ Server reports insufficient tokens! Need: {estimated_tokens}, Have: {rate_tracker.server_remaining_tokens}")
            delays.append(60)
    else:
        # Fallback to local tracking
        if rate_tracker.tokens_per_minute + estimated_tokens > effective_tpm:
            time_until_reset = 60 - (datetime.now() - rate_tracker.minute_window_start).seconds
            delays.append(time_until_reset)
    
    # Check daily limits (usually only local tracking available)
    if rate_tracker.requests_per_day >= effective_rpd:
        time_until_reset = 86400 - (datetime.now() - rate_tracker.day_window_start).seconds
        delays.append(time_until_reset)
    
    if rate_tracker.tokens_per_day + estimated_tokens > effective_tpd:
        time_until_reset = 86400 - (datetime.now() - rate_tracker.day_window_start).seconds
        delays.append(time_until_reset)
    
    return max(delays) if delays else None

def reset_windows_if_needed():
    """Reset rate limit windows if time has passed"""
    global rate_tracker
    now = datetime.now()
    
    # Reset minute window
    if (rate_tracker.minute_window_start is None or 
        now - rate_tracker.minute_window_start >= timedelta(minutes=1)):
        rate_tracker.requests_per_minute = 0
        rate_tracker.tokens_per_minute = 0
        rate_tracker.minute_window_start = now
    
    # Reset day window
    if (rate_tracker.day_window_start is None or 
        now - rate_tracker.day_window_start >= timedelta(days=1)):
        rate_tracker.requests_per_day = 0
        rate_tracker.tokens_per_day = 0
        rate_tracker.day_window_start = now

def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 characters for English)"""
    return len(text) // 4 + 100

def advanced_rate_limiter(func):
    """Advanced decorator with server header integration"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        base_delay = 15
        
        for attempt in range(max_retries):
            try:
                # Pre-flight check with server data integration
                prompt_text = kwargs.get('prompt', args[0] if args else '')
                estimated_tokens = estimate_tokens(prompt_text)
                
                required_delay = smart_rate_limit_check(estimated_tokens)
                # if required_delay:
                #     print(f"🚦 Rate limit protection: waiting {required_delay:.1f}s...")
                #     time.sleep(required_delay + random.uniform(2, 8))
                
                # Make the API call
                result = func(*args, **kwargs)
                return result
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    # Parse headers for precise retry information
                    headers_data = parse_rate_limit_headers(e.response)
                    
                    if headers_data['retry_after']:
                        wait_time = headers_data['retry_after'] + random.uniform(5, 15)
                        print(f"🔄 429 Error: Server requests {headers_data['retry_after']}s wait, using {wait_time:.1f}s")
                    else:
                        wait_time = base_delay * (2 ** attempt) + random.uniform(10, 30)
                        print(f"🔄 429 Error: Exponential backoff {wait_time:.1f}s")
                    
                    time.sleep(wait_time)
                    continue
                else:
                    raise e
            except Exception as e:
                raise e
        
        raise Exception(f"Failed after {max_retries} attempts due to rate limiting")
    
    return wrapper

@advanced_rate_limiter
def call_groq_api(prompt: str, system_prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Enhanced GROQ API call with comprehensive header processing"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "AI enhancement not available - missing GROQ_API_KEY"

    headers = {
        "Authorization": f"Bearer {api_key}", 
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "top_p": 0.95,
        "temperature": 0.1,
        "max_tokens": 1000
    }
    
    print(f"🌐 API call to GROQ (estimated {estimate_tokens(prompt)} tokens)...")
    response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=120)
    
    # ENHANCED: Comprehensive header processing
    update_from_server_headers(response)
    
    response.raise_for_status()
    
    result = response.json()["choices"][0]["message"]["content"]
    
    # Update local counters
    actual_tokens = len(result) // 4 + estimate_tokens(prompt)
    rate_tracker.requests_per_minute += 1
    rate_tracker.requests_per_day += 1
    rate_tracker.tokens_per_minute += actual_tokens
    rate_tracker.tokens_per_day += actual_tokens
    
    print(f"✅ API call successful ({len(result)} chars, ~{actual_tokens} tokens)")
    return result

def display_comprehensive_limits():
    """Display both local tracking and server-reported limits"""
    global rate_tracker
    reset_windows_if_needed()
    
    effective_rpm, effective_rpd, effective_tpm, effective_tpd = get_effective_limits()
    
    print("\n" + "=" * 80)
    print("📊 COMPREHENSIVE RATE LIMIT STATUS")
    print("=" * 80)
    
    print("🏠 LOCAL TRACKING:")
    print(f"  Requests this minute: {rate_tracker.requests_per_minute}/{effective_rpm}")
    print(f"  Requests today: {rate_tracker.requests_per_day}/{effective_rpd}")
    print(f"  Tokens this minute: {rate_tracker.tokens_per_minute:,}/{effective_tpm:,}")
    print(f"  Tokens today: {rate_tracker.tokens_per_day:,}/{effective_tpd:,}")
    
    print("\n🌐 SERVER REPORTED:")
    print(f"  Remaining Requests: {rate_tracker.server_remaining_requests or 'Unknown'}")
    print(f"  Remaining Tokens: {rate_tracker.server_remaining_tokens or 'Unknown'}")
    print(f"  Server RPM Limit: {rate_tracker.server_rpm_limit or 'Unknown'}")
    print(f"  Server TPM Limit: {rate_tracker.server_tpm_limit or 'Unknown'}")
    
    print("=" * 80)
    
def markdown_to_html(markdown_content: str) -> str:
    """Convert Markdown to HTML using python-markdown"""
    md = markdown.Markdown(extensions=[
        'markdown.extensions.extra',      # Tables, fenced code blocks, etc.
        'markdown.extensions.nl2br',      # Convert newlines to <br>
        'markdown.extensions.sane_lists', # Better list handling
        'markdown.extensions.toc'         # Table of contents
    ])
    return md.convert(markdown_content)

def generate_ai_enhanced_content(job_description: str, company_name: str, job_title: str, 
                         qualifications: str = "") -> Dict[str, str]:
    """Generate AI-enhanced content with comprehensive rate limit monitoring"""
    
    load_rate_limit_state()
    
    print("🛡️ ULTRA-SAFE GROQ API USAGE WITH SERVER MONITORING")
    display_comprehensive_limits()
    
    # Define system prompts for each section
    SYSTEM_PROMPTS = {
        "job_description": (
            "You are an AI Agent specializing in writing comprehensive job descriptions for job portals. "
            "Generate a detailed, thorough job description based on the provided information up to 150 words long. "
            "Structure your response with clear headings and well-organized sections. "
            "Use professional, objective tone. Format in Markdown."
        ),
        "key_responsibility": (
            "You are an AI Agent creating key responsibilities sections for job portals. "
            "Generate comprehensive duties list up to 150 words long. "
            "Structure with clear headings. Use objective voice. Format in Markdown."
        ),
        "about_company": (
            "You are an AI Agent crafting 'About the Company' sections for job portals. "
            "Create detailed company profile up to 150 words long. "
            "Use third-person tone. Format in Markdown."
        ),
        "selection_process": (
            "You are an AI Agent creating selection processes for job portals. "
            "Generate comprehensive hiring workflow up to 150 words long. "
            "Use third-person voice. Format in Markdown."
        ),
        "qualification": (
            "You are an AI Agent creating qualifications sections for job portals. "
            "Generate detailed requirements breakdown up to 150 words long. "
            "Use neutral tone. Format in Markdown."
        )
    }
    
    results = {}
    sections = list(SYSTEM_PROMPTS.items())
    
    # Extended delays between sections
    inter_section_delay = (30, 60)  # 30-60 seconds between sections
    
    for i, (topic, system_prompt) in enumerate(sections, 1):
        print(f"\n📝 Generating {topic.replace('_', ' ').title()} ({i}/{len(sections)})...")
        print(f"Current server status before generation:")
        display_comprehensive_limits()
        
        try:
            # Construct prompt
            prompt = f"Company: {company_name}\nJob Title: {job_title}\nDescription: {job_description}\nQualifications: {qualifications}\n\nTask: Create {topic.replace('_', ' ')} content."
            
            # Generate content with enhanced rate limiting
            raw_content = call_groq_api(prompt, system_prompt)
            results[topic] = markdown_to_html(raw_content)
            
            print(f"✅ {topic} completed successfully")
            
            # Extended delay between sections within the same job
            if i < len(sections):
                delay = random.uniform(*inter_section_delay)
                print(f"⏳ Section cooling period: {delay:.1f}s...")
                time.sleep(delay)
                
        except Exception as e:
            print(f"❌ Error generating {topic}: {str(e)}")
            results[topic] = f"Error: {str(e)}"
    
    # Save state after processing
    save_rate_limit_state()
    return results

def safe_batch_generate(jobs_data: list, inter_job_delay_range: tuple = (60, 120)) -> list:
    """
    Ultra-safe batch generation with server header monitoring and extended delays
    
    Args:
        jobs_data: List of job dictionaries
        inter_job_delay_range: Tuple of (min, max) seconds between jobs
    """
    print(f"🛡️ ULTRA-SAFE BATCH MODE WITH SERVER MONITORING: {len(jobs_data)} jobs")
    print(f"⏱️ Using {inter_job_delay_range[0]}-{inter_job_delay_range[1]}s delays between jobs")
    
    enhanced_jobs = []
    
    for idx, job in enumerate(jobs_data, 1):
        print(f"\n{'='*80}")
        print(f"🏢 PROCESSING JOB {idx}/{len(jobs_data)}")
        print(f"Company: {job.get('company_name', 'Unknown')}")
        print(f"Role: {job.get('job_title', 'Unknown')}")
        
        # Display comprehensive limits before processing each job
        display_comprehensive_limits()
        
        try:
            # Process job with enhanced rate limiting and server monitoring
            enhanced_content = generate_ai_enhanced_content(
                job_description=job.get('job_description', ''),
                company_name=job.get('company_name', ''),
                job_title=job.get('job_title', ''),
                qualifications=job.get('qualifications', '')
            )
            
            enhanced_job = {**job, **enhanced_content}
            enhanced_jobs.append(enhanced_job)
            
            print(f"✅ Job {idx} completed successfully")
            print("Final status after job completion:")
            display_comprehensive_limits()
            
            # Extended delay between jobs
            if idx < len(jobs_data):
                delay = random.uniform(*inter_job_delay_range)
                print(f"🕐 Extended cooling period: {delay:.1f}s before next job...")
                time.sleep(delay)
                
        except Exception as e:
            print(f"❌ Failed to process job {idx}: {str(e)}")
            enhanced_jobs.append(job)
    
    return enhanced_jobs

def save_rate_limit_state():
    """Save comprehensive rate limit state including server data"""
    state = {
        'requests_per_minute': rate_tracker.requests_per_minute,
        'requests_per_day': rate_tracker.requests_per_day,
        'tokens_per_minute': rate_tracker.tokens_per_minute,
        'tokens_per_day': rate_tracker.tokens_per_day,
        'minute_window_start': rate_tracker.minute_window_start.isoformat() if rate_tracker.minute_window_start else None,
        'day_window_start': rate_tracker.day_window_start.isoformat() if rate_tracker.day_window_start else None,
        'server_rpm_limit': rate_tracker.server_rpm_limit,
        'server_rpd_limit': rate_tracker.server_rpd_limit,
        'server_tpm_limit': rate_tracker.server_tpm_limit,
        'server_tpd_limit': rate_tracker.server_tpd_limit,
        'server_remaining_requests': rate_tracker.server_remaining_requests,
        'server_remaining_tokens': rate_tracker.server_remaining_tokens
    }
    
    with open('rate_limit_state.json', 'w') as f:
        json.dump(state, f)

def load_rate_limit_state():
    """Load comprehensive rate limit state including server data"""
    global rate_tracker
    try:
        with open('rate_limit_state.json', 'r') as f:
            state = json.load(f)
            
        rate_tracker.requests_per_minute = state.get('requests_per_minute', 0)
        rate_tracker.requests_per_day = state.get('requests_per_day', 0)
        rate_tracker.tokens_per_minute = state.get('tokens_per_minute', 0)
        rate_tracker.tokens_per_day = state.get('tokens_per_day', 0)
        
        # Load server data
        rate_tracker.server_rpm_limit = state.get('server_rpm_limit')
        rate_tracker.server_rpd_limit = state.get('server_rpd_limit')
        rate_tracker.server_tpm_limit = state.get('server_tpm_limit')
        rate_tracker.server_tpd_limit = state.get('server_tpd_limit')
        rate_tracker.server_remaining_requests = state.get('server_remaining_requests')
        rate_tracker.server_remaining_tokens = state.get('server_remaining_tokens')
        
        if state.get('minute_window_start'):
            rate_tracker.minute_window_start = datetime.fromisoformat(state['minute_window_start'])
        if state.get('day_window_start'):
            rate_tracker.day_window_start = datetime.fromisoformat(state['day_window_start'])
            
    except FileNotFoundError:
        pass  # Fresh start

# # Example usage
# if __name__ == "__main__":
#     # Load previous state
#     load_rate_limit_state()
    
#     print("🛡️ ENHANCED GROQ API WITH COMPLETE JOB CONTENT GENERATION")
#     display_comprehensive_limits()
    
#     # Example single job
#     job_data = {
#         "job_description": "Sales Development Representative role focusing on mental health professionals",
#         "company_name": "Heard",
#         "job_title": "Sales Development Representative",
#         "qualifications": "Bachelor's degree, 1-2 years sales experience"
#     }
    
#     print("\n🔥 GENERATING SINGLE JOB CONTENT:")
#     content = generate_ai_enhanced_content(**job_data)
    
#     print("\n📋 Generated Content Preview:")
#     for section, text in content.items():
#         print(f"\n{section.upper()}:")
#         print(f"{text[:100]}..." if len(text) > 100 else text)
    
#     # Example batch processing
#     print("\n\n🔥 EXAMPLE BATCH PROCESSING:")
#     batch_jobs = [
#         {
#             "job_description": "Frontend developer for e-commerce platform",
#             "company_name": "TechCorp",
#             "job_title": "Senior Frontend Developer",
#             "qualifications": "5+ years React experience, TypeScript"
#         },
#         {
#             "job_description": "Backend API development and database management",
#             "company_name": "DataFlow Inc",
#             "job_title": "Backend Engineer",
#             "qualifications": "Python, FastAPI, PostgreSQL experience"
#         }
#     ]
    
#     # Uncomment to test batch processing
#     # enhanced_batch = safe_batch_generate(batch_jobs, (90, 150))  # Longer delays for safety
#     # print(f"\n✅ Batch processing completed: {len(enhanced_batch)} jobs processed")
    
#     # Save final state
#     save_rate_limit_state()
    
#     print("\n🎉 Complete job content generation system ready!")
#     display_comprehensive_limits()