import gradio as gr
import os
import requests
import json
from datetime import datetime
from ai_job_helper import generate_job_details
import tempfile
import shutil

# Constants
JOB_CATEGORIES = ["Fresher", "Internship", "Remote", "Experienced"]
EXPERIENCE_LEVELS = ["Fresher", "1-3 years", "3-5 years"]
QUALIFICATIONS = ["Any Degree", "B.E/CSE", "B.Tech", "B.Sc"]

def process_job_submission(
    category, company_name, job_role, website_link, state, city, 
    experience, qualification, batch, salary_package, 
    job_details, image
):
    """Process the job submission and generate detailed sections using AI"""
    
    # Generate job sections using AI
    try:
        print("Generating AI content...")
        ai_generated_content = generate_job_details(job_details)
        
        # Extract AI-generated sections
        job_description = ai_generated_content["job_description"]
        key_responsibilities = ai_generated_content["key_responsibilities"]
        about_company = ai_generated_content["about_company"]
        selection_process = ai_generated_content["selection_process"]
        qualification_details = ai_generated_content["qualification"]
        
    except Exception as e:
        return f"Error generating content with AI: {str(e)}"
    
    # Handle image upload
    image_path = None
    if image is not None:
        # Create a directory for uploaded images if it doesn't exist
        os.makedirs("uploads", exist_ok=True)
        
        # Create a unique filename based on company name and timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        clean_company_name = "".join(c if c.isalnum() else "_" for c in company_name)
        filename = f"{clean_company_name}_{timestamp}{os.path.splitext(image)[1]}"
        
        # Save the uploaded image
        image_path = os.path.join("uploads", filename)
        shutil.copy(image, image_path)
    
    # In a real application, you would save this data to a database
    # For this example, we'll just create a structured result to display
    job_data = {
        "category": category,
        "company_name": company_name,
        "job_role": job_role,
        "website_link": website_link,
        "state": state,
        "city": city,
        "experience": experience,
        "qualification": qualification,
        "batch": batch,
        "salary_package": salary_package,
        "job_description": job_description,
        "key_responsibilities": key_responsibilities,
        "about_company": about_company,
        "selection_process": selection_process,
        "qualification_details": qualification_details,
        "image_path": image_path
    }
    
    # Save job data to a JSON file (for demonstration purposes)
    try:
        # Create jobs directory if it doesn't exist
        os.makedirs("jobs", exist_ok=True)
        
        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"job_{timestamp}.json"
        filepath = os.path.join("jobs", filename)
        
        # Write job data to file
        with open(filepath, "w") as f:
            json.dump(job_data, f, indent=2)
            
        return f"Job added successfully! Data saved to {filepath}"
    
    except Exception as e:
        return f"Error saving job data: {str(e)}"

def create_interface():
    """Create and configure the Gradio interface"""
    
    with gr.Blocks(title="Job Entry System", theme=gr.themes.Soft()) as app:
        gr.Markdown("# Job Entry System")
        gr.Markdown("Enter job details below. The system will automatically generate detailed sections using AI.")
        
        with gr.Row():
            with gr.Column(scale=1):
                category = gr.Dropdown(
                    choices=JOB_CATEGORIES, 
                    label="Category",
                    info="Select the job category"
                )
                company_name = gr.Textbox(
                    label="Company Name",
                    placeholder="Enter company name",
                    info="Enter the name of the company"
                )
                job_role = gr.Textbox(
                    label="Job Role",
                    placeholder="Enter job role/title",
                    info="Enter the specific job title or role"
                )
                website_link = gr.Textbox(
                    label="Website Link (Optional)",
                    placeholder="https://company.com",
                    info="Company website or job application link"
                )
                state = gr.Textbox(
                    label="State",
                    placeholder="Enter state",
                    info="State where the job is located"
                )
                city = gr.Textbox(
                    label="City",
                    placeholder="Enter city",
                    info="City where the job is located"
                )
                
            with gr.Column(scale=1):
                experience = gr.Dropdown(
                    choices=EXPERIENCE_LEVELS,
                    label="Experience",
                    info="Required experience level"
                )
                qualification_dropdown = gr.Dropdown(
                    choices=QUALIFICATIONS,
                    label="Basic Qualification",
                    info="Minimum qualification required"
                )
                batch = gr.Textbox(
                    label="Batch (Optional)",
                    placeholder="e.g., 2022-2023",
                    info="Target graduation batch if applicable"
                )
                salary_package = gr.Textbox(
                    label="Salary Package (Optional)",
                    placeholder="e.g., 5-8 LPA",
                    info="Salary range or package details"
                )
                image = gr.File(
                    label="Company Image (Optional)",
                    file_types=["image"],
                    info="Upload company logo or relevant image"
                )
        
        # Main job details text area for AI processing
        job_details = gr.Textbox(
            label="Full Job Details", 
            placeholder="Paste the complete job description here. The AI will generate structured sections from this text.",
            lines=10,
            info="Paste the complete job posting or description here. The AI will automatically extract and format the key sections."
        )
        
        # Submit button
        submit_btn = gr.Button("Submit Job", variant="primary")
        
        # Output area
        output = gr.Textbox(label="Result")
        
        # Preview tabs for generated content
        with gr.Accordion("Preview Generated Content", open=False):
            with gr.Tabs():
                with gr.TabItem("Job Description"):
                    job_desc_preview = gr.Markdown()
                with gr.TabItem("Key Responsibilities"):
                    resp_preview = gr.Markdown()
                with gr.TabItem("About Company"):
                    company_preview = gr.Markdown()
                with gr.TabItem("Selection Process"):
                    process_preview = gr.Markdown()
                with gr.TabItem("Qualification Details"):
                    qual_preview = gr.Markdown()
        
        # Set up event handlers
        submit_btn.click(
            fn=process_job_submission,
            inputs=[
                category, company_name, job_role, website_link,
                state, city, experience, qualification_dropdown,
                batch, salary_package, job_details, image
            ],
            outputs=output
        )
        
        # Add preview functionality
        def update_previews(job_details):
            try:
                if not job_details or len(job_details.strip()) < 50:
                    return "Please enter more detailed job information.", "", "", "", ""
                
                result = generate_job_details(job_details)
                return (
                    result["job_description"],
                    result["key_responsibilities"],
                    result["about_company"],
                    result["selection_process"],
                    result["qualification"]
                )
            except Exception as e:
                return f"Error: {str(e)}", "", "", "", ""
        
        preview_btn = gr.Button("Preview AI-Generated Content")
        preview_btn.click(
            fn=update_previews,
            inputs=[job_details],
            outputs=[job_desc_preview, resp_preview, company_preview, process_preview, qual_preview]
        )
        
    return app

if __name__ == "__main__":
    app = create_interface()
    app.launch(server_port=7860, server_name="0.0.0.0", share=True)