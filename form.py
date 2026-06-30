import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# We need access to both Forms (to create the quiz) and Drive (to set up sharing settings/links)
SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/drive.file"
]

def authenticate_google():
    """Authenticates the user and returns the Google Forms API service object."""
    creds = None
    
    # token.json stores the user's access and refresh tokens created automatically
    # when the authorization flow completes for the first time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Looks for the credentials.json you just downloaded
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    # Build the API services
    forms_service = build("forms", "v1", credentials=creds)
    return forms_service

def get_correct_answer_value(q):
    """
    Robust helper to resolve the correct answer value from the question dict.
    Handles direct matching, case-insensitive matching, and letter keys (A, B, C, D).
    """
    ans = q.get("answer") or q.get("correct_answer")
    if not ans:
        return ""
    
    ans_str = str(ans).strip()
    options = q.get("options", [])
    
    # 1. Direct match
    for opt in options:
        if str(opt).strip() == ans_str:
            return opt
            
    # 2. Case-insensitive match
    for opt in options:
        if str(opt).strip().lower() == ans_str.lower():
            return opt
            
    # 3. Check if it's a letter (e.g. "A", "B", "C", "D")
    letters = ["A", "B", "C", "D", "E", "F"]
    if len(ans_str) == 1 and ans_str.upper() in letters[:len(options)]:
        idx = letters.index(ans_str.upper())
        return options[idx]
        
    # 4. Check if it's a letter with a delimiter (e.g. "A.", "A:", "A)")
    if len(ans_str) > 1 and ans_str[0].upper() in letters[:len(options)] and ans_str[1] in [".", ":", ")"]:
        idx = letters.index(ans_str[0].upper())
        return options[idx]
        
    # Default fallback to the stripped answer string
    return ans_str

def create_google_quiz(forms_service, quiz_title, ai_questions):
    """
    Creates a self-grading Google Form quiz from AI-generated questions.
    ai_questions should be a list of dicts: 
    [{'question': '...', 'options': ['A', 'B'...], 'correct_answer': 'A'}]
    """
    
    # 1. Create a basic empty form
    form_details = {
        "info": {
            "title": quiz_title,
            "documentTitle": quiz_title
        }
    }
    
    form = forms_service.forms().create(body=form_details).execute()
    form_id = form.get("formId")
    
    # 2. Build the structural updates (Enable Quiz Mode + Add Questions)
    requests = []
    
    # Request A: Change form settings to a Quiz (Enables grading & correct answers)
    requests.append({
        "updateSettings": {
            "settings": {
                "quizSettings": {
                    "isQuiz": True
                }
            },
            "updateMask": "quizSettings.isQuiz"
        }
    })
    
    # Request B: Loop through AI JSON and create individual items based on type
    for index, q in enumerate(ai_questions):
        q_type = q.get("type", "mcq")
        options = q.get("options", [])
        
        # Determine question type
        if q_type == "short" or not options:
            # Short Answer question
            correct_answer = q.get("answer") or q.get("correct_answer") or ""
            correct_answer = str(correct_answer).strip()
            
            question_details = {
                "required": True,
                "textQuestion": {},
                "grading": {
                    "pointValue": 1,
                    "correctAnswers": {
                        "answers": [{"value": correct_answer}]
                    }
                }
            }
        else:
            # Choice question (MCQ or True/False)
            options_list = [{"value": opt} for opt in options]
            correct_answer = get_correct_answer_value(q)
            
            question_details = {
                "required": True,
                "choiceQuestion": {
                    "type": "RADIO",
                    "options": options_list
                },
                "grading": {
                    "pointValue": 1,
                    "correctAnswers": {
                        "answers": [{"value": correct_answer}]
                    }
                }
            }
            
        item_request = {
            "createItem": {
                "item": {
                    "title": q["question"],
                    "questionItem": {
                        "question": question_details
                    }
                },
                "location": {
                    "index": index # Sequence order in the form
                }
            }
        }
        requests.append(item_request)
        
    # 3. Execute all requests at once in a batchUpdate
    forms_service.forms().batchUpdate(
        formId=form_id, 
        body={"requests": requests}
    ).execute()
    
    # Return the clickable, shareable student responder link
    return f"https://docs.google.com/forms/d/{form_id}/viewform"

# Quick test run
if __name__ == "__main__":
    import sys
    # Reconfigure stdout/stderr encoding to prevent Windows console crashes
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except AttributeError:
            pass
            
    print("Testing Google Authentication...")
    service = authenticate_google()
    print("Success! Authenticated safely with Google.")
    
    # Mock AI data testing MCQ, TF, and Short Answer question types
    mock_ai_data = [
        {
            "type": "mcq",
            "question": "What is the primary programming language used for Streamlit apps?",
            "options": ["Java", "Python", "C++", "JavaScript"],
            "answer": "Python"
        },
        {
            "type": "tf",
            "question": "Python is a compiled language.",
            "options": ["True", "False"],
            "answer": "False"
        },
        {
            "type": "short",
            "question": "What is the name of the Python library used to build interactive web apps easily?",
            "options": [],
            "answer": "Streamlit"
        }
    ]
    
    print("Creating your Google Form Quiz...")
    quiz_url = create_google_quiz(service, "AI Mixed Quiz Test", mock_ai_data)
    
    print("\n🎉 Success! Your Quiz is live!")
    print(f"Shareable Link: {quiz_url}")