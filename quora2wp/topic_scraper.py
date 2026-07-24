import json
import re
import sys
import os
import time
import datetime

def log_lifecycle(message):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(script_dir) == 'quora2wp':
        log_path = os.path.join(os.path.dirname(script_dir), "chrome_lifecycle.log")
    else:
        log_path = os.path.join(script_dir, "chrome_lifecycle.log")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pid = os.getpid()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [PYTHON PID {pid}] {message}\n")
    except Exception as e:
        sys.stderr.write(f"Failed to write to chrome_lifecycle.log: {e}\n")

def scrape_topics_from_url(url):
    """
    Scrapes topic names associated with a Quora URL using 4 fallback scraping methods:
    1. cloudscraper (to handle Cloudflare bypass)
    2. requests
    3. urllib
    4. Selenium Chrome (headless)
    Returns a dictionary: {"success": bool, "topics": list, "error": str}
    """
    html = ""
    success = False
    error_msg = "Could not fetch URL"
    status_code = 0

    # Ensure standard system paths are in environment for selenium/chromedriver
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
            
            log_lifecycle(f"topic_scraper: CREATING Chrome webdriver for URL: {url}")
            driver = webdriver.Chrome(options=options)
            cd_pid = "unknown"
            if hasattr(driver, 'service') and driver.service and hasattr(driver.service, 'process') and driver.service.process:
                cd_pid = driver.service.process.pid
            log_lifecycle(f"topic_scraper: CREATED Chrome webdriver (chromedriver PID={cd_pid})")
            
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
            log_lifecycle(f"topic_scraper: EXCEPTION in selenium block: {e}")
        finally:
            if driver:
                try:
                    cd_pid = "unknown"
                    if hasattr(driver, 'service') and driver.service and hasattr(driver.service, 'process') and driver.service.process:
                        cd_pid = driver.service.process.pid
                    log_lifecycle(f"topic_scraper: QUITTING Chrome webdriver (chromedriver PID={cd_pid})")
                    driver.quit()
                    log_lifecycle(f"topic_scraper: QUIT Chrome webdriver successfully (chromedriver PID={cd_pid})")
                except Exception as ex:
                    log_lifecycle(f"topic_scraper: ERROR quitting Chrome webdriver (chromedriver PID={cd_pid}): {ex}")

    if not success:
        return {"success": False, "error": error_msg, "topics": []}

    # Extract topics using JSON regex pattern
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

    return {"success": True, "topics": topics}
