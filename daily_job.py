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
            kept_rows = []
            removed = 0

            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                for row in reader:
                    posted = date_parser.isoparse(row['posted_on'])
                    if posted >= cutoff_date:
                        kept_rows.append(row)
                    else:
                        removed += 1

            if removed > 0:
                self.logger.info(f"Removing {removed} row(s) from CSV: {path}")
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(kept_rows)
            else:
                self.logger.info(f"No rows to remove from CSV: {path}")

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
            base_dir / "scrapper" / "internships_final.csv",
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
            self.logger.info("Job scraping completed successfully.")
        except Exception:
            self.logger.exception("Job scraping failed.")
            
    def load_csvs(self):
        """
        Load CSV files and import jobs into the database.
        """
        self.logger.info("Loading CSV files and importing jobs into DB…")
        try:
            import_jobs_from_csv()
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
