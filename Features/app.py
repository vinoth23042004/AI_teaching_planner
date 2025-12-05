from flask import Flask, request, render_template, jsonify, send_file, flash, redirect, url_for
import requests
import sqlite3
import os
import json
import re
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from docx import Document
from docx.shared import Inches
import tempfile
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Configure NVIDIA Meta Llama API
NVIDIA_API_KEY = "PASTE_YOUR_NVIDIA_API_KEY_HERE"   # model = meta/llama3.1-8b-instruct
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

class DatabaseManager:
    def __init__(self):
        self.db_path = 'academic_content.db'
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS syllabi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                available_days INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lesson_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                syllabus_id INTEGER,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (syllabus_id) REFERENCES syllabi (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                syllabus_id INTEGER,
                difficulty_level TEXT,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (syllabus_id) REFERENCES syllabi (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_code TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                questions TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_code TEXT NOT NULL,
                student_name TEXT NOT NULL,
                answers TEXT NOT NULL,
                score INTEGER,
                total_questions INTEGER,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quiz_code) REFERENCES quizzes (quiz_code)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_syllabus(self, title, content, available_days):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO syllabi (title, content, available_days) VALUES (?, ?, ?)', 
                      (title, content, available_days))
        syllabus_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return syllabus_id
    
    def save_lesson_plan(self, syllabus_id, content):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO lesson_plans (syllabus_id, content) VALUES (?, ?)', (syllabus_id, content))
        conn.commit()
        conn.close()
    
    def save_assessment(self, syllabus_id, difficulty_level, content):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO assessments (syllabus_id, difficulty_level, content) VALUES (?, ?, ?)', 
                      (syllabus_id, difficulty_level, content))
        conn.commit()
        conn.close()
    
    def save_quiz(self, quiz_code, title, questions):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO quizzes (quiz_code, title, questions) VALUES (?, ?, ?)', 
                      (quiz_code, title, json.dumps(questions)))
        conn.commit()
        conn.close()
    
    def get_quiz(self, quiz_code):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT title, questions FROM quizzes WHERE quiz_code = ?', (quiz_code,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return {'title': result[0], 'questions': json.loads(result[1])}
        return None
    
    def save_quiz_submission(self, quiz_code, student_name, answers, score, total_questions):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO quiz_submissions 
                         (quiz_code, student_name, answers, score, total_questions) 
                         VALUES (?, ?, ?, ?, ?)''', 
                      (quiz_code, student_name, json.dumps(answers), score, total_questions))
        conn.commit()
        conn.close()
    
    def get_quiz_submissions(self, quiz_code):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''SELECT student_name, score, total_questions, submitted_at 
                         FROM quiz_submissions WHERE quiz_code = ? ORDER BY submitted_at DESC''', 
                      (quiz_code,))
        results = cursor.fetchall()
        conn.close()
        return [{'student_name': r[0], 'score': r[1], 'total': r[2], 'submitted_at': r[3]} 
                for r in results]

class TextPreprocessor:
    @staticmethod
    def preprocess_syllabus(text):
        # Clean and tokenize the syllabus text
        cleaned_text = re.sub(r'\s+', ' ', text.strip())
        cleaned_text = re.sub(r'[^\w\s.,!?\-()]', '', cleaned_text)
        
        # Extract modules and topics
        modules = []
        topics = []
        
        # Extract modules
        module_pattern = r'MODULE\s+([IVX]+)\s*[–-]\s*([^*\n]+)'
        module_matches = re.findall(module_pattern, cleaned_text, re.IGNORECASE)
        
        for module_num, module_title in module_matches:
            modules.append(f"Module {module_num}: {module_title.strip()}")
        
        # Extract bullet points as topics
        bullet_pattern = r'\*\s*([^*\n]+)'
        topic_matches = re.findall(bullet_pattern, cleaned_text)
        
        for topic in topic_matches:
            topic = topic.strip()
            if len(topic) > 5 and not topic.startswith('Case Study'):
                topics.append(topic)
        
        # Extract case studies
        case_studies = []
        case_study_pattern = r'\*Case Study:\*\s*([^*\n]+)'
        case_study_matches = re.findall(case_study_pattern, cleaned_text)
        case_studies = [cs.strip() for cs in case_study_matches]
        
        return {
            'cleaned_text': cleaned_text,
            'modules': modules,
            'topics': topics,
            'case_studies': case_studies,
            'word_count': len(cleaned_text.split())
        }

class LlamaAPIClient:
    def __init__(self):
        self.api_key = NVIDIA_API_KEY
        self.api_url = NVIDIA_API_URL
        
    def make_request(self, prompt, max_tokens=2000):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "meta/llama-3.1-8b-instruct",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": max_tokens
        }
        
        try:
            print(f"[API] Sending request with max_tokens={max_tokens}...")
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            print(f"[API] Response received successfully")
            return result['choices'][0]['message']['content']
        except requests.exceptions.Timeout:
            error_msg = "API Error: Request timed out after 120 seconds. Try: 1) Generate one module at a time instead of 'All Modules', 2) Reduce MCQ count to 10-15, 3) Use shorter syllabus content."
            print(f"[API ERROR] {error_msg}")
            return error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"API Error: {str(e)}"
            print(f"[API ERROR] {error_msg}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"[API ERROR DETAIL] {error_detail}")
                    error_msg += f" - {error_detail}"
                except:
                    pass
            return error_msg

class PlanningAgent:
    def __init__(self):
        self.llama_client = LlamaAPIClient()
    
    def generate_weekly_timetable(self, syllabus_content, preprocessed_data, available_days, course_unit='all'):
        """Generate lesson plan/timetable for specific unit or all modules"""
        
        total_modules = len(preprocessed_data['modules'])
        total_topics = len(preprocessed_data['topics'])
        
        # Determine which modules/topics to include
        if course_unit == 'all':
            selected_topics = preprocessed_data['topics']
            selected_modules = preprocessed_data['modules']
            selected_case_studies = preprocessed_data['case_studies']
            unit_description = "All Modules (Complete Course)"
            # Calculate weeks: allocate at least 2.5 weeks per module to ensure coverage
            weeks_needed = max(15, total_modules * 3)
        else:
            # Filter for specific module
            module_index = int(course_unit) - 1
            if module_index < len(preprocessed_data['modules']):
                selected_modules = [preprocessed_data['modules'][module_index]]
                # Get topics related to this module
                topics_per_module = len(preprocessed_data['topics']) // len(preprocessed_data['modules'])
                start_idx = module_index * topics_per_module
                end_idx = start_idx + topics_per_module
                selected_topics = preprocessed_data['topics'][start_idx:end_idx]
                selected_case_studies = preprocessed_data['case_studies'][:2] if preprocessed_data['case_studies'] else []
                unit_description = f"Module {course_unit}"
                weeks_needed = max(2, (len(selected_topics) + available_days - 1) // available_days)
            else:
                selected_topics = preprocessed_data['topics'][:10]
                selected_modules = [preprocessed_data['modules'][0]] if preprocessed_data['modules'] else ["General Topics"]
                selected_case_studies = []
                unit_description = f"Module {course_unit}"
                weeks_needed = 3
        
        prompt = f"""
        Create a COMPREHENSIVE lesson plan/weekly timetable for {unit_description}.
        
        CRITICAL: This course has {total_modules} modules. You MUST cover ALL {total_modules} modules.
        Modules List: {', '.join(selected_modules)}
        
        IMPORTANT: Do NOT stop at Module IV. Continue through Module V and complete ALL modules.
        
        Syllabus Content: {syllabus_content[:2500]}
        
        Available Information:
        - Target: {unit_description}
        - ALL Modules ({total_modules} modules): {', '.join(selected_modules)}
        - Total Topics ({len(selected_topics)} topics): {', '.join(selected_topics[:40])}
        - Case Studies: {', '.join(selected_case_studies)}
        - Teacher Available Days: {available_days} days per week
        - Minimum Duration: {weeks_needed} weeks
        
        MANDATORY REQUIREMENTS:
        1. Create a weekly schedule for AT LEAST {weeks_needed} weeks covering ALL {total_modules} modules
        2. Cover Module I, II, III, IV, and V completely
        3. Allocate 3 weeks per module (total 15 weeks for 5 modules)
        4. For DAILY lesson objectives, create separate entries for EACH WEEK individually
        5. Use specific day names (Monday, Tuesday, Wednesday, Thursday, Friday) for each week
        6. Map ALL {len(selected_topics)} topics to specific days of specific weeks
        7. Integrate case studies where applicable
        8. Include teaching methods, required resources, and assessment points
        
        MODULE COVERAGE CHECKLIST (YOU MUST INCLUDE ALL):
        - Module I: Intelligent Agents (Weeks 1-3)
        - Module II: Problem Solving Agents (Weeks 4-6)
        - Module III: Game Playing and CSP (Weeks 7-9)
        - Module IV: Logical Agents (Weeks 10-12)
        - Module V: Uncertain Knowledge and Reasoning (Weeks 13-15) ✓ MUST INCLUDE
        
        FORMAT REQUIREMENTS:
        
        Weekly Schedule Format:
        Week | Module | Topics | Case Study
        
        Daily Lesson Objectives Format (IMPORTANT - Show each week separately):
        
        Week 1 (Module I - Intelligent Agents)
        Day | Module | Topic | Lesson Objectives
        Monday | Module I | [Topic] | [Objectives]
        Tuesday | Module I | [Topic] | [Objectives]
        Wednesday | Module I | [Topic] | [Objectives]
        Thursday | Module I | [Topic] | [Objectives]
        Friday | Module I | [Topic] | [Objectives]
        
        Week 2 (Module I - Intelligent Agents)
        Day | Module | Topic | Lesson Objectives
        Monday | Module I | [Topic] | [Objectives]
        Tuesday | Module I | [Topic] | [Objectives]
        ...and so on for ALL {weeks_needed} weeks
        
        CRITICAL: List daily objectives for EACH individual week (Week 1, Week 2, Week 3, etc.) up to Week {weeks_needed}.
        Use day names (Monday-Friday) for each {available_days}-day week.
        Do NOT group multiple weeks together in the daily objectives section.
        
        Make sure to cover ALL {total_modules} modules including Module V comprehensively.
        Create a complete {weeks_needed}-week semester plan with daily breakdowns for each week.
        
        Format the response as structured text with clear sections.
        """
        
        try:
            print(f"[PLANNING] Generating lesson plan for {unit_description}...")
            response = self.llama_client.make_request(prompt, max_tokens=3000)
            
            # Check if response is an error message
            if isinstance(response, str) and response.startswith("API Error:"):
                print(f"[PLANNING ERROR] {response}")
                return {"error": response}
            
            print(f"[PLANNING] Lesson plan generated successfully")
            return {
                "course_unit": unit_description,
                "modules": selected_modules,
                "detailed_plan": response,
                "total_weeks": weeks_needed,
                "total_topics": len(selected_topics)
            }
        except Exception as e:
            error_msg = f"Lesson plan generation failed: {str(e)}"
            print(f"[PLANNING ERROR] {error_msg}")
            return {"error": error_msg}

class AssessmentAgent:
    def __init__(self):
        self.llama_client = LlamaAPIClient()
    
    def generate_assessments(self, syllabus_content, preprocessed_data, assessment_unit='all', mcq_count=20, difficulty_level='medium'):
        """Generate MCQ assessments based on user configuration"""
        assessments = {}
        
        # Determine which modules/topics to include
        if assessment_unit == 'all':
            selected_topics = ', '.join(preprocessed_data['topics'][:20])
            selected_modules = ', '.join(preprocessed_data['modules'])
            unit_description = "All Modules"
        else:
            # Filter for specific module
            module_index = int(assessment_unit) - 1
            if module_index < len(preprocessed_data['modules']):
                selected_modules = preprocessed_data['modules'][module_index]
                # Get topics related to this module
                topics_per_module = len(preprocessed_data['topics']) // len(preprocessed_data['modules'])
                start_idx = module_index * topics_per_module
                end_idx = start_idx + topics_per_module
                selected_topics = ', '.join(preprocessed_data['topics'][start_idx:end_idx])
                unit_description = f"Module {assessment_unit}"
            else:
                selected_topics = ', '.join(preprocessed_data['topics'][:10])
                selected_modules = preprocessed_data['modules'][0] if preprocessed_data['modules'] else "General Topics"
                unit_description = f"Module {assessment_unit}"
        
        # Determine which difficulty levels to generate
        if difficulty_level == 'mixed':
            levels_to_generate = ['easy', 'medium', 'hard']
            mcqs_per_level = max(5, mcq_count // 3)  # Distribute MCQs across levels
        else:
            levels_to_generate = [difficulty_level]
            mcqs_per_level = mcq_count
        
        # Generate MCQ assessments for each selected difficulty level
        for level in levels_to_generate:
            num_questions = mcqs_per_level if difficulty_level == 'mixed' else mcq_count
            
            prompt = f"""
Create {num_questions} MULTIPLE CHOICE QUESTIONS (MCQs) based on the syllabus content provided below. 
Make the questions unique, slightly tricky or creative, and include possibilities for:
- Simple sums or calculations
- Conceptual twists
- Small application-based scenarios
- Analytical reasoning based on the syllabus content

SYLLABUS CONTENT:
{syllabus_content[:3000]}

Configuration:
- Unit/Module: {unit_description}
- Difficulty Level: {level.upper()}
- Number of MCQs: {num_questions}

Relevant Content from Syllabus:
- Topics to Cover: {selected_topics}
- Modules to Cover: {selected_modules}
- Case Studies: {', '.join(preprocessed_data['case_studies'][:3]) if preprocessed_data['case_studies'] else 'None'}

Requirements:
1. Generate EXACTLY {num_questions} multiple choice questions.
2. Each question must have 4 options (A, B, C, D).
3. Clearly mark the correct answer for each question.
4. Questions MUST be strictly based on the syllabus content provided above.
5. Make each question UNIQUE — do not repeat questions from previous runs.
6. Questions can involve simple sums, small problem-solving, diagrams (conceptual), or tricky wording — but should be answerable based on syllabus topics.
7. Difficulty level should be {level.upper()}.
8. Include question numbers (Q1, Q2, Q3, etc.).
9. DO NOT include topics not mentioned in the syllabus.

Format each question EXACTLY as:
Q1. [Question text]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
Correct Answer: [A/B/C/D]
Explanation: [Brief explanation]

Ensure questions are clear, engaging, slightly creative, and test understanding of the syllabus content.
"""

            
            try:
                print(f"[ASSESSMENT] Generating {level} level MCQs ({num_questions} questions)...")
                response = self.llama_client.make_request(prompt, max_tokens=1500)
                
                # Check if response is an error message
                if isinstance(response, str) and response.startswith("API Error:"):
                    print(f"[ASSESSMENT ERROR] {response}")
                    assessments[level] = response
                else:
                    print(f"[ASSESSMENT] {level} level MCQs generated successfully")
                    assessments[level] = response
            except Exception as e:
                error_msg = f"Error generating {level} assessment: {str(e)}"
                print(f"[ASSESSMENT ERROR] {error_msg}")
                assessments[level] = error_msg
        
        return assessments

class ConversationalBot:
    def __init__(self):
        self.llama_client = LlamaAPIClient()
    
    def process_feedback(self, original_content, feedback, content_type):
        prompt = f"""
        You are an AI teaching assistant. A teacher has provided feedback on their {content_type}.
        
        Original {content_type}:
        {original_content[:1000]}...  # Truncate for prompt size
        
        Teacher's Feedback:
        {feedback}
        
        Please provide specific suggestions to improve the {content_type} based on the feedback.
        Include:
        1. What changes to make
        2. Why these changes will help
        3. Specific examples or modifications
        4. Alternative approaches if applicable
        
        Keep your response practical and actionable.
        """
        
        try:
            response = self.llama_client.make_request(prompt)
            return response
        except Exception as e:
            return f"Error processing feedback: {str(e)}"
    
    def chat_response(self, message, context=""):
        # Check if it's a simple greeting
        if message.lower().strip() in ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening']:
            return "Hello! I'm your AI teaching assistant. How can I help you with your lesson planning or assessments today?"
        
        # Check if it's asking about the assistant's capabilities
        if any(word in message.lower() for word in ['what can you do', 'help', 'capabilities', 'what do you do']):
            return "I can help you with lesson planning, creating assessments, teaching strategies, and educational content. What specific topic would you like assistance with?"
        
        prompt = f"""
        You are a helpful AI teaching assistant. Answer the teacher's question directly and concisely.
        
        Teacher's Question: {message}
        
        Rules:
        - Give a direct, helpful answer to their specific question
        - Keep responses concise (2-3 sentences max for simple questions)
        - Be conversational and friendly
        - Don't provide unnecessary details unless asked
        - Focus on practical, actionable advice
        
        If they ask about lesson planning, assessments, or teaching methods, give specific, brief guidance.
        """
        
        try:
            response = self.llama_client.make_request(prompt, max_tokens=300)
            return response
        except Exception as e:
            return f"Sorry, I encountered an error. Please try again."

class DocumentGenerator:
    @staticmethod
    def generate_pdf(content, title, filename):
        doc = SimpleDocTemplate(filename, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 12))
        
        # Content
        content_lines = content.split('\n')
        for line in content_lines:
            if line.strip():
                story.append(Paragraph(line, styles['Normal']))
                story.append(Spacer(1, 6))
        
        doc.build(story)
    
    @staticmethod
    def generate_docx(content, title, filename):
        doc = Document()
        doc.add_heading(title, 0)
        
        content_lines = content.split('\n')
        for line in content_lines:
            if line.strip():
                doc.add_paragraph(line)
        
        doc.save(filename)

# Initialize components
db_manager = DatabaseManager()
text_preprocessor = TextPreprocessor()
planning_agent = PlanningAgent()
assessment_agent = AssessmentAgent()
conversational_bot = ConversationalBot()

# Helper function to parse MCQ questions from assessment content
def parse_mcq_questions(content):
    """Parse MCQ questions from generated assessment content"""
    questions = []
    lines = content.split('\n')
    current_question = None
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Remove HTML/markdown formatting (**, <strong>, <b>, etc.)
        line = re.sub(r'\*\*', '', line)  # Remove **
        line = re.sub(r'<strong>|</strong>|<b>|</b>', '', line, flags=re.IGNORECASE)  # Remove HTML tags
        
        # Match question pattern (Q1., Q2., 1., Question 1, etc.)
        if re.match(r'^(Q\d+\.|Question\s+\d+[:.)]|\d+\.)', line, re.IGNORECASE):
            # Save previous question if exists
            if current_question and len(current_question.get('options', [])) >= 2:
                questions.append(current_question)
            
            # Start new question
            question_text = re.sub(r'^(Q\d+\.|Question\s+\d+[:.)]|\d+\.)\s*', '', line, flags=re.IGNORECASE)
            current_question = {
                'question': question_text,
                'options': [],
                'correct_answer': ''
            }
        
        # Match options (A), B), C), D) - with or without space after letter
        elif current_question and re.match(r'^[A-Da-d][\).\:]', line):
            option_letter = line[0].upper()
            option_text = re.sub(r'^[A-Da-d][\).\:]\s*', '', line).strip()
            if option_text:  # Only add if there's actual text
                current_question['options'].append(option_text)
        
        # Match correct answer (various formats)
        elif current_question and re.search(r'correct\s*answer\s*[:\-]?\s*([A-Da-d])', line, re.IGNORECASE):
            match = re.search(r'correct\s*answer\s*[:\-]?\s*([A-Da-d])', line, re.IGNORECASE)
            if match:
                current_question['correct_answer'] = match.group(1).upper()
        
        # Alternative answer format: "Answer:" followed by letter
        elif current_question and re.search(r'^\s*answer\s*[:\-]\s*([A-Da-d])', line, re.IGNORECASE):
            match = re.search(r'^\s*answer\s*[:\-]\s*([A-Da-d])', line, re.IGNORECASE)
            if match:
                current_question['correct_answer'] = match.group(1).upper()
        
        i += 1
    
    # Add last question
    if current_question and len(current_question.get('options', [])) >= 2:
        # If correct answer not found, default to 'A'
        if not current_question['correct_answer']:
            current_question['correct_answer'] = 'A'
        questions.append(current_question)
    
    return questions

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_content', methods=['POST'])
def generate_content():
    try:
        syllabus_title = request.form.get('syllabus_title', 'Untitled Syllabus')
        available_days = int(request.form.get('available_days', 5))
        
        # Get course/lesson plan configuration parameters
        course_unit = request.form.get('course_unit', 'all')
        
        # Get assessment configuration parameters
        assessment_unit = request.form.get('assessment_unit', 'all')
        mcq_count = int(request.form.get('mcq_count', 20))
        difficulty_level = request.form.get('difficulty_level', 'medium')
        
        # Read the syllabus from the file - use absolute path
        syllabus_file_path = r'C:\Users\New\Downloads\pro_final\Final_Year_Project_1\processed_syllabus.txt'
        if os.path.exists(syllabus_file_path):
            with open(syllabus_file_path, 'r', encoding='utf-8') as file:
                syllabus_content = file.read()
        else:
            # Return JSON error instead of redirecting
            return jsonify({
                'success': False, 
                'error': f'Syllabus file not found at {syllabus_file_path}. Please process your syllabus first using app2.py at http://localhost:5000'
            })
        
        # Step 1: Preprocess syllabus
        preprocessed_data = text_preprocessor.preprocess_syllabus(syllabus_content)
        
        # Step 2: Save syllabus to database
        syllabus_id = db_manager.save_syllabus(syllabus_title, syllabus_content, available_days)
        
        # Step 3: Generate lesson plan for selected course unit
        lesson_plan = planning_agent.generate_weekly_timetable(
            syllabus_content, 
            preprocessed_data, 
            available_days,
            course_unit
        )
        
        # Check if lesson plan generation failed
        if 'error' in lesson_plan:
            return jsonify({
                'success': False,
                'error': lesson_plan['error']
            })
        
        # Check if lesson plan contains API error message
        if isinstance(lesson_plan.get('detailed_plan'), str) and 'API Error' in lesson_plan.get('detailed_plan', ''):
            return jsonify({
                'success': False,
                'error': lesson_plan['detailed_plan']
            })
        
        db_manager.save_lesson_plan(syllabus_id, json.dumps(lesson_plan))
        
        # Step 4: Generate MCQ assessments based on user configuration
        assessments = assessment_agent.generate_assessments(
            syllabus_content, 
            preprocessed_data,
            assessment_unit,
            mcq_count,
            difficulty_level
        )
        
        # Check if any assessment contains API errors
        for level, content in assessments.items():
            if isinstance(content, str) and 'API Error' in content:
                return jsonify({
                    'success': False,
                    'error': f'{level.capitalize()} assessment failed: {content}'
                })
        
        # Save assessments to database
        for level, content in assessments.items():
            db_manager.save_assessment(syllabus_id, level, content)
        
        return jsonify({
            'success': True,
            'syllabus_id': syllabus_id,
            'lesson_plan': lesson_plan,
            'assessments': assessments,
            'preprocessed_data': preprocessed_data,
            'course_config': {
                'unit': course_unit
            },
            'assessment_config': {
                'unit': assessment_unit,
                'mcq_count': mcq_count,
                'difficulty_level': difficulty_level
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/refine_content', methods=['POST'])
def refine_content():
    try:
        content = request.json.get('content')
        feedback = request.json.get('feedback')
        content_type = request.json.get('content_type', 'lesson plan')
        
        refined_content = conversational_bot.process_feedback(content, feedback, content_type)
        
        return jsonify({
            'success': True,
            'refined_content': refined_content
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download/<format>/<content_type>/<int:syllabus_id>')
def download_content(format, content_type, syllabus_id):
    try:
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        if content_type == 'lesson_plan':
            cursor.execute('SELECT content FROM lesson_plans WHERE syllabus_id = ?', (syllabus_id,))
            result = cursor.fetchone()
            content = json.loads(result[0]) if result else {}
            title = "Lesson Plan"
            text_content = json.dumps(content, indent=2) if isinstance(content, dict) else str(content)
        
        elif content_type == 'assessments':
            cursor.execute('SELECT difficulty_level, content FROM assessments WHERE syllabus_id = ?', (syllabus_id,))
            results = cursor.fetchall()
            assessments = {row[0]: row[1] for row in results}
            title = "Assessments"
            text_content = '\n\n'.join([f"{level.upper()} LEVEL:\n{content}" for level, content in assessments.items()])
        
        conn.close()
        
        # Generate temporary file
        temp_dir = tempfile.mkdtemp()
        filename = f"{title.replace(' ', '_')}_{syllabus_id}"
        
        if format == 'pdf':
            file_path = os.path.join(temp_dir, f"{filename}.pdf")
            DocumentGenerator.generate_pdf(text_content, title, file_path)
        
        elif format == 'docx':
            file_path = os.path.join(temp_dir, f"{filename}.docx")
            DocumentGenerator.generate_docx(text_content, title, file_path)
        
        return send_file(file_path, as_attachment=True)
    
    except Exception as e:
        flash(f'Error generating download: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/generate_questions', methods=['POST'])
def generate_questions():
    try:
        question_unit = request.form.get('question_unit', 'all')
        two_mark_count = int(request.form.get('two_mark_count', 0))
        five_mark_count = int(request.form.get('five_mark_count', 0))
        
        # Read the syllabus from the file
        syllabus_file_path = r'C:\Users\New\Downloads\pro_final\Final_Year_Project_1\processed_syllabus.txt'
        if os.path.exists(syllabus_file_path):
            with open(syllabus_file_path, 'r', encoding='utf-8') as file:
                syllabus_content = file.read()
        else:
            return jsonify({
                'success': False,
                'error': 'Syllabus file not found. Please process your syllabus first.'
            })
        
        # Preprocess syllabus
        preprocessed_data = text_preprocessor.preprocess_syllabus(syllabus_content)
        
        # Determine which modules/topics to include
        if question_unit == 'all':
            selected_topics = ', '.join(preprocessed_data['topics'][:20])
            selected_modules = ', '.join(preprocessed_data['modules'])
            unit_description = "All Modules"
        else:
            # Filter for specific module
            module_index = int(question_unit) - 1
            if module_index < len(preprocessed_data['modules']):
                selected_modules = preprocessed_data['modules'][module_index]
                # Get topics related to this module
                topics_per_module = len(preprocessed_data['topics']) // len(preprocessed_data['modules'])
                start_idx = module_index * topics_per_module
                end_idx = start_idx + topics_per_module
                selected_topics = ', '.join(preprocessed_data['topics'][start_idx:end_idx])
                unit_description = f"Module {question_unit}"
            else:
                selected_topics = ', '.join(preprocessed_data['topics'][:10])
                selected_modules = preprocessed_data['modules'][0] if preprocessed_data['modules'] else "General Topics"
                unit_description = f"Module {question_unit}"
        
        result = {}
        
        # Generate 2-mark questions
        if two_mark_count > 0:
            prompt_2mark = f"""
Create {two_mark_count} SHORT ANSWER QUESTIONS (2-Mark Questions) based on the syllabus content provided below. 
Make the questions slightly creative or “twisted” — e.g., ask in a way that requires connecting two simple ideas or rephrasing a concept — but keep them EASY to answer in 2–3 sentences.

SYLLABUS CONTENT:
{syllabus_content[:3000]}

Configuration:
- Unit/Module: {unit_description}
- Number of Questions: {two_mark_count}

Relevant Content from Syllabus:
- Topics to Cover: {selected_topics}
- Modules to Cover: {selected_modules}

Requirements:
1. Generate EXACTLY {two_mark_count} short answer questions (2 marks each).
2. Each question should be answerable in 2–3 sentences or a brief paragraph.
3. Make questions slightly creative, twisted, or rephrased — but simple to answer.
4. Focus on definitions, fundamental concepts, simple explanations, or small application scenarios.
5. Include question numbers (Q1, Q2, Q3, etc.).
6. Questions MUST be strictly based on the syllabus content provided above.
7. Avoid repeating questions from previous runs — each set should be fresh.
8. DO NOT include topics not mentioned in the syllabus.

Format each question as:
Q1. [Question text]

Q2. [Question text]

Ensure questions are clear, concise, and thought-provoking yet easy to answer.
"""

            
            try:
                two_mark_response = assessment_agent.llama_client.make_request(prompt_2mark, max_tokens=1500)
                result['two_mark_questions'] = two_mark_response
            except Exception as e:
                result['two_mark_questions'] = f"Error generating 2-mark questions: {str(e)}"
        
        # Generate 5-mark questions
        if five_mark_count > 0:
            prompt_5mark = f"""
Create {five_mark_count} DETAILED ANSWER QUESTIONS (5-Mark Questions) based on the syllabus content provided below. 
Make the questions slightly creative, with possibilities for sub-questions, simple calculations, small problem-solving tasks, or diagram-based prompts, but keep them answerable in a detailed 5-mark response.

SYLLABUS CONTENT:
{syllabus_content[:3000]}

Configuration:
- Unit/Module: {unit_description}
- Number of Questions: {five_mark_count}

Relevant Content from Syllabus:
- Topics to Cover: {selected_topics}
- Modules to Cover: {selected_modules}

Requirements:
1. Generate EXACTLY {five_mark_count} detailed answer questions (5 marks each).
2. Each question should require comprehensive explanation, reasoning, or small problem-solving steps.
3. Questions may include:
   - Sub-questions (a, b, c) based on the main topic
   - Simple numerical calculations or small examples
   - Requests for drawing a simple diagram or flowchart
   - Analytical or comparison-based questions
4. Focus on understanding, application, and critical thinking of concepts.
5. Include question numbers (Q1, Q2, Q3, etc.).
6. Questions MUST be strictly based on the syllabus content provided above.
7. Avoid repeating questions from previous runs — each set should be fresh.
8. DO NOT include topics not mentioned in the syllabus.

Format each question as:
Q1. [Detailed question text with sub-questions, sum, or diagram prompt if applicable]

Q2. [Detailed question text]

Ensure questions are clear, comprehensive, creative, and test deeper understanding of syllabus topics.
"""

            
            try:
                five_mark_response = assessment_agent.llama_client.make_request(prompt_5mark, max_tokens=1500)
                result['five_mark_questions'] = five_mark_response
            except Exception as e:
                result['five_mark_questions'] = f"Error generating 5-mark questions: {str(e)}"
        
        return jsonify({
            'success': True,
            'two_mark_questions': result.get('two_mark_questions', ''),
            'five_mark_questions': result.get('five_mark_questions', ''),
            'unit': unit_description
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/create_quiz', methods=['POST'])
def create_quiz():
    try:
        data = request.json
        assessment_content = data.get('assessment_content')
        title = data.get('title', 'Quiz')
        
        if not assessment_content:
            return jsonify({'success': False, 'error': 'No assessment content provided'})
        
        print("\n" + "="*60)
        print("CREATING QUIZ")
        print("="*60)
        print(f"Title: {title}")
        print(f"Content length: {len(assessment_content)} characters")
        print(f"Content type: {type(assessment_content)}")
        print("\nFull content (first 1500 chars):")
        print(repr(assessment_content[:1500]))
        print("\nFirst 10 lines after split:")
        lines = assessment_content.split('\n')
        for i, line in enumerate(lines[:10]):
            print(f"  Line {i}: '{line}'")
        print("="*60)
        
        # Parse questions from assessment
        questions = parse_mcq_questions(assessment_content)
        
        # Debug: Print to console
        print(f"\n✓ Parsed {len(questions)} questions")
        for idx, q in enumerate(questions[:3], 1):  # Show first 3 questions
            print(f"\nQuestion {idx}:")
            print(f"  Text: {q['question'][:80]}...")
            print(f"  Options: {len(q['options'])}")
            print(f"  Correct: {q['correct_answer']}")
        print("="*60 + "\n")
        
        if not questions:
            # Save the content to a file for debugging
            with open('debug_assessment.txt', 'w', encoding='utf-8') as f:
                f.write(assessment_content)
            print("Content saved to debug_assessment.txt for inspection")
            
            # Try to provide more helpful error message
            return jsonify({
                'success': False, 
                'error': 'No valid MCQ questions found. Please ensure the assessment contains questions in format: Q1. [question] with options A), B), C), D)'
            })
        
        # Generate unique quiz code
        quiz_code = secrets.token_urlsafe(8)
        
        # Save quiz to database
        db_manager.save_quiz(quiz_code, title, questions)
        
        # Generate quiz URL (use port 5002)
        quiz_url = f"http://localhost:5002/quiz/{quiz_code}"
        results_url = f"http://localhost:5002/quiz/{quiz_code}/results"
        
        print(f"✓ Quiz created successfully!")
        print(f"  Code: {quiz_code}")
        print(f"  Questions: {len(questions)}")
        print(f"  Quiz URL: {quiz_url}")
        print("="*60 + "\n")
        
        return jsonify({
            'success': True,
            'quiz_code': quiz_code,
            'quiz_url': quiz_url,
            'results_url': results_url,
            'question_count': len(questions)
        })
    
    except Exception as e:
        print(f"ERROR creating quiz: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/quiz/<quiz_code>')
def quiz_page(quiz_code):
    quiz_data = db_manager.get_quiz(quiz_code)
    if not quiz_data:
        return render_template('error.html', message='Quiz not found'), 404
    
    return render_template('quiz.html', 
                         quiz_code=quiz_code, 
                         title=quiz_data['title'],
                         questions=quiz_data['questions'])

@app.route('/submit_quiz/<quiz_code>', methods=['POST'])
def submit_quiz(quiz_code):
    try:
        student_name = request.form.get('student_name')
        
        # Get quiz data
        quiz_data = db_manager.get_quiz(quiz_code)
        if not quiz_data:
            return jsonify({'success': False, 'error': 'Quiz not found'})
        
        # Get student answers
        answers = {}
        score = 0
        total_questions = len(quiz_data['questions'])
        
        for i, question in enumerate(quiz_data['questions']):
            answer_key = f'question_{i}'
            student_answer = request.form.get(answer_key, '')
            answers[i] = student_answer
            
            if student_answer == question['correct_answer']:
                score += 1
        
        # Save submission
        db_manager.save_quiz_submission(quiz_code, student_name, answers, score, total_questions)
        
        return render_template('quiz_results.html',
                             student_name=student_name,
                             score=score,
                             total=total_questions,
                             percentage=round((score/total_questions)*100, 2))
    
    except Exception as e:
        return render_template('error.html', message=str(e)), 500

@app.route('/quiz/<quiz_code>/results')
def quiz_results(quiz_code):
    quiz_data = db_manager.get_quiz(quiz_code)
    if not quiz_data:
        return render_template('error.html', message='Quiz not found'), 404
    
    submissions = db_manager.get_quiz_submissions(quiz_code)
    
    return render_template('quiz_results_teacher.html',
                         title=quiz_data['title'],
                         quiz_code=quiz_code,
                         submissions=submissions)

@app.route('/test_parser', methods=['POST'])
def test_parser():
    """Debug endpoint to test MCQ parsing"""
    try:
        content = request.json.get('content', '')
        questions = parse_mcq_questions(content)
        return jsonify({
            'success': True,
            'question_count': len(questions),
            'questions': questions
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/chat', methods=['POST'])
def chat():
    try:
        message = request.json.get('message')
        context = request.json.get('context', '')
        
        response = conversational_bot.chat_response(message, context)
        
        return jsonify({
            'success': True,
            'response': response
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5001)