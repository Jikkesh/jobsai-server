import os
from fastapi import FastAPI
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from daily_job import main as daily_job_main
from clean_errors import main as clean_errors_main

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

# Get port from Render environment
port = int(os.getenv("PORT", 3000))  # Default to 8000 if PORT not set

sched = AsyncIOScheduler(timezone="Asia/Kolkata")

@app.on_event("startup")
def startup_event():
    #Remove error entry
    clean_errors_main()
    
    #Run the pipeline
    daily_job_main()

    # Schedule daily cleanup @ 02:30 IST
    india_tz = pytz.timezone("Asia/Kolkata")
    sched.add_job(
        daily_job_main,
        CronTrigger(hour=2, minute=30, timezone=india_tz),
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