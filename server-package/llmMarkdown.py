import ollama

SYSTEM_PROMPT = """You are a meeting summarizer.
Rules:
- Output ONLY the summary in Markdown format.
- Do not write any explanations, prefaces, or extra text.
- Do not say "Here's your summary" or similar.
- Do not include anything except the requested summary.
- Make the summary nicely formatted with proper headers, lists, and bullet points.
Summarize the following meeting transcript:
"""

def run_ollama(model: str, user_prompt: str, system_prompt=SYSTEM_PROMPT) -> str:
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response["message"]["content"]


def run_llmMarkdown(model: str, user_prompt: str) -> str:
    return run_ollama(model, user_prompt)

def sanitize_Markdown(text: str) -> str:
    text = text.replace("–", "-")
    text = text.strip()
    if text.endswith("---"):
        text = text[:-3]
    
    return text