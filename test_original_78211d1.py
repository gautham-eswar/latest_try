#!/usr/bin/env python3
"""
Test script to validate PDF generation using the approach from commit 78211d1.
This script tests the original approach where OpenAI generates the LaTeX directly.
"""

import os
import json
import tempfile
import subprocess
import sys
import re
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables (for OpenAI API key)
load_dotenv()

# Create a simple dummy resume data structure
DUMMY_RESUME_DATA = {
    "personal_info": {
        "name": "Jane Smith",
        "email": "jane.smith@example.com",
        "phone": "+1 (555) 123-4567",
        "location": "San Francisco, CA",
        "linkedin": "linkedin.com/in/janesmith",
        "github": "github.com/janesmith"
    },
    "summary": "Experienced software engineer with expertise in Python, JavaScript, and cloud technologies.",
    "experience": [
        {
            "title": "Senior Software Engineer",
            "company": "Tech Solutions Inc.",
            "location": "San Francisco, CA",
            "start_date": "2020-01",
            "end_date": "Present",
            "description": "Lead development of cloud-based applications using Python and AWS.",
            "achievements": [
                "Reduced system latency by 40% through architecture improvements",
                "Led team of 5 engineers in delivering major platform update"
            ]
        },
        {
            "title": "Software Engineer",
            "company": "WebDev Co",
            "location": "Oakland, CA",
            "start_date": "2017-03",
            "end_date": "2019-12",
            "description": "Developed and maintained web applications using JavaScript and Node.js.",
            "achievements": [
                "Implemented responsive design patterns that improved mobile user experience",
                "Created automated testing framework that caught 25% more bugs before release"
            ]
        }
    ],
    "education": [
        {
            "institution": "University of California, Berkeley",
            "location": "Berkeley, CA",
            "degree": "Bachelor of Science",
            "specialization": "Computer Science",
            "start_date": "2013",
            "end_date": "2017",
            "gpa": "3.8",
            "honors": "Magna Cum Laude"
        }
    ],
    "skills": {
        "technical": ["Python", "JavaScript", "React", "Node.js", "AWS", "Docker", "PostgreSQL"],
        "soft": ["Leadership", "Communication", "Problem Solving"]
    },
    "projects": [
        {
            "name": "Cloud Monitoring Tool",
            "description": "Developed a tool for monitoring AWS resources in real-time.",
            "url": "github.com/janesmith/cloud-monitor",
            "technologies": ["Python", "AWS SDK", "Flask"],
            "achievements": ["Used by 500+ developers", "Featured in AWS blog"]
        }
    ],
    "certifications": [
        {
            "name": "AWS Certified Solutions Architect",
            "issuer": "Amazon Web Services",
            "date": "2021-06"
        }
    ]
}

def call_openai_api(system_prompt, user_prompt, max_retries=3):
    """Call OpenAI API with retry logic and proper error handling."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("OPENAI_API_KEY environment variable is not set. Cannot proceed without API key.")
        sys.exit(1)
    
    base_url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.5
    }
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Making OpenAI API request (attempt {attempt}/{max_retries})")
            response = requests.post(base_url, headers=headers, json=data, timeout=30)
            print(f"OpenAI API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return content
            else:
                print(f"API error: {response.status_code}, {response.text}")
                if attempt == max_retries:
                    raise Exception(f"Failed to call OpenAI API after {max_retries} attempts: {response.text}")
        except Exception as e:
            print(f"Error in attempt {attempt}: {str(e)}")
            if attempt == max_retries:
                raise Exception(f"Failed to call OpenAI API after {max_retries} attempts: {str(e)}")
    
    return None  # Should not reach here due to exception in loop

def generate_latex_resume(resume_data):
    """Generate LaTeX resume from structured data - THIS IS THE ORIGINAL APPROACH FROM COMMIT 78211d1"""
    system_prompt = "You are a LaTeX resume formatting assistant."
    user_prompt = f"""
    Generate a professional LaTeX resume from this data:
    
    {json.dumps(resume_data, indent=2)}
    
    Format your response as a complete LaTeX document using modern formatting.
    Use the article class with appropriate margins.
    Don't include the json input in your response.
    """
    
    result = call_openai_api(system_prompt, user_prompt)
    
    # Extract LaTeX from the result (might be wrapped in markdown code blocks)
    latex_match = re.search(r'```(?:latex)?\s*(.*?)```', result, re.DOTALL)
    latex_content = latex_match.group(1) if latex_match else result
    
    # Ensure it's a proper LaTeX document
    if not latex_content.strip().startswith('\\documentclass'):
        latex_content = f"""\\documentclass[11pt,letterpaper]{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{enumitem}}
\\usepackage{{hyperref}}

\\begin{{document}}
{latex_content}
\\end{{document}}"""
    
    return latex_content

def save_latex_to_file(latex_content, file_path):
    """Save LaTeX content to a file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(latex_content)
    print(f"LaTeX content saved to {file_path}")
    return file_path

def compile_latex_to_pdf(tex_file_path):
    """Compile a LaTeX file to PDF using pdflatex."""
    output_dir = os.path.dirname(tex_file_path)
    
    try:
        # Run pdflatex command
        cmd = [
            "pdflatex",
            "-interaction=nonstopmode",
            f"-output-directory={output_dir}",
            tex_file_path
        ]
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        # Save output for debugging
        output_log_path = f"{tex_file_path}.log.txt"
        with open(output_log_path, 'w', encoding='utf-8') as f:
            f.write(result.stdout)
            f.write("\n\n" + "="*50 + " STDERR " + "="*50 + "\n\n")
            f.write(result.stderr)
        print(f"Compilation log saved to {output_log_path}")
        
        if result.returncode != 0:
            print("Error during PDF generation:")
            print(result.stderr or result.stdout)
            return None
        
        # Get PDF path from TeX path
        pdf_path = tex_file_path.replace('.tex', '.pdf')
        
        if os.path.exists(pdf_path):
            print(f"PDF successfully generated: {pdf_path}")
            return pdf_path
        else:
            print(f"PDF generation failed, no file found at {pdf_path}")
            return None
    
    except Exception as e:
        print(f"Error compiling LaTeX to PDF: {e}")
        return None

def main():
    """Main test function."""
    print("\n=== Testing Original 78211d1 Resume PDF Generation ===\n")
    print("This test uses the original approach from commit 78211d1, which used")
    print("OpenAI to generate LaTeX directly, rather than a template.")
    
    # Create output directory if it doesn't exist
    output_dir = Path("./test_output")
    output_dir.mkdir(exist_ok=True)
    
    # Generate timestamp for unique filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Generate LaTeX from dummy data
    print("\n1. Generating LaTeX from dummy resume data...")
    try:
        latex_content = generate_latex_resume(DUMMY_RESUME_DATA)
        print(f"Successfully generated LaTeX content ({len(latex_content)} characters)")
        
        # Display first few lines of the generated content
        preview_lines = latex_content.split('\n')[:10]
        print("\nPreview of generated LaTeX:")
        for line in preview_lines:
            print(f"  {line}")
        print("  ...")
    except Exception as e:
        print(f"Error generating LaTeX: {e}")
        return
    
    # Save LaTeX to file
    print("\n2. Saving LaTeX content to file...")
    tex_file_path = os.path.join(output_dir, f"original_78211d1_resume_{timestamp}.tex")
    save_latex_to_file(latex_content, tex_file_path)
    
    # Compile LaTeX to PDF
    print("\n3. Compiling LaTeX to PDF...")
    pdf_path = compile_latex_to_pdf(tex_file_path)
    
    if pdf_path and os.path.exists(pdf_path):
        print(f"\n✅ Success! PDF generated at: {pdf_path}")
        # Print file size
        pdf_size = os.path.getsize(pdf_path)
        print(f"PDF file size: {pdf_size / 1024:.1f} KB")
        
        # Instructions for viewing
        print("\nTo view the PDF:")
        print(f"  open {pdf_path}")
    else:
        print("\n❌ Failed to generate PDF.")
        print("Check the compilation log for details.")
        
    print("\nOriginal Approach Details:")
    print("- Uses OpenAI to generate LaTeX directly from resume data")
    print("- No complex string escaping or sanitization needed")
    print("- More flexible but potentially less consistent than template-based approach")
    print("- Avoids the complex sanitization issues that emerged with the template approach")

if __name__ == "__main__":
    main() 