import os
import json
from groq import Groq
from dotenv import load_dotenv

# Step 1: Load environment variables
load_dotenv()

# Step 2: Initialize Groq client
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError(
        "GROQ_API_KEY not found in environment. Please set it in your .env file."
    )

client = Groq(api_key=api_key)

def generate_questions_with_groq(text, num_questions=5, question_type="Multiple Choice", difficulty="Medium", model_name="llama-3.3-70b-versatile"):
    # Customize instructions based on question_type
    if question_type == "Multiple Choice":
        type_instructions = "Generate only multiple-choice questions (MCQs) where each question has exactly 4 options."
    elif question_type == "True/False":
        type_instructions = "Generate only True/False questions where each question has options exactly: ['True', 'False']."
    elif question_type == "Short Answer":
        type_instructions = "Generate only Short Answer questions where the answer is a brief, concise word or phrase (options list must be empty [])."
    else: # Mixed
        type_instructions = "Generate a mix of multiple-choice questions (MCQs with 4 options), True/False questions (with options ['True', 'False']), and Short Answer questions (options list must be empty [])."

    prompt = f"""
Based on the text below, generate exactly {num_questions} questions at a {difficulty} difficulty level.
{type_instructions}

Return ONLY valid JSON matching this schema:
{{
  "questions": [
    {{
      "type": "mcq" | "tf" | "short",
      "question": "The question text",
      "options": ["string"], // For "mcq" (exactly 4 options), for "tf" (exactly ["True", "False"]), for "short" (empty list [])
      "answer": "string", // Must match one of the options exactly (for "mcq" and "tf"), or represent the correct short answer text (for "short")
      "explanation": "Brief explanation of why the answer is correct"
    }}
  ]
}}

Text:
{text}
"""
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that only returns valid JSON matching the requested schema."},
            {"role": "user", "content": prompt},
        ],
        # Force JSON response output to prevent parsing errors
        response_format={"type": "json_object"}
    )
    
    # Parse the response to a Python dictionary
    return json.loads(response.choices[0].message.content)

def generate_mcqs_with_groq(text, num_questions=5, difficulty="Medium", model_name="llama-3.3-70b-versatile"):
    """Wrapper function for backwards compatibility"""
    return generate_questions_with_groq(text, num_questions, "Multiple Choice", difficulty, model_name)