from flask import Flask, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge
import os
import time
import uuid
import llmMarkdown
import transcriber
import mongo
import json



app = Flask(__name__)
# 300 MB limit:
app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
CHAT_DIR = os.path.join(BASE_DIR, 'chat_history')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHAT_DIR, exist_ok=True)


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

        os.remove(os.path.join(UPLOAD_DIR, filename))

        print("transcribed")

        file_name = f"{uuid.uuid4().hex}_{int(time.time())}"
        
        mongo.upload_transcription(transcript, name=file_name)

        markdown = llmMarkdown.run_llmMarkdown(transcript)
        markdown = llmMarkdown.sanitize_Markdown(markdown)

        mongo.create_note(markdown, name="note_{}".format(file_name))

        print("Generate Markdown File")
        os.makedirs("markdown", exist_ok=True)
        with open(f"markdown/{filename}.md", "x") as f:
            f.write(markdown)
        print("Pipeline complete.")

        return {"markdown": markdown, "filename": filename}, 200
    
    except Exception as e:
        print(f"Error running pipeline: {e}")
        return {"error": str(e)}, 500
    

# MARK: Chat endpoint
@app.route('/chat', methods=['POST'])
def run_chat():
    # try:
        print("Running Chat Service...")
        data = request.json
        print('Received data:', data)
        
        chat_id = data.get('filename')
        prompt = data.get('prompt')

        if not prompt:
            return {"error": "No prompt provided"}, 400

        print(f"Chat ID: {chat_id}")
        print(f"Message: {prompt}")

        # get chat history
        print("chat dir: ", CHAT_DIR)
        print(f"Chat history: {os.path.join(CHAT_DIR, chat_id)}")
        print(os.path.exists(os.path.join(CHAT_DIR, chat_id)))
        if not os.path.exists(os.path.join(CHAT_DIR, chat_id)):
            print(f"Creating new chat history for {chat_id}")
            os.makedirs(CHAT_DIR, exist_ok=True)
            with open(os.path.join(CHAT_DIR, chat_id), "w") as f:
                f.write("{}")

        # read as json and then add new message
        with open(os.path.join(CHAT_DIR, chat_id), "r") as f:
            chat_history = json.load(f)
        if not chat_history:
            chat_history = []
        chat_history.append({"role": "user", "content": prompt})

        # write as json
        with open(os.path.join(CHAT_DIR, chat_id), "w") as f:
            json.dump(chat_history, f)

        with open(os.path.join(BASE_DIR, "markdown", chat_id), "r") as f: # markdown or test_outputs, both work
            note = f.read()

        response = llmMarkdown.run_chat(chat_history, note)
        print(f"Response: {response}")

        # yield response here, if streaming 

        chat_history.append({"role": "system", "content": response})

        # write as json
        with open(os.path.join(CHAT_DIR, chat_id), "w") as f:
            json.dump(chat_history, f, indent=4)

        return {"response": response}, 200

    # except Exception as e:
    #     print(f"Error running pipeline: {e}")
    #     return {"error": str(e)}, 500

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