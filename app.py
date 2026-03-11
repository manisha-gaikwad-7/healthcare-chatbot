"""Healthcare Chatbot — Flask backend with Ollama Cloud (OpenAI-compatible) streaming."""

import json
import os

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from openai import OpenAI

import database as db

load_dotenv()

app = Flask(__name__, static_folder="static")

# ---------------------------------------------------------------------------
# Ollama Cloud client setup (OpenAI-compatible API)
# ---------------------------------------------------------------------------
OLLAMA_CLOUD_URL = os.getenv("OLLAMA_CLOUD_URL")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

if not OLLAMA_CLOUD_URL or not OLLAMA_API_KEY:
    raise RuntimeError(
        "OLLAMA_CLOUD_URL and OLLAMA_API_KEY environment variables must be set."
    )

client = OpenAI(base_url=OLLAMA_CLOUD_URL, api_key=OLLAMA_API_KEY)
MODEL = os.getenv("OLLAMA_CLOUD_MODEL", "gpt-oss:20b-cloud")

SYSTEM_PROMPTS = {
    "en": """You are a helpful healthcare assistant chatbot. Your role is to:
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

Format your responses using Markdown when helpful (lists, bold, headers, etc.).""",

    "hi": """आप एक सहायक स्वास्थ्य सहायक चैटबॉट हैं। आपकी भूमिका है:
- सामान्य स्वास्थ्य जानकारी और कल्याण सुझाव प्रदान करना
- उपयोगकर्ताओं को सामान्य चिकित्सा शब्दों और स्थितियों को समझने में मदद करना
- सुझाव देना कि किसी को कब पेशेवर चिकित्सा सहायता लेनी चाहिए
- मानसिक स्वास्थ्य सहायता और तनाव प्रबंधन सलाह प्रदान करना
- स्वस्थ जीवनशैली विकल्पों के बारे में जानकारी साझा करना

महत्वपूर्ण अस्वीकरण जिनका आपको पालन करना चाहिए:
- हमेशा उपयोगकर्ताओं को याद दिलाएं कि आप एक लाइसेंस प्राप्त चिकित्सा पेशेवर नहीं हैं
- कभी भी स्थितियों का निदान न करें या दवाइयां न लिखें
- विशिष्ट चिकित्सा चिंताओं के लिए हमेशा योग्य स्वास्थ्य सेवा प्रदाता से परामर्श करने की सिफारिश करें
- आपात स्थिति में, उपयोगकर्ताओं को तुरंत आपातकालीन सेवाओं को कॉल करने की सलाह दें
- सहानुभूतिपूर्ण, सहायक और स्पष्ट रहें

आपको हमेशा हिंदी में जवाब देना है। Markdown का उपयोग करें जहां सहायक हो (सूचियां, बोल्ड, शीर्षक, आदि)।""",

    "mr": """तुम्ही एक उपयुक्त आरोग्य सहाय्यक चॅटबॉट आहात. तुमची भूमिका अशी आहे:
- सामान्य आरोग्य माहिती आणि निरोगीपणा टिप्स प्रदान करणे
- वापरकर्त्यांना सामान्य वैद्यकीय संज्ञा आणि परिस्थिती समजून घेण्यास मदत करणे
- एखाद्याने व्यावसायिक वैद्यकीय मदत कधी घ्यावी याचे सुचवणे
- मानसिक आरोग्य समर्थन आणि ताण व्यवस्थापन सल्ला देणे
- निरोगी जीवनशैली निवडींबद्दल माहिती सामायिक करणे

महत्त्वाचे अस्वीकरण जे तुम्हाला पाळणे आवश्यक आहे:
- वापरकर्त्यांना नेहमी आठवण करून द्या की तुम्ही परवानाधारक वैद्यकीय व्यावसायिक नाही
- कधीही परिस्थितीचे निदान करू नका किंवा औषधे लिहून देऊ नका
- विशिष्ट वैद्यकीय चिंतांसाठी नेहमी पात्र आरोग्य सेवा प्रदात्याशी सल्लामसलत करण्याची शिफारस करा
- आणीबाणीच्या परिस्थितीत, वापरकर्त्यांना ताबडतोब आणीबाणी सेवांना कॉल करण्याचा सल्ला द्या
- सहानुभूतीशील, सहाय्यक आणि स्पष्ट असा प्रतिसाद द्या

तुम्हाला नेहमी मराठीत उत्तर द्यायचे आहे. Markdown वापरा जिथे उपयुक्त असेल (याद्या, ठळक, शीर्षके, इ.).""",
}



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
    language = data.get("language", "en")

    if not session_id or not user_message:
        return jsonify({"error": "session_id and message are required"}), 400

    # Pick the system prompt for the requested language
    system_prompt = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])

    # Save user message
    db.add_message(session_id, "user", user_message)

    # Build conversation history for context (OpenAI format)
    history = db.get_session_messages(session_id)
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})

    def generate():
        full_response = []
        try:
            stream = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                stream=True,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    full_response.append(delta.content)
                    # Send SSE event
                    yield f"data: {json.dumps({'text': delta.content})}\n\n"

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
