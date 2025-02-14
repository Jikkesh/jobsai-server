import os
from groq import Groq

from dotenv import load_dotenv
load_dotenv()


groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def generate_section(input_text, section_type):
    if not input_text.strip():
        return "❌ No input provided!"
    
    system_prompt = f"""
    You are an AI assistant that helps format job-related information. 
    Given raw text, generate a well-structured **{section_type}** in Markdown format with proper headings, lists, and key points.
    
    Raw Input:
    {input_text}

    Output:
    """

    response = groq_client.chat.completions.create(
        model="gemma2-9b-it",  
        messages=[{"role": "system", "content": system_prompt}]
    )
    
    return response.choices[0].message.content  # Return formatted text