# AI Exam Question Generator
AI-powered Streamlit app that extracts text from PDFs, generates questions (MCQs, True/False, Short Answers) using Groq, and pushes them to a self-grading Google Form Quiz.
## Setup
1. Install requirements: pip install -r requirements.txt
2. Create a .env file and add your GROQ API key:
GROQ_API_KEY=your_api_key_here

3. Add your Google OAuth credentials locally as credentials.json.
Do not upload credentials.json to GitHub.
## Run
streamlit run pdf.py
## Files
pdf.py  | ai.py  | form.py 
