#!/usr/bin/env python3
"""
Quora to WordPress CLI Tool
Converts local export folders or .zip archives to WordPress WXR format.
"""

import os
import sys
import argparse
from quora2wp.wxr_converter import run_conversion

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected (true/false).')

def main():
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    saved_cfg = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                saved_cfg = json.load(f)
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Convert local Quora export folders (index.html) or .zip archives to WordPress WXR format",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--web", "-w",
        action="store_true",
        help="Launch the Flask web application interface"
    )
    
    parser.add_argument(
        "input_path",
        nargs="?",
        default=None,
        help="Path to a single Quora export .zip file, or a directory/folder containing them"
    )
    
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=None,
        help="Directory to save generated WXR XML files (default: same directory/location as input_path)"
    )
    
    parser.add_argument(
        "--include-drafts", 
        type=str2bool, 
        default=saved_cfg.get("include_drafts", True), 
        help="Include draft posts (default: True)"
    )
    parser.add_argument(
        "--include-space-posts", 
        type=str2bool, 
        default=saved_cfg.get("include_space_posts", True), 
        help="Include space posts and shares (default: True)"
    )
    parser.add_argument(
        "--quora-username",
        default=saved_cfg.get("quora_username", ""),
        help="The Quora profile username slug (e.g. Dr-Goulu) to reconstruct valid answer URLs (default: derived from folder name)"
    )
    parser.add_argument(
        "--scrape-topics",
        type=str2bool,
        default=saved_cfg.get("scrape_topics", True),
        help="Automatically scrape Quora topics/tags for each post (default: True)"
    )
    parser.add_argument(
        "--scrape-comments",
        type=str2bool,
        default=saved_cfg.get("scrape_comments", False),
        help="Automatically scrape Quora comments/replies for each post (default: False)"
    )
    parser.add_argument(
        "--max-processes", "-p",
        type=int,
        default=1,
        help="Deprecated/Ignored: conversion is now strictly sequential to avoid Chrome memory saturation (default: 1)"
    )
    parser.add_argument(
        "--link-position",
        choices=["none", "top", "bottom"],
        default=saved_cfg.get("link_position", "none"),
        help="Position to insert link to Quora in post content (none, top, or bottom; default: none)"
    )
    parser.add_argument(
        "--link-template",
        default=saved_cfg.get("link_template", '<a href="$link$" target="_blank">voir sur Quora</a>'),
        help='HTML template for Quora link, using $link$ as URL variable (default: \'<a href="$link$" target="_blank">voir sur Quora</a>\')'
    )
    parser.add_argument(
        "--min-content-length",
        type=int,
        default=saved_cfg.get("min_content_length", 0),
        help="Minimum content character length below which a published post is converted to a draft (default: 0)"
    )
    parser.add_argument(
        "--r2w-support",
        type=str2bool,
        default=saved_cfg.get("r2w_support", False),
        help="Convert Wikipedia links to Reference 2 Wiki syntax [[lang|article|text]] (default: False)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        default=saved_cfg.get("test_mode", False),
        help="Mode test: convertit uniquement au maximum 10 articles contenant des images"
    )

    args = parser.parse_args()

    if args.web or (len(sys.argv) == 1):
        # Launch web interface
        from app import app
        port = int(os.environ.get('PORT', 5000))
        print(f"Starting Quora2WordPress web interface on http://localhost:{port}")
        app.run(host='0.0.0.0', port=port, debug=False)
        sys.exit(0)

    if not args.input_path:
        parser.error("the following arguments are required: input_path (unless --web is specified)")

    if not args.quora_username or not args.quora_username.strip():
        parser.error("the following argument is required: --quora-username (le slug du profil Quora est obligatoire)")

    # Fallback logic for output_dir
    input_path = args.input_path
    output_dir = args.output_dir
    if output_dir is None:
        if os.path.isdir(input_path):
            output_dir = input_path
        else:
            output_dir = os.path.dirname(input_path) or "."

    try:
        run_conversion(
            input_path=input_path,
            output_dir=output_dir,
            include_drafts=args.include_drafts,
            include_space_posts=args.include_space_posts,
            quora_username=args.quora_username,
            scrape_topics=args.scrape_topics,
            scrape_comments=args.scrape_comments,
            test_mode=args.test,
            max_processes=args.max_processes,
            link_position=args.link_position,
            link_template=args.link_template,
            min_content_length=args.min_content_length,
            r2w_support=args.r2w_support
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
