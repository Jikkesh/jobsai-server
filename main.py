import os
from fastapi import FastAPI
from db import engine, Base
from routers import job_router, user_router
from fastapi.middleware.cors import CORSMiddleware
from gradio.routes import mount_gradio_app
from gradio_interface import job_interface
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

# Mount Gradio app at /gradio
app = mount_gradio_app(app, job_interface, path="/gradio")

# Get port from Render environment
port = int(os.getenv("PORT", 8000))  # Default to 8000 if PORT not set

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=port)
