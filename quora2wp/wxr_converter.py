import os
import re
import datetime
import urllib.parse
import unicodedata
import zipfile
from bs4 import BeautifulSoup

def clean_quora_url(url):
    """Strip Quora redirect wrappers and return the clean outbound URL."""
    if not url:
        return url
    if 'quora.com/_/redirect' in url:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        if 'url' in params and params['url']:
            return urllib.parse.unquote(params['url'][0])
    return url

def parse_quora_date(date_str):
    """
    Parse Quora export date strings like 'Dec 26, 2012 03:29 AM PST'
    Returns tuple of (local_datetime, gmt_datetime).
    """
    date_str = date_str.strip()
    parts = date_str.split()
    if not parts:
        return None, None
    
    tz = parts[-1]
    # Check if tz is a timezone abbreviation (e.g. PST, PDT, CEST, CET, UTC)
    if tz.isupper() and 3 <= len(tz) <= 4:
        dt_part = ' '.join(parts[:-1])
    else:
        tz = 'PST' # fallback timezone
        dt_part = ' '.join(parts)
        
    try:
        # standard format: Dec 26, 2012 03:29 AM
        # Clean double spaces and commas
        dt_part_clean = re.sub(r'\s+', ' ', dt_part).replace(',', '')
        if 'AM' in dt_part_clean or 'PM' in dt_part_clean:
            dt = datetime.datetime.strptime(dt_part_clean, "%b %d %Y %I:%M %p")
        else:
            dt = datetime.datetime.strptime(dt_part_clean, "%b %d %Y %H:%M")
    except Exception:
        # Fallback if parsing fails: return current time
        return datetime.datetime.now(), datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        
    # Calculate timezone offset relative to GMT
    offset = 0
    if tz == 'PDT':
        offset = -7
    elif tz == 'PST':
        offset = -8
    elif tz == 'CEST':
        offset = 2
    elif tz == 'CET':
        offset = 1
    elif tz == 'UTC':
        offset = 0
    else:
        offset = -8 # Default to California time (PST) since Quora is US-based
        
    gmt_dt = dt - datetime.timedelta(hours=offset)
    return dt, gmt_dt

def parse_comment_date_helper(date_str, post_date_str):
    """
    Parse a Quora comment date string (relative or absolute, French or English)
    and return (local_date_str, gmt_date_str) in MySQL format 'YYYY-MM-DD HH:MM:SS'.
    """
    now = datetime.datetime.now()
    
    # Try parsing post_date_str to get fallback time
    post_dt = None
    if post_date_str:
        try:
            post_dt = datetime.datetime.strptime(post_date_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
            
    if not post_dt:
        post_dt = now

    if not date_str:
        # Fallback to post_dt + 1 day
        dt = post_dt + datetime.timedelta(days=1)
        return dt.strftime("%Y-%m-%d %H:%M:%S"), dt.strftime("%Y-%m-%d %H:%M:%S")

    # Lowercase and clean
    date_str_clean = date_str.lower().strip()
    
    # Strip prefixes like "mis à jour le", "mis à jour", "updated", "répondu le", etc.
    prefixes = ["mis à jour le", "mis à jour", "updated", "répondu le", "answered"]
    for p in prefixes:
        if date_str_clean.startswith(p):
            date_str_clean = date_str_clean[len(p):].strip()

    french_months = {
        'janvier': 'January', 'février': 'February', 'mars': 'March',
        'avril': 'April', 'mai': 'May', 'juin': 'June',
        'juillet': 'July', 'août': 'August', 'septembre': 'September',
        'octobre': 'October', 'novembre': 'November', 'décembre': 'December',
        # Short months
        'janv.': 'Jan', 'févr.': 'Feb', 'avr.': 'Apr', 'juil.': 'Jul', 'sept.': 'Sep',
        'oct.': 'Oct', 'nov.': 'Nov', 'déc.': 'Dec'
    }

    # Normalize French months to English
    for fr, en in french_months.items():
        date_str_clean = date_str_clean.replace(fr, en)

    # 1. Try parsing direct absolute date formats
    for fmt in [
        "%d %B %Y", "%d %B", "%B %d %Y", "%B %d",
        "%d %b %Y", "%d %b", "%b %d %Y", "%b %d",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"
    ]:
        try:
            dt = datetime.datetime.strptime(date_str_clean, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=post_dt.year)
            if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                dt = dt.replace(hour=12, minute=0, second=0)
            return dt.strftime("%Y-%m-%d %H:%M:%S"), dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    # 2. Check relative date regex patterns
    val = None
    delta = None
    
    # years
    m = re.match(r'^(\d+)\s*(ans?|y|yrs?|years?)', date_str_clean)
    if m:
        val = int(m.group(1))
        delta = datetime.timedelta(days=val*365)
        
    # months
    if not delta:
        m = re.match(r'^(\d+)\s*(mois|mo|mos?|months?)', date_str_clean)
        if m:
            val = int(m.group(1))
            delta = datetime.timedelta(days=val*30)
            
    # weeks
    if not delta:
        m = re.match(r'^(\d+)\s*(sem\.?|w|weeks?)', date_str_clean)
        if m:
            val = int(m.group(1))
            delta = datetime.timedelta(weeks=val)
            
    # days
    if not delta:
        m = re.match(r'^(\d+)\s*(j|d|days?|jours?)', date_str_clean)
        if m:
            val = int(m.group(1))
            delta = datetime.timedelta(days=val)
            
    # hours
    if not delta:
        m = re.match(r'^(\d+)\s*(h|hours?|heures?)', date_str_clean)
        if m:
            val = int(m.group(1))
            delta = datetime.timedelta(hours=val)
            
    # minutes
    if not delta:
        m = re.match(r'^(\d+)\s*(min|m|minutes?)', date_str_clean)
        if m:
            val = int(m.group(1))
            delta = datetime.timedelta(minutes=val)
            
    # seconds
    if not delta:
        m = re.match(r'^(\d+)\s*(s|seconds?)', date_str_clean)
        if m:
            val = int(m.group(1))
            delta = datetime.timedelta(seconds=val)

    if delta:
        computed = now - delta
        if computed < post_dt:
            computed = post_dt + datetime.timedelta(days=1)
        return computed.strftime("%Y-%m-%d %H:%M:%S"), computed.strftime("%Y-%m-%d %H:%M:%S")

    computed = post_dt + datetime.timedelta(days=1)
    return computed.strftime("%Y-%m-%d %H:%M:%S"), computed.strftime("%Y-%m-%d %H:%M:%S")

def process_html_content(content_html, folder_name, image_base_url, use_cdn_images=True):
    """Clean links and rewrite relative image URLs inside the HTML body."""
    if not content_html:
        return ""
    
    # Replace [math] and [/math] with $
    content_html = re.sub(r'\[/?math\]', '$', content_html, flags=re.IGNORECASE)
    
    # If there are no HTML tags, avoid BeautifulSoup warning and overhead
    if '<' not in content_html:
        return content_html
    
    # Use html.parser to process the fragment without wrapping it in html/body tags
    soup = BeautifulSoup(content_html, 'html.parser')
    
    # Collapse newlines inside text nodes to avoid wpautop rendering extra <br> tags on WordPress import
    for text_node in soup.find_all(string=True):
        if text_node.parent and text_node.parent.name in ['pre', 'code']:
            continue
        if text_node.string:
            new_text = re.sub(r'\s*\n\s*', ' ', text_node.string)
            if new_text != text_node.string:
                text_node.replace_with(new_text)
    
    # 1. Clean Quora redirect links
    for a in soup.find_all('a'):
        href = a.get('href')
        if href:
            a['href'] = clean_quora_url(href)
            
    # 2. Rewrite image sources / attributes
    if use_cdn_images:
        for element in soup.find_all(True):
            for attr, val in list(element.attrs.items()):
                if isinstance(val, str) and 'qimg-' in val:
                    m = re.search(r'qimg-([a-f0-9]+)', val)
                    if m:
                        element[attr] = f"https://qph.cf2.quoracdn.net/main-qimg-{m.group(1)}"
    else:
        # Fallback rewriting to local assets
        for img in soup.find_all('img'):
            src = img.get('src')
            master_src = img.get('master_src')
            if src:
                base = image_base_url.rstrip('/')
                if src.startswith('images/'):
                    img['src'] = f"{base}/{folder_name}/{src}"
                elif 'qimg-' in src:
                    img['src'] = f"{base}/{folder_name}/images/{src}"
            if master_src:
                base = image_base_url.rstrip('/')
                if master_src.startswith('images/'):
                    img['master_src'] = f"{base}/{folder_name}/{master_src}"
                elif 'qimg-' in master_src:
                    img['master_src'] = f"{base}/{folder_name}/images/{master_src}"
                
    return str(soup)

def slugify(text):
    """Normalize accents and convert text into a URL-friendly slug."""
    if not text:
        return "post"
    normalized = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    slug = normalized.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug if slug else "post"

def extract_author_from_folder(folder_name):
    """Attempt to extract author name from folder (e.g. 'Contenu_Philippe_Guglielmetti_1' -> 'Philippe Guglielmetti')."""
    if folder_name.startswith('Contenu_'):
        name = folder_name[8:]
        name = re.sub(r'_\d+$', '', name) # Strip trailing digits
        name_parts = name.split('_')
        return ' '.join(name_parts)
    return None

def get_post_title(post_data, h2_type):
    """Extract or generate a clean title for the post."""
    for key in ['Question', 'Post title', 'Title']:
        if key in post_data and post_data[key]:
            title = post_data[key].strip()
            title = re.sub(r'\s+', ' ', title)
            return title
            
    # Fallback for Space elements/shares that do not have a title key
    content_key = 'Post content' if 'Post content' in post_data else 'Content'
    if content_key in post_data and post_data[content_key]:
        html_content = post_data[content_key]
        s = BeautifulSoup(html_content, 'html.parser')
        
        # If the content starts with an anchor link, use its text as the title
        first_a = s.find('a')
        if first_a and first_a.text.strip():
            # Check if the link starts early in the HTML body
            if html_content.index(str(first_a)) < 50:
                return first_a.text.strip()
                
        # Otherwise, use the first 80 characters of text
        text = s.get_text().strip()
        text = re.sub(r'\s+', ' ', text)
        if len(text) > 80:
            return text[:80] + '...'
        return text if text else f"Untitled {h2_type}"
        
    return f"Untitled {h2_type}"

def escape_cdata(text):
    """Escape CDATA termination sequence in XML fields."""
    if not text:
        return ""
    return text.replace("]]>", "]]&gt;")

def remove_accents(text):
    """Remove accents from a string using NFKD normalization."""
    if not text:
        return ""
    return "".join(c for c in unicodedata.normalize('NFKD', text) if unicodedata.category(c) != 'Mn')

def quora_slugify(title, replace_apostrophes=False):
    """Reconstruct a Quora-compatible slug that preserves case and accents."""
    if not title:
        return ''
    
    # Strip [math] and [/math] tags if present
    title = re.sub(r'\[/?math\]', '', title, flags=re.IGNORECASE)

    if replace_apostrophes:
        # Option A: replace apostrophes, periods, and accent typos with spaces (which become hyphens)
        for c in ["'", '’', '.', '´', '`']:
            title = title.replace(c, ' ')
    else:
        # Option B: delete all apostrophes, periods, and accent typos
        for c in ["'", '’', '.', '´', '`']:
            title = title.replace(c, '')

    # Replace slashes, underscores, carets, parentheses, brackets, and braces with spaces to prevent word merging
    for c in ['/', '_', '^', '(', ')', '[', ']', '{', '}']:
        title = title.replace(c, ' ')

    # Strip everything except letters, numbers, spaces, and hyphens (preserving accents and case)
    slug = re.sub(r'[^\w\s\-]', '', title)
    slug = slug.replace('_', '')  # \w matches underscore, so strip it manually
    
    # Replace spaces/tabs and consecutive hyphens with a single hyphen
    slug = re.sub(r'[\s\-]+', '-', slug)
    slug = slug.strip('-')
    
    # Truncate slug to 190 bytes to match Quora answer URLs
    slug_bytes = slug.encode('utf-8')
    if len(slug_bytes) > 190:
        truncated_bytes = slug_bytes[:190]
        truncated = truncated_bytes.decode('utf-8', errors='ignore')
        
        trunc_len_bytes = len(truncated.encode('utf-8'))
        next_char_bytes = slug_bytes[trunc_len_bytes:trunc_len_bytes+1]
        next_char = next_char_bytes.decode('utf-8', errors='ignore')
        
        if next_char == '-' or next_char == '':
            slug = truncated
        else:
            last_hyphen = truncated.rfind('-')
            if last_hyphen != -1:
                slug = truncated[:last_hyphen]
            else:
                slug = truncated

    # Enforce URL-encoded length limit of 255 characters
    encoded = urllib.parse.quote(slug, safe='-+')
    if len(encoded) > 255:
        while len(urllib.parse.quote(slug, safe='-+')) > 255 and len(slug) > 0:
            slug = slug[:-1]
        last_hyphen = slug.rfind('-')
        if last_hyphen != -1:
            slug = slug[:last_hyphen]
            
    # URL-encode all accented and special characters while preserving hyphens and plus signs
    return urllib.parse.quote(slug, safe='-+')

def append_suffix_to_url(url, suffix):
    """Helper to append a numeric suffix to a URL."""
    if url.endswith('/'):
        return url + suffix.strip('/')
    else:
        return url.rstrip('/') + suffix

def build_quora_url_with_slug(post, type_str, title_slug, profile_slug, domain, is_answer):
    """Build the actual Quora URL structure using the provided slug."""
    if is_answer and profile_slug and title_slug:
        return f"https://{domain}/{title_slug}/answer/{profile_slug}"
        
    space_subdomain = ''
    
    # 1. Try to extract it from the direct URL (if any metadata exists)
    for key in ['Answer', 'Question', 'Link', 'url', 'Share url', 'Share URL']:
        if key in post and post[key]:
            val = post[key].strip()
            if val.startswith(('http://', 'https://')) and 'quora.com' in val:
                parsed = urllib.parse.urlparse(val)
                host = parsed.netloc
                if host:
                    parts = host.split('.')
                    if len(parts) >= 3 and parts[-2] == 'quora' and parts[-1] == 'com':
                        sub = parts[0].lower()
                        if sub not in ['www', 'fr', 'es', 'de', 'it', 'en']:
                            space_subdomain = sub
                            break
                            
    # 2. Fall back to Space name
    if not space_subdomain and 'Space name' in post and post['Space name']:
        normalized = remove_accents(post['Space name'])
        space_subdomain = re.sub(r'[^A-Za-z0-9]', '', normalized).lower()
        
    if space_subdomain:
        if title_slug:
            return f"https://{space_subdomain}.quora.com/{title_slug}"
        return f"https://{space_subdomain}.quora.com"
        
    if title_slug:
        return f"https://{domain}/{title_slug}"
        
    return f"https://{domain}"

def get_candidate_urls(post, quora_username):
    """Get candidate Quora URLs based on title containing apostrophes or not."""
    title = ''
    if 'Question' in post and post['Question']:
        title = post['Question']
    elif 'Title' in post and post['Title']:
        title = post['Title']
    elif 'Post title' in post and post['Post title']:
        title = post['Post title']
        
    if not title:
        title = get_post_title(post, post.get('type', ''))
        
    # Check if there is a direct URL in metadata
    for key in ['Answer', 'Question', 'Link', 'url', 'Share url', 'Share URL']:
        if key in post and post[key]:
            val = post[key].strip()
            if val.startswith(('http://', 'https://')) and 'quora.com' in val:
                return [val]
                
    # Base domain based on language
    lang = post.get('Content language', 'français').lower()
    domain = 'fr.quora.com' if 'fran' in lang else 'www.quora.com'
    
    # Author profile name
    profile_slug = ''
    if quora_username:
        normalized = remove_accents(quora_username)
        cleaned_name = re.sub(r'[^A-Za-z0-9_\-\s]', '', normalized)
        profile_slug = cleaned_name.replace(' ', '-').replace('_', '-')
        profile_slug = re.sub(r'-+', '-', profile_slug)
        
    # Check post type
    post_type = post.get('type', '')
    is_answer = 'répondre' in post_type.lower() or 'answer' in post_type.lower()
    
    url_a = build_quora_url_with_slug(post, post_type, quora_slugify(title, replace_apostrophes=True), profile_slug, domain, is_answer)
    url_b = build_quora_url_with_slug(post, post_type, quora_slugify(title, replace_apostrophes=False), profile_slug, domain, is_answer)
    
    groups = {
        'slug_a': [],
        'slug_b': []
    }
    
    if url_a:
        groups['slug_a'].append(url_a)
        groups['slug_a'].append(append_suffix_to_url(url_a, '-1'))
        groups['slug_a'].append(append_suffix_to_url(url_a, '-2'))
        
    if url_b:
        groups['slug_b'].append(url_b)
        groups['slug_b'].append(append_suffix_to_url(url_b, '-1'))
        groups['slug_b'].append(append_suffix_to_url(url_b, '-2'))
        
    urls = []
    # Add slug_a first, then slug_b (matches quora-importer ordering default success method logic)
    for group in ['slug_a', 'slug_b']:
        for url in groups[group]:
            if url not in urls:
                urls.append(url)
                
    return urls

def test_url_status(url):
    """Helper to check if a candidate URL exists (non-404 status)."""
    # 1. Try cloudscraper
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        res = scraper.get(url, timeout=5, stream=True)
        return res.status_code
    except Exception:
        pass

    # 2. Try requests
    try:
        import requests
        res = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }, timeout=5, stream=True)
        return res.status_code
    except Exception:
        pass

    # 3. Try curl command line
    try:
        import subprocess
        res = subprocess.run([
            'curl', '-I', '-s', '-L', '-o', '/dev/null', '-w', '%{http_code}',
            '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            url
        ], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            status = int(res.stdout.strip())
            if status > 0:
                return status
    except Exception:
        pass

    return 0

def find_best_quora_url(post, quora_username, check_online=False):
    """Resolves the best Quora URL for a post."""
    candidate_urls = get_candidate_urls(post, quora_username)
    if not candidate_urls:
        return ""
        
    if check_online:
        for candidate in candidate_urls:
            status = test_url_status(candidate)
            if status == 200 or (status > 0 and status != 404):
                return candidate
                
    return candidate_urls[0]

def get_active_chrome_processes():
    """Scan /proc to find active chrome, chromium, or chromedriver processes, excluding Vivaldi."""
    active = []
    if not os.path.exists('/proc'):
        return active
    for pid_str in os.listdir('/proc'):
        if pid_str.isdigit():
            try:
                pid = int(pid_str)
                if pid == os.getpid():
                    continue
                comm_path = os.path.join('/proc', pid_str, 'comm')
                cmd_path = os.path.join('/proc', pid_str, 'cmdline')
                
                comm = ""
                if os.path.exists(comm_path):
                    with open(comm_path, 'r', errors='ignore') as f:
                        comm = f.read().strip().lower()
                        
                cmdline = ""
                if os.path.exists(cmd_path):
                    with open(cmd_path, 'rb') as f:
                        cmdline = f.read().replace(b'\x00', b' ').decode('utf-8', errors='ignore').lower()
                
                # Exclude Vivaldi processes
                if 'vivaldi' in comm or 'vivaldi' in cmdline:
                    continue
                    
                is_chrome = False
                if any(x in comm for x in ['chrome', 'chromedriver', 'chromium']):
                    is_chrome = True
                elif any(x in cmdline for x in ['chrome', 'chromedriver', 'chromium']):
                    is_chrome = True
                    
                if is_chrome:
                    active.append((pid, comm, cmdline))
            except (IOError, OSError, ValueError):
                continue
    return active

def generate_wxr(posts, folder_name, image_base_url, author, author_email, use_cdn_images=True, quora_username=None, check_online=False, scrape_topics=True, scrape_comments=False, test_mode=False, max_processes=3, output_file=None):
    """Generate a valid WXR XML string from a list of post dictionaries."""
    site_title = f"Quora Export - {folder_name}"
    site_link = "https://quora.com"
    site_desc = "WordPress eXtended RSS export from Quora"
    pub_date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    
    # Try to determine author name
    extracted_author = extract_author_from_folder(folder_name)
    author_display = author if author else (extracted_author if extracted_author else "Admin")
    author_login = slugify(author_display)
    author_email_str = author_email if author_email else f"{author_login}@localhost"
    
    # Resolve the default quora username to use for link generation
    resolved_quora_username = quora_username
    if not resolved_quora_username:
        resolved_quora_username = author_login
        
    # Determine channel language from first post
    chan_lang = "fr-FR"
    if posts:
        lang = posts[0].get("Content language", "").lower()
        if "english" in lang:
            chan_lang = "en-US"
            
    xml = []
    xml.append(f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"
	xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
	xmlns:content="http://purl.org/rss/1.0/modules/content/"
	xmlns:wfw="http://wellformedweb.org/CommentAPI/"
	xmlns:dc="http://purl.org/dc/elements/1.1/"
	xmlns:wp="http://wordpress.org/export/1.2/"
>

<channel>
	<title>{escape_cdata(site_title)}</title>
	<link>{site_link}</link>
	<description>{escape_cdata(site_desc)}</description>
	<pubDate>{pub_date}</pubDate>
	<language>{chan_lang}</language>
	<wp:wxr_version>1.2</wp:wxr_version>
	<wp:base_site_url>{site_link}</wp:base_site_url>
	<wp:base_blog_url>{site_link}</wp:base_blog_url>

	<wp:author>
		<wp:author_id>1</wp:author_id>
		<wp:author_login>{author_login}</wp:author_login>
		<wp:author_email>{author_email_str}</wp:author_email>
		<wp:author_display_name><![CDATA[{escape_cdata(author_display)}]]></wp:author_display_name>
		<wp:author_first_name><![CDATA[]]></wp:author_first_name>
		<wp:author_last_name><![CDATA[]]></wp:author_last_name>
	</wp:author>
""")

    total_posts = len(posts)

    def process_single_post(idx_post):
        idx, post = idx_post
        title = get_post_title(post, post["type"])
        title = re.sub(r'\[/?math\]', '$', title, flags=re.IGNORECASE)
        print(f"  [{idx}/{total_posts}] Converting: {title}", flush=True)
        raw_content = post.get("Content", post.get("Post content", ""))
        content = process_html_content(raw_content, folder_name, image_base_url, use_cdn_images)
        
        # Dates
        raw_date = post.get("Creation time", post.get("Last updated", post.get("Time", "")))
        local_dt, gmt_dt = parse_quora_date(raw_date)
        
        if local_dt:
            post_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")
            post_date_gmt = gmt_dt.strftime("%Y-%m-%d %H:%M:%S")
            item_pub_date = gmt_dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
        else:
            now = datetime.datetime.now()
            post_date = now.strftime("%Y-%m-%d %H:%M:%S")
            post_date_gmt = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            item_pub_date = pub_date
            
        post_name = slugify(title)
        
        # Reconstruct the correct Quora URL for the <link> tag
        quora_url = find_best_quora_url(post, resolved_quora_username, check_online)
        if not quora_url:
            # General fallback
            lang = post.get('Content language', 'français').lower()
            domain = 'fr.quora.com' if 'fran' in lang else 'www.quora.com'
            quora_url = f"https://{domain}/{post_name}"
            
        # Map statuses
        status = "publish"
        if "brouillon" in post["type"].lower():
            status = "draft"
            
        # Unique post ID
        post_id = idx
        
        # Categories & tags
        cats_and_tags = []
        
        # Base categories/tags depending on block type
        if post["type"] == "Répondre":
            cats_and_tags.append('<category domain="category" nicename="quora-answers"><![CDATA[Quora Answers]]></category>')
        elif post["type"] == "Brouillon de réponse":
            cats_and_tags.append('<category domain="category" nicename="quora-drafts"><![CDATA[Quora Drafts]]></category>')
        elif post["type"] in ["Envoi d'espace", "Élément d'espace"]:
            cats_and_tags.append('<category domain="category" nicename="quora-space-posts"><![CDATA[Quora Space Posts]]></category>')
        else:
            cats_and_tags.append('<category domain="category" nicename="quora-export"><![CDATA[Quora Export]]></category>')
            
        # Add space name category if applicable
        if "Space name" in post and post["Space name"]:
            space_name = post["Space name"]
            cats_and_tags.append(f'<category domain="category" nicename="{slugify(space_name)}"><![CDATA[{escape_cdata(space_name)}]]></category>')
            
        # Add content language as tag
        if "Content language" in post and post["Content language"]:
            lang = post["Content language"]
            cats_and_tags.append(f'<category domain="post_tag" nicename="{slugify(lang)}"><![CDATA[{escape_cdata(lang)}]]></category>')
            
        # Global Quora tag
        cats_and_tags.append('<category domain="post_tag" nicename="quora"><![CDATA[Quora]]></category>')
        
        # Automatic Scraping of Topics (Tags)
        if scrape_topics and quora_url:
            try:
                from quora2wp.topic_scraper import scrape_topics_from_url
                topics_result = scrape_topics_from_url(quora_url)
                if topics_result.get("success") and topics_result.get("topics"):
                    for topic in topics_result["topics"]:
                        tag_xml = f'<category domain="post_tag" nicename="{slugify(topic)}"><![CDATA[{escape_cdata(topic)}]]></category>'
                        if tag_xml not in cats_and_tags:
                            cats_and_tags.append(tag_xml)
                    print(f"  [{idx}/{total_posts}]   - Topics: Success (found {len(topics_result['topics'])} topics)", flush=True)
                else:
                    pass
            except Exception as e:
                print(f"  [{idx}/{total_posts}]   - Topics error: {e}", flush=True)
                
        # Automatic Scraping of Comments
        comments_xml_str = ""
        if scrape_comments and quora_url:
            try:
                from quora2wp.comment_scraper import scrape_comments_from_urls
                comments_result = scrape_comments_from_urls([quora_url])
                if comments_result.get("success") and comments_result.get("comments"):
                    base_comment_id = idx * 10000
                    id_to_int = {}
                    for c_idx, c in enumerate(comments_result["comments"], start=1):
                        id_to_int[c["id"]] = base_comment_id + c_idx
                        
                    comments_list = []
                    for c_idx, c in enumerate(comments_result["comments"], start=1):
                        c_int_id = id_to_int[c["id"]]
                        parent_int_id = 0
                        if c.get("parent_id") and c["parent_id"] in id_to_int:
                            parent_int_id = id_to_int[c["parent_id"]]
                            
                        c_date, c_date_gmt = parse_comment_date_helper(c.get("date"), post_date)
                        
                        profile_url = c.get("profile_url", "")
                        if profile_url and not profile_url.startswith("http"):
                            profile_url = f"https://www.quora.com{profile_url}"
                            
                        comments_list.append(f"""		<wp:comment>
			<wp:comment_id>{c_int_id}</wp:comment_id>
			<wp:comment_author><![CDATA[{escape_cdata(c.get('author', 'Anonyme'))}]]></wp:comment_author>
			<wp:comment_author_email><![CDATA[]]></wp:comment_author_email>
			<wp:comment_author_url>{escape_cdata(profile_url)}</wp:comment_author_url>
			<wp:comment_author_IP><![CDATA[]]></wp:comment_author_IP>
			<wp:comment_date><![CDATA[{c_date}]]></wp:comment_date>
			<wp:comment_date_gmt><![CDATA[{c_date_gmt}]]></wp:comment_date_gmt>
			<wp:comment_content><![CDATA[{escape_cdata(c.get('text', ''))}]]></wp:comment_content>
			<wp:comment_approved><![CDATA[1]]></wp:comment_approved>
			<wp:comment_type><![CDATA[comment]]></wp:comment_type>
			<wp:comment_parent>{parent_int_id}</wp:comment_parent>
			<wp:comment_user_id>0</wp:comment_user_id>
		</wp:comment>""")
                    comments_xml_str = "\n".join(comments_list)
                    print(f"  [{idx}/{total_posts}]   - Comments: Success (found {len(comments_result['comments'])} comments)", flush=True)
                else:
                    pass
            except Exception as e:
                print(f"  [{idx}/{total_posts}]   - Comments error: {e}", flush=True)

        cats_xml = "\n\t\t".join(cats_and_tags)
        
        item_xml = f"""	<item>
		<title><![CDATA[{escape_cdata(title)}]]></title>
		<link>{escape_cdata(quora_url)}</link>
		<pubDate>{item_pub_date}</pubDate>
		<dc:creator><![CDATA[{author_login}]]></dc:creator>
		<guid isPermaLink="false">{site_link}/?p={post_id}</guid>
		<description></description>
		<content:encoded><![CDATA[{escape_cdata(content)}]]></content:encoded>
		<excerpt:encoded><![CDATA[]]></excerpt:encoded>
		<wp:post_id>{post_id}</wp:post_id>
		<wp:post_date><![CDATA[{post_date}]]></wp:post_date>
		<wp:post_date_gmt><![CDATA[{post_date_gmt}]]></wp:post_date_gmt>
		<wp:comment_status><![CDATA[open]]></wp:comment_status>
		<wp:ping_status><![CDATA[open]]></wp:ping_status>
		<wp:post_name><![CDATA[{post_name}]]></wp:post_name>
		<wp:status><![CDATA[{status}]]></wp:status>
		<wp:post_parent>0</wp:post_parent>
		<wp:menu_order>0</wp:menu_order>
		<wp:post_type><![CDATA[post]]></wp:post_type>
		<wp:post_password><![CDATA[]]></wp:post_password>
		<wp:is_sticky>0</wp:is_sticky>
		{cats_xml}
{comments_xml_str}
	</item>
"""
        return idx, item_xml, content, comments_xml_str

    import time
    import signal

    # Always process sequentially to avoid Chrome process memory saturation
    for idx, post in enumerate(posts, start=1):
        idx, item_xml, content, comments_xml_str = process_single_post((idx, post))
        xml.append(item_xml)
        
        # Write to file progressively if output_file is provided
        if output_file:
            try:
                out_dir = os.path.dirname(output_file)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                
                # build a temporary XML string with the current channel closed
                current_xml = xml + ["</channel>\n</rss>"]
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write('\n'.join(current_xml))
            except Exception as fe:
                sys.stderr.write(f"Error writing progressive XML to '{output_file}': {fe}\n")
        
        if test_mode:
            # Check for active chrome processes after converting each article
            time.sleep(1)  # small grace period for clean driver shutdown
            active_chrome = get_active_chrome_processes()
            if active_chrome:
                print(f"  [Test Mode] WARNING: Active Chrome processes detected after converting post {idx}:")
                for pid, comm, cmdline in active_chrome:
                    print(f"    - PID {pid}: {comm} ({cmdline[:80]}...)")
                print("  [Test Mode] Terminating active Chrome processes to free memory...")
                for pid, _, _ in active_chrome:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except Exception:
                        pass
            else:
                print(f"  [Test Mode] Verification: No active Chrome processes detected after converting post {idx}.", flush=True)

            has_image = "<img" in content.lower()
            has_comments = bool(comments_xml_str.strip())
            if has_image and has_comments:
                print(f"  --> Test mode: Found post with both images and comments! Early exit triggered.")
                break
            if idx >= 30:
                print(f"  --> Test mode: Reached backup limit of 30 processed posts. Stopping early.")
                break
        
    xml.append("""</channel>
</rss>""")
    return '\n'.join(xml)

def process_html_soup_to_posts(soup, include_drafts, include_space_posts):
    """Common extraction logic to parse post structures from index.html BeautifulSoup."""
    target_types = ["Répondre", "Brouillon de réponse", "Envoi d'espace", "Élément d'espace", "Brouillon de publication"]
    
    posts = []
    h2s = soup.find_all("h2")
    
    for h2 in h2s:
        h2_type = h2.text.strip()
        if h2_type not in target_types:
            continue
            
        # Parse post fields from siblings
        post_data = {"type": h2_type}
        curr = h2.next_sibling
        while curr and curr.name != "h2":
            if curr.name == "div":
                strong = curr.find("strong")
                if strong:
                    label = strong.text.strip().rstrip(":").strip()
                    span = curr.find("span")
                    if span:
                        if label in ["Content", "Post content"]:
                            # Preserve child markup for content
                            value = "".join(str(c) for c in span.contents)
                        else:
                            value = span.text.strip()
                    else:
                        value = curr.text.replace(strong.text, "", 1).strip()
                    post_data[label] = value
            curr = curr.next_sibling
            
        # Filters
        if "brouillon" in h2_type.lower() and not include_drafts:
            continue
        if h2_type in ["Envoi d'espace", "Élément d'espace"] and not include_space_posts:
            continue
            
        posts.append(post_data)
        
    return posts

def process_folder(folder_path, image_base_url, author, author_email, include_drafts, include_space_posts, use_cdn_images=True, quora_username=None, check_online=False, scrape_topics=True, scrape_comments=False, test_mode=False, max_processes=3, output_file=None):
    """Parse index.html in the folder and return the WXR XML content if posts found."""
    folder_name = os.path.basename(folder_path)
    index_path = os.path.join(folder_path, "index.html")
    if not os.path.isfile(index_path):
        return None, 0
        
    with open(index_path, "r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "lxml")
        
    posts = process_html_soup_to_posts(soup, include_drafts, include_space_posts)
        
    if not posts:
        return None, 0
        
    wxr_content = generate_wxr(posts, folder_name, image_base_url, author, author_email, use_cdn_images, quora_username, check_online, scrape_topics, scrape_comments, test_mode, max_processes, output_file=output_file)
    return wxr_content, len(posts)

def process_zip(zip_path, image_base_url, author, author_email, include_drafts, include_space_posts, use_cdn_images=True, quora_username=None, check_online=False, scrape_topics=True, scrape_comments=False, test_mode=False, max_processes=3, output_file=None):
    """Parse index.html in the zip file and return the WXR XML content if posts found."""
    folder_name = os.path.splitext(os.path.basename(zip_path))[0]
    
    with zipfile.ZipFile(zip_path, 'r') as z:
        # Find index.html inside the zip.
        index_name = None
        for name in z.namelist():
            if name.endswith('index.html'):
                index_name = name
                break
                
        if not index_name:
            raise FileNotFoundError(f"index.html not found in zip archive '{zip_path}'")
            
        with z.open(index_name) as f:
            html_content = f.read().decode('utf-8', errors='replace')
            
    soup = BeautifulSoup(html_content, "lxml")
    posts = process_html_soup_to_posts(soup, include_drafts, include_space_posts)
        
    if not posts:
        return None, 0
        
    wxr_content = generate_wxr(posts, folder_name, image_base_url, author, author_email, use_cdn_images, quora_username, check_online, scrape_topics, scrape_comments, test_mode, max_processes, output_file=output_file)
    return wxr_content, len(posts)

def run_conversion(input_path, output_dir, image_base_url, author, author_email, include_drafts, include_space_posts, use_cdn_images=True, quora_username=None, check_online=False, scrape_topics=True, scrape_comments=False, test_mode=False, max_processes=3):
    """Processes input_path (which can be a single zip, single folder, or dir of folders/zips) and saves WXR to output_dir."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Error: Input path '{input_path}' does not exist.")
        
    os.makedirs(output_dir, exist_ok=True)
    
    targets = []
    
    if os.path.isfile(input_path):
        if input_path.endswith('.zip'):
            targets.append(('zip', input_path))
        else:
            raise ValueError(f"Error: Supported file inputs must be .zip files, got '{input_path}'.")
    else:
        # It is a directory. Search for valid subfolders and zip files.
        for entry in os.listdir(input_path):
            full_path = os.path.join(input_path, entry)
            if os.path.isdir(full_path):
                if os.path.isfile(os.path.join(full_path, "index.html")):
                    targets.append(('dir', full_path))
            elif os.path.isfile(full_path) and entry.endswith('.zip'):
                targets.append(('zip', full_path))
                
    if not targets:
        print(f"No valid Quora export folders or .zip files found in '{input_path}'.")
        return
        
    targets.sort(key=lambda t: t[1])
    
    total_files = 0
    total_posts = 0
    
    print(f"Scanning '{input_path}' for exports...")
    
    for target_type, path in targets:
        name = os.path.basename(path)
        if target_type == 'zip':
            print(f"\nProcessing zip file '{name}'...", flush=True)
            try:
                folder_name = os.path.splitext(name)[0]
                output_file = os.path.join(output_dir, f"{folder_name}.xml")
                wxr_content, post_count = process_zip(
                    path, image_base_url, author, author_email, include_drafts, include_space_posts, use_cdn_images, quora_username, check_online, scrape_topics, scrape_comments, test_mode, max_processes, output_file=output_file
                )
                if post_count > 0:
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(wxr_content)
                    print(f"--> Success! Saved {post_count} posts to '{output_file}'")
                    total_files += 1
                    total_posts += post_count
                else:
                    print("--> Skipped (no matching content found)")
            except Exception as e:
                print(f"Error: {e}")
        else:
            print(f"\nProcessing directory '{name}'...", flush=True)
            try:
                output_file = os.path.join(output_dir, f"{name}.xml")
                wxr_content, post_count = process_folder(
                    path, image_base_url, author, author_email, include_drafts, include_space_posts, use_cdn_images, quora_username, check_online, scrape_topics, scrape_comments, test_mode, max_processes, output_file=output_file
                )
                if post_count > 0:
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(wxr_content)
                    print(f"--> Success! Saved {post_count} posts to '{output_file}'")
                    total_files += 1
                    total_posts += post_count
                else:
                    print("--> Skipped (no matching content found)")
            except Exception as e:
                print(f"Error: {e}")
                
    print(f"\nCompleted! Converted {total_files} inputs to WXR files, with a total of {total_posts} posts.")
