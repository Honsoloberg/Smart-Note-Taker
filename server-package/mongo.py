from pymongo.mongo_client import MongoClient #pip install pymongo
from pymongo.server_api import ServerApi
from pymongo.errors import PyMongoError, DocumentTooLarge
from bson import ObjectId
from bson.errors import BSONError
import random as r
# import uuid
from datetime import datetime, timezone
from dotenv import dotenv_values
import json

env = dotenv_values("..//.env")
uri = str(env.get("DB_URI"))

def upload_transcription(content: str, noteID: str, user_id='697cf4b73f15e2493ee71297'):
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client["App"]
    transcriptions = db["Transcription"]

    upload = {
        "text": content,
        "noteID": ObjectId(noteID),
    }

    result = transcriptions.insert_one(upload)
    client.close()

    return result.inserted_id

def get_transcription(noteID):
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client["App"]
    transcriptions = db["Transcription"]

    transcription= transcriptions.find_one({"noteID": noteID})
    client.close()

    return transcription

def create_note(content: str, user_id='697cf4b73f15e2493ee71297', name=""):
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client["App"]
    notes = db["Notes"]
    
    number = r.randint(1000, 9999)
    doc_name = "note_{}".format(number) if name == "" else name
    
    upload = {
        "user_id": ObjectId(user_id),
        "name": doc_name,
        "content": str(content),
        "created_at": str(datetime.now(timezone.utc))
    }

    result = notes.insert_one(upload)
    client.close()

    return result.inserted_id

def get_notes(user_id='697cf4b73f15e2493ee71297'):
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client["App"]
    notes = db["Notes"]

    notes_list = list(notes.find({"user_id": user_id}))
    client.close()

    return notes_list

def create_chat(noteID: str):
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client["App"]
    chats = db["Ai_chatbot"]
    transcriptions = db["Transcription"]
    notes = db["Notes"]

    note = notes.find_one({"_id": ObjectId(noteID)}) or {}
    transcription = transcriptions.find_one({"noteID": ObjectId(noteID)}) or {}

    head = [
        {"role": "system", "content": str(transcription.get("text"))},
        {"role": "system", "content": str(note.get("content"))}
    ]

    upload = {
        "noteID": ObjectId(noteID),
        "queries": [],
        "head": head
    }

    print("new chat created for noteID: ", noteID)

    result = chats.insert_one(upload)
    client.close()

    return result.inserted_id

def get_chat(noteID: str):
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client["App"]
    chats = db["Ai_chatbot"]

    chat = chats.find_one({"noteID": ObjectId(noteID)})

    print(chat)

    if not chat:
        id = create_chat(noteID)
        chat = chats.find_one({"_id": ObjectId(id)}) or {}
        print(chat)

    chatID = chat.get("_id")
    history = chat.get("queries", [])
    head = chat.get("head", [])

    # print(f"{history}")
    # print(str(chatID))

    client.close()

    return str(chatID), history, head

def update_chat(chatID: str, history):
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client["App"]
    chats = db["Ai_chatbot"]

    # print(chatID)

    prompt = history[-2]
    response = history[-1]

    try:
        result = chats.update_one({"_id": ObjectId(chatID)}, {
            "$push": {
                "queries": {
                    "$each": [prompt, response],
                    "$slice": -100
                }
            }
        })
        if result.modified_count <= 0:
            print(f"Failed to update chat with ID: {chatID}")
            client.close()
            return False
    except DocumentTooLarge as e:    
        print("Chat history exceeded document size limit.")
        client.close()
        return False
    except PyMongoError as e:
        print(f"Error updating chat with ID {chatID}: {e}")
        client.close()
        return False

    return True




    

if __name__ == "__main__":
    if not uri:
        print("<---------------------------------------->")
        print("env not working for Database")
        print("<---------------------------------------->")
    else:
        print(uri)

    with MongoClient(uri, server_api=ServerApi('1')) as client:
        try:
            reply = client.server_info()
            print("<---------------------------------------->")
            print(reply)
            client.close()
        except PyMongoError as e:
            print(f"Error connecting to MongoDB: {e}")