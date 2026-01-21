import os
from openai import OpenAI
from dotenv import dotenv_values

TRANSCRIBE_PROMPT = """You are a meeting summarizer.
Rules:
- Output ONLY the summary in Markdown format.
- Do not write any explanations, prefaces, or extra text.
- Do not say "Here's your summary" or similar.
- Do not include anything except the requested summary.
- Make the summary nicely formatted with proper headers, lists, and bullet points.
Summarize the following meeting transcript:
"""

CHAT_PROMPT = """You are a helpful AI assistant that helps users by answering questions based on previous conversation history. 
Use the context of the previous messages to provide accurate and relevant answers. Be concise and clear in your responses.
The following message is a markdown file of the note you are to answer questions about:
"""

env = dotenv_values("..\\.env")
api_key = str(env.get("API_KEY"))

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com") or None
model = "deepseek-chat"

def run_AItranscribe(model: str, user_prompt: str, system_prompt=TRANSCRIBE_PROMPT) -> str:
    print("Running AI model...")
    print(api_key)
    if not client:
        raise ValueError("OpenAI client not initialized. Check API key.")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        stream=False
    )
    print("AI model response received.")
    print(response.choices[0].message.content)
    return str(response.choices[0].message.content)


def run_llmMarkdown(user_prompt: str) -> str:
    print("Running LLM Markdown generation...")
    return run_AItranscribe(model, user_prompt)

def sanitize_Markdown(text: str) -> str:
    text = text.replace("–", "-")
    text = text.strip()
    if text.endswith("---"):
        text = text[:-3]
    
    return text

def run_AIchat(model: str, chat_history, note) -> str:
    print("Running AI chat model...")
    if not client:
        raise ValueError("OpenAI client not initialized. Check API key.")
    
    # messages = [{"role": "system", "content": chat_history},
    #             {"role": "user", "content": user_prompt}
    # ]
    chat_history = chat_history.copy()
    chat_history.insert(0, {"role": "system", "content": CHAT_PROMPT})
    chat_history.insert(1, {"role": "system", "content": note})

    
    response = client.chat.completions.create(
        model=model,
        messages=chat_history,
        stream=False
    )
    print("AI chat model response received.")
    print(response.choices[0].message.content)
    return str(response.choices[0].message.content)

def run_chat(chat_history, note) -> str:
    print("Running chat...")
    return run_AIchat(model, chat_history, note)
