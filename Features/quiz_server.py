from flask import Flask, render_template, request, jsonify
import sqlite3
import json

app = Flask(__name__)

class QuizDatabase:
    def __init__(self):
        self.db_path = 'academic_content.db'
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database with required tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create quizzes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_code TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                questions TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create quiz_submissions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_code TEXT NOT NULL,
                student_name TEXT NOT NULL,
                answers TEXT NOT NULL,
                score INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quiz_code) REFERENCES quizzes (quiz_code)
            )
        ''')
        
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

db = QuizDatabase()

@app.route('/')
def home():
    # Get list of available quizzes
    quizzes = []
    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT quiz_code, title, created_at FROM quizzes ORDER BY created_at DESC LIMIT 10')
        quizzes = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"Error fetching quizzes: {e}")
    
    quiz_list_html = ""
    if quizzes:
        quiz_list_html = "<h3>📋 Available Quizzes:</h3><ul style='text-align: left; list-style: none; padding: 0;'>"
        for quiz_code, title, created_at in quizzes:
            quiz_list_html += f"""
                <li style='margin: 15px 0; padding: 15px; background: #f5f5f5; border-radius: 8px;'>
                    <strong>{title}</strong><br>
                    <small>Created: {created_at}</small><br>
                    <a href='/quiz/{quiz_code}' style='color: #4facfe; text-decoration: none;'>📝 Take Quiz</a> | 
                    <a href='/quiz/{quiz_code}/results' style='color: #28a745; text-decoration: none;'>📊 View Results</a><br>
                    <code style='background: #e0e0e0; padding: 2px 8px; border-radius: 4px; font-size: 12px;'>Code: {quiz_code}</code>
                </li>
            """
        quiz_list_html += "</ul>"
    else:
        quiz_list_html = """
            <div style='background: #fff3cd; padding: 20px; border-radius: 8px; margin-top: 20px; border-left: 4px solid #ffc107;'>
                <p><strong>⚠️ No quizzes available yet</strong></p>
                <p style='font-size: 14px;'>Create a quiz from the main app at <a href='http://localhost:5001' target='_blank'>http://localhost:5001</a></p>
            </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Quiz Server</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }}
            h1 {{ color: #333; margin-bottom: 10px; }}
            h3 {{ color: #555; margin-top: 30px; }}
            p {{ color: #666; font-size: 16px; }}
            .info {{
                background: #e3f2fd;
                padding: 20px;
                border-radius: 8px;
                margin-top: 20px;
                text-align: left;
            }}
            .info strong {{ color: #1976d2; }}
            code {{
                background: #f5f5f5;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: monospace;
            }}
            a {{ color: #4facfe; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎓 Quiz Server</h1>
            <p style='color: #28a745; font-weight: bold;'>✅ Server is running on port 5002</p>
            
            <div class="info">
                <p><strong>📖 How to use:</strong></p>
                <ol style='line-height: 1.8;'>
                    <li>Create assessments on the <a href='http://localhost:5001' target='_blank'>Main App (Port 5001)</a></li>
                    <li>Click "Create Quiz Link" button</li>
                    <li>Share the quiz link with students</li>
                    <li>View results using the teacher results link</li>
                </ol>
                <p><strong>📝 Quiz URL Format:</strong></p>
                <p><code>http://localhost:5002/quiz/[your-quiz-code]</code></p>
                <p><strong>📊 Results URL Format:</strong></p>
                <p><code>http://localhost:5002/quiz/[your-quiz-code]/results</code></p>
            </div>
            
            {quiz_list_html}
        </div>
    </body>
    </html>
    """

@app.route('/quiz/<quiz_code>')
def quiz_page(quiz_code):
    quiz_data = db.get_quiz(quiz_code)
    if not quiz_data:
        return render_template('error.html', message='Quiz not found'), 404
    
    # Add enumeration to questions for easier template rendering
    enumerated_questions = []
    for i, question in enumerate(quiz_data['questions']):
        enumerated_options = []
        for j, option in enumerate(question['options']):
            enumerated_options.append({
                'index': j,
                'letter': chr(65 + j),  # A, B, C, D
                'text': option
            })
        
        enumerated_questions.append({
            'index': i,
            'number': i + 1,
            'question': question['question'],
            'options': enumerated_options
        })
    
    return render_template('quiz.html', 
                         quiz_code=quiz_code, 
                         title=quiz_data['title'],
                         questions=enumerated_questions)

@app.route('/submit_quiz/<quiz_code>', methods=['POST'])
def submit_quiz(quiz_code):
    try:
        student_name = request.form.get('student_name')
        
        # Get quiz data
        quiz_data = db.get_quiz(quiz_code)
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
        db.save_quiz_submission(quiz_code, student_name, answers, score, total_questions)
        
        return render_template('quiz_results.html',
                             student_name=student_name,
                             score=score,
                             total=total_questions,
                             percentage=round((score/total_questions)*100, 2))
    
    except Exception as e:
        return render_template('error.html', message=str(e)), 500

@app.route('/quiz/<quiz_code>/results')
def quiz_results(quiz_code):
    quiz_data = db.get_quiz(quiz_code)
    if not quiz_data:
        return render_template('error.html', message='Quiz not found'), 404
    
    submissions = db.get_quiz_submissions(quiz_code)
    
    return render_template('quiz_results_teacher.html',
                         title=quiz_data['title'],
                         quiz_code=quiz_code,
                         submissions=submissions)

if __name__ == '__main__':
    print("=" * 60)
    print("Quiz Server Starting on Port 5002")
    print("=" * 60)
    print("Student Quiz URL: http://localhost:5002/quiz/[quiz-code]")
    print("Teacher Results URL: http://localhost:5002/quiz/[quiz-code]/results")
    print("=" * 60)
    app.run(debug=True, port=5002)
