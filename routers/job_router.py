from mimetypes import guess_type
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session
from db import get_db
from models import Job
from schemas import CategoryResponse, JobCreate, JobOut, JobResponse, JobUpdate
from typing import Dict, List

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# -------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------
def get_image_url(job: Job) -> str:
    """
    Returns the URL for the job image if available.
    If no image exists, returns None.
    """
    if job.image:  # type: ignore
        return f"/jobs/{job.id}/image"
    return None  # type: ignore

def job_to_response(job: Job) -> JobResponse:
    """
    Converts a Job ORM instance to a JobResponse schema.
    Also attaches the image URL if available.
    """
    job_response = JobResponse.from_orm(job)
    job_response.image_url = get_image_url(job)
    return job_response

# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------

# Get Top Jobs from each Category based on Count
@router.get("/top_jobs", response_model=Dict[str, List[CategoryResponse]])
def get_top_jobs(db: Session = Depends(get_db)):
    """
    Retrieve the top 5 jobs for each specified category.
    
    Categories: Fresher, Internship, Remote, Part_time.
    The result is a dictionary where keys are the category names in lowercase
    and values are lists of CategoryResponse objects.
    """
    categories = ["Fresher", "Internship", "Remote", "Part_time"]
    jobs_by_category = {}

    for category in categories:
        # Fetch jobs for the current category with order by created_at DESC
        jobs = db.query(Job).filter(Job.category == category).order_by(Job.created_at.desc()).limit(6).all()
        job_responses = [job_to_response(job) for job in jobs]
        jobs_by_category[category.lower()] = [
            CategoryResponse(category=category, jobs_data=job_responses)
        ]

    return jobs_by_category

#Get jobs by category with Pagination
@router.get("/category/{category}", response_model=dict)
def get_jobs_by_category(
    category: str,
    page: int = Query(1, alias="currentPage", ge=1),
    page_size: int = Query(10, alias="pageSize", ge=1),
    db: Session = Depends(get_db),
):
    """
    Retrieve paginated jobs for a given category.
    
    Query Parameters:
      - currentPage: The page number (default 1)
      - pageSize: Number of jobs per page (default 10)
    
    Returns a dictionary with the job list and total job count.
    """
    query = db.query(Job).filter(Job.category == category).order_by(Job.created_at.desc())
    total_count = query.count()  # Total jobs for pagination
    jobs = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "jobs": [job_to_response(job) for job in jobs],
        "totalCount": total_count
    }

#Get a Job by ID
@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific job by its ID.
    
    Raises a 404 error if the job does not exist.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_response(job)

#Get Image for a Job
@router.get("/{job_id}/image")
def get_job_image(job_id: int, db: Session = Depends(get_db)):
    """
    Retrieve the image associated with a specific job.
    
    If the job or its image is not found, raises a 404 error.
    The MIME type is determined based on the image filename.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or not job.image:  # type: ignore
        raise HTTPException(status_code=404, detail="Image not found")

    mime_type, _ = guess_type(job.image_filename) if hasattr(job, 'image_filename') else (None, None)
    mime_type = mime_type or "application/octet-stream"
    return Response(content=job.image, media_type=mime_type)

#Get all jobs
@router.get("/", response_model=List[JobResponse])
def get_jobs(db: Session = Depends(get_db)):
    """
    Retrieve all jobs from the database.
    
    Returns a list of job responses.
    """
    jobs = db.query(Job).order_by(Job.created_at.asc()).all()
    return [job_to_response(job) for job in jobs]

#Create a Job
@router.post("/", response_model=JobOut)
async def create_job(
    category: str = Form(...),
    company_name: str = Form(...),
    job_role: str = Form(...),
    website_link: str = Form(None),
    state: str = Form(...),
    city: str = Form(...),
    experience: str = Form(...),
    qualification: str = Form(...),
    batch: str = Form(None),
    salary_package: str = Form(None),
    job_description: str = Form(...),
    key_responsibilty: str = Form(None),
    about_company: str = Form(None),
    selection_process: str = Form(None),
    db: Session = Depends(get_db),
    image: UploadFile = File(None)
):
    """
    Create a new job entry.
    
    Accepts job details as form fields along with an optional image file.
    If an image is provided, it is read asynchronously and stored.
    Returns the newly created job.
    """
    new_job = Job(
        category=category,
        company_name=company_name,
        job_role=job_role,
        website_link=website_link,
        state=state,
        city=city,
        experience=experience,
        qualification=qualification,
        batch=batch,
        salary_package=salary_package,
        job_description=job_description,
        key_responsibilty=key_responsibilty,
        about_company=about_company,
        selection_process=selection_process
    )

    if image:  # If an image file is provided, update the image field
        new_job.image = await image.read()  # type: ignore
        # Optionally, store image metadata such as filename:
        # new_job.image_filename = image.filename

    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return job_to_response(new_job)

#Update Job 
@router.put("/{job_id}", response_model=JobOut)
async def update_job(
    job_id: int,
    category: str = Form(...),
    company_name: str = Form(...),
    job_role: str = Form(...),
    website_link: str = Form(None),
    state: str = Form(...),
    city: str = Form(...),
    experience: str = Form(...),
    qualification: str = Form(...),
    batch: str = Form(None),
    salary_package: str = Form(None),
    job_description: str = Form(...),
    key_responsibilty: str = Form(None),
    about_company: str = Form(None),
    selection_process: str = Form(None),
    db: Session = Depends(get_db),
    image: UploadFile = File(None)
):
    """
    Update an existing job entry by its ID.
    
    Accepts job details as form fields along with an optional new image file.
    If a new image is provided, it replaces the existing one.
    Raises a 404 error if the job is not found.
    Returns the updated job.
    """
    db_job = db.query(Job).filter(Job.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Update job fields with the new data
    db_job.category = category  # type: ignore
    db_job.company_name = company_name  # type: ignore
    db_job.job_role = job_role  # type: ignore
    db_job.website_link = website_link  # type: ignore
    db_job.state = state  # type: ignore
    db_job.city = city  # type: ignore
    db_job.experience = experience  # type: ignore
    db_job.qualification = qualification  # type: ignore
    db_job.batch = batch  # type: ignore
    db_job.salary_package = salary_package  # type: ignore
    db_job.job_description = job_description  # type: ignore
    db_job.key_responsibilty = key_responsibilty  # type: ignore
    db_job.about_company = about_company  # type: ignore
    db_job.selection_process = selection_process  # type: ignore

    if image:  # If a new image is uploaded, update it
        db_job.image = await image.read()  # type: ignore
        db_job.image_filename = image.filename

    db.commit()
    db.refresh(db_job)
    return job_to_response(db_job)

#Delete a Job entry
@router.delete("/{job_id}", response_model=JobOut)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    """
    Delete a job entry identified by its ID.
    
    Raises a 404 error if the job is not found.
    Returns the deleted job as a response.
    """
    db_job = db.query(Job).filter(Job.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(db_job)
    db.commit()
    return job_to_response(db_job)
