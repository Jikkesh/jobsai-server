from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import smtplib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db import get_db
from models import User
from schemas import UserCreate, UserResponse
from typing import List

from dotenv import load_dotenv
load_dotenv() 

router = APIRouter(prefix="/users", tags=["Users"])

class ContactForm(BaseModel):
    name: str
    email: str
    message: str


@router.post("/contact")
async def send_contact_email(form_data: ContactForm):
    # Email configuration
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER", "your-email@gmail.com")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your-app-password")

    # Create message
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = "jikkekumar98@gmail.com"
    msg["Subject"] = "New Contact Form Submission"

    body = f"""
    New contact form submission:
    
    Name: {form_data.name}
    Email: {form_data.email}
    Message: {form_data.message}
    """
    
    msg.attach(MIMEText(body, "plain"))

    try:
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, "jikkekumar98@gmail.com", msg.as_string())
        return {"message": "Email sent successfully"}
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to send email: {str(e)}"
        )



@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get("/", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}
