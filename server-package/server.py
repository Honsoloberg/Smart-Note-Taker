from flask import Flask, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge
import os
import time
import uuid
import llmMarkdown
import transcriber


app = Flask(__name__)
# 300 MB limit:
app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.errorhandler(RequestEntityTooLarge)
def handle_over_limit(e):
    return {"error": "File too large"}, 413

@app.route('/upload', methods=['POST'])
def upload():
    print("got upload request")
    print(request)
    fileData = request.get_data()
    if not fileData:
        return {"error": "No file part"}, 400

    new_name = f"{uuid.uuid4().hex}_{int(time.time())}{'.m4a'}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    save_path = os.path.abspath(os.path.join(UPLOAD_DIR, new_name))

    with open(save_path, 'wb') as f:
        f.write(fileData)
    print(f"Saved to {save_path}")
    return {"filename": new_name}, 200


@app.route('/run', methods=['POST'])
def run_pipeline():
    try:
        print("Running pipeline...")
        # get filename from request
        print(request.json)
        if request.json:
            filename = request.json['filename']
        else:
            return {"error": "JSON error"}, 400
        print(f"Got filename: {filename}")
        transcript = transcriber.transcribe(os.path.join(UPLOAD_DIR, filename))
        print("transcribed")
        with open("transcript.txt", "w") as f:
            f.write(transcript)
        markdown = llmMarkdown.run_llmMarkdown(transcript)
        markdown = llmMarkdown.sanitize_Markdown(markdown)
        print("Generate Markdown File")
        os.makedirs("markdown", exist_ok=True)
        with open(f"markdown/{filename}.md", "x") as f:
            f.write(markdown)
        print("Pipeline complete.")
        return {"markdown": markdown, "filename": filename}, 200
    except Exception as e:
        print(f"Error running pipeline: {e}")
        return {"error": str(e)}, 500

@app.route('/api/notes/<filename>', methods=['GET'])
@app.route('/notes/<filename>', methods=['GET'])
def get_note(filename):
    return send_file(os.path.join("markdown", filename) + ".md", mimetype='text/markdown')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005)
    # use something like gunicorn
    # pip install gunicorn
    # gunicorn -b 0.0.0.0:5000 server:app

    #  deploy with docker
    #  use something to interact with https

    # probably should buy a domain