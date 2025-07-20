import os
import requests
import csv
import time
from datetime import datetime, timedelta
from pathlib import Path
from io import BytesIO
from typing import List, Dict, Tuple, Set
from PIL import Image
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv() 

from services.description_cleaner import preprocess_job_description
from services.text_extraction import generate_ai_enhanced_content 

ROOT_DIR = Path(__file__).resolve().parent.parent

# Alias map for company image lookup
alias_map = {
        "ernst & young": "ey",
        "ernst and young": "ey",
        "eurofinsscientific" : "eurofins",
    }

class RemoteJobGenerator:
    def __init__(
        self,
        job_category: str = "Remote",
        images_dir: Path = ROOT_DIR / "uploaded_images",
        csv_path: Path = ROOT_DIR / "services" / "temp" / "remote_jobs.csv",
        max_age_days: int = 2
    ):
        self.job_category = job_category
        self.images_dir = images_dir
        self.csv_path = csv_path
        self.max_age = timedelta(days=max_age_days)
        self.existing_images: Set[str] = {
            p.stem.lower() for p in images_dir.glob("*.png")
        } if images_dir.exists() else set()

        # Ensure storage directories exist
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.csv_exists = os.path.exists(self.csv_path)

        # Updated CSV header with new fieldnames order
        self.fieldnames = [
            'company_name', 'job_role', 'website_link', 'state', 'city',
            'experience', 'qualification', 'batch', 'salary_package',
            'job_description', 'key_responsibility', 'about_company',
            'selection_process', 'image', 'posted_on'
        ]
        
        # Check if CSV exists and create with header if it doesn't
        self._ensure_csv_exists()

    def _ensure_csv_exists(self) -> None:
        """Ensure CSV file exists with proper header."""
        if not self.csv_path.exists():
            with open(self.csv_path, mode="w", newline='', encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()
            print(f"Created new CSV with header: {self.csv_path}")
        else:
            # Verify existing CSV has correct header
            try:
                with open(self.csv_path, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    existing_fields = reader.fieldnames
                    if existing_fields != self.fieldnames:
                        print(f"Warning: Existing CSV header {existing_fields} differs from expected {self.fieldnames}")
            except Exception as e:
                print(f"Error reading existing CSV: {e}")

    def run_all(self) -> None:
        """Fetch, filter by age, dedupe, convert, and save to CSV."""
        raw = self._fetch_job_data()
        cutoff = datetime.utcnow() - self.max_age
        # Keep only postings within the last max_age days
        recent = []
        for item in raw:
            date_str = item.get("date")
            posted = datetime.fromisoformat(date_str.rstrip('Z')).replace(tzinfo=None)
            if posted >= cutoff:
                recent.append(item)

        existing_keys = self._load_existing_csv_keys()
        new_items = [item for item in recent if self._make_key(item) not in existing_keys]

        if not new_items:
            print("No new recent jobs to add.")
            return

        converted = self._convert_data(new_items)
        self._append_to_csv(converted)
        print(f"Saved {len(converted)} new jobs to CSV.")

    def _make_key(self, item: Dict) -> Tuple[str, str, str]:
        company = item.get("company", "").strip().lower()
        role = item.get("position", "").strip().lower()
        date_str = item.get("date") or ""
        try:
            posted = datetime.fromisoformat(date_str.rstrip('Z')).replace(tzinfo=None)
        except:
            posted = datetime.fromtimestamp(item.get("epoch", 0))
        return (company, role, posted.isoformat())

    def _load_existing_csv_keys(self) -> Set[Tuple[str, str, str]]:
        keys: Set[Tuple[str, str, str]] = set()
        if not self.csv_path.exists():
            return keys
        try:
            with open(self.csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    keys.add((
                        row.get("company_name", "").strip().lower(),
                        row.get("job_role", "").strip().lower(),
                        row.get("posted_on", "").strip()
                    ))
        except Exception as e:
            print(f"Error reading existing CSV keys: {e}")
        return keys
    
    def load_existing_images(self):
        """Load list of existing company images"""
        for filename in self.images_dir.iterdir():
            if filename.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                company_name = filename.name.rsplit('.', 1)[0].replace('_', '/')
                self.existing_images.add(company_name.lower())
        print(f"🖼️ Found {len(self.existing_images)} existing company images")

    def _fetch_job_data(self) -> List[Dict]:
        url = "https://remoteok.com/api"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [d for d in data if isinstance(d, dict) and "id" in d]

    def _convert_data(self, raw_jobs: List[Dict]) -> List[Dict]:
        converted: List[Dict] = []
        for item in raw_jobs:
            company = item.get("company", "Not Specified")
            title = item.get("position", "")
            website = item.get("apply_url") or item.get("url", "")
            loc = item.get("location", "Remote") or "Remote"
            salary_min = item.get("salary_min", "Not Specified")
            salary_max = item.get("salary_max", "Not Specified")
            salary = f"{salary_min} - {salary_max}" if salary_min and salary_max else "Not Specified"
            # Parse location into state and city
            if loc.lower() == "remote":
                state, city = "Remote", "Remote"
            else:
                # Simple parsing - you may want to enhance this based on your data
                parts = loc.split(',')
                if len(parts) >= 2:
                    city = parts[0].strip()
                    state = parts[1].strip()
                else:
                    city = loc.strip()
                    state = ""

            # Parse date
            date_str = item.get("date")
            posted_dt = datetime.fromisoformat(date_str.rstrip('Z')).replace(tzinfo=None)
            posted_iso = posted_dt.isoformat()

            # Plain text description
            raw_html = item.get("description", "")
            soup = BeautifulSoup(raw_html, "html.parser")
            
            # Remove unwanted words and summarize description
            plain_desc = soup.get_text(separator="\n").strip()
            
            try:
                # Clean and summarize the job description
                processed_desc = preprocess_job_description(plain_desc, max_words=350)
                print(f"✅ Job description preprocessed successfully")

                # Alternative: Use section extraction if you want more control
                # processed_result = preprocess_with_section_extraction(plain_desc)
                # processed_desc = processed_result["processed_description"]
                # sections = processed_result["sections"]  # You could use individual sections if needed
            
            except Exception as e:
                print(f"⚠️  Warning: Preprocessing failed for {company} - {title}: {e}")
                # Fallback: use first 500 words of plain text
                words = plain_desc.split()
                processed_desc = ' '.join(words[:500]) if len(words) > 500 else plain_desc

            # Length check for description
            print("Description length:", len(processed_desc.split()))

            # AI-enhanced structured fields
            enhanced = generate_ai_enhanced_content(
                job_description=processed_desc,
                company_name=company,
                job_title=title,
                qualifications=""
            )

            # Generate image filename as company_name.png
            image_filename = self.get_company_image(company)

            converted.append({
                "company_name": company,
                "job_role": title,
                "website_link": website or "",
                "state": state,
                "city": city,
                "experience": enhanced.get("experience", "Any Experience"),
                "qualification": enhanced.get("qualification", "Not Specified"),
                "batch": "Not Specified",
                "salary_package": salary,
                "job_description": enhanced.get("job_description", ""),
                "key_responsibility": enhanced.get("key_responsibility", ""),
                "about_company": enhanced.get("about_company", ""),
                "selection_process": enhanced.get("selection_process", ""),
                "image": image_filename,
                "posted_on": posted_iso
            })
            time.sleep(5)
        return converted

    def _append_to_csv(self, items: List[Dict]) -> None:
        """Append new job items to CSV using DictWriter for proper field ordering."""
        if self.csv_exists:
            # Append to existing file
            mode = 'a'
            write_header = False
            action = "APPENDED TO EXISTING"
        else:
            # Create new file
            mode = 'w'
            write_header = True
            action = "CREATED NEW"
        
        with open(self.csv_path, mode, newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            if write_header:
                writer.writeheader()
            for job in items:
                writer.writerow(job)

    def get_company_image(self, company_name: str, size=(400, 200)) -> str:
        """Fetch company logo from Clearbit API with alias and suffix handling"""
        if not company_name or company_name.lower() == "not specified":
            return ""

        # Step 1: Normalize name
        company_key = company_name.strip().lower()

        # Step 2: Handle known aliases or suffix trimming
        for suffix in [" technologies", "technology", "Solutions", "Solution", "Pvt Ltd", " Pvt. Ltd", " Private Limited", " Ltd", " Limited", " Inc", " Corporation", " Corp"]:
                if company_key.endswith(suffix):
                    company_key = company_key.replace(suffix, "")
                    break
            
        if company_key in alias_map:
            lookup_name = alias_map[company_key]
        else:
            lookup_name = company_key

        image_filename = f"{company_name}.png"
        save_path = self.images_dir / image_filename

        # Check if already exists
        if company_name.lower() in self.existing_images:
            print(f"  🖼️ Company image already exists: {image_filename}")
            return image_filename

        if os.path.exists(save_path):
            print(f"  🖼️ Company image file already exists: {image_filename}")
            self.existing_images.add(company_name.lower())
            return image_filename

        # Build domain for logo fetching
        domain = lookup_name.replace(" ", "").replace("pvt", "").replace("ltd", "") + ".com"
        logo_url = f"https://logo.clearbit.com/{domain}"

        try:
            print(f"  🌐 Fetching logo for {company_name}...")
            response = requests.get(logo_url, timeout=10)
            response.raise_for_status()

            logo = Image.open(BytesIO(response.content)).convert("RGBA")
            white_bg = Image.new("RGBA", logo.size, (255, 255, 255, 255))
            combined = Image.alpha_composite(white_bg, logo)

            combined.thumbnail(size, Image.LANCZOS)
            final = Image.new("RGB", size, (255, 255, 255))
            position = (
                (size[0] - combined.width) // 2,
                (size[1] - combined.height) // 2
            )
            final.paste(combined.convert("RGB"), position)

            final.save(save_path)
            self.existing_images.add(company_name.lower())
            print(f"  ✅ Successfully saved logo: {image_filename}")
            return image_filename

        except requests.RequestException as e:
            image_filename = f"hiring.png"
            print(f"  ❌ Failed to fetch logo for {company_name}: {e} - using default image")
            return image_filename
        except Exception as e:
            image_filename = f"hiring.png"
            print(f"  ❌ Error processing logo for {company_name}: {e} - using default image")
            return image_filename

if __name__ == "__main__":
    RemoteJobGenerator().run_all()