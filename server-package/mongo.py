from pymongo import MongoClient #pip install pymongo
from bson import ObjectId
import random as r
# import uuid
from datetime import datetime, timezone
from dotenv import dotenv_values

env = dotenv_values("..\\.env")
uri = str(env.get("DB_URI"))

if not uri:
    print("<---------------------------------------->")
    print("env not working for Database")
    print("<---------------------------------------->")
else:
    print(uri)

def upload_transcription(content: str, user_id='697cf4b73f15e2493ee71297', name=""):
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client["App"]
    transcriptions = db["Transcription"]

    number = r.randint(1000, 9999)
    doc_name = "transcribed_{}".format(number) if name == "" else name

    upload = {
        "user_id": str(ObjectId(user_id)),
        "name": str(doc_name),
        "content": str(content),
        "created_at": str(datetime.now(timezone.utc))
    }

    result = transcriptions.insert_one(upload)
    return result.inserted_id

def create_note(content: str, user_id='697cf4b73f15e2493ee71297', name=""):
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client["App"]
    notes = db["Notes"]
    
    number = r.randint(1000, 9999)
    doc_name = "note_{}".format(number) if name == "" else name
    
    upload = {
        "user_id": ObjectId(user_id),
        "name": str(name),
        "alias": "NaN",
        "content": str(content),
        "created_at": str(datetime.now(timezone.utc))
    }

    result = notes.insert_one(upload)
    return result.inserted_id

def get_notes(user_id='697cf4b73f15e2493ee71297'):
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client["App"]
    notes = db["Notes"]

    notes_list = list(notes.find({"user_id": user_id}))

    return notes_list