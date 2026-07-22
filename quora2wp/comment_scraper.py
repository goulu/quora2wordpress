import sys
import os
import time
import re
import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By

def log_lifecycle(message):
    log_path = "/home/goulu/Documents/develop/quora2wordpress/chrome_lifecycle.log"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pid = os.getpid()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [PYTHON PID {pid}] {message}\n")
    except Exception as e:
        sys.stderr.write(f"Failed to write to chrome_lifecycle.log: {e}\n")

def expand_all_comments(driver):
    """Attempt to click expand buttons and load collapsed comment threads."""
    try:
        driver.execute_script("document.querySelectorAll('[id*=\"onetrust\"], [class*=\"onetrust\"], [id*=\"consent\"]').forEach(el => el.remove());")
    except Exception:
        pass
        
    for attempt in range(5):
        expanded_something = False
        
        # 1. Click collapsed comment previews
        try:
            collapsed_elms = driver.find_elements(By.CSS_SELECTOR, "div.qu-bg--darken.qu-cursor--pointer")
            for el in collapsed_elms:
                try:
                    driver.execute_script("arguments[0].click();", el)
                    expanded_something = True
                    time.sleep(0.5)
                except Exception:
                    pass
        except Exception:
            pass
            
        # 2. Click comment/reply expansion buttons/spans/links/divs
        try:
            xpath_query = (
                "//*[self::button or self::span or self::a or (self::div and @role='button')]"
                "[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ', 'abcdefghijklmnopqrstuvwxyzaaaaaaeceeeeiiiidnoooooouuuuyt'), 'réponse') or "
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ', 'abcdefghijklmnopqrstuvwxyzaaaaaaeceeeeiiiidnoooooouuuuyt'), 'reponse') or "
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ', 'abcdefghijklmnopqrstuvwxyzaaaaaaeceeeeiiiidnoooooouuuuyt'), 'comment') or "
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ', 'abcdefghijklmnopqrstuvwxyzaaaaaaeceeeeiiiidnoooooouuuuyt'), 'repli')]"
            )
            all_clickable = driver.find_elements(By.XPATH, xpath_query)
            for el in all_clickable:
                try:
                    driver.execute_script("arguments[0].click();", el)
                    expanded_something = True
                    time.sleep(0.5)
                except Exception:
                    pass
        except Exception:
            pass
            
        if not expanded_something:
            break

def clean_comment_html(soup, text_div):
    """Clean the HTML snippet of the comment, removing unnecessary wrappers/tags."""
    # 1. Replace link cards with simple <a> tags
    for a in text_div.find_all('a'):
        if a.find('div'):
            href = a.get('href', '')
            title_div = a.find(class_=re.compile(r'qu-truncateLines--3'))
            if title_div:
                title = title_div.get_text(strip=True)
            else:
                first_div = a.find('div')
                title = first_div.get_text(strip=True) if first_div else href
            
            clean_link = soup.new_tag('a', href=href, target='_blank')
            clean_link.string = title
            a.replace_with(clean_link)
        else:
            href = a.get('href', '')
            a.attrs = {'href': href, 'target': '_blank'}
            
    # 2. Remove divs that just display a raw URL (like the footer of a link card)
    for div in text_div.find_all('div'):
        div_text = div.get_text(strip=True)
        if div_text.startswith('http://') or div_text.startswith('https://'):
            div.decompose()
            
    # 3. Clean up the tags and attributes bottom-up
    allowed_tags = {'p', 'a', 'b', 'strong', 'i', 'em', 'code', 'pre', 'br'}
    for tag in list(text_div.find_all(True)):
        if tag.name not in allowed_tags:
            tag.unwrap()
        else:
            if tag.name == 'a':
                href = tag.get('href', '')
                tag.attrs = {'href': href, 'target': '_blank'}
            else:
                tag.attrs = {}
                
    parts = []
    for child in text_div.children:
        parts.append(str(child))
    return "".join(parts).strip()

def scrape_comments_from_urls(urls, gui=False):
    """
    Scrapes comments for the given list of Quora URLs.
    If gui is True, launches Google Chrome with UI visible.
    Returns a dictionary: {"success": bool, "comments": list, "error": str, "resolved_url": str}
    """
    # Prepend standard system paths to process environment
    os.environ["PATH"] = "/usr/bin:/bin:/usr/local/bin:" + os.environ.get("PATH", "")

    # Pre-check URLs using cloudscraper to filter out 404s
    valid_urls = []
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        for url in urls:
            try:
                res = scraper.get(url, timeout=5, allow_redirects=False)
                sys.stderr.write(f"DEBUG: Precheck {url} -> status={res.status_code}\n")
                if res.status_code == 200:
                    valid_urls.append(url)
                elif res.status_code in [403, 503, 301, 302]:
                    valid_urls.append(url)
            except Exception as e:
                sys.stderr.write(f"DEBUG: Precheck error for {url}: {e}\n")
                valid_urls.append(url)
    except ImportError:
        sys.stderr.write("DEBUG: cloudscraper not installed, skipping precheck\n")
        valid_urls = list(urls)
        
    if not valid_urls:
        return {"success": False, "error": "None of the Quora URLs could be loaded (Page not found or redirected).", "comments": []}

    # Set up a persistent profile to remember login sessions/cookies
    user_home = os.path.expanduser("~")
    main_profile_dir = os.path.join(user_home, ".config", "quora_importer_chrome_profile")
    
    import threading
    import shutil
    thread_id = threading.get_ident()
    pid = os.getpid()
    profile_dir = os.path.join(user_home, ".config", f"quora_importer_chrome_profile_{pid}_{thread_id}")
    
    if os.path.exists(main_profile_dir):
        try:
            shutil.copytree(main_profile_dir, profile_dir, symlinks=True,
                            ignore=shutil.ignore_patterns('SingletonLock', 'SingletonSocket', 'SingletonCookie', '*lock*', '*socket*'))
        except Exception as e:
            sys.stderr.write(f"DEBUG: Error copying profile: {e}\n")
            os.makedirs(profile_dir, exist_ok=True)
    else:
        os.makedirs(profile_dir, exist_ok=True)
        
    try:
        options = webdriver.ChromeOptions()
        options.add_argument(f"user-data-dir={profile_dir}")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Run headlessly by default, unless gui is requested
        if not gui:
            options.add_argument("--headless=new")
        
        options.page_load_strategy = 'eager'
        
        html = ""
        successful_url = None
        
        for url in valid_urls:
            driver = None
            try:
                log_lifecycle(f"comment_scraper: CREATING Chrome webdriver for URL: {url}")
                driver = webdriver.Chrome(options=options)
                cd_pid = "unknown"
                if hasattr(driver, 'service') and driver.service and hasattr(driver.service, 'process') and driver.service.process:
                    cd_pid = driver.service.process.pid
                log_lifecycle(f"comment_scraper: CREATED Chrome webdriver (chromedriver PID={cd_pid})")
                
                driver.set_page_load_timeout(20)
                
                # Prevent Cloudflare from detecting webdriver
                driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                })
                
                driver.get(url)
                
                # Smart wait loop: waits up to 15s for Cloudflare's challenge page to clear
                is_valid = False
                for i in range(15):
                    time.sleep(1)
                    html = driver.page_source
                    soup = BeautifulSoup(html, "html.parser")
                    
                    title = soup.title.string if soup.title else ''
                    sys.stderr.write(f"DEBUG: i={i}, title={title}\n")
                    
                    # Wait until Cloudflare verification clears
                    if title and ('Un instant' in title or 'Just a moment' in title or 'Vérification de sécurité' in title):
                        continue
                        
                    title_lower = title.strip().lower()
                    page_text_lower = soup.get_text().lower()
                    
                    sys.stderr.write(f"DEBUG: title_lower={title_lower}, text_snippet={page_text_lower[:200].replace(chr(10), ' ')}\n")
                    
                    if (not title or 
                        title_lower in ["erreur", "error", "quora"] or 
                        "page not found" in page_text_lower or 
                        "n'avons pas trouvé la page" in page_text_lower or 
                        "page introuvable" in page_text_lower or 
                        "n'existe pas" in page_text_lower):
                        sys.stderr.write("DEBUG: Match failed invalid condition\n")
                        break
                    
                    is_valid = True
                    break
                
                if is_valid:
                    expand_all_comments(driver)
                    successful_url = url
                    html = driver.page_source
                    log_lifecycle(f"comment_scraper: QUITTING Chrome webdriver (chromedriver PID={cd_pid})")
                    driver.quit()
                    log_lifecycle(f"comment_scraper: QUIT Chrome webdriver successfully (chromedriver PID={cd_pid})")
                    driver = None
                    break
            except Exception as e:
                sys.stderr.write(f"DEBUG: Error trying to scrape URL {url}: {e}\n")
                log_lifecycle(f"comment_scraper: EXCEPTION in scraping block: {e}")
                continue
            finally:
                if driver:
                    try:
                        cd_pid = "unknown"
                        if hasattr(driver, 'service') and driver.service and hasattr(driver.service, 'process') and driver.service.process:
                            cd_pid = driver.service.process.pid
                        log_lifecycle(f"comment_scraper: QUITTING Chrome webdriver in finally (chromedriver PID={cd_pid})")
                        driver.quit()
                        log_lifecycle(f"comment_scraper: QUIT Chrome webdriver successfully in finally (chromedriver PID={cd_pid})")
                    except Exception as ex:
                        log_lifecycle(f"comment_scraper: ERROR quitting Chrome webdriver in finally (chromedriver PID={cd_pid}): {ex}")
                
        if not successful_url:
            return {"success": False, "error": "None of the Quora URLs could be loaded (Page not found or redirected).", "comments": []}
            
        if not html:
            return {"success": False, "error": "Could not retrieve page source", "comments": [], "resolved_url": successful_url}
            
        # Parse HTML using BeautifulSoup
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            comments_header = soup.find(string=re.compile(r'^(Commentaires|Comments)$'))
            if not comments_header:
                return {"success": True, "comments": [], "warning": "Comments section not found on page.", "resolved_url": successful_url}
                
            comments_section = None
            curr = comments_header.parent
            while curr:
                links = curr.find_all('a', href=re.compile(r'/profile/'))
                if len(links) > 1:
                    comments_section = curr
                    break
                curr = curr.parent
                
            if not comments_section:
                return {"success": True, "comments": [], "warning": "Comments section container not found.", "resolved_url": successful_url}
                
            author_links = comments_section.find_all('a', href=re.compile(r'/profile/'))
            
            extracted = []
            seen_comments = set()
            
            for link in author_links:
                author_name = link.get_text(strip=True)
                profile_url = link.get('href')
                if not author_name:
                    continue
                    
                wrapper = None
                curr = link.parent
                for _ in range(15):
                    if not curr:
                        break
                    text_div = curr.find(lambda el: el.name == 'div' and el.get('class') == ['q-text'])
                    if text_div and link in curr.descendants and text_div != link:
                        wrapper = curr
                        break
                    curr = curr.parent
                    
                if not wrapper:
                    continue
                    
                wrapper_id = id(wrapper)
                if wrapper_id in seen_comments:
                    continue
                seen_comments.add(wrapper_id)
                
                comment_id = None
                date_text = ""
                for a in wrapper.find_all('a'):
                    href = a.get('href', '')
                    if 'comment_id=' in href:
                        m = re.search(r'comment_id=(\d+)', href)
                        if m:
                            comment_id = m.group(1)
                        date_text = a.get_text(strip=True)
                        
                if not comment_id:
                    comment_id = f"fallback_{len(seen_comments)}"
                    
                text_div = wrapper.find(lambda el: el.name == 'div' and el.get('class') == ['q-text'])
                comment_text = clean_comment_html(soup, text_div) if text_div else ""
                    
                distance = 0
                p = wrapper
                while p and p != comments_section:
                    distance += 1
                    p = p.parent
                    
                extracted.append({
                    "id": comment_id,
                    "author": author_name,
                    "profile_url": profile_url,
                    "text": comment_text,
                    "date": date_text,
                    "distance": distance
                })
                
            if extracted:
                min_distance = min(c["distance"] for c in extracted)
                for c in extracted:
                    c["nesting"] = (c["distance"] - min_distance) // 3
                    del c["distance"]
                    
            last_seen_at_level = {}
            for c in extracted:
                lvl = c["nesting"]
                last_seen_at_level[lvl] = c["id"]
                if lvl > 0:
                    c["parent_id"] = last_seen_at_level.get(lvl - 1)
                else:
                    c["parent_id"] = None
                    
            return {"success": True, "comments": extracted, "resolved_url": successful_url}
            
        except Exception as e:
            return {"success": False, "error": f"Parsing error: {str(e)}", "comments": [], "resolved_url": successful_url}
    finally:
        if os.path.exists(profile_dir) and profile_dir != main_profile_dir:
            try:
                shutil.rmtree(profile_dir, ignore_errors=True)
            except Exception:
                pass
