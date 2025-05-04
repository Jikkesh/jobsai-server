import gradio as gr
from datetime import datetime
from ai_job_helper import generate_job_details
from sqlalchemy.orm import Session
from models import Job
from db import SessionLocal
from upload_image import upload_job_image

# Import your DB session and Job model
from db import SessionLocal  # your session maker from your db file
from models import Job    # your SQLAlchemy Job model

from ai_job_helper import generate_job_details

# Constants
JOB_CATEGORIES = ["Fresher", "Internship", "Remote", "Experienced"]
EXPERIENCE_LEVELS = ["Fresher", "0-1 years", "0-2 years", "1-3 years", "3-5 years"]
QUALIFICATIONS = ["Any Degree", "Any Engineering Degree", "B.E/CSE", "B.Tech", "B.Sc"]


def process_job_submission(
    category,
    company_name,
    job_role,
    website_link,
    state,
    city,
    experience,
    batch,
    salary_package,
    image,
    job_desc_preview,
    resp_preview,
    company_preview,
    process_preview,
    qual_preview
):
    """Process the job submission and store in DB"""
    try:
        # Use the previewed/generated content
        job_description = job_desc_preview
        key_responsibilities = resp_preview
        about_company = company_preview
        selection_process = process_preview
        qualification_details = qual_preview
    except Exception as e:
        return f"Error reading previewed content: {str(e)}"

    # Handle image upload
    image_filename = None
    if image is not None:
        image_filename = upload_job_image(image, company_name)

    try:
        db = SessionLocal()
        job_entry = Job(
            category=category,
            company_name=company_name,
            job_role=job_role,
            website_link=website_link,
            state=state,
            city=city,
            experience=experience,
            qualification=qualification_details,
            batch=batch,
            salary_package=salary_package,
            job_description=job_description,
            key_responsibilty=key_responsibilities,
            about_company=about_company,
            selection_process=selection_process,
            image=image_filename,
        )
        db.add(job_entry)
        db.commit()
        db.refresh(job_entry)
        db.close()
        return f"✅ Job added successfully with ID: {job_entry.id}"
    except Exception as e:
        db.rollback()
        return f"Error saving job data: {str(e)}"
    finally:
        db.close()


def create_interface():
    """Create and configure the Gradio interface"""
    with gr.Blocks(title="Job Entry System", theme=gr.themes.Soft()) as app:
        gr.Markdown("# Job Entry System")
        gr.Markdown("Enter job details below. The system will automatically generate detailed sections using AI.")

        with gr.Row():
            with gr.Column(scale=1):
                category = gr.Dropdown(choices=JOB_CATEGORIES, label="* Category")
                company_name = gr.Textbox(label="* Company Name", placeholder="Enter company name")
                job_role = gr.Textbox(label="* Job Role", placeholder="Enter job role/title")
                website_link = gr.Textbox(label="* Website Link (Optional)", placeholder="https://company.com")
                state = gr.Textbox(label="State", placeholder="Enter state")
                city = gr.Textbox(label="City", placeholder="Enter city")
            with gr.Column(scale=1):
                experience = gr.Dropdown(choices=EXPERIENCE_LEVELS, label="Experience")
                batch = gr.Textbox(label="Batch (Optional)", placeholder="e.g., 2022-2023")
                salary_package = gr.Textbox(label="* Salary Package", placeholder="e.g., 5-8 LPA")
                image = gr.File(label="* Company Image", file_types=["image"])

        job_details = gr.TextArea(label="Full Job Details", lines=10, placeholder="Paste the complete job description here...")
        output = gr.Markdown(label="Result")

        # Preview sections
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

        # Hidden state holders
        job_desc_state = gr.State()
        resp_state     = gr.State()
        company_state  = gr.State()
        process_state  = gr.State()
        qual_state     = gr.State()

        # Preview button with built-in progress tracking
        preview_btn = gr.Button("Generate Content using AI")
        preview_btn.click(
            fn=generate_and_state,
            inputs=[job_details],
            outputs=[
                job_desc_preview, resp_preview, company_preview,
                process_preview, qual_preview,
                job_desc_state, resp_state, company_state,
                process_state, qual_state
            ],
            show_progress=True
        )

        # Submit button uses the preview state values
        submit_btn = gr.Button("Submit Job", variant="primary")
        submit_btn.click(
            fn=process_job_submission,
            inputs=[
                category, company_name, job_role, website_link,
                state, city, experience,
                batch, salary_package, image,
                job_desc_state, resp_state, company_state,
                process_state, qual_state
            ],
            outputs=output
        )
    return app


def generate_and_state(job_details):
    """Generate AI previews and update progress bar"""
    if not job_details or len(job_details.strip()) < 50:
        empty = ""
        return ("Please enter more detailed job information.",) + (empty,) * 9

    result = generate_job_details(job_details)

    return (
        result["job_description"],
        result["key_responsibilities"],
        result["about_company"],
        result["selection_process"],
        result["qualification"],
        # states
        result["job_description"],
        result["key_responsibilities"],
        result["about_company"],
        result["selection_process"],
        result["qualification"]
    )

