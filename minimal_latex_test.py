#!/usr/bin/env python3
"""
Minimal LaTeX PDF Generation Test
Tests the exact pipeline used in the current system.
"""

import os
import subprocess
import tempfile
from pathlib import Path

def test_minimal_latex():
    """Test minimal LaTeX compilation using current system setup."""
    
    # Minimal LaTeX content with current preamble
    minimal_latex = r"""
\documentclass[letterpaper,11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{microtype}
\usepackage{latexsym}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\usepackage{amsfonts}
\usepackage{textcomp}
\usepackage[left=0.4in, right=0.4in, top=0.4in, bottom=0.35in, footskip=25pt]{geometry}
\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}
\titleformat{\section}{\scshape\raggedright\large}{}{0pt}{}[\titlerule]
\titlespacing{\section}{0pt}{5pt}{2pt}
\pdfgentounicode=1

\begin{document}

\begin{center}
{\Huge \textbf{JOHN DOE}}\\[5pt]
{\large Software Engineer}\\[5pt]
\href{mailto:john.doe@example.com}{john.doe@example.com} $|$ 
(555) 123-4567 $|$ 
\href{https://linkedin.com/in/johndoe}{linkedin.com/in/johndoe}
\end{center}

\section{EXPERIENCE}
\textbf{Software Engineer} \hfill \textit{2020 - Present}\\
\textit{Tech Company} \hfill \textit{San Francisco, CA}
\begin{itemize}[leftmargin=0.15in, label={$\bullet$}]
    \item Developed scalable web applications using Python \& JavaScript
    \item Improved system performance by 25\% through optimization
    \item Led a team of 3 developers on critical projects
\end{itemize}

\section{EDUCATION}
\textbf{Bachelor of Science in Computer Science} \hfill \textit{2016 - 2020}\\
\textit{University of California} \hfill \textit{Berkeley, CA}

\section{SKILLS}
\textbf{Programming Languages:} Python, JavaScript, Java, C++\\
\textbf{Technologies:} React, Node.js, Docker, AWS, PostgreSQL

\end{document}
"""

    print("=== Minimal LaTeX PDF Generation Test ===")
    print("Using exact compilation pipeline from current system\n")
    
    # Create temporary directory (same as current system)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        tex_file_path = temp_dir_path / "minimal_test.tex"
        pdf_file_path = temp_dir_path / "minimal_test.pdf"
        
        # Write LaTeX content
        print("1. Writing LaTeX content...")
        with open(tex_file_path, 'w', encoding='utf-8') as f:
            f.write(minimal_latex)
        print(f"   ✓ Written to: {tex_file_path}")
        
        # Change to temp directory (same as current system)
        original_cwd = os.getcwd()
        os.chdir(temp_dir_path)
        
        try:
            # Use exact command from current system
            print("\n2. Compiling with pdflatex...")
            cmd = ["pdflatex", "-interaction=nonstopmode", "minimal_test.tex"]
            print(f"   Command: {' '.join(cmd)}")
            
            process = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            print(f"   Return code: {process.returncode}")
            
            if process.returncode == 0:
                print("   ✓ Compilation successful!")
                
                if pdf_file_path.exists():
                    # Copy to current directory for inspection
                    import shutil
                    output_pdf = Path("minimal_test_output.pdf")
                    shutil.copy(pdf_file_path, output_pdf)
                    print(f"   ✓ PDF copied to: {output_pdf}")
                    
                    # Basic analysis
                    pdf_size = output_pdf.stat().st_size
                    print(f"   PDF size: {pdf_size / 1024:.1f} KB")
                    
                    # Try to analyze with pdfinfo if available
                    try:
                        info_result = subprocess.run(["pdfinfo", str(output_pdf)], 
                                                   capture_output=True, text=True)
                        if info_result.returncode == 0:
                            for line in info_result.stdout.splitlines():
                                if "Pages:" in line or "Creator:" in line or "Producer:" in line:
                                    print(f"   {line}")
                    except FileNotFoundError:
                        print("   (pdfinfo not available for detailed analysis)")
                        
                else:
                    print("   ❌ PDF file not created despite successful return code")
                    
            else:
                print("   ❌ Compilation failed!")
                print("\nLaTeX Error Output:")
                print(process.stdout[-1000:])  # Last 1000 chars
                if process.stderr:
                    print("\nstderr:")
                    print(process.stderr[-500:])
                
                # Save log for debugging
                log_file = temp_dir_path / "minimal_test.log"
                if log_file.exists():
                    with open("minimal_test_debug.log", "w") as f:
                        f.write(log_file.read_text())
                    print(f"   Debug log saved to: minimal_test_debug.log")
                    
        finally:
            os.chdir(original_cwd)
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_minimal_latex() 