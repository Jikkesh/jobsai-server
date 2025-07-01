import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from db import engine, Base
from routers import job_router, user_router
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from gradio_interface import create_interface
from daily_job import main as daily_job_main
import gradio as gr

# Initialize FastAPI app
app = FastAPI()
# Allow all CORS origins (Temporary for testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Include Routers
app.include_router(job_router.router)
app.include_router(user_router.router)

#Greetings
@app.get("")
async def root():
    return {"message": "Hello World"}

#CMS System Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_images")
app.mount("/images", StaticFiles(directory=UPLOAD_DIR), name="images")

@app.get("/cms/Admin", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

gradio_blocks = create_interface()
app = gr.mount_gradio_app(app, gradio_blocks, path="/add-job/Admin")


# Get port from Render environment
port = int(os.getenv("PORT", 3000))  # Default to 8000 if PORT not set

sched = AsyncIOScheduler(timezone="Asia/Kolkata")

@app.on_event("startup")
def startup_event():

    # Schedule daily cleanup @ 21:30 IST
    india_tz = pytz.timezone("Asia/Kolkata")
    sched.add_job(
        daily_job_main,
        CronTrigger(hour=21, minute=10, timezone=india_tz),
        id="daily_job",
        replace_existing=True,  
    )
    sched.start()
    
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 3000)),
        reload=False,
    )