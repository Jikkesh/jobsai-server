import csv
import os
from pathlib import Path
import sys
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from dateutil import parser as date_parser

from db import SessionLocal
from scrapper.intern_main import main as scrape_intern_jobs
from scrapper.fresher_main import main as scrape_fresher_jobs
from scrapper.import_script import main as import_jobs_from_csv
from services.import_script import main as import_remote_jobs_from_csv
from services.remote_jobs import RemoteJobGenerator

# Configure logging with UTF-8 console output
utf8_console = logging.StreamHandler(
    open(sys.stdout.fileno(), 'w', encoding='utf-8', closefd=False)
)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('job_cleanup.log'),
        utf8_console
    ]
)

class DailyJob:
    def __init__(self):
        self.session = SessionLocal()
        self.logger = logging.getLogger(__name__)
        self.remote_jobs = RemoteJobGenerator()

    def cleanup_expired_jobs(self, days_threshold: int = 100):
        """
        Delete jobs older than `days_threshold` days from the database.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        self.logger.info(f"Starting DB cleanup: removing jobs posted before {cutoff_date.isoformat()}")

        try:
            count_q = text("""
                SELECT COUNT(*) FROM jobs WHERE posted_on < :cutoff
            """ )
            count = self.session.execute(count_q, {"cutoff": cutoff_date}).scalar() or 0

            if count == 0:
                self.logger.info("No expired DB jobs to delete.")
                return

            self.logger.info(f"Deleting {count} expired DB job(s)...")
            del_q = text("""
                DELETE FROM jobs WHERE posted_on < :cutoff
            """ )
            result = self.session.execute(del_q, {"cutoff": cutoff_date})
            self.session.commit()
            self.logger.info(f"Deleted {result.rowcount} row(s) from database.")
            self.get_job_statistics()

        except Exception:
            self.logger.exception("Error during DB cleanup")
            self.session.rollback()
            raise

        finally:
            self.session.close()

    def cleanup_csv_files(self, csv_paths: list[str], days_threshold: int = 100):
        """
        Remove rows from each CSV whose `posted_on` is older than cutoff_date.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        
        for path in csv_paths:
            # Check if file exists before processing
            if not os.path.exists(path):
                self.logger.warning(f"CSV file not found: {path}")
                continue
                
            kept_rows = []
            removed = 0

            try:
                with open(path, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames or []
                    
                    for row in reader:
                        try:
                            posted = date_parser.isoparse(row['posted_on'])
                            
                            # Make posted datetime timezone-aware if it's naive
                            if posted.tzinfo is None:
                                posted = posted.replace(tzinfo=timezone.utc)
                            
                            if posted >= cutoff_date:
                                kept_rows.append(row)
                            else:
                                removed += 1
                                
                        except (ValueError, KeyError) as e:
                            self.logger.warning(f"Skipping invalid row in {path}: {e}")
                            # Keep the row if we can't parse the date
                            kept_rows.append(row)

                if removed > 0:
                    self.logger.info(f"Removing {removed} row(s) from CSV: {path}")
                    with open(path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(kept_rows)
                else:
                    self.logger.info(f"No rows to remove from CSV: {path}")
                    
            except Exception as e:
                self.logger.error(f"Error processing CSV file {path}: {e}")
                continue

    def deduplicate_fresher_jobs(self):
        """
        Remove fresher jobs that already exist in internships CSV based on company name and job role.
        Creates a new cleaned CSV file for import while preserving the original.
        """
        base_dir = Path(__file__).resolve().parent
        internships_csv = base_dir / "scrapper" / "internships_final.csv"
        freshers_csv = base_dir / "scrapper" / "freshers_final.csv"
        freshers_cleaned_csv = base_dir / "scrapper" / "freshers_final_cleaned.csv"
        
        if not os.path.exists(internships_csv):
            self.logger.warning(f"Internships CSV not found: {internships_csv}")
            return
            
        if not os.path.exists(freshers_csv):
            self.logger.warning(f"Freshers CSV not found: {freshers_csv}")
            return

        self.logger.info("Starting deduplication: removing fresher jobs that exist in internships...")

        try:
            # Load internship jobs and create a set of (company, role) tuples for fast lookup
            internship_jobs = set()
            with open(internships_csv, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Normalize company and role for comparison (case-insensitive, stripped)
                    company = row.get('company_name', '').strip().lower()
                    role = row.get('job_role', '').strip().lower()
                    if company and role:
                        internship_jobs.add((company, role))
            
            self.logger.info(f"Loaded {len(internship_jobs)} unique internship jobs for comparison")

            # Process fresher jobs and keep only those not in internships
            kept_rows = []
            removed_count = 0
            total_count = 0
            
            with open(freshers_csv, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                
                for row in reader:
                    total_count += 1
                    company = row.get('company_name', '').strip().lower()
                    role = row.get('job_role', '').strip().lower()
                    
                    # Check if this job already exists in internships
                    if company and role and (company, role) in internship_jobs:
                        removed_count += 1
                        self.logger.debug(f"Removing duplicate: {row.get('company_name')} - {row.get('job_role')}")
                    else:
                        kept_rows.append(row)

            # Write the deduplicated fresher jobs to a new cleaned file
            self.logger.info(f"Creating cleaned freshers CSV with {len(kept_rows)} jobs (removed {removed_count} duplicates out of {total_count} total)")
            with open(freshers_cleaned_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(kept_rows)
            
            if removed_count > 0:
                self.logger.info(f"Cleaned freshers CSV created: {freshers_cleaned_csv}")
                self.logger.info(f"Original freshers CSV preserved: {freshers_csv}")
            else:
                self.logger.info("No duplicate jobs found - cleaned CSV is identical to original")

        except Exception as e:
            self.logger.error(f"Error during deduplication: {e}")
            raise

    def get_job_statistics(self):
        """Log total count, counts by category, and min/max dates."""
        try:
            total = self.session.execute(text("SELECT COUNT(*) FROM jobs")).scalar() or 0
            self.logger.info(f"Total jobs in DB: {total}")

            rows = self.session.execute(
                text("SELECT category, COUNT(*) FROM jobs GROUP BY category")
            ).all()
            for category, cnt in rows:
                self.logger.info(f"  {category}: {cnt}")

            oldest, newest = self.session.execute(
                text("SELECT MIN(posted_on), MAX(posted_on) FROM jobs")
            ).one()
            self.logger.info(f"Oldest job posted: {oldest}, Newest job posted: {newest}")

        except Exception:
            self.logger.exception("Error getting job statistics")

    def run_cleanup(self, days_threshold: int = 100):
        """
        Run both DB cleanup and CSV cleanup back-to-back.
        """
        self.logger.info("=" * 20 + " CLEANUP START " + "=" * 20)
        try:
            self.cleanup_expired_jobs(days_threshold)

            base_dir = Path(__file__).resolve().parent
            csv_files = [
                base_dir / "scrapper" / "freshers_final.csv",
                base_dir / "scrapper" / "freshers_final_cleaned.csv",
                base_dir / "scrapper" / "internships_final.csv",
                base_dir / "services" / "temp" / "remote_jobs.csv",
            ]
            self.cleanup_csv_files(csv_files, days_threshold)

            self.logger.info("Cleanup (DB + CSV) completed successfully.")
        except Exception:
            self.logger.exception("Full cleanup failed.")
        self.logger.info("=" * 20 + " CLEANUP END " + "=" * 20)

    def run_scraping(self):
        """
        Run the scraping process for both intern and fresher jobs.
        """
        self.logger.info("Starting job scraping process…")
        try:
            self.logger.info("-> Scraping fresher jobs…")
            scrape_fresher_jobs()
            self.logger.info("-> Scraping intern jobs…")
            scrape_intern_jobs()
            self.logger.info("-> Scraping remote jobs…")
            self.remote_jobs.run_all()
            self.logger.info("Job scraping completed successfully.")
        except Exception:
            self.logger.exception("Job scraping failed.")
            
    def load_csvs(self):
        """
        Load CSV files and import jobs into the database.
        """
        self.logger.info("Loading CSV files and importing jobs into DB…")
        try:
            # Deduplicate fresher jobs before importing
            self.deduplicate_fresher_jobs()
            
            import_jobs_from_csv()
            import_remote_jobs_from_csv()
            self.logger.info("CSV import completed successfully.")
        except Exception:
            self.logger.exception("CSV import failed.")


def main():
    """For quick CLI testing."""
    dj = DailyJob()
    dj.run_cleanup()
    dj.run_scraping()
    dj.load_csvs()

if __name__ == "__main__":
    main()