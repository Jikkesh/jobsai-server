import datetime
from mimetypes import guess_type
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from db import get_db
from models import Job
from schemas import CategoryResponse, JobResponse
from typing import Dict, List

router = APIRouter(prefix="/jobs", tags=["Jobs"])


# Route to get all Jobs
@router.get("/", response_model=List[JobResponse])
def get_jobs(db: Session = Depends(get_db)):
    jobs = db.query(Job).all()
    return [job_to_response(job) for job in jobs]


# Route to get the first 5 jobs in each category
@router.get("/top_jobs", response_model=Dict[str, List[CategoryResponse]])
def get_top_jobs(db: Session = Depends(get_db)):
    categories = ["Fresher", "Internship", "Remote", "Part_time"]
    jobs_by_category = {}

    for category in categories:
        jobs = db.query(Job).filter(Job.category == category).limit(5).all()
        job_responses = [job_to_response(job) for job in jobs]
        jobs_by_category[category.lower()] = [
            CategoryResponse(category=category, jobs_data=job_responses)
        ]

    return jobs_by_category

# Route to get jobs by category
@router.get("/category/{category}", response_model=dict)
def get_jobs_by_category(
    category: str,
    page: int = Query(1, alias="currentPage", ge=1),
    page_size: int = Query(10, alias="pageSize", ge=1),
    db: Session = Depends(get_db),
):
    """Fetch paginated jobs by category"""
    query = db.query(Job).filter(Job.category == category)
    
    total_count = query.count()  # Get total count of jobs
    jobs = query.offset((page - 1) * page_size).limit(page_size).all()  # Apply pagination
    
    return {
        "jobs": [job_to_response(job) for job in jobs],  # Convert jobs to response format
        "totalCount": total_count  # Include total count for frontend pagination
    }


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_response(job)

@router.get("/{job_id}/image")
def get_job_image(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or not job.image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Guess the MIME type based on the file extension (fallback to "application/octet-stream")
    mime_type, _ = guess_type(job.image_filename) if hasattr(job, 'image_filename') else (None, None)
    mime_type = mime_type or "application/octet-stream"

    return Response(content=job.image, media_type=mime_type)


def get_image_url(job: Job) -> str:
    if job.image: # type: ignore
        return f"/jobs/{job.id}/image"
    return None # type: ignore

def job_to_response(job: Job) -> JobResponse:
    job_response = JobResponse.from_orm(job)
    job_response.image_url = get_image_url(job)
    return job_response


