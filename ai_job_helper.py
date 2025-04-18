import os
import requests
from typing import Dict, Optional
import json

# Constants for the API integration
DEFAULT_MODEL = "gemma2-9b-it"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# System prompts for each topic
SYSTEM_PROMPTS = {
    "job_description": ("You are an expert HR advisor specializing in job descriptions. More than 600 words. "
    "Extract and summarize the main aspects of the provided job details. "
    "Format your response with a clear heading, sub heading and more points  for key aspects of the role."
    "Make it easy to read, professional, and concise. Generate it in HTML."),
    
    "key_responsibilities": ("You are an expert HR advisor specializing in job responsibilities. More than 600 words. " 
    "Extract and structure the key responsibilities from the provided job details. "
    "Format your response with a clear 'Key Responsibilities' heading and Sub headings with more points . "
    "Each sub heading should clearly communicate a specific responsibility. Generate it in HTML."),
    
    "about_company": ("You are an expert company researcher. "
    "Extract and summarize information about the company from the job details. More than 600 words. " 
    "Format your response with an 'About the Company' heading, followed by organized sub headings thier goal and market position with more points . "
    "Include information about the company's mission, values, industry, size, culture, and any other relevant details mentioned. Generate it in HTML."),
    
    "selection_process": ("You are an expert HR advisor specializing in recruitment processes. "
    "Extract and structure information about the selection process from the job description. More than 600 words. " 
    "Format your response with a proper heading and sub heading of each process with more points . "
    "Include details on interviews, assessments, timeline, and what candidates should be prepared for. "
    "If minimal information is provided, make reasonable inferences based on industry standards in India and Job details. Generate it in HTML."),
    
    "qualification": ("You are an expert HR advisor specializing in job qualifications. "
    "Extract and structure the required and preferred qualifications from the job description. More than 600 words. " 
    "Format your response with heading, followed by sub headings in categories like: use more points"
    "- Education Requirements "
    "- Experience Requirements "
    "- Technical Skills "
    "- Soft Skills "
    "Use clear, concise language and maintain the original requirements. Generate it in HTML.")
}

def call_groq_api(api_key: str, prompt: str, system_prompt: str, model: str = DEFAULT_MODEL) -> str:
    """
    Make a call to the GROQ API to generate content
    
    Args:
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
        results[topic] = call_groq_api(api_key, job_description, system_prompt)
    
    return results

# Test function
# if __name__ == "__main__":

#     test_desc = """Software Engineer position at Tech Solutions Inc. Responsibilities include developing web applications, 
#     debugging code, and working with the team. Requirements: Bachelor's degree in Computer Science, 
#     2+ years of experience in JavaScript and Python."""
    
#     result = generate_job_details(test_desc)
#     print(json.dumps(result, indent=2))
#     #Print each section
#     for section in result.items():
#         print(f"Section: {section}\n\n")