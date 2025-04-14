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

def call_groq_api(prompt: str, system_prompt: str, model: str = DEFAULT_MODEL) -> str:
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
        "Authorization": f"Bearer {os.environ.get('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
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
        raise Exception("GROQ API key is required. Please set the GROQ_API_KEY environment variable.")
    
    # Process each topic
    results = {}
    for topic, system_prompt in SYSTEM_PROMPTS.items():
        results[topic] = call_groq_api( job_description, system_prompt)
    
    return results

