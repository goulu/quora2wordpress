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

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "author": "",
    "author_email": "",
    "quora_username": "",
    "link_position": "none",
    "link_template": '<a href="$link$" target="_blank">voir sur Quora</a>',
    "include_drafts": True,
    "include_space_posts": True,
    "scrape_topics": True,
    "scrape_comments": False,
    "check_online": False,
    "test_mode": False
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(cfg)
                return merged
        except Exception as e:
            print(f"Error reading config.json: {e}", file=sys.stderr)
    return DEFAULT_CONFIG.copy()

def save_config(cfg_dict):
    try:
        cfg_to_save = {}
        for key in DEFAULT_CONFIG:
            if key in cfg_dict:
                cfg_to_save[key] = cfg_dict[key]
            else:
                cfg_to_save[key] = DEFAULT_CONFIG[key]
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg_to_save, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving config.json: {e}", file=sys.stderr)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(load_config())

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

active_processes = {}

@app.route('/api/convert', methods=['POST'])
def convert():
    data = request.json or {}
    filenames = data.get('files', [])
    session_id = data.get('session_id', 'default_session')
    if not filenames:
        return jsonify({'error': 'No files specified for conversion'}), 400

    # Save user preferences automatically for subsequent runs
    save_config(data)

    def generate_logs():
        results = []
        is_cancelled = False
        for filename in filenames:
            if is_cancelled:
                break

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
            if data.get('author'):
                cmd.extend(['--author', data['author']])
            if data.get('author_email'):
                cmd.extend(['--author-email', data['author_email']])
            if data.get('quora_username'):
                cmd.extend(['--quora-username', data['quora_username']])
            
            cmd.extend(['--include-drafts', 'true' if data.get('include_drafts', True) else 'false'])
            cmd.extend(['--include-space-posts', 'true' if data.get('include_space_posts', True) else 'false'])
            cmd.extend(['--scrape-topics', 'true' if data.get('scrape_topics', True) else 'false'])
            cmd.extend(['--scrape-comments', 'true' if data.get('scrape_comments', False) else 'false'])
            
            if data.get('link_position') and data['link_position'] != 'none':
                cmd.extend(['--link-position', data['link_position']])
                if data.get('link_template'):
                    cmd.extend(['--link-template', data['link_template']])
                    
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
            active_processes[session_id] = process

            try:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        clean_line = line.strip()
                        yield f"data: {json.dumps({'type': 'log', 'message': clean_line})}\n\n"

                    # Check if process was killed externally/cancelled
                    if process.poll() is not None:
                        break
            finally:
                process.stdout.close()
                rc = process.poll()
                if rc is None:
                    process.wait()
                    rc = process.returncode
                active_processes.pop(session_id, None)

            if rc != 0 and rc is not None and rc < 0: # Terminated by signal
                is_cancelled = True
                yield f"data: {json.dumps({'type': 'log', 'message': '=== Conversion annulée par l’utilisateur ==='})}\n\n"

            expected_xml_name = f"{os.path.splitext(safe_filename)[0]}.xml"
            xml_path = os.path.join(EXPORTS_DIR, expected_xml_name)

            if os.path.exists(xml_path) and os.path.getsize(xml_path) > 0:
                xml_size_mb = round(os.path.getsize(xml_path) / (1024 * 1024), 2)
                status_msg = f"Fichier WXR partiel disponible : {expected_xml_name} ({xml_size_mb} MB)" if is_cancelled else f"Successfully generated {expected_xml_name}"
                yield f"data: {json.dumps({'type': 'log', 'message': status_msg})}\n\n"
                results.append({
                    'zip_file': safe_filename,
                    'xml_file': expected_xml_name,
                    'size': f"{xml_size_mb} MB",
                    'download_url': f"/api/download/{expected_xml_name}",
                    'partial': is_cancelled
                })
            else:
                yield f"data: {json.dumps({'type': 'log', 'message': f'Conversion failed or interrupted before saving posts for {safe_filename}'})}\n\n"

            if is_cancelled:
                break

        yield f"data: {json.dumps({'type': 'done', 'cancelled': is_cancelled, 'results': results})}\n\n"

    return Response(generate_logs(), mimetype='text/event-stream')

@app.route('/api/cancel', methods=['POST'])
def cancel_conversion():
    data = request.json or {}
    session_id = data.get('session_id', 'default_session')
    if session_id in active_processes:
        proc = active_processes[session_id]
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        active_processes.pop(session_id, None)
        return jsonify({'success': True, 'message': 'Conversion process cancelled'})
    return jsonify({'success': False, 'message': 'No active process found for session'}), 400

@app.route('/api/download/<filename>')
def download_file(filename):
    safe_filename = werkzeug.utils.secure_filename(filename)
    return send_from_directory(EXPORTS_DIR, safe_filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Quora2WordPress web interface on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
