# main.py
from fastapi import FastAPI
from db import engine, Base
from routers import job_router, user_router
from fastapi.middleware.cors import CORSMiddleware
from gradio.routes import mount_gradio_app
from gradio_interface import job_interface # Import Gradio app instance

# Initialize FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Your frontend URL
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8003)
    #Swagger Doc: "http://localhost:8003/docs"
    