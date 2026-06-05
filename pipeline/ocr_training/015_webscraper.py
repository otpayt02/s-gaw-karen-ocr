# ============================================================
# FILE: 5_webscraper.py
# PURPOSE: Phase 2 data discovery tool. Crawls Karen language
#          websites to find real-world Karen script images and
#          text samples for expanding the training dataset beyond
#          synthetic images. Saves image URLs and page text to
#          disk for manual review and labeling.
# PIPELINE POSITION: Phase 2 — Real-world data collection
# REQUIRES: requests, BeautifulSoup4 (pip install beautifulsoup4)
# PRODUCES: /root/karen_lang_trans/scraped_karen_data.json
#           /root/karen_lang_trans/scraped_images/ folder
# ============================================================

# IMPORT — requests for making HTTP GET requests to Karen websites
import requests

# IMPORT — BeautifulSoup for parsing HTML and extracting content
from bs4 import BeautifulSoup

# IMPORT — json for saving scraped data records
import json

# IMPORT — os for creating output directories
import os

# IMPORT — time for adding delays between requests (polite scraping)
import time

# IMPORT — urllib.parse for handling relative URLs on scraped pages
from urllib.parse import urljoin, urlparse

# LIST/DICT/SET — target Karen language websites to scrape
# WHY: these are known sources of real Sgaw Karen text and imagery
TARGET_URLS = [
    'https://www.karendictionary.org/',
    'https://www.sil.org/resources/publications/entry/42178',
]

# VARIABLE DECLARATION — output directory for downloaded images
IMG_OUT_DIR = '/root/karen_lang_trans/scraped_images/'

# FUNCTION CALL — creates the image output directory
os.makedirs(IMG_OUT_DIR, exist_ok=True)

# VARIABLE DECLARATION — list to accumulate all scraped data records
scraped_records = []

# VARIABLE DECLARATION — HTTP request headers to identify our scraper politely
HEADERS = {'User-Agent': 'KarenOCR-DataCollector/1.0 (academic research)'}

# LOOP — iterates over each target Karen language website
for base_url in TARGET_URLS:
    # EXCEPTION HANDLER — catches network errors per URL without stopping the loop
    try:
        # FUNCTION CALL — makes an HTTP GET request to the Karen website
        # ARGUMENT — timeout=10 prevents hanging on slow servers
        response = requests.get(base_url, headers=HEADERS, timeout=10)

        # CONDITIONAL — only processes successful responses (HTTP 200)
        if response.status_code != 200:
            print(f"Skipping {base_url} — HTTP {response.status_code}")
            continue

        # INSTANTIATION — parses the HTML response with BeautifulSoup
        # ARGUMENT — 'html.parser' uses Python's built-in HTML parser
        soup = BeautifulSoup(response.text, 'html.parser')

        # METHOD CALL — extracts all text content from the page
        # WHY: Karen text in page content can be used for dictionary expansion
        page_text = soup.get_text(separator='\n', strip=True)

        # VARIABLE DECLARATION — finds all image tags on the page
        img_tags = soup.find_all('img')

        # VARIABLE DECLARATION — list of absolute image URLs found
        img_urls = []

        # LOOP — processes each image tag found on the page
        for img in img_tags:
            # METHOD CALL — gets the src attribute (image URL)
            src = img.get('src', '')
            # CONDITIONAL — skips empty src attributes
            if not src:
                continue
            # FUNCTION CALL — converts relative URLs to absolute
            # WHY: many websites use relative paths like /images/karen_word.png
            abs_url = urljoin(base_url, src)
            img_urls.append(abs_url)

        # METHOD CALL — appends this page's data to the records list
        scraped_records.append({
            'source_url':  base_url,
            'text_sample': page_text[:2000],
            'image_urls':  img_urls[:20]
        })

        # OUTPUT/PRINT — reports progress
        print(f"Scraped {base_url}: {len(img_urls)} images, {len(page_text)} chars")

        # FUNCTION CALL — waits 2 seconds between requests
        # WHY: polite scraping avoids overloading the server and getting IP-blocked
        time.sleep(2)

    except Exception as e:
        # OUTPUT/PRINT — reports the error and continues to next URL
        print(f"Error scraping {base_url}: {e}")

# FILE OPERATION — saves all scraped records to JSON
out_path = '/root/karen_lang_trans/scraped_karen_data.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(scraped_records, f, ensure_ascii=False, indent=2)

# OUTPUT/PRINT — final summary
print(f"\nScraping complete. {len(scraped_records)} pages saved to {out_path}")
print("Review scraped_karen_data.json to find Karen script images for labeling.")
