@echo off
REM Check if the virtual environment exists by verifying the activate script
if not exist ".venv\Scripts\activate" (
    echo Virtual environment not found. Creating .venv...
    python -m venv .venv
) else (
    echo Virtual environment already exists.
)

echo Activating virtual environment...
call .venv\Scripts\activate

echo Installing dependencies...
pip install -r requirements.txt

echo Running the application...
python main.py

pause

