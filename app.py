from flask import Flask, request, jsonify, session
from werkzeug.utils import secure_filename
from extensions import db
from models import *
import os
import re
import pdfplumber
import docx
import json
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS
from flask_cors import CORS




app = Flask(__name__)
from flask_cors import CORS

CORS(app, supports_credentials=True)
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=False
)



app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
app.secret_key = "hkjndn7499034nhefui57{ew7672ghwi1lkha_klkldawqsnlcedclrp"


db.init_app(app)


@app.route("/signup", methods=["POST"])
def signup():
    data = request.json

    if Users.query.filter_by(email=data["email"]).first():  # cheking from the database.
        return jsonify({"error": "Email already exists"}), 400

    user = Users(   # here one User entry is created. 
        email=data["email"], 
        password_hash=data.get("password"), 
        role="candidate"
    )
    db.session.add(user)
    db.session.commit()

    # Just after after the signup-
    candidate = Candidates(  # here one Candidate entry is created.
        user_id=user.user_id, 
        full_name=data.get("full_name"), 
        experience_years=data.get("experience_years")
    )
    db.session.add(candidate)
    db.session.commit()

    return jsonify({"message": "Signup successful"})


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user = Users.query.filter_by(email=data["email"]).first()

    if not user or user.password_hash != data["password"]: # cheking that is user exist in theh database or not.
        return jsonify({"error": "Login failed"}), 401

    session["user_id"] = user.user_id  # for whole session, here we create user_is for the session, it will help to differentiate all the user and to know that user is signed in or not. 
    session["role"] = user.role

    return jsonify({"message": "Login successful"})


@app.route("/logout")
def logout():
    session.clear() # clearig the all session variables values, like user_id. 
    return jsonify({"message": "Logged out"})


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session: # checking, user is signed in or not.
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify({
        "actions": 
        [
            {
                "label": "Upload Resume + Analyze",
                "endpoint": "/analyze",
                "method": "POST"
            },
            {
                "label": "Show Past Resume Analysis",
                "endpoint": "/resumes",
                "method": "GET"
            },
            {
                "label": "Profile",
                "endpoint": "/profile",
                "method": "GET"
            }
        ]
    })


# 1. Extract raw text (ALL formats)
def extract_text(file_path):
    text = ""

    if file_path.endswith(".pdf"):
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""

    elif file_path.endswith(".docx"):
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"

    elif file_path.endswith(".tex"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        # Remove LaTeX commands
        text = re.sub(r"\\[a-zA-Z]+\{.*?\}", " ", text)
        text = re.sub(r"\\[a-zA-Z]+", " ", text)
        text = re.sub(r"\{|\}", " ", text)

    return text.lower()


# 2. Skill Extraction (same as before)
KNOWN_SKILLS = [
    "python", "c", "c++", "java", "javascript",
    "html", "css", "sql", "flask", "django",
    "react", "node", "machine learning", "deep learning"
]
def extract_skills(text):
    found_skills = set()

    for skill in KNOWN_SKILLS:
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text):
            found_skills.add(skill.capitalize())

    return list(found_skills)

# 3. GitHub Username Extraction (LaTeX-safe)
def extract_github_username(text):
    match = re.search(
        r"github\.com/([a-zA-Z0-9_-]+)",
        text
    )

    if match:
        return match.group(1)

    return None

# 4. Final Unified Parser (CLEAN)
def parse_resume(file_path):
    text = extract_text(file_path)

    skills = extract_skills(text)
    github_username = extract_github_username(text)

    return {
        "skills": skills,
        "github_username": github_username
    }


@app.route("/analyze", methods=["POST"])
def analyze_resume():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    resume_file = request.files.get("resume") #fetching the resume file
    if not resume_file: # check it present or not
        return jsonify({"error": "No resume uploaded"}), 400

    filename = secure_filename(resume_file.filename) # securing it
    path = os.path.join("uploads", filename)
    resume_file.save(path)

    candidate = Candidates.query.filter_by(user_id=session["user_id"]).first()

    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    resume = Resumes(            # here one resume intery is created
        candidate_id=candidate.candidate_id,
        resume_path=path
    )
    db.session.add(resume)
    db.session.commit()


    parsed_text = parse_resume(path)
    # this will be send to the ml model
    extracted_skills = parsed_text["skills"]
    github_username = parsed_text["github_username"]    

    
    platform = Platforms.query.filter_by(platform_name="GitHub").first() # extracting the github plaatform data.

    if not platform: # if in datadase github platform not exist
        platform = Platforms(platform_name="GitHub")
        db.session.add(platform)
        db.session.commit()


    # Create skill claims 
    claims_map = {}  # skill_name -> claim_id,  claims_map = {"skill": id, "skill": id, "skill": id}
    
    for skill in extracted_skills: # here we storing the all claimed skill to the database for the one resume
        claim = Skillclaims(
            resume_id=resume.resume_id,
            skill_name=skill
        )
        db.session.add(claim)
        db.session.commit()
        claims_map[skill] = claim.claim_id # claims_map = { "Python": 12, "C": 13 }
        #           |               |
        #         skill           claim_id    


    # Send data to ML model (STUB) ------------------------------------------------
    ml_request_payload = {
        "github_username": github_username,
        "skills": extracted_skills
    }


    # Example: streaming ML response (JSON lines)
    # Simulated ML response
    ml_stream_response = [
        '{"user": "Vishalfot", "status": "processing"}',
        '{"C": {"semantic_similarity": {"score": 0.6, "evidence": "Moderate"}, "complexity": "Low", "project_maturity": "Experimental", "consistency": "Consistent", "recency": "Stale"}}',
        '{"Python": {"semantic_similarity": {"score": 0.0, "evidence": "Weak"}, "complexity": "Low", "project_maturity": "Experimental", "consistency": "One-off", "recency": "Dormant"}}',
        '{"JavaScript": {"semantic_similarity": {"score": 0.55, "evidence": "Moderate"}, "complexity": "High", "project_maturity": "Experimental", "consistency": "Occasional", "recency": "Active"}}'
    ]


    # merge ML stream into single JSON
    final_ml_results = {}
    for message in ml_stream_response:
        data = json.loads(message)

        # Ignore status messages
        if "status" in data:
            continue

        # Skill-wise evaluation
        for skill, evaluation in data.items():
            final_ml_results[skill] = evaluation


    # Store ML evaluation 
    for skill, evaluation in final_ml_results.items(): # it will store evaluation/json_responce for each skill for each flatform(github thistime)
        if skill not in claims_map: # for just safe case
            continue

        verification = ClaimVerification(
            claim_id=claims_map[skill],
            platform_id=platform.platform_id,
            evaluation_json=evaluation,
            model_version="v1.0" # just a random value
        )
        db.session.add(verification)
    db.session.commit()

    final_response = { # this will go to the frontend
        "message": "Resume analyzed successfully",
        "platform": platform.platform_name,
        "response": final_ml_results
    }

    resume.analysis_json = final_response # here the resume analysis will get store in the database for future use
    db.session.commit()

    return jsonify(final_response), 200

    

@app.route("/resumes") # showing past uploaded resumes
def past_resumes():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    candidate = Candidates.query.filter_by(user_id=session["user_id"]).first()
    if not candidate:
        return jsonify([])

    resumes = Resumes.query.filter_by(candidate_id=candidate.candidate_id).order_by(Resumes.uploaded_at.desc()).all()

    return jsonify([ # this will send the all resumes for one person
        {
            "resume_id": r.resume_id, # resume id 
            "uploaded_at": r.uploaded_at # date
        }
        for r in resumes
    ])



@app.route("/resume/<int:resume_id>") # showing the past resume after clicking the resume in the past/history resumes section
def get_resume_analysis(resume_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    candidate = Candidates.query.filter_by(user_id=session["user_id"]).first()
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    resume = Resumes.query.filter_by(
        resume_id=resume_id,
        candidate_id=candidate.candidate_id
    ).first()

    if not resume:
        return jsonify({"error": "Resume not found"}), 404

    return jsonify(resume.analysis_json) # this json send file is exactally what /anlyze retuens.
 


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    candidate = Candidates.query.filter_by(
        user_id=session["user_id"]
    ).first()

    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    return jsonify({
        "full_name": candidate.full_name,
        "experience_years": candidate.experience_years
    })



@app.route("/profile/update", methods=["POST"])
def update_profile():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    candidate = Candidates.query.filter_by(
        user_id=session["user_id"]
    ).first()

    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    if "full_name" in data:
        candidate.full_name = data["full_name"]

    if "experience_years" in data:
        candidate.experience_years = data["experience_years"]

    db.session.commit()

    return jsonify({"message": "Profile updated successfully"})


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
