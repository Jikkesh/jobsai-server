import os
import requests
from typing import Dict, Optional
import json

# Constants for the API integration
DEFAULT_MODEL = "llama3-70b-8192"  # Using Llama3 70B as default model
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# System prompts for each topic
SYSTEM_PROMPTS = {
    "job_description": """You are an expert HR advisor specializing in job descriptions. 
    Extract and summarize the main aspects of the provided job description.
    Format your response with a clear heading, followed by bullet points for key aspects of the role.
    Make it easy to read, professional, and concise.""",
    
    "key_responsibilities": """You are an expert HR advisor specializing in job responsibilities.
    Extract and structure the key responsibilities from the job description.
    Format your response with a clear 'Key Responsibilities' heading, followed by bullet points.
    Each bullet point should be concise, start with an action verb, and clearly communicate a specific responsibility.""",
    
    "about_company": """You are an expert company researcher.
    Extract and summarize information about the company from the job description.
    Format your response with an 'About the Company' heading, followed by organized paragraphs or bullet points.
    Include information about the company's mission, values, industry, size, culture, and any other relevant details mentioned.""",
    
    "selection_process": """You are an expert HR advisor specializing in recruitment processes.
    Extract and structure information about the selection process from the job description.
    Format your response with a 'Selection Process' heading, followed by ordered steps or bullet points.
    Include details on interviews, assessments, timeline, and what candidates can expect.
    If minimal information is provided, make reasonable inferences based on industry standards.""",
    
    "qualification": """You are an expert HR advisor specializing in job qualifications.
    Extract and structure the required and preferred qualifications from the job description.
    Format your response with a 'Qualifications' heading, followed by bullet points in categories like:
    - Education Requirements
    - Experience Requirements
    - Technical Skills
    - Soft Skills
    Use clear, concise language and maintain the original requirements."""
}

def call_groq_api(api_key: str, prompt: str, system_prompt: str, model: str = DEFAULT_MODEL) -> str:
    """
    Make a call to the GROQ API to generate content
    
    Args:
        api_key: GROQ API key
        prompt: The job description text
        system_prompt: The system instructions for the specific section
        model: Model name to use
        
    Returns:
        The generated text
    """
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
        "temperature": 0.5,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.RequestException as e:
        raise Exception(f"GROQ API error: {str(e)}")


def generate_job_details(job_description: str) -> Dict[str, str]:
    """
    Process a job description through GROQ AI to generate structured sections
    
    Args:
        job_description: The complete job description text
        
    Returns:
        Dictionary with the generated sections
    """
    # Get API key from environment
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        # Try mock content for testing if API key is not available
        if os.getenv("MOCK_AI_RESPONSES", "false").lower() == "true":
            return generate_mock_content(job_description)
        raise Exception(
            "GROQ API key is required. Please set the GROQ_API_KEY environment variable."
        )
    
    # Process each topic
    results = {}
    for topic, system_prompt in SYSTEM_PROMPTS.items():
        results[topic] = call_groq_api(api_key, job_description, system_prompt)
    
    return results


def generate_mock_content(job_description: str) -> Dict[str, str]:
    """
    Generate mock content for testing without an API key
    
    Args:
        job_description: The job description text
        
    Returns:
        Dictionary with mock generated sections
    """
    # Simple mock content for testing without an API
    sample = job_description[:100] + "..." if len(job_description) > 100 else job_description
    
    return {
        "job_description": f"# Job Description Summary\n\n* This is mock content for {sample}\n* Position requires relevant skills\n* Full-time position",
        "key_responsibilities": "# Key Responsibilities\n\n* Develop and maintain software applications\n* Collaborate with team members\n* Report to management",
        "about_company": "# About the Company\n\nThis is a mock company description. The company operates in the technology sector and values innovation.",
        "selection_process": "# Selection Process\n\n1. Resume screening\n2. Technical interview\n3. HR interview\n4. Final selection",
        "qualification": "# Qualifications\n\n* Education: Bachelor's degree in relevant field\n* Experience: 2+ years in similar role\n* Skills: Programming, communication"
    }


# Test function
if __name__ == "__main__":
    # Set to use mock content for testing
    os.environ["MOCK_AI_RESPONSES"] = "true"
    
    test_desc = """Software Engineer position at Tech Solutions Inc. Responsibilities include developing web applications, 
    debugging code, and working with the team. Requirements: Bachelor's degree in Computer Science, 
    2+ years of experience in JavaScript and Python."""
    
    result = generate_job_details(test_desc)
    print(json.dumps(result, indent=2))