import gradio as gr
import os
import json
from datetime import datetime, timedelta
import shutil

# Import your DB session and Job model
from db import SessionLocal  # your session maker from your db file
from models import Job    # your SQLAlchemy Job model

from ai_job_helper import generate_job_details

# Constants
JOB_CATEGORIES = ["Fresher", "Internship", "Remote", "Experienced"]
EXPERIENCE_LEVELS = ["Fresher", "1-3 years", "3-5 years"]
QUALIFICATIONS = ["Any Degree", "B.E/CSE", "B.Tech", "B.Sc"]

def process_job_submission(
    category, company_name, job_role, website_link, state, city, 
    experience, batch, salary_package, 
    job_details, image
):
    """Process the job submission, generate detailed sections using AI,
       and save the job to the database using the Job model.
    """
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
    
    # Handle image upload and conversion to binary data for DB storage
    job_image = None
    if image is not None:
        # For DB storage, we read the file in binary mode.
        try:
            with open(image, "rb") as f:
                job_image = f.read()
        except Exception as e:
            return f"Error processing image file: {str(e)}"
    
    # Set up the database session
    db = SessionLocal()
    try:
        # Create a new Job instance
        new_job = Job(
            category=category,
            company_name=company_name,
            job_role=job_role,
            website_link=website_link,
            state=state,
            city=city,
            experience=experience,
            qualification= qualification_details,  # note: this corresponds to your model's "qualification" field
            batch=batch,
            salary_package=salary_package,
            job_description=job_description,
            key_responsibilty=key_responsibilities,  # note the field name: "key_responsibilty" in the model.
            about_company=about_company,
            selection_process=selection_process,
            image=job_image
            # created_at and expiry_date will be auto-handled by the model defaults.
        )
        db.add(new_job)
        db.commit()
        db.refresh(new_job)  # To retrieve the auto-generated id, etc.
        
        return f"Job added successfully! Job ID: {new_job.id}"
    
    except Exception as e:
        db.rollback()
        return f"Error saving job data: {str(e)}"
    finally:
        db.close()

def create_interface():
    """Create and configure the Gradio interface."""
    
    with gr.Blocks(title="Job Entry System", theme=gr.themes.Soft()) as app:
        gr.Markdown("# Job Entry System")
        gr.Markdown("Enter job details below. The system will automatically generate detailed sections using AI and save the job details to the database.")
        
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
                )
        
        # Main job details text area for AI processing
        job_details = gr.Textbox(
            label="Full Job Details", 
            placeholder="Paste the complete job description here. The AI will generate structured sections from this text.",
            lines=10,
            info="Paste the complete job posting or description here. The AI will automatically extract and format the key sections."
        )
        
        # Submit button for job submission
        submit_btn = gr.Button("Submit Job", variant="primary")
        
        # Output area to show submission result
        output = gr.Textbox(label="Result")
        
        # Preview tabs for generated content
        with gr.Accordion("Generated AI Content Preview", open=False):
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
        
        # Set up event handler for job submission
        submit_btn.click(
            fn=process_job_submission,
            inputs=[
                category, company_name, job_role, website_link,
                state, city, experience, qualification_dropdown,
                batch, salary_package, job_details, image
            ],
            outputs=output
        )
        
        # Add "Generate with AI" button for previewing AI generated content
        def update_previews(job_details):
            try:
                if not job_details or len(job_details.strip()) < 50:
                    return ("Please enter more detailed job information.",
                            "", "", "", "")
                
                result = generate_job_details(job_details)
                return (
                    result["job_description"],
                    result["key_responsibilities"],
                    result["about_company"],
                    result["selection_process"],
                    result["qualification"]
                )
            except Exception as e:
                return (f"Error: {str(e)}", "", "", "", "")
        
        generate_btn = gr.Button("Generate with AI")
        generate_btn.click(
            fn=update_previews,
            inputs=[job_details],
            outputs=[job_desc_preview, resp_preview, company_preview, process_preview, qual_preview]
        )
        
    return app

if __name__ == "__main__":
    app = create_interface()
    app.launch(server_port=7860, server_name="localhost", share=True)
