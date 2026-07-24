# quora2wordpress

Converts Quora export files/folders to WXR files importable into WordPress, and allows scraping Quora topics and comments.

This project combines local conversion features and Quora command-line scraping tools.

## Installation

1. Make sure you have Python 3.12+ installed.
2. Configure the virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Web Interface

You can launch a modern Web Interface (identical in design to the `quora-importer` WordPress plugin) allowing you to drag & drop `.zip` archives, configure all conversion options, watch live logs, and download generated WXR files directly:

```bash
# Launch the web interface (opens on http://localhost:5000 by default)
python quora2wp.py --web

# Or run directly via app.py
python app.py
```

## CLI Usage

The main script is `quora2wp.py`. It converts Quora export folders or `.zip` archives (containing an `index.html` file) into WordPress WXR XML files. By default, it automatically retrieves Quora topics, but comment scraping is disabled by default.

```bash
# Converts all zips present in the "tests/" folder and saves the XML files in the same location ("tests/")
python quora2wp.py tests/

# Converts files in "tests/" and saves results in the "exports/" folder
python quora2wp.py tests/ exports/

# Converts a specific archive, saves the result in "exports/" and specifies a Quora username
python quora2wp.py tests/Contenu_Dr._Goulu_5.zip exports/ --quora-username Dr-Goulu
```

Positional arguments:
* `input_path` (Required): Path to a single Quora export `.zip` file, or a directory containing them.
* `output_dir` (Optional): Destination folder for generated WXR XML files. If not specified, WXR files will be saved in the same location as `input_path`.

Available options:
* `--include-drafts`: Include draft posts (`True` or `False`, default: `True`)
* `--include-space-posts`: Include space posts and shares (`True` or `False`, default: `True`)
* `--quora-username`: Quora profile username slug (e.g. `Dr-Goulu`) to reconstruct valid answer URLs (default: derived from folder name)
* `--check-online`: Enable online verification of candidate URLs to ensure links are active (can be slow or blocked by Cloudflare)
* `--scrape-topics`: Automatically retrieve Quora tags/topics for each converted post (`True` or `False`, default: `True`)
* `--scrape-comments`: Automatically retrieve comments and nested replies for each converted post (`True` or `False`, default: `False`)
* `--link-position`: Position to insert backlink to Quora in post content (`none`, `top`, or `bottom`, default: `none`)
* `--link-template`: HTML link template with `$link$` placeholder (default: `<a href="$link$" target="_blank">voir sur Quora</a>`)
* `--test`: Mode test. Convertit uniquement un maximum de 10 articles contenant des images pour valider rapidement la conversion et la génération des médias WXR.
