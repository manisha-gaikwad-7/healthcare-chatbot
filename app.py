"""Healthcare Chatbot — Flask backend with Gemini API streaming."""

import json
import os

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from google import genai

import database as db

load_dotenv()

app = Flask(__name__, static_folder="static")

# ---------------------------------------------------------------------------
# Gemini client setup
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set. Get one at https://aistudio.google.com/apikey")

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-3-flash-preview"

SYSTEM_PROMPT = """You are a helpful healthcare assistant chatbot. Your role is to:
- Provide general health information and wellness tips
- Help users understand common medical terms and conditions
- Suggest when someone should seek professional medical help
- Offer mental health support and stress management advice
- Share information about healthy lifestyle choices

IMPORTANT DISCLAIMERS you must follow:
- Always remind users that you are NOT a licensed medical professional
- Never diagnose conditions or prescribe medications
- Always recommend consulting a qualified healthcare provider for specific medical concerns
- In case of emergencies, advise users to call emergency services immediately
- Be empathetic, supportive, and clear in your responses

Format your responses using Markdown when helpful (lists, bold, headers, etc.)."""


# ---------------------------------------------------------------------------
# Routes — Static
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ---------------------------------------------------------------------------
# Routes — Sessions
# ---------------------------------------------------------------------------
@app.route("/api/sessions", methods=["POST"])
def create_session():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "New Chat")
    session = db.create_session(title)
    return jsonify(session), 201


@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    sessions = db.get_sessions()
    return jsonify(sessions)


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    messages = db.get_session_messages(session_id)
    return jsonify(messages)


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    db.delete_session(session_id)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Routes — Chat (streaming via SSE)
# ---------------------------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    session_id = data.get("session_id")
    user_message = data.get("message", "").strip()

    if not session_id or not user_message:
        return jsonify({"error": "session_id and message are required"}), 400

    # Save user message
    db.add_message(session_id, "user", user_message)

    # Build conversation history for context
    history = db.get_session_messages(session_id)
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    def generate():
        full_response = []
        try:
            response = client.models.generate_content_stream(
                model=MODEL,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.7,
                    max_output_tokens=2048,
                ),
            )
            for chunk in response:
                if chunk.text:
                    full_response.append(chunk.text)
                    # Send SSE event
                    yield f"data: {json.dumps({'text': chunk.text})}\n\n"

            # Save full assistant response
            assistant_text = "".join(full_response)
            db.add_message(session_id, "assistant", assistant_text)

            # Auto-title the session if it's the first exchange
            if len(history) <= 1:
                short_title = user_message[:50] + ("…" if len(user_message) > 50 else "")
                db.update_session_title(session_id, short_title)
                yield f"data: {json.dumps({'title_update': short_title})}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, port=5000)
