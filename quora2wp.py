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
        "--image-base-url", 
        default="/wp-content/uploads/quora", 
        help="Base URL prefix for rewriting images (default: /wp-content/uploads/quora)"
    )
    parser.add_argument(
        "--author", 
        default="", 
        help="Default author display name for the posts (default: extracted from folder name)"
    )
    parser.add_argument(
        "--author-email", 
        default="", 
        help="Default author email for the WXR header"
    )
    parser.add_argument(
        "--include-drafts", 
        type=str2bool, 
        default=True, 
        help="Include draft posts (default: True)"
    )
    parser.add_argument(
        "--include-space-posts", 
        type=str2bool, 
        default=True, 
        help="Include space posts and shares (default: True)"
    )
    parser.add_argument(
        "--use-cdn-images",
        type=str2bool,
        default=True,
        help="Rewrite image sources containing qimg- to Quora CDN URLs (default: True)"
    )
    parser.add_argument(
        "--quora-username",
        default="",
        help="The Quora profile username slug (e.g. Dr-Goulu) to reconstruct valid answer URLs (default: derived from folder name)"
    )
    parser.add_argument(
        "--check-online",
        action="store_true",
        help="Check candidates against Quora online to verify link validity (may be slow/blocked by Cloudflare)"
    )
    parser.add_argument(
        "--scrape-topics",
        type=str2bool,
        default=True,
        help="Automatically scrape Quora topics/tags for each post (default: True)"
    )
    parser.add_argument(
        "--scrape-comments",
        type=str2bool,
        default=False,
        help="Automatically scrape Quora comments/replies for each post (default: False)"
    )
    parser.add_argument(
        "--max-processes", "-p",
        type=int,
        default=1,
        help="Deprecated/Ignored: conversion is now strictly sequential to avoid Chrome memory saturation (default: 1)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Stop conversion early as soon as posts containing both images and comments are found"
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
            image_base_url=args.image_base_url,
            author=args.author,
            author_email=args.author_email,
            include_drafts=args.include_drafts,
            include_space_posts=args.include_space_posts,
            use_cdn_images=args.use_cdn_images,
            quora_username=args.quora_username,
            check_online=args.check_online,
            scrape_topics=args.scrape_topics,
            scrape_comments=args.scrape_comments,
            test_mode=args.test,
            max_processes=args.max_processes
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
