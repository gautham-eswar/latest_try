#!/usr/bin/env python3
"""
Test script to validate PDF generation using the actual classic template.
This script tests the real classic_template.py module from resume_latex_generator.
"""

import os
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime

# Add the parent directory to the Python path so we can import the resume_latex_generator modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Try importing the generate_latex_content function from the classic template
try:
    from resume_latex_generator.templates.classic_template import generate_latex_content
    print("Successfully imported generate_latex_content from classic_template")
except ImportError as e:
    print(f"Error importing from classic_template: {e}")
    sys.exit(1)

# Create a sample resume data structure compatible with the classic template
CLASSIC_RESUME_DATA = {
    "personal_info": {
        "name": "Jane Smith",
        "email": "jane.smith@example.com",
        "phone": "+1 (555) 123-4567",
        "location": "San Francisco, CA",
        "linkedin": "linkedin.com/in/janesmith",
        "github": "github.com/janesmith"
    },
    "objective": "Experienced software engineer with expertise in Python, JavaScript, and cloud technologies.",
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
    print("\n=== Testing Resume PDF Generation with Classic Template ===\n")
    
    # Create output directory if it doesn't exist
    output_dir = Path("./test_output")
    output_dir.mkdir(exist_ok=True)
    
    # Generate timestamp for unique filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Generate LaTeX using the classic template
    print("\n1. Generating LaTeX from resume data using classic template...")
    try:
        latex_content = generate_latex_content(CLASSIC_RESUME_DATA)
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
    tex_file_path = os.path.join(output_dir, f"classic_resume_{timestamp}.tex")
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

if __name__ == "__main__":
    main() 