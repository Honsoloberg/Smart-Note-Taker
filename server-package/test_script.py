#!/usr/bin/env python3
"""
send_audio_test.py
Simple test script to upload an audio file to the server's /upload endpoint
and then trigger processing with /run. Saves returned markdown to an output file.

Usage:
  python send_audio_test.py --file path/to/audio.m4a --server http://localhost:5005

Requires: requests (`pip install requests`)
"""

import argparse
import os
import sys
import requests
import json
import time


def upload_file(server_url, filepath, timeout=60):
    url = server_url.rstrip('/') + '/upload'
    headers = {'Content-Type': 'application/octet-stream'}
    with open(filepath, 'rb') as f:
        resp = requests.post(url, data=f, headers=headers, timeout=timeout)
    return resp

def run_processing(server_url, filename, timeout=10000):
    url = server_url.rstrip('/') + '/run'
    payload = {'filename': filename}
    start = time.monotonic()
    print(f"Start time: {start:.2f}")
    resp = requests.post(url, json=payload, timeout=timeout)
    elapsed = time.monotonic() - start
    # attach elapsed time for caller convenience
    print(f"Process Completed In: {elapsed:.2f}")
    return resp

def chat_run(server_url, filename, prompt, timeout=300):
    url = server_url.rstrip('/') + '/chat'
    payload = {'filename' : filename, 
               'prompt' : prompt}
    
    resp = requests.post(url, json=payload, timeout=timeout)
    return resp


def main():
    p = argparse.ArgumentParser(description='Upload audio to server and trigger processing')
    p.add_argument('--file', '-f', default="", help='Path to audio/transcription file')
    p.add_argument('--server', '-s', default='http://127.0.0.1:5005', help='Server base URL')
    p.add_argument('--outdir', '-o', default='test_outputs', help='Directory to save returned markdown')
    p.add_argument('--mode', '-m', default='t', help='Specifiy the type of request sent. transcription(t) or chat(c)')
    args = p.parse_args()

    #Test functionality for chat feature
    if(args.mode == 'c'):

        # if not os.path.isfile(args.file):
        #     print("Error: file not found: {args.file}")
        #     sys.exit(2)

        os.makedirs("chat_history", exist_ok=True)

        while(True):
            prompt = input("Ask AI a question: ")
            if prompt.lower() == "y":
                sys.exit(0)

            chat_run(args.server, args.file, prompt)





    if not os.path.isfile(args.file):
        print(f"Error: file not found: {args.file}")
        sys.exit(2)

    os.makedirs(args.outdir, exist_ok=True)

    print(f"Uploading {args.file} to {args.server}/upload ...")
    try:
        resp = upload_file(args.server, args.file)
    except Exception as e:
        print(f"Upload request failed: {e}")
        sys.exit(1)

    try:
        data = resp.json()
    except Exception:
        print(f"Upload failed (status {resp.status_code}): {resp.text}")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"Upload error ({resp.status_code}): {data}")
        sys.exit(1)

    filename = data.get('filename')
    if not filename:
        print(f"Upload response missing filename: {data}")
        sys.exit(1)

    print(f"Uploaded. Server saved filename: {filename}")

    print(f"Triggering processing via {args.server}/run ...")
    try:
        resp2 = run_processing(args.server, filename)
    except Exception as e:
        print(f"Run request failed: {e}")
        sys.exit(1)

    try:
        data2 = resp2.json()
    except Exception:
        print(f"Run failed (status {resp2.status_code}): {resp2.text}")
        sys.exit(1)

    if resp2.status_code != 200:
        print(f"Run error ({resp2.status_code}): {data2}")
        sys.exit(1)

    markdown = data2.get('markdown')
    if not markdown:
        print(f"Run response missing markdown: {data2}")
        sys.exit(1)

    outpath = os.path.join(args.outdir, f"{filename}.md")
    with open(outpath, 'w', encoding='utf-8') as outf:
        outf.write(markdown)

    print(f"Saved markdown to: {outpath}")
    print(json.dumps(data2, indent=2))


if __name__ == '__main__':
    main()
