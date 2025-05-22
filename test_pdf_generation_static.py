#!/usr/bin/env python3
"""
Test script to validate PDF generation using a static LaTeX template.
This script demonstrates the PDF generation capability without relying on the OpenAI API.
"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Static LaTeX template for a resume
STATIC_LATEX_TEMPLATE = r"""\documentclass[11pt,letterpaper]{article}
\usepackage[margin=1in]{geometry}
\usepackage{enumitem}
\usepackage{hyperref}
\usepackage{fontawesome}
\usepackage{titlesec}
\usepackage{color}

% Define colors
\definecolor{primary}{RGB}{70, 130, 180}
\definecolor{secondary}{RGB}{128, 128, 128}

% Format section headings
\titleformat{\section}{\Large\bfseries\color{primary}}{\thesection}{0em}{}[\titlerule]
\titlespacing{\section}{0pt}{12pt}{8pt}

% Format subsection headings
\titleformat{\subsection}{\bfseries\color{secondary}}{\thesubsection}{0em}{}
\titlespacing{\subsection}{0pt}{8pt}{4pt}

% Custom commands for contact info
\newcommand{\contactItem}[2]{\textbf{#1}: #2 \hspace{1cm}}

\begin{document}

% Header with name and contact details
\begin{center}
    {\Huge \textbf{Jane Smith}} \\[0.2cm]
    
    \begin{tabular}{c}
    \contactItem{\faPhone}{(555) 123-4567} 
    \contactItem{\faEnvelope}{jane.smith@example.com} 
    \contactItem{\faLinkedin}{linkedin.com/in/janesmith} \\
    \contactItem{\faMapMarker}{San Francisco, CA} 
    \contactItem{\faGithub}{github.com/janesmith}
    \end{tabular}
\end{center}

% Summary
\section*{Professional Summary}
Experienced software engineer with expertise in Python, JavaScript, and cloud technologies.

% Experience
\section{Experience}
\subsection{Tech Solutions Inc., San Francisco, CA}
\textbf{Senior Software Engineer} \hfill \textit{January 2020 - Present}
\begin{itemize}[leftmargin=*]
    \item Lead development of cloud-based applications using Python and AWS.
    \item Reduced system latency by 40\% through architecture improvements.
    \item Led team of 5 engineers in delivering major platform update.
\end{itemize}

\subsection{WebDev Co, Oakland, CA}
\textbf{Software Engineer} \hfill \textit{March 2017 - December 2019}
\begin{itemize}[leftmargin=*]
    \item Developed and maintained web applications using JavaScript and Node.js.
    \item Implemented responsive design patterns that improved mobile user experience.
    \item Created automated testing framework that caught 25\% more bugs before release.
\end{itemize}

% Education
\section{Education}
\subsection{University of California, Berkeley}
\textbf{Bachelor of Science in Computer Science} \hfill \textit{2013 - 2017}
\begin{itemize}[leftmargin=*]
    \item GPA: 3.8 / 4.0, Magna Cum Laude
\end{itemize}

% Skills
\section{Skills}
\textbf{Technical:} Python, JavaScript, React, Node.js, AWS, Docker, PostgreSQL \\
\textbf{Soft:} Leadership, Communication, Problem Solving

% Projects
\section{Projects}
\subsection{Cloud Monitoring Tool}
\begin{itemize}[leftmargin=*]
    \item Developed a tool for monitoring AWS resources in real-time.
    \item Technologies: Python, AWS SDK, Flask
    \item Used by 500+ developers, Featured in AWS blog
\end{itemize}

% Certifications
\section{Certifications}
\textbf{AWS Certified Solutions Architect} \hfill \textit{June 2021}

\end{document}
"""

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
    print("\n=== Testing Resume PDF Generation with Static Template ===\n")
    
    # Create output directory if it doesn't exist
    output_dir = Path("./test_output")
    output_dir.mkdir(exist_ok=True)
    
    # Generate timestamp for unique filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save static LaTeX template to file
    print("\n1. Saving LaTeX template to file...")
    tex_file_path = os.path.join(output_dir, f"static_resume_{timestamp}.tex")
    save_latex_to_file(STATIC_LATEX_TEMPLATE, tex_file_path)
    
    # Compile LaTeX to PDF
    print("\n2. Compiling LaTeX to PDF...")
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
        print("Check if LaTeX is installed on your system:")
        print("  - On macOS: Install MacTeX (https://tug.org/mactex/)")
        print("  - On Linux: sudo apt-get install texlive-full")
        print("  - On Windows: Install MiKTeX (https://miktex.org/)")

if __name__ == "__main__":
    main() 