from pathlib import Path
import pandas as pd
from sqlalchemy import text
from datetime import datetime, timedelta, timezone
import os
import sys
from typing import Optional, Set, Tuple
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db import SessionLocal

class JobCSVImporter:
    def __init__(self):
        self.session = SessionLocal()
        self.existing_jobs = set()  # Cache for existing jobs
    
    def load_existing_jobs(self, category: str):
        """Load existing jobs from database to check for duplicates"""
        try:
            print(f"Loading existing {category} jobs from database...")
            
            # Query to get existing jobs with key identifying fields for the specific category
            query = text("""
                SELECT LOWER(TRIM(company_name)) as company_name, 
                       LOWER(TRIM(job_role)) as job_role,
                       LOWER(TRIM(website_link)) as website_link,
                       DATE(posted_on) as posted_date,
                       category
                FROM jobs
                WHERE company_name IS NOT NULL 
                AND job_role IS NOT NULL
                AND category = :category
            """)
            
            result = self.session.execute(query, {"category": category})
            
            for row in result:
                # Create a tuple key for each existing job (including category)
                job_key = (
                    row.company_name,
                    row.job_role,
                    row.website_link,
                    row.posted_date,
                    row.category
                )
                self.existing_jobs.add(job_key)
            
            print(f"Loaded {len(self.existing_jobs)} existing {category} jobs for duplicate checking")
            
        except Exception as e:
            print(f"Error loading existing jobs: {str(e)}")
            self.existing_jobs = set()
    
    def create_job_key(self, company_name: str, job_role: str, website_link: str, posted_on: datetime, category: str) -> tuple:
        """Create a unique key for a job to check against existing jobs"""
        return (
            company_name.lower().strip(),
            job_role.lower().strip(),
            website_link.lower().strip(),
            posted_on.date(),
            category
        )
    
    def is_duplicate_job(self, company_name: str, job_role: str, website_link: str, posted_on: datetime, category: str) -> bool:
        """Check if a job already exists in the database"""
        job_key = self.create_job_key(company_name, job_role, website_link, posted_on, category)
        return job_key in self.existing_jobs
    
    def parse_posted_on(self, posted_on_str: str) -> Optional[datetime]:
        """Parse posted_on string to datetime object - handles ISO 8601 format"""
        if not posted_on_str or posted_on_str == 'Not specified':
            return datetime.now(timezone.utc)

        # Date formats to try - prioritizing ISO 8601 format
        date_formats = [
            '%Y-%m-%dT%H:%M:%S+00:00',  # ISO 8601 with timezone: 2025-06-21T06:19:21+00:00
            '%Y-%m-%dT%H:%M:%SZ',       # ISO 8601 UTC: 2025-06-21T06:19:21Z
            '%Y-%m-%dT%H:%M:%S',        # ISO 8601 without timezone: 2025-06-21T06:19:21
            '%Y-%m-%d %H:%M:%S',        # Standard datetime: 2025-06-21 06:19:21
            '%Y-%m-%d',                 # Date only: 2025-06-21
            '%d-%m-%Y',
            '%m/%d/%Y',
            '%d/%m/%Y'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(posted_on_str, fmt)
            except ValueError:
                continue
        
        print(f"Warning: Could not parse date '{posted_on_str}', using current date")
        return datetime.utcnow()
    
    def clean_text_field(self, value: str) -> str:
        """Clean text fields by removing extra whitespace and handling None values"""
        if pd.isna(value) or value is None:
            return 'Not specified'
        return str(value).strip()
    
    def import_csv(self, csv_file_path: str, category: str):
        """Import CSV data into PostgreSQL database, skipping duplicates"""
        try:
            # Load existing jobs first for this specific category
            self.load_existing_jobs(category)
            
            # Read CSV file
            print(f"Reading CSV file: {csv_file_path}")
            df = pd.read_csv(csv_file_path)
            
            print(f"Found {len(df)} records in CSV")
            print(f"Columns in CSV: {list(df.columns)}")
            
            # Process each row
            successful_imports = 0
            failed_imports = 0
            duplicate_skips = 0
            
            for index, row in df.iterrows():
                try:
                    # Parse posted_on date
                    posted_on = self.parse_posted_on(str(row.get('posted_on', '')))
                    
                    # Clean key fields for duplicate checking
                    company_name = self.clean_text_field(row.get('company_name', 'Not specified'))
                    job_role = self.clean_text_field(row.get('job_role', 'Not specified'))
                    website_link = self.clean_text_field(row.get('website_link', 'Not specified'))
                    
                    # Check if this job already exists
                    if self.is_duplicate_job(company_name, job_role, website_link, posted_on, category):
                        duplicate_skips += 1
                        if duplicate_skips % 50 == 0:
                            print(f"Skipped {duplicate_skips} duplicate jobs so far...")
                        continue
                    
                    # Prepare job data
                    job_data = {
                        'category': category,
                        'company_name': company_name,
                        'job_role': job_role,
                        'website_link': website_link,
                        'state': self.clean_text_field(row.get('state', 'Not specified')),
                        'city': self.clean_text_field(row.get('city', 'Not specified')),
                        'experience': self.clean_text_field(row.get('experience', 'Not specified')),
                        'qualification': self.clean_text_field(row.get('qualification', 'Not specified')),
                        'batch': self.clean_text_field(row.get('batch', 'Not specified')),
                        'salary_package': self.clean_text_field(row.get('salary_package', 'Not specified')),
                        'job_description': self.clean_text_field(row.get('job_description', 'Not specified')),
                        'key_responsibility': self.clean_text_field(row.get('key_responsibility', 'Not specified')),
                        'about_company': self.clean_text_field(row.get('about_company', 'Not specified')),
                        'selection_process': self.clean_text_field(row.get('selection_process', 'Not specified')),
                        'image': self.clean_text_field(row.get('image', 'Not specified')),
                        'posted_on': posted_on
                    }
                    
                    # Insert into database
                    insert_query = text("""
                        INSERT INTO jobs (
                            category, company_name, job_role, website_link, state, city,
                            experience, qualification, batch, salary_package, job_description,
                            key_responsibility, about_company, selection_process, image,
                            posted_on
                        ) VALUES (
                            :category, :company_name, :job_role, :website_link, :state, :city,
                            :experience, :qualification, :batch, :salary_package, :job_description,
                            :key_responsibility, :about_company, :selection_process, :image,
                            :posted_on
                        )
                    """)
                    
                    self.session.execute(insert_query, job_data)
                    successful_imports += 1
                    
                    # Add to existing jobs cache to prevent duplicates within the same CSV
                    job_key = self.create_job_key(company_name, job_role, website_link, posted_on, category)
                    self.existing_jobs.add(job_key)
                    
                    if successful_imports % 50 == 0:
                        print(f"Processed {successful_imports} new records...")
                        self.session.commit()
                
                except Exception as e:
                    print(f"Error processing row {index}: {str(e)}")
                    failed_imports += 1
                    continue
            
            # Final commit
            self.session.commit()
            
            print(f"\nImport completed!")
            print(f"Total records in CSV: {len(df)}")
            print(f"Successfully imported NEW jobs: {successful_imports}")
            print(f"Skipped duplicates: {duplicate_skips}")
            print(f"Failed imports: {failed_imports}")
            
        except Exception as e:
            print(f"Error reading CSV file: {str(e)}")
            self.session.rollback()
        
        finally:
            self.session.close()
    
    def import_freshers_csv(self, csv_file_path: str):
        """Import freshers CSV with category 'Fresher'"""
        self.import_csv(csv_file_path, 'Fresher')
    
    def import_internships_csv(self, csv_file_path: str):
        """Import internships CSV with category 'Internship'"""
        self.import_csv(csv_file_path, 'Internship')


def main():
    """Main function to run the import process for both CSV files"""
    # Define the CSV files and their categories
    base_dir = Path(__file__).resolve().parent
    csv_files = [
        (base_dir / 'temp' / 'remote_jobs.csv', 'Remote'),
    ]

    total_new_jobs = 0
    total_duplicates = 0

    for csv_file, category in csv_files:
        if not os.path.exists(csv_file):
            print(f"Warning: CSV file '{csv_file}' not found! Skipping...")
            continue
        
        try:
            print(f"\n{'='*60}")
            print(f"Processing {category} jobs from {csv_file}")
            print(f"{'='*60}")
            
            importer = JobCSVImporter()
            importer.import_csv(csv_file, category)
            
            print(f"Completed processing {csv_file}")
            
        except Exception as e:
            print(f"Error processing {csv_file}: {str(e)}")
    
    print(f"\n{'='*60}")
    print("All CSV files processed!")
    print("Only NEW jobs have been imported to the database.")
    print("Existing jobs were automatically skipped.")
    print(f"{'='*60}")
    
    return True

if __name__ == "__main__":
    main()