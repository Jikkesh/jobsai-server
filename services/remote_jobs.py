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
    "eurofinsscientific": "eurofins",
}

class RemoteJobGenerator:
    def __init__(
        self,
        job_category: str = "Remote",
        images_dir: Path = ROOT_DIR / "uploaded_images",
        csv_path: Path = ROOT_DIR / "services" / "temp" / "remote_jobs.csv",
        max_age_days: int = 30
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

        self.fieldnames = [
            'company_name', 'job_role', 'website_link', 'state', 'city',
            'experience', 'qualification', 'batch', 'salary_package',
            'job_description', 'key_responsibility', 'about_company',
            'selection_process', 'image', 'posted_on'
        ]
        self._ensure_csv_exists()

    def _ensure_csv_exists(self) -> None:
        """Ensure CSV file exists with header if missing."""
        if not self.csv_path.exists():
            with open(self.csv_path, mode="w", newline='', encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()
            self.csv_exists = True

    def run_all(self) -> None:
        """Fetch, filter, dedupe, process each job and write immediately."""
        raw = self._fetch_job_data()
        cutoff = datetime.utcnow() - self.max_age
        existing_keys = self._load_existing_csv_keys()

        for item in raw:
            # Filter out old posts
            date_str = item.get("date") or ""
            try:
                posted_dt = datetime.fromisoformat(date_str.rstrip('Z')).replace(tzinfo=None)
            except:
                continue
            if posted_dt < cutoff:
                continue

            key = self._make_key(item)
            if key in existing_keys:
                continue

            try:
                record = self._process_single(item)
                self._append_to_csv([record])
                existing_keys.add(key)
                print(f"✅ Saved job: {record['company_name']} - {record['job_role']}")
            except Exception as e:
                print(f"⚠️ Failed processing {item.get('company')} - {item.get('position')}: {e}")

    def _process_single(self, item: Dict) -> Dict:
        """Convert a single raw job dict into CSV-ready record."""
        company = item.get("company", "Not Specified")
        title = item.get("position", "")
        website = item.get("apply_url") or item.get("url", "")
        loc = item.get("location", "Remote") or "Remote"
        if loc.lower() == "remote":
            state, city = "Remote", "Remote"
        else:
            parts = loc.split(',')
            city = parts[0].strip() if parts else loc.strip()
            state = parts[1].strip() if len(parts) > 1 else ""

        salary_min = item.get("salary_min") or "Not Specified"
        salary_max = item.get("salary_max") or ""
        salary = f"{salary_min} - {salary_max}" if salary_max else salary_min

        # Parse and normalize date
        date_str = item.get("date", "")
        posted_iso = datetime.fromisoformat(date_str.rstrip('Z')).replace(tzinfo=None).isoformat()

        # Clean description
        raw_html = item.get("description", "")
        soup = BeautifulSoup(raw_html, "html.parser")
        plain_desc = soup.get_text(separator="\n").strip()
        try:
            processed_desc = preprocess_job_description(plain_desc, max_words=350)
            print("✅ Processed job description successfully.")
            print("Processed Description:")
            print(processed_desc)
        except Exception:
            words = plain_desc.split()
            processed_desc = ' '.join(words[:500])

        # AI-enhanced fields
        enhanced = generate_ai_enhanced_content(
            job_description=processed_desc,
            company_name=company,
            job_title=title,
            qualifications=""
        )

        # Fetch or reuse company logo
        image_filename = self.get_company_image(company)
        time.sleep(5)

        return {
            "company_name": company,
            "job_role": title,
            "website_link": website,
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
        }

    def _append_to_csv(self, items: List[Dict]) -> None:
        """Append records to CSV, writing header only once."""
        mode = 'a' if self.csv_exists else 'w'
        with open(self.csv_path, mode, newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            if not self.csv_exists:
                writer.writeheader()
                self.csv_exists = True
            for job in items:
                if job.get("company_name") != "Not Specified" and job.get("job_role") != "Not Specified":
                    writer.writerow(job)

    def _make_key(self, item: Dict) -> Tuple[str, str, str]:
        """Generate unique key based on company, role, and post date."""
        company = item.get("company", "").strip().lower()
        role = item.get("position", "").strip().lower()
        date_str = item.get("date", "")
        try:
            posted = datetime.fromisoformat(date_str.rstrip('Z')).replace(tzinfo=None)
        except:
            posted = datetime.fromtimestamp(item.get("epoch", 0))
        return (company, role, posted.isoformat())

    def _load_existing_csv_keys(self) -> Set[Tuple[str, str, str]]:
        """Load set of keys from existing CSV to avoid duplicates."""
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

    def load_existing_images(self) -> None:
        """Populate existing_images set from disk."""
        for filename in self.images_dir.iterdir():
            if filename.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                key = filename.stem.lower()
                self.existing_images.add(key)
        print(f"🖼️ Found {len(self.existing_images)} existing company images")

    def _fetch_job_data(self) -> List[Dict]:
        """Fetch raw job data from RemoteOK API."""
        url = "https://remoteok.com/api"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [d for d in data if isinstance(d, dict) and "id" in d]

    def get_company_image(self, company_name: str, size: Tuple[int, int] = (400, 200)) -> str:
        """Fetch or reuse a company logo via Clearbit."""
        if not company_name or company_name.lower() == "not specified":
            return ""

        company_key = company_name.strip().lower()
        # Trim common suffixes
        for suffix in [" technologies", "technology", "solutions", "solution", "pvt ltd", "private limited", "ltd", "limited", "inc", "corp", "corporation"]:
            if company_key.endswith(suffix):
                company_key = company_key[: -len(suffix)]
                break
        lookup = alias_map.get(company_key, company_key)

        filename = f"{company_name}.png"
        save_path = self.images_dir / filename
        if company_key in self.existing_images or save_path.exists():
            return filename

        domain = lookup.replace(" ", "").replace("pvt", "").replace("ltd", "") + ".com"
        logo_url = f"https://logo.clearbit.com/{domain}"

        try:
            resp = requests.get(logo_url, timeout=10)
            resp.raise_for_status()
            logo = Image.open(BytesIO(resp.content)).convert("RGBA")
            bg = Image.new("RGBA", logo.size, (255,255,255,255))
            comp = Image.alpha_composite(bg, logo)
            comp.thumbnail(size, Image.LANCZOS)
            canvas = Image.new("RGB", size, (255,255,255))
            pos = ((size[0]-comp.width)//2, (size[1]-comp.height)//2)
            canvas.paste(comp.convert("RGB"), pos)
            canvas.save(save_path)
            self.existing_images.add(company_key)
            return filename
        except Exception:
            return "hiring.png"

if __name__ == "__main__":
    RemoteJobGenerator().run_all()