import base64
from pydantic import BaseModel, EmailStr, validator
from typing import List, Optional

#Job Schema
class JobCreate(BaseModel):
    company_name: str
    job_role: str
    website_link: str
    state: str
    city: str
    experience_years: Optional[int] = None
    is_fresher: bool = False
    qualification: str
    batch: str
    salary_package: str
    job_description: str

class JobResponse(BaseModel):
    id: int
    category: str
    company_name: str
    job_role: str
    website_link: str
    state: str
    city: str
    experience_years: Optional[int] = None
    is_fresher: bool = False
    qualification: str
    batch: str
    salary_package: str
    job_description: str
    key_responsibilty: str
    about_company: str
    selection_process: str
    image_url: Optional[str] = None
    
    class Config:
        from_attributes = True
        

class CategoryResponse(BaseModel):
    category: str
    jobs_data: List[JobResponse]
    
    class Config:
        from_attributes = True

#User Schema
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    location: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    location: str

    class Config:
        orm_mode = True
