import json
import re
import sys
import os
import time
import datetime

def log_lifecycle(message):
    pass

def fetch_html_from_url(url):
    """
    Fetches raw HTML for a Quora URL using 5 fallback scraping methods:
    1. cloudscraper (to handle Cloudflare bypass)
    2. requests
    3. urllib
    4. curl CLI
    5. Selenium Chrome (headless)
    Returns (success, html, error_msg)
    """
    html = ""
    success = False
    error_msg = "Could not fetch URL"
    status_code = 0

    os.environ["PATH"] = "/usr/bin:/bin:/usr/local/bin:" + os.environ.get("PATH", "")

    # Method 1: cloudscraper
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, timeout=10)
        status_code = response.status_code
        if response.status_code == 200:
            html = response.text
            success = True
        else:
            error_msg = f"HTTP {response.status_code}"
    except Exception as e:
        error_msg = f"cloudscraper: {str(e)}"

    # Method 2: requests
    if not success and status_code != 404:
        try:
            import requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            }
            response = requests.get(url, headers=headers, timeout=10)
            status_code = response.status_code
            if response.status_code == 200:
                html = response.text
                success = True
            else:
                error_msg = f"HTTP {response.status_code}"
        except Exception as e:
            error_msg = f"requests: {str(e)}"

    # Method 3: urllib
    if not success and status_code != 404:
        try:
            import urllib.request
            import urllib.error
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')
                success = True
        except urllib.error.HTTPError as e:
            status_code = e.code
            error_msg = f"HTTP {e.code}"
        except Exception as e:
            error_msg = f"urllib: {str(e)}"

    # Method 4: curl
    if not success and status_code != 404:
        try:
            import subprocess
            res = subprocess.run([
                'curl', '-s', '-L',
                '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '-H', 'Accept-Language: fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
                url
            ], capture_output=True, timeout=10)
            if res.returncode == 0:
                html = res.stdout.decode('utf-8', errors='ignore')
                if "page not found" in html.lower() or "page introuvable" in html.lower() or "n'avons pas trouvé la page" in html.lower():
                    status_code = 404
                    error_msg = "HTTP 404"
                elif "un instant" in html.lower() or "just a moment" in html.lower():
                    error_msg = "curl: blocked by Cloudflare challenge"
                else:
                    success = True
            else:
                error_msg = f"curl error: returncode {res.returncode}"
        except Exception as e:
            error_msg = f"curl: {str(e)}"

    # Method 5: Selenium Chrome
    if not success and status_code != 404:
        driver = None
        try:
            from selenium import webdriver
            options = webdriver.ChromeOptions()
            options.add_argument('--headless=new')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            driver = webdriver.Chrome(options=options)
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
            driver.get(url)
            
            # Wait up to 5 seconds for Cloudflare Turnstile to clear
            for _ in range(5):
                title = driver.title if driver.title else ""
                if "Un instant" in title or "Just a moment" in title or "Vérification de sécurité" in title:
                    time.sleep(1)
                else:
                    break
            
            title_lower = driver.title.strip().lower() if driver.title else ""
            if (not title_lower or 
                title_lower in ["erreur", "error", "quora"] or 
                "page not found" in title_lower or 
                "page introuvable" in title_lower):
                status_code = 404
                error_msg = "HTTP 404"
            else:
                html = driver.page_source
                success = True
        except Exception as e:
            error_msg = f"selenium: {str(e)}"
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    return success, html, error_msg

def extract_topics_from_html(html):
    """Extract topic names from Quora HTML string using JSON regex pattern."""
    if not html:
        return []

    pattern = r'\\*\"url\\*\":\\*\"((?:https?://[^\"/\\ ]+)?/topic/(?:[^\"\\]|\\.)*?)\\*\",\\*\"name\\*\":\\*\"((?:[^\"\\]|\\.)*?)\\*\"'
    matches = re.findall(pattern, html)

    topics = []
    for m in matches:
        name = m[1]
        name_clean = name.replace('\\"', '"').replace('\\\\', '\\')
        try:
            decoded_name = bytes(name_clean, "utf-8").decode("unicode_escape")
        except Exception:
            decoded_name = name_clean

        decoded_name = decoded_name.strip()
        if decoded_name and decoded_name not in topics and len(decoded_name) < 50:
            topics.append(decoded_name)

    return topics

def scrape_topics_from_url(url):
    """Scrapes topic names associated with a Quora URL."""
    success, html, error_msg = fetch_html_from_url(url)
    if not success or not html:
        return {"success": False, "error": error_msg, "topics": []}

    topics = extract_topics_from_html(html)
    return {"success": True, "topics": topics}
