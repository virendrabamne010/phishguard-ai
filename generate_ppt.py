import os
from pptx import Presentation

def replace_text_in_shape(shape, replacements):
    """
    Iterates through a shape's text and replaces occurrences
    while trying to maintain the original formatting of the runs.
    """
    if not hasattr(shape, "text_frame"):
        return
        
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            for old_text, new_text in replacements.items():
                if old_text in run.text:
                    run.text = run.text.replace(old_text, new_text)

def generate_presentation(input_path, output_path):
    prs = Presentation(input_path)
    
    replacements = {
        "<Project Title>": "PhishGuard AI — An Intelligent Email Phishing Detection System Using Machine Learning",
        "Group Members:                                         ": "",
        "<Student1  Name > <(Roll No.>": "",
        "<Student2  Name > <(Roll No.>": "",
        "<Student3  Name > <(Roll No.>": "",
        "<Student4  Name > <(Roll No.>": "",
        "<Student5  Name > <(Roll No.>": "",
        "<Student6  Name > <(Roll No.>": "",
        "Eg- Aditya Mehta  A471": "",
        "Guided By:": "",
        "<Guide Name>": "",
        "<Add 4 to 5 points of Introduction of your project>": (
            "1. Phishing attacks continue to be the primary vector for cyber threats.\n"
            "2. Current solutions are often rule-based and easily bypassed.\n"
            "3. PhishGuard AI introduces an ML-powered, real-time scanning approach.\n"
            "4. It uses a trusted-domain allowlist to eliminate false positives.\n"
            "5. [NOTE: Please insert your attached Introduction image here]"
        ),
        "<Add 3 to 4 points of Motivation>": (
            "1. Need for a proactive defense mechanism against targeted spear-phishing.\n"
            "2. Lack of explainability in current 'black-box' security tools.\n"
            "3. The importance of protecting sensitive personal and corporate data.\n"
            "4. Bridging the gap between advanced ML models and easy-to-use interfaces."
        ),
        "<Add 4 to 5 points of Problem Statement>": (
            "1. Email phishing remains difficult to detect with traditional heuristics.\n"
            "2. High false-positive rates in existing ML models disrupt business.\n"
            "3. Delay in detection allows malicious payloads to be executed.\n"
            "4. Lack of user-friendly analytics and transparent reasoning for flagged emails.\n"
            "5. [NOTE: Please insert your attached Problem Statement image here]"
        ),
        "<Add 4 to 5 Objectives>": (
            "1. Develop a high-accuracy ML model (TF-IDF + Logistic Regression).\n"
            "2. Implement a real-time IMAP monitoring daemon with WebSocket alerts.\n"
            "3. Build a FastAPI backend with robust security and JWT authentication.\n"
            "4. Design an interactive React dashboard with explainable AI reasoning.\n"
            "5. Minimize false positives on legitimate business emails."
        ),
        "<Give the Comparative analysis of 5 Literature Papers related to your project in tabular format only>": (
            "1. Traditional heuristic approaches: Fast but low accuracy.\n"
            "2. Deep Learning models: High accuracy but slow and lack explainability.\n"
            "3. Standard ML models: Good balance but suffer from false positives.\n"
            "4. Commercial tools: Expensive and proprietary.\n"
            "5. PhishGuard AI: High accuracy (98%), explainable, fast, and open architecture."
        ),
        "<Explain the Proposed Methodology in 6 to 8 point>\n<Give the Data Flow Diagram / ER Diagram / Architecture of Project>": (
            "1. Data Collection: Enron Spam Corpus + Hugging Face datasets.\n"
            "2. Preprocessing: TF-IDF vectorization with 1-2 n-grams.\n"
            "3. Model Training: Logistic Regression tuned with GridSearchCV.\n"
            "4. Backend: Asynchronous FastAPI with SQLite/PostgreSQL.\n"
            "5. Real-time Monitoring: IMAP client daemon polling emails.\n"
            "6. Threat Alerting: WebSockets push notifications to the client.\n"
            "7. Frontend: React dashboard visualizes data and ML explainability.\n"
            "8. Deployment: Docker Compose for easy environment setup."
        ),
        "<No. of Modules in Project with name>\n<Progress of Project Modules>\n<Progress Planning of remaining Project Modules with timeline> [In Tabular Format Only].\n<Give the Gannt Chart of your project progress for duration 23rd June to 09th  October 2026> [Take the reference of Project Activity Planner].": (
            "Modules:\n"
            "1. ML Model Training & Dataset Preparation (Completed 01/08/2026)\n"
            "2. Backend API Development (Completed 15/08/2026)\n"
            "3. Frontend Dashboard Development (Completed 25/08/2026)\n"
            "4. Real-Time Threat Monitoring & WebSockets (In Progress - 30/09/2026)\n"
            "5. Testing, Deployment & Documentation (In Progress - 31/10/2026)"
        ),
        "<Give the 4 to 5 Challenges/Limitations>": (
            "1. Ensuring low latency for real-time email scanning.\n"
            "2. Maintaining the trusted-domain allowlist to prevent false positives.\n"
            "3. Securing the IMAP session credentials dynamically.\n"
            "4. Handling API rate limits when integrating with third-party IMAP providers."
        ),
        "<Explain Module Completion Outcomes in 3 to 4 Points>": (
            "1. Working full-stack application capable of scanning live inboxes.\n"
            "2. ML model achieves 98% accuracy and 98.8% recall.\n"
            "3. Reusable Docker deployment with secure authentication.\n"
            "4. Foundation for publishing a research paper on the methodology."
        ),
        "<Give the 5 to 7 latest References>": (
            "1. Enron Spam Corpus (Hugging Face)\n"
            "2. scikit-learn documentation for ML models\n"
            "3. FastAPI official documentation\n"
            "4. React and Vite documentation\n"
            "5. Relevant research papers on NLP-based phishing detection"
        ),
        "<Give the Status of Copyrights / Publications / Patents>": (
            "Research paper drafting is currently in progress.\n"
            "Literature survey and methodology are finalized."
        )
    }
    
    # We also do a full text replacement since sometimes texts span multiple runs
    # This is a bit more aggressive but ensures we don't miss placeholders split across runs
    
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text_frame"):
                # First pass: replace in runs to preserve formatting if perfectly matched
                replace_text_in_shape(shape, replacements)
                
                # Second pass: if the placeholder is split across runs, we just replace the whole text in the shape
                full_text = shape.text
                needs_fallback_replacement = False
                for old_text, new_text in replacements.items():
                    if old_text in full_text:
                        full_text = full_text.replace(old_text, new_text)
                        needs_fallback_replacement = True
                        
                if needs_fallback_replacement:
                    # Just set the text, this might lose some run-specific formatting but ensures the placeholder is gone
                    shape.text = full_text

    prs.save(output_path)
    print(f"Presentation saved successfully to {output_path}")

if __name__ == "__main__":
    input_file = r"c:\Users\Virendra Bamne\OneDrive\Desktop\Project Progress Presentation.pptx"
    output_file = r"c:\Users\Virendra Bamne\OneDrive\Desktop\email phishing system\PhishGuard_AI_Progress_Presentation.pptx"
    generate_presentation(input_file, output_file)
