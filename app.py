#!/usr/bin/env python3
"""
Flask Web Interface for Quora to WordPress Converter (quora2wordpress)
Provides a web GUI for uploading ZIP exports, configuring options, 
monitoring conversion progress in real-time, and downloading WXR files.
"""

import os
import sys
import json
import subprocess
import werkzeug.utils
from flask import Flask, render_template, request, jsonify, Response, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"), static_folder=os.path.join(BASE_DIR, "static"))
app.config['UPLOAD_FOLDER'] = UPLOADS_DIR
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max upload limit

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400
    
    files = request.files.getlist('files')
    uploaded_info = []

    for file in files:
        if file.filename == '':
            continue
        if file and file.filename.lower().endswith('.zip'):
            filename = werkzeug.utils.secure_filename(file.filename)
            # Ensure unique filename if collision occurs
            filepath = os.path.join(UPLOADS_DIR, filename)
            file.save(filepath)
            size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)
            uploaded_info.append({
                'filename': filename,
                'path': filepath,
                'size': f"{size_mb} MB"
            })
    
    if not uploaded_info:
        return jsonify({'error': 'No valid .zip files were uploaded'}), 400
        
    return jsonify({'success': True, 'files': uploaded_info})

@app.route('/api/convert', methods=['POST'])
def convert():
    data = request.json or {}
    filenames = data.get('files', [])
    if not filenames:
        return jsonify({'error': 'No files specified for conversion'}), 400

    def generate_logs():
        results = []
        for filename in filenames:
            safe_filename = werkzeug.utils.secure_filename(filename)
            input_file = os.path.join(UPLOADS_DIR, safe_filename)
            if not os.path.exists(input_file):
                yield f"data: {json.dumps({'type': 'log', 'message': f'Error: File {safe_filename} not found.'})}\n\n"
                continue

            # Build CLI command for quora2wp.py
            cmd = [
                sys.executable,
                os.path.join(BASE_DIR, "quora2wp.py"),
                input_file,
                EXPORTS_DIR
            ]

            # Append option arguments
            if data.get('image_base_url'):
                cmd.extend(['--image-base-url', data['image_base_url']])
            if data.get('author'):
                cmd.extend(['--author', data['author']])
            if data.get('author_email'):
                cmd.extend(['--author-email', data['author_email']])
            if data.get('quora_username'):
                cmd.extend(['--quora-username', data['quora_username']])
            
            cmd.extend(['--include-drafts', 'true' if data.get('include_drafts', True) else 'false'])
            cmd.extend(['--include-space-posts', 'true' if data.get('include_space_posts', True) else 'false'])
            cmd.extend(['--use-cdn-images', 'true' if data.get('use_cdn_images', True) else 'false'])
            cmd.extend(['--scrape-topics', 'true' if data.get('scrape_topics', True) else 'false'])
            cmd.extend(['--scrape-comments', 'true' if data.get('scrape_comments', False) else 'false'])
            
            if data.get('check_online'):
                cmd.append('--check-online')
            if data.get('test_mode'):
                cmd.append('--test')

            cmd_str = " ".join(cmd)
            yield f"data: {json.dumps({'type': 'log', 'message': f'=== Starting conversion for {safe_filename} ==='})}\n\n"
            yield f"data: {json.dumps({'type': 'log', 'message': f'Running command: {cmd_str}'})}\n\n"

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in iter(process.stdout.readline, ''):
                if line:
                    clean_line = line.strip()
                    yield f"data: {json.dumps({'type': 'log', 'message': clean_line})}\n\n"

            process.stdout.close()
            process.wait()

            expected_xml_name = f"{os.path.splitext(safe_filename)[0]}.xml"
            xml_path = os.path.join(EXPORTS_DIR, expected_xml_name)

            if process.returncode == 0 and os.path.exists(xml_path):
                xml_size_mb = round(os.path.getsize(xml_path) / (1024 * 1024), 2)
                yield f"data: {json.dumps({'type': 'log', 'message': f'Successfully generated {expected_xml_name}'})}\n\n"
                results.append({
                    'zip_file': safe_filename,
                    'xml_file': expected_xml_name,
                    'size': f"{xml_size_mb} MB",
                    'download_url': f"/api/download/{expected_xml_name}"
                })
            else:
                yield f"data: {json.dumps({'type': 'log', 'message': f'Conversion failed or no posts found for {safe_filename}'})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'results': results})}\n\n"

    return Response(generate_logs(), mimetype='text/event-stream')

@app.route('/api/download/<filename>')
def download_file(filename):
    safe_filename = werkzeug.utils.secure_filename(filename)
    return send_from_directory(EXPORTS_DIR, safe_filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Quora2WordPress web interface on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
