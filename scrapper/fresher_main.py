import os
import requests
from bs4 import BeautifulSoup
import csv
import time
import re
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
from PIL import Image, ImageOps
from scrapper.text_extraction import generate_ai_enhanced_content
from dotenv import load_dotenv
from const import alias_map
from pathlib import Path

# load .env file to environment
load_dotenv()


class JobScrapingOrchestrator:
    def __init__(self, base_url="https://freshercareers.in/category/fresher-jobs/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.jobs_data = []
        self.detailed_jobs_data = []
        self.failed_links = []
        self.two_months_ago = datetime.now() - timedelta(days=60)  # 60 days back
        self.existing_jobs = set()  # Store existing job signatures
        self.existing_images = set()  # Store existing company images
        
        # Ensure images directory exists
        ROOT_DIR    = Path(__file__).resolve().parent.parent
        IMAGES_DIR  = ROOT_DIR / "uploaded_images"
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        self.images_dir = IMAGES_DIR
        
        # Load existing data
        self.load_existing_data()

    def load_existing_data(self):
        """Load existing CSV data to avoid duplicates"""
        module_dir = Path(__file__).resolve().parent
        self.csv_file = module_dir / "freshers_final.csv"
        self.csv_exists = os.path.exists(self.csv_file)
        
        if self.csv_exists:
            try:
                df = pd.read_csv(self.csv_file)
                print(f"📋 Found existing CSV with {len(df)} records")
                print("🔍 DUPLICATE DETECTION MODE: Only new jobs will be scraped")
                
                for _, row in df.iterrows():
                    # Create a signature for duplicate detection
                    posted_date = str(row.get('posted_on', '')).strip()
                    
                    # Parse and normalize the posted date
                    normalized_date = self.normalize_date_for_comparison(posted_date)
                    signature = f"{normalized_date}"
                    self.existing_jobs.add(signature)
                
                print(f"✅ Loaded {len(self.existing_jobs)} existing job signatures for duplicate detection")
                
            except Exception as e:
                print(f"⚠️ Warning: Could not load existing CSV: {e}")
                self.csv_exists = False
        else:
            print("📋 No existing CSV found")
            print("🆕 FRESH SCRAPING MODE: Will scrape all jobs and create new CSV")
        
        # Load existing images
        self.load_existing_images()

    def load_existing_images(self):
        """Load list of existing company images"""
        for filename in self.images_dir.iterdir():
            if filename.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                company_name = filename.name.rsplit('.', 1)[0].replace('_', '/')
                self.existing_images.add(company_name.lower())
        print(f"🖼️ Found {len(self.existing_images)} existing company images")

    def normalize_date_for_comparison(self, date_str):
        """Normalize date string for consistent comparison"""
        if not date_str or date_str == "Not specified":
            return "unknown"
        
        try:
            # Try to parse the date and format it consistently
            parsed_date = self.parse_date(date_str)
            if parsed_date:
                return parsed_date.strftime('%Y-%m-%d')
            else:
                return date_str.strip().lower()
        except:
            return date_str.strip().lower()

    def is_duplicate_job(self, company, posted_on):
        """Check if this job already exists in our database"""
        company = str(company).strip().lower()
        normalized_date = self.normalize_date_for_comparison(posted_on)
        
        signature = f"{normalized_date}"
        return signature in self.existing_jobs

    def get_company_image(self, company_name: str, size=(400, 200)) -> str:
        """Fetch company logo from Clearbit API with duplicate check"""
        if not company_name or company_name == "Not specified":
            return ""
        
        company_key = company_name.strip().lower()
        lookup_name = alias_map.get(company_key, company_key)
        
        # Clean company name for filename
        clean_company_name = company_name.replace('/', '_').replace('\\', '_')
        image_filename = f"{clean_company_name}.png"
        save_path = self.images_dir / image_filename
        
        # Check if image already exists
        if company_name.lower() in self.existing_images:
            print(f"  🖼️ Company image already exists: {image_filename}")
            return image_filename
        
        # Check if file exists on disk
        if os.path.exists(save_path):
            print(f"  🖼️ Company image file already exists: {image_filename}")
            self.existing_images.add(company_name.lower())
            return image_filename
        
        # Generate domain for logo fetching
        domain = lookup_name.lower().replace(" ", "").replace("pvt", "").replace("ltd", "").replace("&", "and") + ".com"
        logo_url = f"https://logo.clearbit.com/{domain}"

        try:
            print(f"  🌐 Fetching logo for {lookup_name}...")
            response = requests.get(logo_url, timeout=10)
            response.raise_for_status()
            
            logo = Image.open(BytesIO(response.content)).convert("RGBA")
            white_bg = Image.new("RGBA", logo.size, (255, 255, 255, 255))
            combined = Image.alpha_composite(white_bg, logo)

            # Resize and center the logo
            combined.thumbnail(size, Image.Resampling.LANCZOS)
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
            print(f"  ❌ Failed to fetch logo for {company_name}: {e} - using default image")
            image_filename = 'hiring.png'  # Default image if logo fetch fails
            return image_filename
        except Exception as e:
            print(f"  ❌ Error processing logo for {company_name}: {e} - using default image")
            return image_filename

    # ==================== BASIC JOB LISTING SCRAPER ====================
    
    def get_page_content(self, url):
        """Fetch page content with error handling"""
        try:
            print(f"Fetching: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def parse_date(self, date_str):
        """Parse date string to datetime object"""
        try:
            if 'T' in date_str:
                date_part = date_str.split('T')[0]
                return datetime.strptime(date_part, '%Y-%m-%d')
            
            date_formats = [
                '%Y-%m-%d',
                '%B %d, %Y',
                '%b %d, %Y',
                '%d %B %Y',
                '%d %b %Y'
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
            
            print(f"Could not parse date: {date_str}")
            return None
            
        except Exception as e:
            print(f"Error parsing date '{date_str}': {e}")
            return None
    
    def is_date_within_two_months(self, date_str):
        """Check if date is within last 2 months"""
        if not date_str or date_str == "Not specified":
            return True
        
        parsed_date = self.parse_date(date_str)
        if not parsed_date:
            return True
        
        return parsed_date >= self.two_months_ago
    
    def extract_company_and_role(self, title):
        """Extract company name and job role from title"""
        try:
            title = title.replace(" – Apply Now!", "").replace(" - Apply Now!", "")
            
            if "Off Campus" in title:
                parts = title.split("Off Campus", 1)
                company = parts[0].strip()
                
                remaining = parts[1] if len(parts) > 1 else ""
                role_match = re.search(r'(?:Hiring\s*(?:\d{4})?\s*[–-]\s*)([^–-]+)', remaining)
                if role_match:
                    job_role = role_match.group(1).strip()
                else:
                    role_parts = remaining.split("–", 1) or remaining.split("-", 1)
                    job_role = role_parts[1].strip() if len(role_parts) > 1 else remaining.strip()
            else:
                parts = title.split("–", 1) or title.split("-", 1)
                company = parts[0].strip()
                job_role = parts[1].strip() if len(parts) > 1 else "Not specified"
            
            company = re.sub(r'\s+(Hiring|Job|Career|Recruitment).*$', '', company, flags=re.IGNORECASE)
            
            return company.strip(), job_role.strip()
        except Exception as e:
            print(f"Error parsing title '{title}': {e}")
            return "Unknown", "Unknown"
    
    def parse_job_listings(self, html_content):
        """Parse job listings from HTML content and return (jobs, should_continue)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        articles = soup.find_all('article', class_=lambda x: x and 'post-' in x)
        
        jobs = []
        should_continue = True
        duplicates_found = 0
        
        print(f"Found {len(articles)} articles on this page")
        
        for article in articles:
            try:
                header = article.find('header', class_='entry-header')
                if not header:
                    continue
                
                title_element = header.find('h2', class_='entry-title')
                if not title_element:
                    continue
                
                link_element = title_element.find('a')
                if not link_element:
                    continue
                
                title = link_element.get_text(strip=True)
                link = link_element.get('href', '')
                
                posted_on = "Not specified"
                meta_div = header.find('div', class_='entry-meta')
                if meta_div:
                    time_element = meta_div.find('time', class_='entry-date')
                    if time_element:
                        posted_on = time_element.get('datetime', time_element.get_text(strip=True))
                
                if not self.is_date_within_two_months(posted_on):
                    print(f"Job posted more than 2 months ago: {posted_on}. Stopping scraping.")
                    should_continue = False
                    break
                
                company, job_role = self.extract_company_and_role(title)
                
                # Only check for duplicates if CSV exists
                if self.csv_exists and self.is_duplicate_job(company, posted_on):
                    print(f"  🔄 DUPLICATE SKIPPED: {company}: {job_role}")
                    duplicates_found += 1
                    continue
                
                jobs.append({
                    'company': company,
                    'job_role': job_role,
                    'posted_on': posted_on,
                    'link': link,
                    'full_title': title
                })
                
                status = "NEW" if self.csv_exists else "FOUND"
                print(f"  ✅ {status}: {company}: {job_role} ({posted_on})")
                
            except Exception as e:
                print(f"Error parsing article: {e}")
                continue
        
        if self.csv_exists:
            print(f"Page summary: {len(jobs)} new jobs, {duplicates_found} duplicates skipped")
        else:
            print(f"Page summary: {len(jobs)} jobs found")
        return jobs, should_continue
    
    def get_total_pages(self, html_content):
        """Extract total number of pages from pagination"""
        soup = BeautifulSoup(html_content, 'html.parser')
        nav = soup.find('nav', {'id': 'nav-below', 'class': 'paging-navigation'})
        
        if not nav:
            return 1
        
        nav_links = nav.find('div', class_='nav-links')
        if not nav_links:
            return 1
        
        page_links = nav_links.find_all('a', class_='page-numbers')
        max_page = 1
        
        for link in page_links:
            href = link.get('href', '')
            page_match = re.search(r'/page/(\d+)/', href)
            if page_match:
                page_num = int(page_match.group(1))
                max_page = max(max_page, page_num)
        
        return max_page
    
    def scrape_basic_listings(self):
        """Scrape basic job listings from all pages"""
        print("🚀 STEP 1: Starting basic job listing scraper...")
        print(f"Filtering jobs posted within last 2 months (since {self.two_months_ago.strftime('%Y-%m-%d')})")
        
        if self.csv_exists:
            print("📊 Mode: Incremental scraping (only new jobs)")
        else:
            print("📊 Mode: Full scraping (creating new database)")
        
        html_content = self.get_page_content(self.base_url)
        if not html_content:
            print("Failed to fetch the first page")
            return False
        
        jobs, should_continue = self.parse_job_listings(html_content)
        self.jobs_data.extend(jobs)
        
        if self.csv_exists:
            print(f"Page 1: Found {len(jobs)} new jobs")
        else:
            print(f"Page 1: Found {len(jobs)} jobs")
        
        if not should_continue:
            print("Date limit reached on first page.")
            return True
        
        total_pages = self.get_total_pages(html_content)
        print(f"Total pages available: {total_pages}")
        
        for page_num in range(2, min(total_pages + 1, 6)):  # Limit to 5 pages for demo
            print(f"\nFetching page {page_num}/{total_pages}")
            page_url = f"{self.base_url}page/{page_num}/"
            
            html_content = self.get_page_content(page_url)
            if html_content:
                jobs, should_continue = self.parse_job_listings(html_content)
                self.jobs_data.extend(jobs)
                
                if self.csv_exists:
                    print(f"Page {page_num}: Found {len(jobs)} new jobs")
                else:
                    print(f"Page {page_num}: Found {len(jobs)} jobs")
                
                if not should_continue:
                    break
            
            time.sleep(2)
        
        if self.csv_exists:
            print(f"\n✅ STEP 1 COMPLETED: Found {len(self.jobs_data)} total new jobs")
        else:
            print(f"\n✅ STEP 1 COMPLETED: Found {len(self.jobs_data)} total jobs")
        return True

    # ==================== STEP 2: DETAILED JOB SCRAPER ====================
    
    def parse_job_details_table(self, soup):
        """Extract job details from the table inside figure element"""
        job_details = {
            'company_name': 'Not specified',
            'job_role': 'Not specified', 
            'state': 'Not specified',
            'city': 'Not specified',
            'experience': 'Not specified',
            'qualification': 'Not specified',
            'batch': 'Not specified',
            'salary_package': 'Not specified'
        }
        
        try:
            figure = soup.find('figure', class_=lambda x: x and 'wp-block-table' in x)
            if not figure:
                table = soup.find('table')
            else:
                table = figure.find('table')
            
            if not table:
                return job_details
            
            rows = table.find_all('tr')
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)
                    
                    if 'company' in key:
                        job_details['company_name'] = value
                    elif 'job role' in key or 'role' in key:
                        job_details['job_role'] = value
                    elif 'location' in key or 'work location' in key:
                        location_parts = value.split(',')
                        if len(location_parts) >= 2:
                            job_details['city'] = location_parts[0].strip()
                            job_details['state'] = location_parts[1].strip()
                        else:
                            job_details['city'] = value
                    elif 'experience' in key:
                        job_details['experience'] = value
                    elif 'qualification' in key:
                        job_details['qualification'] = value
                    elif 'batch' in key:
                        job_details['batch'] = value
                    elif 'package' in key or 'salary' in key:
                        job_details['salary_package'] = value
            
        except Exception as e:
            print(f"Error parsing job details table: {e}")
        
        return job_details
    
    def find_apply_link(self, soup):
        """Find the application link"""
        try:
            button_divs = soup.find_all('div', class_='wp-block-buttons')
            
            if len(button_divs) > 1:
                button_div = button_divs[1]
                link_element = button_div.find('a', class_='wp-block-button__link')
                
                if link_element:
                    href = link_element.get('href', '')
                    return href
            
            return 'Not specified'
        
        except Exception as e:
            print(f"Error finding apply link: {e}")
            return 'Not specified'
    
    def extract_job_description(self, soup):
        """Extract job description between 'Job Description' and 'How to Apply?' headings"""
        try:
            h2_elements = soup.find_all('h2')
            
            start_h2 = None
            end_h2 = None
            
            for h2 in h2_elements:
                h2_text = h2.get_text(strip=True).lower()
                if 'job description' in h2_text:
                    start_h2 = h2
                elif 'how to apply' in h2_text and start_h2:
                    end_h2 = h2
                    break
            
            if not start_h2:
                return 'Job description not available'
            
            description_parts = []
            current_element = start_h2.next_sibling
            
            while current_element and current_element != end_h2:
                if hasattr(current_element, 'name'):
                    if current_element.name in ['p', 'div']:
                        text = current_element.get_text(strip=True)
                        if text:
                            description_parts.append(text)
                    elif current_element.name in ['ul', 'ol']:
                        list_items = current_element.find_all('li')
                        for li in list_items:
                            li_text = li.get_text(strip=True)
                            if li_text:
                                description_parts.append(f"• {li_text}")
                    elif current_element.name == 'h3':
                        h3_text = current_element.get_text(strip=True)
                        if h3_text:
                            description_parts.append(f"\n{h3_text}:")
                
                current_element = current_element.next_sibling
            
            job_description = '\n'.join(description_parts).strip()
            return job_description if job_description else 'Job description not available'
                
        except Exception as e:
            print(f"Error extracting job description: {e}")
            return 'Error extracting job description'
    
    def scrape_detailed_job_info(self, job_link):
        """Scrape detailed information from a single job posting"""
        html_content = self.get_page_content(job_link)
        if not html_content:
            return None
        
        soup = BeautifulSoup(html_content, 'html.parser')
        article = soup.find('article') or soup
        
        job_details = self.parse_job_details_table(article)
        job_details['website_link'] = self.find_apply_link(article)
        job_details['job_information'] = self.extract_job_description(article)
        
        return job_details
    
    def scrape_all_detailed_info(self):
        """Scrape detailed information for all basic jobs"""
        print(f"\n🔍 STEP 2: Starting detailed scraping for {len(self.jobs_data)} jobs...")
        
        for i, job in enumerate(self.jobs_data, 1):
            print(f"\n[{i}/{len(self.jobs_data)}] Processing: {job.get('company', 'Unknown')}")
            
            job_link = job.get('link', '')
            if not job_link:
                continue
            
            job_details = self.scrape_detailed_job_info(job_link)

            if job_details and job_details.get('company_name') != 'Not specified' and job_details.get('job_role') != 'Not specified':
                enhanced_job = {
                    'no': i,
                    'original_company': job.get('company', ''),
                    'original_job_role': job.get('job_role', ''),
                    'posted_on': job.get('posted_on', ''),
                    'link': job_link,
                    **job_details
                }
                
                self.detailed_jobs_data.append(enhanced_job)
                print(f"  ✅ Successfully scraped")
            else:
                self.failed_links.append(job_link)
                print(f"  ❌ Failed to scrape")
            
            if i % 5 == 0:
                time.sleep(3)
            else:
                time.sleep(1)
        
        print(f"\n✅ STEP 2 COMPLETED: {len(self.detailed_jobs_data)} jobs detailed")

    
    # ==================== ORCHESTRATION & FINAL CSV ====================
    
    def process_all_jobs_with_ai(self):
        """Process all detailed jobs with AI enhancement and image fetching"""
        print(f"\n🤖 STEP 3: AI Enhancement for {len(self.detailed_jobs_data)} jobs...")
        
        enhanced_jobs = []
        
        for i, job in enumerate(self.detailed_jobs_data, 1):
            print(f"\n[{i}/{len(self.detailed_jobs_data)}] Enhancing: {job.get('company_name', 'Unknown')}")
            
            # Prepare job description for AI
            job_description = job.get('job_information', 'No job description available')
            
            # Generate AI-enhanced content
            ai_content = generate_ai_enhanced_content(job_description, job.get('company_name', 'Unknown'), job.get('job_role', 'Unknown'), job.get('qualifications', 'Unknown'))

            # Fetch company image with duplicate check
            image_path = self.get_company_image(job.get('company_name', ''))
            
            # Create final job record matching the database schema
            final_job = {
                'company_name': job.get('company_name', 'Not specified'),
                'job_role': job.get('job_role', 'Not specified'),
                'website_link': job.get('website_link', 'Not specified'),
                'state': job.get('state', 'Not specified'),
                'city': job.get('city', 'Not specified'),
                'experience': job.get('experience', 'Not specified'),
                'qualification': ai_content.get('qualification', job.get('qualification', 'Not specified')),
                'batch': job.get('batch', 'Not specified'),
                'salary_package': job.get('salary_package', 'Not specified'),
                'job_description': ai_content.get('job_description', job_description),
                'key_responsibility': ai_content.get('key_responsibility', 'Not specified'),
                'about_company': ai_content.get('about_company', 'Not specified'),
                'selection_process': ai_content.get('selection_process', 'Not specified'),
                'image': image_path,
                'posted_on': job.get('posted_on', 'Not specified')  # Keep posted_on for future reference
            }
            
            enhanced_jobs.append(final_job)
            print(f"  ✅ Enhanced successfully")
            
            # Rate limiting
            time.sleep(2)
        
        self.enhanced_jobs_data = enhanced_jobs
        print(f"\n✅ STEP 3 COMPLETED: {len(enhanced_jobs)} jobs enhanced")

    def save_final_csv(self, filename=None):
        """Save the final enhanced data to CSV matching the database schema"""
        
        if filename is None:
            module_dir = Path(__file__).resolve().parent
            filename = module_dir / "freshers_final.csv"
            

        if not hasattr(self, 'enhanced_jobs_data') or not self.enhanced_jobs_data:
            print("No enhanced data to save")
            return
        
        try:
            fieldnames = [
                'company_name', 'job_role', 'website_link', 'state', 'city',
                'experience', 'qualification', 'batch', 'salary_package',
                'job_description', 'key_responsibility', 'about_company',
                'selection_process', 'image', 'posted_on'
            ]
            
            # Determine write mode based on CSV existence
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
            
            with open(filename, mode, newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                if write_header:
                    writer.writeheader()
                
                for job in self.enhanced_jobs_data:
                    writer.writerow(job)
            
            print(f"\n🎉 CSV FILE {action}: {filename}")
            print(f"📊 Records processed: {len(self.enhanced_jobs_data)}")
            
            if not self.csv_exists:
                print("💡 Next time this script runs, it will only scrape NEW jobs!")
                
        except Exception as e:
            print(f"❌ Error saving final CSV: {e}")

    def run_complete_pipeline(self):
        """Run the complete job scraping and enhancement pipeline"""
        print("=" * 80)
        print("🚀 STARTING COMPLETE JOB SCRAPING PIPELINE")
        print("=" * 80)
        
        # Step 1: Scrape basic job listings
        if not self.scrape_basic_listings():
            print("❌ Failed at basic scraping step")
            return
        
        if not self.jobs_data:
            if self.csv_exists:
                print("🎉 No new jobs found! All jobs are already in the database.")
            else:
                print("😔 No jobs found to scrape.")
            return
        
        # Step 2: Scrape detailed job information
        self.scrape_all_detailed_info()
        
        # Step 3: AI enhancement and image fetching
        self.process_all_jobs_with_ai()
        
        # Step 4: Save final CSV
        self.save_final_csv()
        
        print("\n" + "=" * 80)
        print("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
        if self.csv_exists:
            print(f"✅ New records added: {len(self.enhanced_jobs_data)}")
        else:
            print(f"✅ Total records created: {len(self.enhanced_jobs_data)}")
            print("💡 CSV database created! Future runs will only scrape new jobs.")
        print("=" * 80)

def main():
    """Main function to run the complete orchestrator"""
    print("🤖 Job Scraping Orchestrator - Complete Pipeline with Duplicate Detection")
    print("=" * 80)
    
    orchestrator = JobScrapingOrchestrator()
    orchestrator.run_complete_pipeline()
    return True

if __name__ == "__main__":
    main()