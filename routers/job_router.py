from mimetypes import guess_type
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session
from db import get_db
from models import Job
from schemas import CategoryResponse, JobCreate, JobOut, JobResponse, JobUpdate
from typing import Dict, List
from sqlalchemy.exc import OperationalError

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

def get_image_url(job: Job, request: Request) -> str:
    if job.image:
        return f"{request.base_url}images/{job.image}"
    return ""

def job_to_response(job: Job, request: Request) -> JobResponse:
    """
    Converts a Job ORM instance to a JobResponse schema.
    Also attaches the image URL if available.
    """
    job_response = JobResponse.from_orm(job)
    job_response.image_url = get_image_url(job, request)
    return job_response

# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------

@router.get("/category/{category}", response_model=dict)
def get_jobs_by_category(
    request: Request,
    category: str,
    page: int = Query(1, alias="currentPage", ge=1),
    page_size: int = Query(10, alias="pageSize", ge=1),
    db: Session = Depends(get_db),
):
    """
    Retrieve paginated jobs for a given category with retry on connection drop.
    """
    try:
        return _fetch_jobs_by_category(request, category, page, page_size, db)

    except OperationalError as e:
        logger.warning(f"Database connection dropped, retrying query: {e}")
        db.rollback()  # rollback broken transaction
        try:
            return _fetch_jobs_by_category(request, category, page, page_size, db)
        except Exception as e2:
            logger.error(f"Retry failed: {e2}")
            raise HTTPException(status_code=500, detail="Database connection error")


def _fetch_jobs_by_category(request, category, page, page_size, db):
    query = (
        db.query(Job)
        .filter(Job.category == category.title())
        .order_by(Job.posted_on.desc())
    )
    total_count = query.count()
    jobs = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "jobs": [job_to_response(job, request) for job in jobs],
        "totalCount": total_count
    }

#Get a Job by ID
@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int,request: Request, db: Session = Depends(get_db)):
    """
    Retrieve a specific job by its ID.
    
    Raises a 404 error if the job does not exist.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_response(job,request)

@router.get("/", response_model=List[JobResponse])
def get_jobs(request: Request, db: Session = Depends(get_db)):
    """
    Retrieve all jobs from the database.
    """
    jobs = db.query(Job).order_by(Job.posted_on.asc()).all()
    return [job_to_response(job, request) for job in jobs]

@router.put("/{job_id}", response_model=JobOut)
async def update_job(
    request: Request,
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
    key_responsibility: str = Form(None),
    about_company: str = Form(None),
    selection_process: str = Form(None),
    db: Session = Depends(get_db),
    image: UploadFile = File(None)
):
    """
    Update an existing job entry by its ID.
    """
    db_job = db.query(Job).filter(Job.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")

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
    db_job.key_responsibility = key_responsibility  # type: ignore
    db_job.about_company = about_company  # type: ignore
    db_job.selection_process = selection_process  # type: ignore

    if image:
        db_job.image = await image.read()  # type: ignore
        db_job.image_filename = image.filename

    db.commit()
    db.refresh(db_job)
    return job_to_response(db_job, request)

@router.delete("/{job_id}", response_model=JobOut)
def delete_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Delete a job entry identified by its ID.
    """
    db_job = db.query(Job).filter(Job.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(db_job)
    db.commit()
    return job_to_response(db_job, request)
