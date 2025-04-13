from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import httpx
import os
import re
from typing import Dict
import json
from dotenv import load_dotenv

load_dotenv()

# Create a router
router = APIRouter(prefix="/ai", tags=["ai-processing"])

# Response Model
class JobDescriptionResponse(BaseModel):
    job_description: str
    key_responsibilities: str
    about_company: str
    selection_process: str
    qualification: str

# Constants
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama3-70b-8192"  # Using Llama3 70B as default model

# Intermediate preprocessing function for the job description text
def preprocess_job_description(text: str) -> str:
    """
    Clean and normalize the job description text to be LLM friendly.
    - Strips leading/trailing whitespace.
    - Replaces multiple consecutive newlines with a single newline.
    - Removes unwanted control characters.
    """
    # Remove unwanted control characters except newline
    text = re.sub(r"[\r\f\v]", "", text)
    # Normalize newlines: Replace multiple newlines with one
    text = re.sub(r"\n\s*\n", "\n", text)
    # Trim whitespace
    return text.strip()

# Enhanced system prompts with SEO best practices added
SYSTEM_PROMPTS: Dict[str, str] = {
    "job_description": (
        "You are a professional HR content creator and SEO expert. "
        "Analyze the provided job description and extract the best job title and overview. "
        "Produce a compelling, clear, and SEO-friendly job description with a distinct title. "
        "Include industry-relevant keywords and maintain a professional tone."
    ),
    "key_responsibilities": (
        "You are an expert HR advisor and SEO content writer. "
        "Extract and clearly outline the key responsibilities from the provided job description. "
        "Format the output under a 'Key Responsibilities' heading using concise bullet points. "
        "Ensure each bullet starts with a strong action verb and incorporate SEO-friendly terms."
    ),
    "about_company": (
        "You are an experienced company researcher and SEO specialist. "
        "Summarize the information about the company from the job description, "
        "focusing on its mission, values, size, culture, and industry. "
        "Present the content under an 'About the Company' heading, integrating strategic SEO keywords."
    ),
    "selection_process": (
        "You are an HR expert skilled in recruitment and content creation. "
        "Detail the selection process based on the job description. "
        "Present it under a 'Selection Process' heading with clear steps or bullet points. "
        "Include SEO-friendly wording that highlights candidate benefits and process transparency."
    ),
    "qualification": (
        "You are an expert HR advisor and professional content creator. "
        "Extract and organize the required and preferred qualifications from the job description. "
        "Format the output under a 'Qualifications' heading with bullet points for Education, Experience, Technical and Soft Skills. "
        "Ensure the content is SEO optimized and easy to read."
    )
}

async def call_groq_api(prompt: str, system_prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Make a call to the GROQ API using the provided prompt and system prompt."""
    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(GROQ_API_URL, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GROQ API error: {response.text}"
                )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"GROQ API service unavailable: {str(exc)}")

@router.post("/process-job-description", response_model=JobDescriptionResponse)
async def process_job_description(request: Request):
    """
    Process a job description to generate SEO-optimized content for a job posting.
    This endpoint:
      1. Reads the raw request body.
      2. Cleans the input to remove invalid control characters.
      3. Parses the cleaned text as JSON.
      4. Preprocesses the job description.
      5. Calls an external AI service (GROQ API) for each content section.
    """
    try:
        # Read the raw request body as bytes
        raw_body = await request.body()
        # Decode with 'replace' to handle invalid characters
        body_text = raw_body.decode("utf-8", errors="replace")
        # Remove any invalid control characters in the raw JSON string
        body_text = re.sub(r'[\x00-\x1f]', '', body_text)
        # Now parse the cleaned string as JSON
        data = json.loads(body_text)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")
    
    job_description = data.get("job_description", "")
    if not job_description:
        raise HTTPException(status_code=400, detail="Job description is required in the request body.")
    
    # Preprocess the job description to normalize formatting for the LLM
    cleaned_job_description = preprocess_job_description(job_description)
    if not cleaned_job_description:
        raise HTTPException(status_code=400, detail="Job description cannot be empty after preprocessing.")
    
    # Ensure API key exists
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(
            status_code=400,
            detail="GROQ API key is required. Please set the GROQ_API_KEY environment variable."
        )
    
    results = {}
    # Process each content section sequentially using the specialized system prompts
    for topic, system_prompt in SYSTEM_PROMPTS.items():
        results[topic] = await call_groq_api(cleaned_job_description, system_prompt)
    
    # Build and return the structured response
    return JobDescriptionResponse(
        job_description=results["job_description"],
        key_responsibilities=results["key_responsibilities"],
        about_company=results["about_company"],
        selection_process=results["selection_process"],
        qualification=results["qualification"]
    )
