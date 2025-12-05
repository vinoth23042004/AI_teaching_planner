# Quiz System Guide

## Overview
The quiz system allows teachers to create online quizzes from generated MCQ assessments. Students can take quizzes via a unique link, and results are automatically calculated and displayed to teachers.

## How It Works

### For Teachers

#### 1. Generate Assessments
- Configure your course settings (course title, units, etc.)
- Select MCQ settings:
  - Assessment Unit: All Modules or specific Module
  - Number of MCQs: 5-50 questions
  - Difficulty Level: Easy, Medium, Hard, or Mixed
- Click "Generate Lesson Plan & Assessments"

#### 2. Create Quiz
- After assessments are generated, you'll see a **"Create Quiz Link"** button for each difficulty level
- Click the button to create a quiz
- A green box will appear with:
  - **Student Quiz Link**: Share this with students
  - **View Results Link**: Use this to see student submissions
  - Copy buttons for easy sharing

#### 3. View Results
- Click "View Results" or use the results link
- See real-time dashboard with:
  - Total submissions
  - Average score
  - Pass rate
  - Individual student scores
- Results auto-refresh every 30 seconds

### For Students

#### 1. Access Quiz
- Open the quiz link provided by teacher
- Enter your full name

#### 2. Answer Questions
- Read each question carefully
- Select one option (A, B, C, or D) for each question
- All questions must be answered before submission

#### 3. Submit Quiz
- Click "Submit Quiz"
- Confirm submission (answers cannot be changed after)
- View your results immediately:
  - Score (correct answers)
  - Percentage
  - Performance message

## Features

### Teacher Features
- ✅ Create unlimited quizzes
- ✅ Unique quiz codes for each quiz
- ✅ Real-time results tracking
- ✅ Automatic grading
- ✅ Statistics dashboard
- ✅ Copy quiz links easily

### Student Features
- ✅ Simple, clean interface
- ✅ No account needed
- ✅ Instant results
- ✅ Mobile-friendly
- ✅ Answer validation

## Database Structure

### New Tables
1. **quizzes**: Stores quiz information
   - quiz_code (unique identifier)
   - title
   - questions (JSON)
   - created_at

2. **quiz_submissions**: Stores student responses
   - quiz_code
   - student_name
   - answers (JSON)
   - score
   - total_questions
   - submitted_at

## URLs

- Main App: `http://localhost:5001`
- Quiz Page: `http://localhost:5001/quiz/<quiz_code>`
- Results (Teacher): `http://localhost:5001/quiz/<quiz_code>/results`

## Tips

### For Teachers
- Create separate quizzes for different difficulty levels
- Share the quiz link via email, LMS, or messaging apps
- Bookmark the results page for easy access
- Check results regularly (auto-refreshes every 30 seconds)

### For Students
- Make sure you enter your correct name
- Answer all questions before submitting
- Review your answers before final submission
- You cannot retake the quiz once submitted

## Troubleshooting

**Quiz not found**: Make sure you're using the correct quiz link

**Cannot submit**: Ensure all questions are answered and name is entered

**Results not showing**: Wait a few seconds and refresh the page

**Quiz link not working**: Check that the Flask app is running on port 5001

## Technical Details

### Question Parsing
- Automatically extracts MCQs from assessment content
- Recognizes format: Q1., Q2., etc.
- Extracts options: A), B), C), D)
- Identifies correct answers from assessment

### Grading
- Automatic comparison of student answers with correct answers
- Score = number of correct answers
- Percentage = (score / total_questions) × 100

### Security
- Quiz codes are generated using cryptographic random tokens
- Each quiz has a unique 8-character code
- No authentication required for students (teacher-controlled access)
