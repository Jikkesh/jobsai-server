import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from db import engine, Base
from routers import job_router, user_router
from fastapi.middleware.cors import CORSMiddleware
from gradio.routes import mount_gradio_app
import uvicorn

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


#CMS System
# Serve static files (including our index.html)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/cms", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.get("/add-job", response_class=HTMLResponse)
async def read_addjobs():
    with open("static/addjob.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)



# Get port from Render environment
port = int(os.getenv("PORT", 8000))  # Default to 8000 if PORT not set

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.1.1.1", port=port)
