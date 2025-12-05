import re

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
        
        # Match question pattern (Q1., Q2., 1., etc.)
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

# Test with actual debug file content
with open('debug_assessment.txt', 'r', encoding='utf-8') as f:
    test_content = f.read()

questions = parse_mcq_questions(test_content)
print(f"Found {len(questions)} questions\n")

for i, q in enumerate(questions[:5], 1):
    print(f"Question {i}:")
    print(f"  Text: {q['question']}")
    print(f"  Options ({len(q['options'])}):")
    for j, opt in enumerate(q['options']):
        print(f"    {chr(65+j)}) {opt}")
    print(f"  Correct Answer: {q['correct_answer']}")
    print()
