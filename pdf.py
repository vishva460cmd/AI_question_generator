import streamlit as st
from ai import generate_questions_with_groq
from form import authenticate_google, create_google_quiz
import pdfplumber
import time

# Set up page configurations
st.set_page_config(
    page_title="PDF MCQ Generator",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Header Section
st.title("🤖 PDF MCQ Generator")
st.markdown("Extract text from any PDF document and generate multiple-choice questions (MCQs) using high-quality LLMs.")

st.divider()

# Initialize session state for quiz tracking
if "questions" not in st.session_state:
    st.session_state.questions = []
if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = ""

# Sidebar Settings
st.sidebar.header("⚙️ Configuration")

# Model Selection
model_options = {
    "Llama 3.3 70B (Recommended)": "llama-3.3-70b-versatile",
    "GPT-OSS 120B (High Reasoning)": "openai/gpt-oss-120b",
    "Llama 3.1 8B (Fast)": "llama-3.1-8b-instant"
}
selected_model_label = st.sidebar.selectbox(
    "Select AI Model",
    options=list(model_options.keys()),
    index=0,
    help="Select the model to generate the questions. 70B is highly recommended for balanced accuracy and speed."
)
model_name = model_options[selected_model_label]

st.sidebar.divider()

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    # Clear quiz if a new file is uploaded
    if st.session_state.uploaded_file_name != uploaded_file.name:
        st.session_state.questions = []
        st.session_state.uploaded_file_name = uploaded_file.name

    # Open the uploaded PDF to read page count
    with pdfplumber.open(uploaded_file) as pdf:
        total_pages = len(pdf.pages)
        st.success(f"Successfully uploaded: **{uploaded_file.name}** ({total_pages} pages)")
        
        # Page Selection Mode
        st.sidebar.subheader("📄 Page Selection")
        page_selection_type = st.sidebar.radio(
            "Select pages to process",
            ["All Pages", "Page Range", "Single Page"],
            index=1  # Default to page range as it is the most practical
        )
        
        if page_selection_type == "Page Range":
            col1, col2 = st.sidebar.columns(2)
            with col1:
                start_page = st.number_input("Start Page", min_value=1, max_value=total_pages, value=1)
            with col2:
                end_page = st.number_input("End Page", min_value=start_page, max_value=total_pages, value=min(start_page + 4, total_pages))
        elif page_selection_type == "Single Page":
            start_page = st.number_input("Page Number", min_value=1, max_value=total_pages, value=min(200, total_pages))
            end_page = start_page
        else:
            start_page = 1
            end_page = total_pages

        st.sidebar.divider()
        
        # Advanced Rate Limit settings
        with st.sidebar.expander("🛡️ Rate Limit & Batch Settings"):
            batch_size = st.slider(
                "Batch Size (Pages per Request)",
                min_value=1,
                max_value=15,
                value=5,
                help="Process pages in chunks to avoid Token Per Minute (TPM) limits."
            )
            sleep_time = st.slider(
                "Rate Limit Delay (Seconds)",
                min_value=0,
                max_value=60,
                value=15,
                help="Waiting time between requests to allow the rate limit counter to reset."
            )

        # Extract only selected pages
        extracted_pages = []
        with st.spinner("Extracting text from selected pages..."):
            for page_num in range(start_page - 1, end_page):
                page = pdf.pages[page_num]
                text = page.extract_text()
                extracted_pages.append((page_num + 1, text or ""))
        
        # Filter pages that actually contain text
        valid_pages = [(p_num, text) for p_num, text in extracted_pages if text.strip()]
        
        if valid_pages:
            # Reconstruct preview text
            preview_text = "\n\n".join([f"--- Page {p_num} ---\n{text[:300]}..." for p_num, text in valid_pages[:3]])
            if len(valid_pages) > 3:
                preview_text += f"\n\n... and {len(valid_pages) - 3} more page(s) extracted."
            
            st.subheader("📝 Selected Content Preview")
            st.text_area("Selected Pages Preview", preview_text, height=180, disabled=True)
            
            st.divider()
            
            # --- Question Generation Section ---
            st.subheader("🤖 Question Generation Settings")
            col_count, col_type, col_diff = st.columns([2, 2, 1])
            with col_count:
                num_questions = st.slider("Total questions to generate", min_value=1, max_value=30, value=5)
            with col_type:
                question_type = st.selectbox("Question Type", ["Multiple Choice", "True/False", "Short Answer", "Mixed"], index=0)
            with col_diff:
                difficulty = st.selectbox("Difficulty Level", ["Easy", "Medium", "Hard"], index=1)
            
            if st.button("✨ Generate Questions", type="primary"):
                # Helper to split pages list into chunks
                def chunk_list(lst, chunk_size):
                    for i in range(0, len(lst), chunk_size):
                        yield lst[i:i + chunk_size]
                
                chunks = list(chunk_list(valid_pages, batch_size))
                num_chunks = len(chunks)
                
                all_questions = []
                progress_bar = st.progress(0)
                status_box = st.empty()
                
                # Execute calls
                for idx, chunk in enumerate(chunks):
                    # Calculate proportional questions for this chunk
                    chunk_questions_count = (num_questions // num_chunks) + (1 if idx < (num_questions % num_chunks) else 0)
                    if chunk_questions_count == 0:
                        continue
                    
                    chunk_pages_str = f"Pages {chunk[0][0]}" if len(chunk) == 1 else f"Pages {chunk[0][0]}-{chunk[-1][0]}"
                    status_box.info(f"Generating {chunk_questions_count} questions from {chunk_pages_str} (Batch {idx+1}/{num_chunks})...")
                    
                    # Combine text for the chunk
                    chunk_text = "\n\n".join([f"--- Page {p_num} ---\n{text}" for p_num, text in chunk])
                    
                    try:
                        # Call API
                        result = generate_questions_with_groq(
                            chunk_text, 
                            num_questions=chunk_questions_count, 
                            question_type=question_type,
                            difficulty=difficulty,
                            model_name=model_name
                        )
                        questions = result.get("questions", [])
                        for q in questions:
                            q["difficulty"] = difficulty
                            # Fallback if AI didn't output type
                            if "type" not in q or not q["type"]:
                                if question_type == "Multiple Choice":
                                    q["type"] = "mcq"
                                elif question_type == "True/False":
                                    q["type"] = "tf"
                                elif question_type == "Short Answer":
                                    q["type"] = "short"
                                else:
                                    q["type"] = "mcq"
                        all_questions.extend(questions)
                    except Exception as e:
                        st.error(f"Failed to generate questions for {chunk_pages_str}. Error: {e}")
                        break
                    
                    # Update progress
                    progress_bar.progress((idx + 1) / num_chunks)
                    
                    # Pause between requests if not the last batch to prevent rate limit limits
                    if idx < num_chunks - 1:
                        for remaining in range(sleep_time, 0, -1):
                            status_box.warning(f"⏳ Sleeping {remaining}s to respect rate limits before next batch...")
                            time.sleep(1)
                
                if all_questions:
                    status_box.success(f"🎉 Completed! Generated {len(all_questions)} questions in total.")
                    st.session_state.questions = all_questions
                    st.rerun()

            # Render Quiz from Session State if questions exist
            if st.session_state.questions:
                st.divider()
                st.subheader("📤 Export to Google Forms Quiz")
                with st.expander("Configure & Create Google Form", expanded=True):
                    default_quiz_title = "AI Generated Quiz"
                    if st.session_state.uploaded_file_name:
                        base_name = st.session_state.uploaded_file_name.rsplit(".", 1)[0]
                        default_quiz_title = f"{base_name} Quiz"
                        
                    quiz_title = st.text_input("Form Title", value=default_quiz_title)
                    
                    if st.button("🚀 Push to Google Forms", type="primary", use_container_width=True):
                        with st.spinner("Creating Google Form Quiz..."):
                            try:
                                service = authenticate_google()
                                quiz_url = create_google_quiz(service, quiz_title, st.session_state.questions)
                                st.success("🎉 Successfully created Google Form Quiz!")
                                st.link_button("🌐 Open Google Form Quiz", quiz_url, use_container_width=True)
                            except Exception as e:
                                st.error(f"❌ Failed to create quiz: {e}")
                
                st.divider()
                st.subheader("🛠️ Manage Question Pool")
                col_clear, col_csv = st.columns([1, 1])
                with col_clear:
                    if st.button("🗑️ Clear All Questions", type="secondary", use_container_width=True):
                        st.session_state.questions = []
                        st.rerun()
                with col_csv:
                    import pandas as pd
                    df_export = []
                    for q in st.session_state.questions:
                        q_type = q.get("type", "mcq")
                        options = q.get("options") or []
                        # Pad options to at least 4 items
                        padded_options = list(options)
                        while len(padded_options) < 4:
                            padded_options.append("")
                            
                        df_export.append({
                            "Type": q_type.upper(),
                            "Question": q.get("question", ""),
                            "Option A": padded_options[0],
                            "Option B": padded_options[1],
                            "Option C": padded_options[2],
                            "Option D": padded_options[3],
                            "Correct Answer": q.get("answer", ""),
                            "Difficulty": q.get("difficulty", "Medium"),
                            "Explanation": q.get("explanation", "")
                        })
                    df = pd.DataFrame(df_export)
                    csv_data = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download CSV File",
                        data=csv_data,
                        file_name="generated_quiz_questions.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                st.divider()
                st.header("📋 Interactive Quiz")
                st.markdown("Test your knowledge! Select an option for each question to see immediate feedback.")
                
                correct_count = 0
                total_answered = 0
                
                for i, q in enumerate(st.session_state.questions):
                    with st.container():
                        diff = q.get("difficulty", "Medium")
                        q_type = q.get("type", "mcq").upper()
                        
                        color_map = {"Easy": "#10B981", "Medium": "#F59E0B", "Hard": "#EF4444"}
                        badge_color = color_map.get(diff, "#F59E0B")
                        
                        type_color_map = {"MCQ": "#3B82F6", "TF": "#8B5CF6", "SHORT": "#EC4899"}
                        type_badge_color = type_color_map.get(q_type, "#3B82F6")
                        
                        st.markdown(f"**Question {i + 1}** &nbsp; <span style='background-color: {badge_color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; vertical-align: middle;'>{diff}</span> &nbsp; <span style='background-color: {type_badge_color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; vertical-align: middle;'>{q_type}</span>", unsafe_allow_html=True)
                        st.subheader(q.get('question'))
                        
                        q_type_lower = q.get("type", "mcq").lower()
                        user_choice = None
                        
                        if q_type_lower == "mcq":
                            options = q.get("options", [])
                            correct_ans_str = str(q.get("answer", "")).strip()
                            correct_letter = ""
                            letters = ["A", "B", "C", "D", "E", "F"][:len(options)]
                            if len(correct_ans_str) > 0:
                                first_char = correct_ans_str[0].upper()
                                if first_char in letters:
                                    correct_letter = first_char
                            else:
                                correct_letter = correct_ans_str.upper()
                            
                            radio_options = []
                            correct_option_label = ""
                            for idx, opt in enumerate(options):
                                letter = letters[idx]
                                label = opt
                                if not opt.strip().startswith((f"{letter}:", f"{letter}. ", f"{letter})")):
                                    label = f"{letter}: {opt}"
                                radio_options.append(label)
                                if letter == correct_letter:
                                    correct_option_label = label
                                    
                            user_choice = st.radio(
                                "Choose your answer:",
                                options=radio_options,
                                key=f"quiz_q_{i}",
                                index=None,
                                help="Select your response"
                            )
                            
                            if user_choice is not None:
                                total_answered += 1
                                selected_letter = ""
                                clean_choice = user_choice.strip()
                                if len(clean_choice) > 0:
                                    first_char = clean_choice[0].upper()
                                    if first_char in letters:
                                        selected_letter = first_char
                                
                                st.markdown(f"👉 **Your Selection:** `{user_choice}`")
                                if selected_letter == correct_letter:
                                    st.success(f"🎉 **Correct Answer!** Excellent job.")
                                    correct_count += 1
                                else:
                                    st.error(f"❌ **Incorrect.**")
                                    st.markdown(f"**Correct Option:** `{correct_option_label}`")
                                    
                        elif q_type_lower == "tf":
                            user_choice = st.radio(
                                "Select True or False:",
                                options=["True", "False"],
                                key=f"quiz_q_{i}",
                                index=None
                            )
                            if user_choice is not None:
                                total_answered += 1
                                correct_ans = str(q.get("answer", "")).strip()
                                st.markdown(f"👉 **Your Selection:** `{user_choice}`")
                                if user_choice.lower() == correct_ans.lower():
                                    st.success(f"🎉 **Correct Answer!** Excellent job.")
                                    correct_count += 1
                                else:
                                    st.error(f"❌ **Incorrect.**")
                                    st.markdown(f"**Correct Answer:** `{correct_ans}`")
                                    
                        elif q_type_lower == "short":
                            user_choice = st.text_input(
                                "Type your answer:",
                                key=f"quiz_q_{i}",
                                placeholder="Enter response here..."
                            )
                            if user_choice.strip():
                                total_answered += 1
                                correct_ans = str(q.get("answer", "")).strip()
                                st.markdown(f"👉 **Your Selection:** `{user_choice.strip()}`")
                                if user_choice.strip().lower() == correct_ans.lower():
                                    st.success(f"🎉 **Correct Answer!** Excellent job.")
                                    correct_count += 1
                                else:
                                    st.error(f"❌ **Incorrect.**")
                                    st.markdown(f"**Correct Answer:** `{correct_ans}`")
                                    
                        if (user_choice is not None and q_type_lower != "short") or (q_type_lower == "short" and user_choice and user_choice.strip()):
                            if q.get("explanation"):
                                with st.expander("💡 View Explanation"):
                                    st.info(q.get("explanation"))
                        st.divider()
                
                # Show scorecard
                if total_answered > 0:
                    st.subheader("📊 Quiz Scorecard")
                    st.metric(
                        label="Final Score", 
                        value=f"{correct_count} / {len(st.session_state.questions)}", 
                        delta=f"{int(correct_count/len(st.session_state.questions)*100)}% Correct"
                    )
        else:
            st.warning("No text could be extracted from the selected pages.")
else:
    st.info("Upload a PDF file using the uploader above to begin.")