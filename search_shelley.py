import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

# Target info
SEARCH_TERMS = ["Shelley Stoner", "Michele Stoner", "mstoner@gettysburg.edu"]
BASE_DOMAIN = "www.gettysburg.edu"
START_URL = "https://www.gettysburg.edu"

visited = set()
to_visit = [START_URL]
results = []

print(f"Starting audit for {SEARCH_TERMS}...")

while to_visit:
    url = to_visit.pop(0)
    if url in visited:
        continue
    visited.add(url)

    try:
        # Respectful delay so we don't hammer the college server
        time.sleep(0.1) 
        
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            continue

        # Check for the person's name
        content = response.text.lower()
        for term in SEARCH_TERMS:
            if term.lower() in content:
                print(f"MATCH FOUND: {url}")
                results.append(url)
                break # Move to next page once one term is found

        # Find new internal links to follow
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            full_url = urljoin(START_URL, link['href'])
            parsed = urlparse(full_url)
            
            # Stay on the gettysburg.edu domain and avoid non-html files for now
            if parsed.netloc == BASE_DOMAIN and full_url not in visited:
                if not any(ext in full_url for ext in ['.jpg', '.png', '.mp4', '.zip']):
                    to_visit.append(full_url)

    except Exception as e:
        print(f"Error scanning {url}: {e}")

# Save results to a file for your HR/Admin team
with open("stoner_mentions_report.txt", "w") as f:
    for item in results:
        f.write(item + "\n")

print(f"Audit complete. Found {len(results)} pages.")