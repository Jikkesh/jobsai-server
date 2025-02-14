import gradio as gr
from sqlalchemy.orm import Session
from ai_helper import generate_section
from db import get_db
from models import Job
from datetime import datetime, timedelta

# Function to add job after LLM formatting
def add_job(company_name, category, job_role, website_link, state, city, experience_years, is_fresher, qualification, batch, salary_package, raw_job_description, raw_key_responsibility, raw_about_company, raw_selection_process,image):
    db: Session = next(get_db())

    if not company_name or not job_role or not category or not state or not city or not qualification or not raw_job_description:
        return "❌ Please fill in all required fields!"

    experience_years = None if is_fresher else (int(experience_years) if experience_years else None)
    expiry_date = datetime.utcnow() + timedelta(days=15)

    # Generate structured Markdown content using LLM
    job_description = generate_section(raw_job_description, "Job Description")
    key_responsibility = generate_section(raw_key_responsibility, "Key Responsibilities")
    about_company = generate_section(raw_about_company, "About Company")
    selection_process = generate_section(raw_selection_process, "Selection Process")

    new_job = Job(
        company_name=company_name,
        category=category,
        job_role=job_role,
        website_link=website_link,
        state=state,
        city=city,
        experience_years=experience_years,
        is_fresher=is_fresher,
        qualification=qualification,
        batch=batch,
        salary_package=salary_package,
        job_description=job_description,
        key_responsibilty=key_responsibility,
        about_company=about_company,
        selection_process=selection_process,
        expiry_date=expiry_date,
        image=image,
    )

    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return f"✅ Job '{job_role}' at {company_name} added successfully!"

# Gradio UI
with gr.Blocks() as job_interface:
    gr.Markdown("### 📝 Job Posting Form")

    company_name = gr.Textbox(label="Company Name", placeholder="Enter company name", interactive=True)
    category = gr.Dropdown(["Fresher", "Internship", "Remote", "Part-time"], label="Category", interactive=True)
    job_role = gr.Textbox(label="Job Role", placeholder="Enter job role", interactive=True)
    website_link = gr.Textbox(label="Website Link", placeholder="Enter website URL", interactive=True)
    state = gr.Textbox(label="State", placeholder="Enter state", interactive=True)
    city = gr.Textbox(label="City", placeholder="Enter city", interactive=True)
    experience_years = gr.Number(label="Experience (years)", value=0, interactive=True)
    is_fresher = gr.Checkbox(label="Is Fresher?", interactive=True)

    qualification = gr.Textbox(label="Qualification", placeholder="Enter required qualifications", interactive=True)
    batch = gr.Textbox(label="Batch (Optional)", placeholder="Enter batch", interactive=True)
    salary_package = gr.Textbox(label="Salary Package (Optional)", placeholder="Enter salary", interactive=True)

    # Job Details Input (Raw)
    job_description_input = gr.Textbox(label="Job Description (Raw Input)", placeholder="Paste raw job description...", lines=5, interactive=True)
    key_responsibility_input = gr.Textbox(label="Key Responsibilities (Raw Input)", placeholder="Paste raw responsibilities...", lines=5, interactive=True)
    about_company_input = gr.Textbox(label="About Company (Raw Input)", placeholder="Paste raw company details...", lines=5, interactive=True)
    selection_process_input = gr.Textbox(label="Selection Process (Raw Input)", placeholder="Paste raw selection steps...", lines=5, interactive=True)

    # Generate Button
    generate_button = gr.Button("🧠 Generate Structured Content")

    # Markdown Previews
    job_description_preview = gr.Markdown()
    key_responsibility_preview = gr.Markdown()
    about_company_preview = gr.Markdown()
    selection_process_preview = gr.Markdown()

    # Generate structured text when button is clicked
    generate_button.click(
        lambda jd, kr, ac, sp: (generate_section(jd, "Job Description"), 
                                generate_section(kr, "Key Responsibilities"), 
                                generate_section(ac, "About Company"), 
                                generate_section(sp, "Selection Process")),
        inputs=[job_description_input, key_responsibility_input, about_company_input, selection_process_input],
        outputs=[job_description_preview, key_responsibility_preview, about_company_preview, selection_process_preview]
    )
    
    image_upload = gr.File(label="Company Image (Optional)", type="binary", interactive=True)

    # Submit button and output
    submit_btn = gr.Button("Add Job ✅")
    output_text = gr.Textbox(label="Status", interactive=False)
    
    submit_btn.click(
        add_job, 
        inputs=[company_name, category, job_role, website_link, state, city, experience_years, is_fresher, qualification, batch, salary_package, job_description_input, key_responsibility_input, about_company_input, selection_process_input,image_upload], 
        outputs=output_text
    )
