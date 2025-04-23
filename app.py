from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import requests
import json
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_history.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

API_KEY = os.environ.get("API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
CSE_ID = os.environ.get("CSE_ID")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# Database model
class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'user' or 'bot'
    message = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<ChatHistory {self.id} {self.user_id} {self.role}>'

with app.app_context():
    db.create_all()

# Load user profile data from Google Drive
def load_all_user_data(file_id):
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(url)
    if response.status_code == 200:
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            raise Exception("Invalid JSON format.")
    else:
        raise Exception(f"Failed to download: {response.status_code}")

file_id = "1DiIYwGARYQGxPXpEWgugr6RNyu1c48tC"
all_users_data = load_all_user_data(file_id)

def extract_answer_with_gemini(question, snippets):
    prompt = f"""
    سوال کاربر:
    {question}

    نتایج جستجو:
    {snippets}

    با توجه به اطلاعات بالا، لطفاً پاسخی واضح، دقیق و کوتاه به زبان فارسی بده. فقط پاسخ مفید بده و از آوردن لینک یا اطلاعات اضافی خودداری کن.
    """

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}

    response = requests.post(GEMINI_URL, json=payload, headers=headers)
    try:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return "خطا در دریافت پاسخ از مدل زبان."


def build_context(user_profile):
    return f"""
User Profile:
- Name: {user_profile['Personal Information']['name']}
- Age: {user_profile['Personal Information']['age']}
- Sex: {user_profile['Personal Information']['sex']}
- Location: {user_profile['Personal Information']['habitat']}

Career:
- Job Title: {user_profile['career']['job title']}
- Current Role: {user_profile['career']['Current job']}
- First Work Experience: {user_profile['career']['first work experience']}
- Skills: {", ".join(user_profile['career']['skills'])}
- Achievements: {", ".join(user_profile['career']['achievements'])}

Education:
- Level of Education: {user_profile['Education'].get('Level of education', 'N/A')}
- Special Programs: {", ".join(user_profile['Education'].get('Special educational programs', []))}
- University Success: {user_profile['Education'].get('Significant academic experience', 'N/A')}
- Courses with High Performance: {", ".join(user_profile['Education'].get('University courses with good performance', []))}
- Awards & Scholarships: {user_profile['Education'].get('Awards and Scholarships', 'N/A')}

Personal Achievements:
- Sports Achievement: {user_profile['Personal Achievements'].get('Significant sport achievement', 'N/A')}
- Overcome Obstacles: {user_profile['Personal Achievements'].get('an overcame obstacle', 'N/A')}

Major Life Events:
- Moved Cities: {user_profile['major changes in life'].get('moving to a new city', 'N/A')}
- Relationships: {user_profile['major changes in life'].get('relationships', 'N/A')}
- Family Changes: {user_profile['major changes in life'].get('family changes', 'N/A')}
- Retirement: {user_profile['major changes in life'].get('retirement', 'N/A')}
- Most Important Life Experience: {user_profile['major changes in life'].get('most important life experience', 'N/A')}

Preferences:
- Music: {", ".join(user_profile['Preferences'].get('music', []))}
- Movies: {", ".join(user_profile['Preferences'].get('movies', []))}
- Favorite Topics: {", ".join(user_profile['Preferences'].get('favorite_topics', []))}

Travel Experience:
- First Foreign Trip: {user_profile['Travel Experience'].get('First foreign travel experience', 'N/A')}
- Most Valuable Trip: {user_profile['Travel Experience'].get('the most valuable travel experience', 'N/A')}
- Cultural Exchange: {user_profile['Travel Experience'].get('cultural exchange', 'N/A')}

Social Impact:
- Volunteer Work: {user_profile['Social Impact'].get('Volunteer work', 'N/A')}
- Social Events: {", ".join(user_profile['Social Impact'].get('Social event', []))}
- Social Movements: {user_profile['Social Impact'].get('Attending a social movement', 'N/A')}

Cognitive Traits:
- IQ: {user_profile['Intelligence'].get('IQ', 'N/A')}
- EQ: {user_profile['Intelligence'].get('EQ', 'N/A')}

Instructions:
- Use this detailed profile to provide responses that are tailored and empathetic.
- Reflect the user’s professional background, personal journey, values, and personality in your answers.
- Prioritize clarity and relevance in advice, referencing their education, experiences, or preferences as needed.
- When applicable, consider location and culture in the context of recommendations or examples.

User Question: INSERT_USER_QUESTION_HERE
"""

# Generate response from Gemini
def generate_response(user_question, user_id):
    user_profile = all_users_data["users"].get(user_id)
    if not user_profile:
        return f"Error: User ID '{user_id}' not found."

    prompt = build_context(user_profile).replace("INSERT_USER_QUESTION_HERE", user_question)
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}

    response = requests.post(GEMINI_URL, json=payload, headers=headers)
    if "candidates" in response.json():
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    else:
        return "Error: No AI response received."

# Search Persian content via Google CSE
def search_persian_content(query):
    params = {
        "key": GOOGLE_API_KEY,
        "cx": CSE_ID,
        "q": query,
        "num": 3,
        "lr": "lang_fa"
    }
    try:  
        response = requests.get(GOOGLE_SEARCH_URL, params=params)
        response.raise_for_status()
        data = response.json()
        snippets = "\n\n".join(
            [item.get("snippet") for item in data.get("items", []) if item.get("snippet")]
        )

        if not snippets:
            return "متأسفم، اطلاعات مرتبطی پیدا نشد."

        return extract_answer_with_gemini(query, snippets)

    except requests.RequestException as e:
        print("Search failed:", e)
        return "خطا در دریافت اطلاعات از اینترنت."

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    query = data.get("query")
    user_id = data.get("user_id", "anonymous")

    if not query:
        return jsonify({"reply": "Missing query."}), 400

    # Save user message
    db.session.add(ChatHistory(user_id=user_id, role='user', message=query))
    db.session.commit()

    # Try search engine
    search_result = search_persian_content(query)

    # Save bot reply
    db.session.add(ChatHistory(user_id=user_id, role='bot', message=search_result))
    db.session.commit()

    return jsonify({"reply": search_result})

@app.route("/history", methods=["POST"])
def get_history():
    data = request.json
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"history": []})

    messages = ChatHistory.query.filter_by(user_id=user_id).all()
    history = [{"role": msg.role, "content": msg.message} for msg in messages]
    return jsonify({"history": history})

@app.route("/clear_history", methods=["POST"])
def clear_history():
    data = request.json
    user_id = data.get("user_id")
    if user_id:
        ChatHistory.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return jsonify({"message": "Chat history cleared."})
    return jsonify({"error": "No user_id provided."}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
