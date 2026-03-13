from flask import Flask, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge
import os
import time
import uuid
import llmMarkdown
import transcriber
import mongo
import json
from dotenv import load_dotenv
import bcrypt
import flask_jwt_extended as fljwt # pip install flask-jwt-extended
from io import BytesIO

load_dotenv()

app = Flask(__name__)
jwt = fljwt.JWTManager(app)
# 300 MB limit:
app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024
app.config["JWT_SECRET_KEY"] = str(os.getenv("JWT_SECRET_KEY", "some-secret-key-for-SmartNoteApp"))
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
CHAT_DIR = os.path.join(BASE_DIR, 'chat_history')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHAT_DIR, exist_ok=True)

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    print(data)
    if mongo.get_user_by_username(data["username"]):
        return {"msg": "Username exists"}, 400

    mongo.create_user(data["username"], data["password"].encode())

    return {"msg": "User created"}, 201

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user = mongo.get_user_by_username(data["username"])
    print(user)

    if not user:
        print("registering new user")
        return register()

    if not bcrypt.checkpw(
        data["password"].encode(),
        user["password_hash"]
    ):
        return {"msg": "Bad password"}, 401

    token = fljwt.create_access_token(identity=str(user["_id"]))
    return {"access_token": token}

@app.route("/profile")
@fljwt.jwt_required()
def profile():

    user_id = fljwt.get_jwt_identity()
    user = mongo.get_user_by_id(user_id) or {}

    return {
        "username": user["username"]
    }

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

        markdown = llmMarkdown.run_llmMarkdown(transcript)
        markdown = llmMarkdown.sanitize_Markdown(markdown)

        note_id = mongo.create_note(markdown, name="note_{}".format(file_name))

        mongo.upload_transcription(transcript, str(note_id))

        print("Generate Markdown File")
        # os.makedirs("markdown", exist_ok=True)
        
        # with open(f"markdown/{filename}.md", "x") as f:
        #     f.write(markdown)
        print("Pipeline complete.")

        return {"filename": str(note_id)}, 200
    
    except Exception as e:
        print(f"Error running pipeline: {e}")
        return {"error": str(e)}, 500
    
# MARK: Chat endpoint
@app.route('/chat', methods=['POST'])
def run_chat():
    # try:
        print("Running Chat Service...")
        data = request.json

        chat_id, chat_history, head= mongo.get_chat(data.get("filename"))
        prompt = data.get('prompt')

        if not prompt:
            return {"error": "No prompt provided"}, 400

        chat_history.append({"role": "user", "content": prompt})

        response = llmMarkdown.run_chat(chat_history, head)

        # yield response here, if streaming is implemented
        chat_history.append({"role": "system", "content": response})

        if not mongo.update_chat(str(chat_id), chat_history):
            return {"error": "Failed to contact server"}, 500

        return {"response": response}, 200

@app.route('/notes/<filename>', methods=['GET'])
def get_note(filename):
    note_content = mongo.get_indNote(filename)
    return send_file(BytesIO(note_content.encode()), mimetype='text/markdown', as_attachment=True, download_name=f"{filename}.md")

@app.route('/notes', methods=['GET'])
def get_notes():
    notes = mongo.get_notes()
    if notes is None:
        return {"error": "Failed to retrieve notes"}, 500
    notes_json = json.dumps(dict(notes=[{"_id": str(note["_id"]), "name": note.get("name", ""), "content": note.get("content", ""), "created_at": note.get("created_at", "")} for note in notes]))

    return {"notes": notes_json}, 200

@app.route('/health', methods=['GET'])
def health_check():
    return {"status": "healthy"}, 200

@app.route("/test")
def test_page():
    return send_file(os.path.join(BASE_DIR, "test.html"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80 if str(os.getenv("FLASK_ENV")) == "production" else 5005)
    #  run with: gunicorn --bind 0.0.0.0:80 server:app