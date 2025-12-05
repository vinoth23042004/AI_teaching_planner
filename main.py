from flask import Flask, render_template, request, jsonify, send_file
import re
import requests
import json
import os
from werkzeug.utils import secure_filename
import tempfile
from datetime import datetime

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# File to store processed content
OUTPUT_FILE = r"C:\Users\New\Downloads\pro_final\Final_Year_Project_1\processed_syllabus.txt"

class UniversalSyllabusProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://integrate.api.nvidia.com/v1"
        
    def clean_input(self, text):
        """Basic text cleaning while preserving structure"""
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()
        return text
    
    def ai_structure_content(self, content):
        """Use Llama AI to intelligently structure any syllabus format"""
        
        system_prompt = """
You are an expert at converting unstructured syllabus content into clean, organized format. 

RULES:
1. Extract ALL modules/units/chapters/sections and number them as MODULE I, MODULE II, etc.
2. For each module, extract individual topics as single bullet points (no subtopics)
3. Identify and separate case studies
4. Clean up redundant text and make topics concise but descriptive
5. Maintain the logical flow and grouping of topics
6. Remove page numbers, credits, and other metadata

OUTPUT FORMAT:
*MODULE I – [MODULE TITLE]*
* Topic 1
* Topic 2  
* Topic 3
*Case Study:* Description (if any)

*MODULE II – [MODULE TITLE]*
* Topic 1
* Topic 2
*Case Studies:* 
* Study 1
* Study 2

Continue this pattern for all modules found.
"""

        user_prompt = f"""
Convert this syllabus content into the structured format:

{content}

Make sure to:
- Extract ALL topics as individual bullet points
- Group related topics under appropriate modules
- Clean up any messy formatting
- Identify case studies separately
- Make topic names clear and descriptive
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "meta/llama-3.1-8b-instruct",
            "messages": [
                {
                    "role": "system", 
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 2048
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()
            formatted_content = result['choices'][0]['message']['content'].strip()
            return self.post_process_output(formatted_content)
            
        except Exception as e:
            print(f"API Error: {e}")
            return self.fallback_processing(content)
    
    def post_process_output(self, ai_output):
        """Clean up AI output to ensure consistent formatting"""
        lines = ai_output.split('\n')
        processed_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                processed_lines.append('')
                continue
                
            if re.match(r'\*\*MODULE\s+[IVX]+', line, re.IGNORECASE):
                processed_lines.append(line)
            elif re.match(r'MODULE\s+[IVX]+', line, re.IGNORECASE):
                processed_lines.append(f"{line}")
            elif line.startswith('*') and not line.startswith('**'):
                processed_lines.append(line)
            elif line.startswith('-') or line.startswith('•'):
                processed_lines.append(f"* {line[1:].strip()}")
            elif 'case study' in line.lower() and not line.startswith('*'):
                processed_lines.append(f"*{line}*")
            else:
                if len(line) > 10 and not line.startswith('*') and not line.endswith('*'):
                    if any(keyword in line.lower() for keyword in ['regression', 'algorithm', 'method', 'analysis', 'learning', 'network', 'tree', 'classification']):
                        processed_lines.append(f"* {line}")
                    else:
                        processed_lines.append(line)
                else:
                    processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    def fallback_processing(self, content):
        """Rule-based processing when AI fails"""
        lines = content.split('\n')
        processed = []
        module_counter = 1
        romans = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if re.search(r'(module|unit|chapter|section|part)\s*[–\-—]?\s*[IVX\d]+', line, re.IGNORECASE):
                title_match = re.search(r'(module|unit|chapter|section|part)\s*[–\-—]?\s*[IVX\d]+[:\s](.+?)(?:\d+\s*$|$)', line, re.IGNORECASE)
                if title_match:
                    title = title_match.group(2).strip()
                    roman = romans[module_counter - 1] if module_counter <= len(romans) else str(module_counter)
                    processed.append(f"\n*MODULE {roman} – {title.upper()}*")
                    module_counter += 1
                continue
            
            if 'case study' in line.lower():
                case_study_text = re.sub(r'case study[:\s]*', '', line, flags=re.IGNORECASE).strip()
                processed.append(f"*Case Study:* {case_study_text}")
                continue
            
            if len(line) > 5:
                topics = re.split(r'[,;]\s+', line)
                for topic in topics:
                    topic = topic.strip()
                    if len(topic) > 3:
                        topic = re.sub(r'^\w+\s*:', '', topic)
                        topic = topic.strip()
                        if topic:
                            processed.append(f"* {topic}")
        
        return '\n'.join(processed)
    
    def process_any_format(self, raw_text):
        """Main processing function"""
        cleaned_text = self.clean_input(raw_text)
        structured_output = self.ai_structure_content(cleaned_text)
        return structured_output

    def save_to_file(self, content, filename=OUTPUT_FILE):
        """Save processed content to file, overwriting existing content"""
        try:
            # Add timestamp header
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            header = f"=== Processed Syllabus - {timestamp} ===\n\n"
            
            # Write to file (overwrites existing content)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(header + content)
            
            print(f"✅ Content saved to: {filename}")
            return True
        except Exception as e:
            print(f"❌ Error saving to file: {e}")
            return False

# Initialize processor with API key
API_KEY = "PASTE_YOUR_NVIDIA_API_KEY_HERE"   # model = meta/llama3.1-8b-instruct
processor = UniversalSyllabusProcessor(API_KEY)

@app.route('/')
def index():
    """Main page with input form"""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Universal Syllabus Processor</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.15);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 40px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }

        .header::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            animation: float 6s ease-in-out infinite;
        }

        @keyframes float {
            0%, 100% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-20px) rotate(180deg); }
        }

        .header h1 {
            font-size: 3rem;
            margin-bottom: 15px;
            font-weight: 700;
            position: relative;
            z-index: 1;
        }

        .header p {
            font-size: 1.2rem;
            opacity: 0.95;
            position: relative;
            z-index: 1;
        }

        .main-content {
            padding: 40px;
        }

        .feature-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }

        .feature-card {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 25px;
            border-radius: 15px;
            border-left: 5px solid #4facfe;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .feature-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.1);
        }

        .feature-card h3 {
            color: #2c3e50;
            margin-bottom: 15px;
            font-size: 1.3rem;
        }

        .feature-card p {
            color: #6c757d;
            line-height: 1.6;
        }

        .form-section {
            background: #f8f9fa;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
        }

        .form-group {
            margin-bottom: 25px;
        }

        .form-group label {
            display: block;
            margin-bottom: 10px;
            font-weight: 600;
            color: #495057;
            font-size: 1.1rem;
        }

        .form-group textarea {
            width: 100%;
            min-height: 300px;
            padding: 20px;
            border: 2px solid #dee2e6;
            border-radius: 12px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            resize: vertical;
            box-sizing: border-box;
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
        }

        .form-group textarea:focus {
            outline: none;
            border-color: #4facfe;
            box-shadow: 0 0 0 3px rgba(79, 172, 254, 0.1);
        }

        .file-upload-area {
            border: 3px dashed #dee2e6;
            border-radius: 12px;
            padding: 30px;
            text-align: center;
            background: #f8f9fa;
            transition: all 0.3s ease;
            cursor: pointer;
        }

        .file-upload-area:hover {
            border-color: #4facfe;
            background: #e3f2fd;
        }

        .file-upload-area.dragover {
            border-color: #4facfe;
            background: #e3f2fd;
            transform: scale(1.02);
        }

        .file-upload-area input[type="file"] {
            display: none;
        }

        .file-upload-text {
            color: #6c757d;
            font-size: 1.1rem;
        }

        .file-upload-text i {
            font-size: 2rem;
            margin-bottom: 10px;
            display: block;
            color: #4facfe;
        }

        .button-group {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 30px;
            flex-wrap: wrap;
        }

        .btn {
            padding: 15px 30px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 10px;
            text-decoration: none;
        }

        .btn-primary {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 25px rgba(79, 172, 254, 0.4);
        }

        .btn-secondary {
            background: #6c757d;
            color: white;
        }

        .btn-secondary:hover {
            background: #5a6268;
            transform: translateY(-3px);
        }

        .btn-success {
            background: #28a745;
            color: white;
        }

        .btn-success:hover {
            background: #218838;
            transform: translateY(-3px);
        }

        .btn-info {
            background: #17a2b8;
            color: white;
        }

        .btn-info:hover {
            background: #138496;
            transform: translateY(-3px);
        }

        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none !important;
        }

        .loading {
            display: none;
            text-align: center;
            padding: 40px;
            background: #f8f9fa;
            border-radius: 15px;
            margin: 20px 0;
        }

        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #4facfe;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin-bottom: 15px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .output-section {
            margin-top: 30px;
            padding: 30px;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 15px;
            display: none;
            animation: slideIn 0.5s ease;
        }

        @keyframes slideIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .output-content {
            background: white;
            padding: 25px;
            border-radius: 12px;
            font-family: 'Courier New', monospace;
            white-space: pre-wrap;
            border: 1px solid #dee2e6;
            max-height: 500px;
            overflow-y: auto;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }

        .file-status {
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
            color: #155724;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            display: none;
            border-left: 5px solid #28a745;
        }

        .example {
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 30px;
            border-left: 5px solid #2196f3;
        }

        .example h4 {
            color: #1976d2;
            margin-bottom: 15px;
            font-size: 1.2rem;
        }

        .example pre {
            background: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
            overflow-x: auto;
            border: 1px solid #e3f2fd;
        }

        .action-buttons {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 20px;
            flex-wrap: wrap;
        }

        .progress-bar {
            width: 100%;
            height: 6px;
            background: #e9ecef;
            border-radius: 3px;
            overflow: hidden;
            margin: 20px 0;
            display: none;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #4facfe, #00f2fe);
            width: 0%;
            transition: width 0.3s ease;
            animation: shimmer 2s infinite;
        }

        @keyframes shimmer {
            0% { background-position: -200px 0; }
            100% { background-position: calc(200px + 100%) 0; }
        }

        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 10px;
            color: white;
            font-weight: 600;
            z-index: 1000;
            transform: translateX(400px);
            transition: transform 0.3s ease;
        }

        .notification.show {
            transform: translateX(0);
        }

        .notification.success {
            background: linear-gradient(135deg, #28a745, #20c997);
        }

        .notification.error {
            background: linear-gradient(135deg, #dc3545, #e74c3c);
        }

        @media (max-width: 768px) {
            .header h1 {
                font-size: 2rem;
            }
            
            .main-content {
                padding: 20px;
            }
            
            .button-group {
                flex-direction: column;
                align-items: center;
            }
            
            .btn {
                width: 100%;
                max-width: 300px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-graduation-cap"></i> Universal Syllabus Processor</h1>
            <p>Transform any messy syllabus into clean, organized content with AI-powered processing</p>
        </div>

        <div class="main-content">
            <div class="feature-cards">
                <div class="feature-card">
                    <h3><i class="fas fa-magic"></i> AI-Powered Processing</h3>
                    <p>Uses Meta Llama 3.1 8B to intelligently structure and organize your syllabus content with advanced natural language processing.</p>
                </div>
                <div class="feature-card">
                    <h3><i class="fas fa-file-alt"></i> Multiple Formats</h3>
                    <p>Supports various input formats including text files, documents, and direct text input. Automatically detects and processes different syllabus structures.</p>
                </div>
                <div class="feature-card">
                    <h3><i class="fas fa-download"></i> Instant Export</h3>
                    <p>Download your processed content in multiple formats. Content is automatically saved to processed_syllabus.txt for further use in the main application.</p>
                </div>
            </div>

            <div class="example">
                <h4><i class="fas fa-lightbulb"></i> Example Transformation</h4>
                <pre><strong>Input:</strong>
MODULE–I: INTRODUCTION 9
Review of Linear Algebra for Machine Learning. Introduction and motivation...
Case Study: Stock Price Prediction

<strong>Output:</strong>
*MODULE I – INTRODUCTION*
* Linear Algebra for Machine Learning
* Introduction and Motivation for Machine Learning
*Case Study:* Stock Price Prediction</pre>
            </div>

            <div class="form-section">
                <form id="syllabusForm">
                    <div class="form-group">
                        <label for="textInput"><i class="fas fa-edit"></i> Paste Your Syllabus Content</label>
                        <textarea id="textInput" name="content" placeholder="Paste your syllabus content here... any format works! The AI will automatically detect and structure it properly."></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label><i class="fas fa-upload"></i> Or Upload a File</label>
                        <div class="file-upload-area" onclick="document.getElementById('fileInput').click()">
                            <input type="file" id="fileInput" name="file" accept=".txt,.doc,.docx" onchange="handleFileUpload(this)">
                            <div class="file-upload-text">
                                <i class="fas fa-cloud-upload-alt"></i>
                                <div>Click to upload or drag and drop</div>
                                <small>Supports .txt, .doc, .docx files</small>
                            </div>
                        </div>
                    </div>
                    
                    <div class="button-group">
                        <button type="submit" class="btn btn-primary">
                            <i class="fas fa-rocket"></i> Process Syllabus
                        </button>
                        <button type="button" class="btn btn-secondary" onclick="clearAll()">
                            <i class="fas fa-trash"></i> Clear All
                        </button>
                    </div>
                </form>
            </div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <h3>Processing your syllabus with AI...</h3>
                <p>This may take a few moments. Please wait.</p>
                <div class="progress-bar">
                    <div class="progress-fill"></div>
                </div>
            </div>
            
            <div class="output-section" id="outputSection">
                <h3><i class="fas fa-check-circle"></i> Formatted Output</h3>
                <div class="output-content" id="outputContent"></div>
                <div class="file-status" id="fileStatus">
                    <i class="fas fa-check"></i> Content successfully saved to processed_syllabus.txt
                </div>
                <div class="action-buttons">
                    <button class="btn btn-success" onclick="downloadOutput()">
                        <i class="fas fa-download"></i> Download as TXT
                    </button>
                    <button class="btn btn-info" onclick="viewSavedFile()">
                        <i class="fas fa-eye"></i> View in Main App
                    </button>
                    <button class="btn btn-info" onclick="window.open('http://localhost:9000', '_blank');">
    Dashboard
</button>


                </div>
            </div>
        </div>
    </div>

    <div id="notification" class="notification"></div>

    <script>
        let processedOutput = '';
        
        function showNotification(message, type = 'success') {
            const notification = document.getElementById('notification');
            notification.textContent = message;
            notification.className = `notification ${type}`;
            notification.classList.add('show');
            
            setTimeout(() => {
                notification.classList.remove('show');
            }, 3000);
        }
        
        function handleFileUpload(input) {
            const file = input.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    document.getElementById('textInput').value = e.target.result;
                    showNotification(`File "${file.name}" loaded successfully!`, 'success');
                };
                reader.readAsText(file);
            }
        }
        
        function clearAll() {
            document.getElementById('textInput').value = '';
            document.getElementById('fileInput').value = '';
            document.getElementById('outputSection').style.display = 'none';
            document.getElementById('fileStatus').style.display = 'none';
            processedOutput = '';
            showNotification('All content cleared!', 'success');
        }
        
        function downloadOutput() {
            if (!processedOutput) return;
            
            const blob = new Blob([processedOutput], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `formatted_syllabus_${new Date().toISOString().slice(0,10)}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showNotification('File downloaded successfully!', 'success');
        }
        
        function viewSavedFile() {
            // Redirect to the main app (app.py) on port 5001
            window.open('http://localhost:5001', '_blank');
        }
        
        // Drag and drop functionality
        const fileUploadArea = document.querySelector('.file-upload-area');
        
        fileUploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            fileUploadArea.classList.add('dragover');
        });
        
        fileUploadArea.addEventListener('dragleave', () => {
            fileUploadArea.classList.remove('dragover');
        });
        
        fileUploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            fileUploadArea.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                const file = files[0];
                if (file.type.startsWith('text/') || file.name.endsWith('.txt')) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        document.getElementById('textInput').value = e.target.result;
                        showNotification(`File "${file.name}" loaded successfully!`, 'success');
                    };
                    reader.readAsText(file);
                } else {
                    showNotification('Please upload a text file (.txt)', 'error');
                }
            }
        });
        
        document.getElementById('syllabusForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const content = document.getElementById('textInput').value.trim();
            if (!content) {
                showNotification('Please enter some syllabus content!', 'error');
                return;
            }
            
            // Show loading
            document.getElementById('loading').style.display = 'block';
            document.getElementById('outputSection').style.display = 'none';
            document.querySelector('button[type="submit"]').disabled = true;
            
            // Animate progress bar
            const progressBar = document.querySelector('.progress-bar');
            const progressFill = document.querySelector('.progress-fill');
            progressBar.style.display = 'block';
            
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += Math.random() * 15;
                if (progress > 90) progress = 90;
                progressFill.style.width = progress + '%';
            }, 200);
            
            try {
                const response = await fetch('/process', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ content: content })
                });
                
                const data = await response.json();
                
                clearInterval(progressInterval);
                progressFill.style.width = '100%';
                
                setTimeout(() => {
                    if (data.success) {
                        processedOutput = data.result;
                        document.getElementById('outputContent').textContent = data.result;
                        document.getElementById('outputSection').style.display = 'block';
                        
                        if (data.file_saved) {
                            document.getElementById('fileStatus').style.display = 'block';
                        }
                        
                        showNotification('Syllabus processed successfully!', 'success');
                    } else {
                        showNotification('Error: ' + data.error, 'error');
                    }
                }, 500);
                
            } catch (error) {
                clearInterval(progressInterval);
                showNotification('Network error: ' + error.message, 'error');
            } finally {
                setTimeout(() => {
                    document.getElementById('loading').style.display = 'none';
                    document.querySelector('button[type="submit"]').disabled = false;
                    progressBar.style.display = 'none';
                    progressFill.style.width = '0%';
                }, 1000);
            }
        });
    </script>
</body>
</html>
    '''

@app.route('/process', methods=['POST'])
def process_syllabus():
    """Process the syllabus content via AJAX"""
    try:
        data = request.get_json()
        content = data.get('content', '').strip()
        
        if not content:
            return jsonify({'success': False, 'error': 'No content provided'})
        
        # Process the content
        result = processor.process_any_format(content)
        
        # Save to file (overwrites existing content)
        file_saved = processor.save_to_file(result)
        
        return jsonify({
            'success': True, 
            'result': result,
            'file_saved': file_saved,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/view-file')
def view_saved_file():
    """View the saved processed content"""
    try:
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Return as HTML with proper formatting
            return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Saved Processed Syllabus</title>
                <style>
                    body {{ font-family: 'Courier New', monospace; padding: 20px; background: #f5f5f5; }}
                    .container {{ background: white; padding: 20px; border-radius: 8px; max-width: 1000px; margin: 0 auto; }}
                    pre {{ white-space: pre-wrap; line-height: 1.5; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>📄 Saved Processed Syllabus</h2>
                    <pre>{content}</pre>
                </div>
            </body>
            </html>
            '''
        else:
            return "<h3>No saved file found. Process some content first!</h3>"
    except Exception as e:
        return f"<h3>Error reading file: {str(e)}</h3>"

@app.route('/download')
def download_result():
    """Download the processed result as a text file"""
    content = request.args.get('content', '')
    if not content:
        return "No content to download", 400
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    temp_file.write(content)
    temp_file.close()
    
    filename = f"formatted_syllabus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    return send_file(
        temp_file.name,
        as_attachment=True,
        download_name=filename,
        mimetype='text/plain'
    )

@app.route('/download-saved')
def download_saved_file():
    """Download the saved processed file"""
    try:
        if os.path.exists(OUTPUT_FILE):
            return send_file(
                OUTPUT_FILE,
                as_attachment=True,
                download_name=f"processed_syllabus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mimetype='text/plain'
            )
        else:
            return "No saved file found", 404
    except Exception as e:
        return f"Error downloading file: {str(e)}", 500

@app.route('/api/process', methods=['POST'])
def api_process():
    """API endpoint for external access"""
    try:
        if request.is_json:
            data = request.get_json()
            content = data.get('content', '')
        else:
            content = request.form.get('content', '')
        
        if not content.strip():
            return jsonify({'error': 'No content provided'}), 400
        
        result = processor.process_any_format(content)
        
        # Save to file
        file_saved = processor.save_to_file(result)
        
        return jsonify({
            'success': True,
            'formatted_content': result,
            'file_saved': file_saved,
            'file_location': OUTPUT_FILE if file_saved else None,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def cleanup_on_startup():
    """Clean up old content on app startup"""
    if os.path.exists(OUTPUT_FILE):
        print(f"🗑️ Clearing previous content from {OUTPUT_FILE}")
        try:
            os.remove(OUTPUT_FILE)
            print("✅ Previous file cleared successfully")
        except Exception as e:
            print(f"⚠️ Warning: Could not remove old file: {e}")

if __name__ == '__main__':
    print("🚀 Starting Universal Syllabus Processor Flask App...")
    print("📱 Open your browser and go to: http://localhost:5000")
    print("🔗 API endpoint available at: http://localhost:5000/api/process")
    print(f"📄 Processed content will be saved to: {OUTPUT_FILE}")
    
    # Clean up any existing output file on startup - COMMENTED OUT to preserve file
    # cleanup_on_startup()
    
    app.run(debug=True, host='0.0.0.0', port=5000)