# from pymongo.mongo_client import MongoClient #pip install pymongo
try:
    import mongomock
    MongoClient = mongomock.MongoClient
    print("Using mock MongoDB")
except ImportError:
    from pymongo.mongo_client import MongoClient
    
from pymongo.server_api import ServerApi
from pymongo.errors import PyMongoError, DocumentTooLarge
from bson import ObjectId
from bson.errors import BSONError
import random as r
# import uuid
from datetime import datetime, timezone
from dotenv import dotenv_values
import json
import bcrypt

env = dotenv_values("..//.env")
uri = str(env.get("DB_URI"))

def get_client():
    return MongoClient(uri, server_api=ServerApi('1'))

def upload_transcription(content: str, noteID: str, user_id='697cf4b73f15e2493ee71297'):
    db = get_client()["App"]
    transcriptions = db["Transcription"]

    upload = {
        "text": content,
        "noteID": ObjectId(noteID),
    }

    result = transcriptions.insert_one(upload)
    

    return result.inserted_id

def get_transcription(noteID):
    db = get_client()["App"]
    transcriptions = db["Transcription"]

    transcription= transcriptions.find_one({"noteID": noteID})
    

    return transcription

def create_note(content: str, user_id='697cf4b73f15e2493ee71297', name=""):
    db = get_client()["App"]
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
    

    return result.inserted_id

def get_notes(user_id='697cf4b73f15e2493ee71297'):
    db = get_client()["App"]
    notes = db["Notes"]

    notes_list = list(notes.find({"user_id": user_id}))
    

    return notes_list

def create_chat(noteID: str):
    db = get_client()["App"]
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
    

    return result.inserted_id

def get_chat(noteID: str):
    db = get_client()["App"]
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

    

    return str(chatID), history, head

def update_chat(chatID: str, history):
    db = get_client()["App"]
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
            
            return False
    except DocumentTooLarge as e:    
        print("Chat history exceeded document size limit.")
        
        return False
    except PyMongoError as e:
        print(f"Error updating chat with ID {chatID}: {e}")
        
        return False

    return True

def get_user_by_username(username):
    db = get_client()["App"]
    users = db["Users"]

    try:
        user = users.find_one({"username": username})
        if user is None:
            print(f"No user found with username: {username}")
            
            return None
        else:
            return user
    except PyMongoError as e:
        print(f"Error getting user with username {username}: {e}")
        
        return None

def create_user(username, password):
    db = get_client()["App"]
    users = db["Users"]

    try:
        user = users.find_one({"username": username})
        if user is not None:
            print(f"User with username {username} already exists.")
            
            return None
        else:
            password_hash = bcrypt.hashpw(password, bcrypt.gensalt())
            user = {
                "username": username,
                "password_hash": password_hash,
                "created_at": str(datetime.now(timezone.utc))
            }
            result = users.insert_one(user)
            if result.inserted_id is None:
                print(f"Failed to create user with username: {username}")
                
                return None
            else:
                return result.inserted_id
    except PyMongoError as e:
        print(f"Error creating user with username {username}: {e}")
        
        return None

def get_user_by_id(user_id):
    db = get_client()["App"]
    users = db["Users"]

    try:
        user = users.find_one({"_id": ObjectId(user_id)})
        if user is None:
            print(f"No user found with ID: {user_id}")
            
            return None
        else:
            return user
    except PyMongoError as e:
        print(f"Error getting user with ID {user_id}: {e}")
        
        return None


    

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
            
        except PyMongoError as e:
            print(f"Error connecting to MongoDB: {e}")