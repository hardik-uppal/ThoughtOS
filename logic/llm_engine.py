import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')
else:
    model = None
    print("Warning: GOOGLE_API_KEY not found in .env")

def ask_gemini(prompt):
    """
    Sends a prompt to Gemini and returns the text response.
    Returns None if API is not configured.
    """
    if not model:
        return "Error: Gemini API Key missing."
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return f"Error generating content: {e}"

def ask_gemini_json(prompt):
    """
    Asks Gemini to return a JSON object. 
    Appends 'Return JSON only.' to the prompt.
    """
    json_prompt = f"{prompt}\n\nReturn valid JSON only. Do not use markdown code blocks."
    response_text = ask_gemini(json_prompt)
    
    # Clean up potential markdown formatting
    response_text = response_text.replace("```json", "").replace("```", "").strip()
    
    return response_text

def get_embedding(text):
    """
    Generates a vector embedding for the given text using 'text-embedding-004'.
    Returns a list of floats.
    """
    if not GOOGLE_API_KEY:
        return None
        
    try:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document",
            title="ContextOS Embedding"
        )
        return result['embedding']
    except Exception as e:
        print(f"Embedding Error: {e}")
        return None
