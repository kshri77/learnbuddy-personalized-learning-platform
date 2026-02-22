from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import os
import json
import requests
import urllib.parse
from datetime import datetime

# ---------------- ENV SETUP ---------------- #

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

app = Flask(__name__)
CORS(app)

user_performance_data = {}

# ---------------- OLLAMA HELPER ---------------- #

def ask_ollama(prompt):
    url = "http://localhost:11434/api/generate"

    payload = {
        "model": "mistral",
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()

    data = response.json()
    return data["response"]

# ---------------- BASIC ROUTES ---------------- #

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/signup.html")
def signup():
    return render_template("signup.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/streams")
def streams():
    return render_template("streams.html")

@app.route("/streams11_12")
def streams11_12():
    return render_template("streams11-12.html")

@app.route("/quiz")
def quiz():
    return render_template("quiz.html")

@app.route("/modules")
def modules_page():
    return render_template("modules.html")

@app.route("/final-assessment")
def final_assessment():
    return render_template("final_assessment.html")

@app.route("/report")
def report():
    score = request.args.get('score', 0, type=int)
    total = request.args.get('total', 0, type=int)
    subject = request.args.get('subject', 'Science')
    grade = request.args.get('grade', '10')

    percentage = round((score / total) * 100) if total > 0 else 0
    current_date = datetime.now().strftime('%B %d, %Y')

    return render_template(
        "report.html",
        score=score,
        total=total,
        subject=subject,
        grade=grade,
        percentage=percentage,
        current_date=current_date
    )

# ---------------- YOUTUBE FETCH ---------------- #

def fetch_youtube_videos(query, max_results=3):
    try:
        query_encoded = urllib.parse.quote(query)
        url = (
            f"https://www.googleapis.com/youtube/v3/search"
            f"?part=snippet&type=video&q={query_encoded}&maxResults={max_results}&key={YOUTUBE_API_KEY}"
        )

        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        videos = []
        for item in data.get("items", []):
            video_id = item["id"].get("videoId")
            snippet = item.get("snippet", {})

            if not video_id or not snippet:
                continue

            videos.append({
                "title": snippet.get("title"),
                "channel": snippet.get("channelTitle"),
                "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url"),
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "embed_url": f"https://www.youtube.com/embed/{video_id}"
            })

        return videos

    except Exception as e:
        print("YouTube error:", e)
        return []

# ---------------- QUIZ GENERATION ---------------- #

@app.route("/generate-quiz", methods=["POST"])
def generate_quiz():
    try:
        data = request.get_json()
        subject = data.get("subject", "Science")
        grade = data.get("grade", "10")

        prompt = f"""
Create 5 multiple choice questions for {subject} suitable for Grade {grade}.
Return ONLY valid JSON in this format:
[
  {{
    "question": "string",
    "options": ["A", "B", "C", "D"],
    "answer": "Correct option text"
  }}
]
Do not include explanations.
"""

        content = ask_ollama(prompt).strip()

        start = content.find("[")
        end = content.rfind("]") + 1
        questions = json.loads(content[start:end])

        return jsonify({"questions": questions})

    except Exception as e:
        print("Quiz error:", e)
        return jsonify({"error": str(e), "questions": []}), 500

# ---------------- MODULE GENERATION ---------------- #

@app.route("/generate-modules", methods=["POST"])
def generate_modules():
    try:
        data = request.get_json()
        subject = data.get("subject", "Science")
        grade = data.get("grade", "10")
        score = int(data.get("score", 0))

        learner_type = (
            "Slow Learner" if score <= 40
            else "Intermediate Learner" if score <= 75
            else "Fast Learner"
        )

        prompt = f"""
Create 4 structured learning modules for {subject} Grade {grade}
for a {learner_type}.
Return ONLY valid JSON array with fields:
topic, description, key_points (array).
"""

        content = ask_ollama(prompt).strip()

        start = content.find("[")
        end = content.rfind("]") + 1
        modules = json.loads(content[start:end])

        for module in modules:
            query = module.get("topic", f"{subject} Grade {grade}")
            module["youtube_videos"] = fetch_youtube_videos(query)
            module["status"] = "locked"

        if modules:
            modules[0]["status"] = "unlocked"

        return jsonify({
            "modules": modules,
            "learner_type": learner_type
        })

    except Exception as e:
        print("Module error:", e)
        return jsonify({"error": str(e), "modules": []}), 500

# ---------------- FINAL ASSESSMENT ---------------- #

@app.route("/generate-final-assessment", methods=["POST"])
def generate_final_assessment():
    try:
        data = request.get_json()
        subject = data.get("subject", "Science")
        grade = data.get("grade", "10")
        learner_type = data.get("learner_type", "Intermediate Learner")

        prompt = f"""
Create a 10-question final assessment for {subject} Grade {grade}
for a {learner_type}.
Return ONLY valid JSON object with:
quiz_title, subject, grade, questions[]
Each question must include:
question, options (4), answer, explanation.
"""

        content = ask_ollama(prompt).strip()

        start = content.find("{")
        end = content.rfind("}") + 1
        quiz_data = json.loads(content[start:end])

        quiz_data["is_fallback"] = False

        return jsonify(quiz_data)

    except Exception as e:
        print("Final assessment error:", e)
        return jsonify({
            "quiz_title": f"Sample {subject} Assessment",
            "subject": subject,
            "grade": grade,
            "questions": [],
            "is_fallback": True
        })

# ---------------- CHATBOT ---------------- #

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        message = data.get("message", "")
        context = data.get("context", "")

        prompt = f"""
You are a helpful learning assistant.
Context: {context}
Question: {message}
Answer clearly and simply.
"""

        reply = ask_ollama(prompt).strip()

        return jsonify({"reply": reply})

    except Exception as e:
        print("Chat error:", e)
        return jsonify({"error": str(e)}), 500

# ---------------- RUN SERVER ---------------- #

if __name__ == "__main__":
    app.run(debug=True)