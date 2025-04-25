import sys
import os
from typing import Dict, List, Any

# Remove the import that doesn't work
# Add the parent directory to the path to import the classic_template module
# parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# sys.path.append(parent_dir)

# from classic_template import generate_latex_content

def format_resume_data_for_template(resume_data):
    """
    Format resume data from our API format to the format expected by classic_template.py
    
    Args:
        resume_data (dict): Resume data from the API
        
    Returns:
        dict: Formatted resume data for the template
    """
    personal_info = resume_data.get("Personal Information", {})
    if isinstance(personal_info, dict):
        name = personal_info.get("name", "")
        email = personal_info.get("email", "")
        phone = personal_info.get("phone", "")
        location = personal_info.get("location", "")
        linkedin = personal_info.get("website/LinkedIn", "")
    else:
        name = resume_data.get("name", "")
        email = resume_data.get("email", "")
        phone = resume_data.get("phone", "")
        location = resume_data.get("location", "")
        linkedin = resume_data.get("linkedin", "")
    
    # Clean LinkedIn URL - remove spaces and handle various formats
    if linkedin:
        # Remove any spaces
        linkedin = linkedin.strip()
        # Extract just the username if it contains LinkedIn URL
        if "linkedin.com/in/" in linkedin:
            username = linkedin.split("linkedin.com/in/")[-1].split("/")[0].split(" ")[0]
            linkedin = username
        elif "linkedin.com" in linkedin:
            # Just use "LinkedIn" as the text if we can't extract a clean username
            linkedin = "LinkedIn"
    
    formatted_data = {}
    
    # Personal information
    formatted_data["name"] = name
    
    # Contact information
    formatted_data["contact"] = {
        "email": email,
        "phone": phone,
        "linkedin": linkedin
    }
    
    # Location
    formatted_data["location"] = location
    
    # Summary/Objective
    summary = resume_data.get("Summary/Objective", "")
    formatted_data["summary"] = summary
    
    # Education
    formatted_data["education"] = []
    for edu in resume_data.get("Education", []):
        formatted_edu = {
            "institution": edu.get("university", ""),
            "location": edu.get("location", ""),
            "degree": edu.get("degree", ""),
            "specialization": edu.get("specialization", ""),
            "start_date": edu.get("start_date", ""),
            "end_date": edu.get("end_date", ""),
            "gpa": edu.get("gpa", ""),
            "honors": edu.get("honors", ""),
            "relevant_coursework": edu.get("additional_info", [])
        }
        formatted_data["education"].append(formatted_edu)
    
    # Work Experience
    formatted_data["work_experience"] = []
    for exp in resume_data.get("Experience", []):
        formatted_exp = {
            "company": exp.get("company", ""),
            "location": exp.get("location", ""),
            "position": exp.get("title", ""),
            "start_date": exp.get("start_date", ""),
            "end_date": exp.get("end_date", ""),
            "responsibilities": exp.get("responsibilities/achievements", [])
        }
        formatted_data["work_experience"].append(formatted_exp)
    
    # Projects
    formatted_data["projects"] = []
    for proj in resume_data.get("Projects", []):
        technologies = proj.get("technologies", [])
        if isinstance(technologies, str):
            technologies = [tech.strip() for tech in technologies.split(",")]
            
        description = proj.get("description", "")
        if isinstance(description, list):
            description = description
        else:
            description = [description] if description else []
            
        formatted_proj = {
            "title": proj.get("title", ""),
            "description": description,
            "technologies": technologies
        }
        formatted_data["projects"].append(formatted_proj)
    
    # Skills
    formatted_data["skills"] = {}
    skills = resume_data.get("Skills", {})
    if isinstance(skills, dict):
        for category, skill_list in skills.items():
            formatted_data["skills"][category] = skill_list
    elif isinstance(skills, list):
        formatted_data["skills"]["Technical Skills"] = skills
    
    # Certifications/Awards
    formatted_data["certifications"] = []
    for cert in resume_data.get("Certifications/Awards", []):
        if isinstance(cert, str):
            formatted_data["certifications"].append({"name": cert})
        elif isinstance(cert, dict):
            formatted_data["certifications"].append({
                "name": cert.get("name", ""),
                "issuer": cert.get("issuer", ""),
                "date": cert.get("date", "")
            })
    
    # Languages
    formatted_data["languages"] = resume_data.get("Languages", [])
    
    # Publications
    formatted_data["publications"] = []
    for pub in resume_data.get("Publications", []):
        if isinstance(pub, dict):
            formatted_data["publications"].append({
                "title": pub.get("title", ""),
                "authors": pub.get("authors", ""),
                "journal": pub.get("journal/conference", ""),
                "date": pub.get("date", ""),
                "url": pub.get("url", "")
            })
    
    # Volunteer Experience
    formatted_data["volunteer"] = []
    for vol in resume_data.get("Volunteer Experience", []):
        if isinstance(vol, dict):
            formatted_data["volunteer"].append({
                "organization": vol.get("organization", ""),
                "role": vol.get("role", ""),
                "location": vol.get("location", ""),
                "dates": vol.get("dates", ""),
                "description": vol.get("description", "")
            })
    
    return formatted_data

def generate_latex_content(data: Dict[str, Any]) -> str:
    """
    Generate LaTeX content for the classic resume template.
    
    Args:
        data: Dictionary containing formatted resume data
        
    Returns:
        str: LaTeX content for the resume
    """
    latex = []
    
    # Helper function to escape LaTeX special characters
    def escape_latex(text):
        if not text:
            return ""
        if not isinstance(text, str):
            return str(text)
            
        # Replace LaTeX special characters
        replacements = {
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '_': r'\_',
            '{': r'\{',
            '}': r'\}',
            '~': r'\textasciitilde{}',
            '^': r'\textasciicircum{}',
            '\\': r'\textbackslash{}',
            '<': r'\textless{}',
            '>': r'\textgreater{}'
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        return text
    
    # Document preamble
    latex.append(r'\documentclass[letterpaper,11pt]{article}')
    latex.append('')
    latex.append(r'% Package Imports')
    latex.append(r'\usepackage{latexsym}')
    latex.append(r'\usepackage[empty]{fullpage}')
    latex.append(r'\usepackage{titlesec}')
    latex.append(r'\usepackage{marvosym}')
    latex.append(r'\usepackage[usenames,dvipsnames]{color}')
    latex.append(r'\usepackage{verbatim}')
    latex.append(r'\usepackage{enumitem}')
    latex.append(r'\usepackage[pdftex]{hyperref}')
    latex.append(r'\usepackage{fancyhdr}')
    latex.append(r'\usepackage{multirow}')
    latex.append(r'\usepackage{array}')
    latex.append('')
    
    # Page style
    latex.append(r'% Page Style')
    latex.append(r'\pagestyle{fancy}')
    latex.append(r'\fancyhf{}')
    latex.append(r'\fancyfoot{}')
    latex.append(r'\renewcommand{\headrulewidth}{0pt}')
    latex.append(r'\renewcommand{\footrulewidth}{0pt}')
    latex.append('')
    
    # Margins
    latex.append(r'% Margins')
    latex.append(r'\addtolength{\oddsidemargin}{-0.5in}')
    latex.append(r'\addtolength{\evensidemargin}{-0.5in}')
    latex.append(r'\addtolength{\textwidth}{1in}')
    latex.append(r'\addtolength{\topmargin}{-.5in}')
    latex.append(r'\addtolength{\textheight}{1in}')
    latex.append('')
    
    # Section formatting
    latex.append(r'% Section Formatting')
    latex.append(r'\titleformat{\section}{\vspace{-4pt}\scshape\raggedright\large}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]')
    latex.append('')
    
    # Custom commands
    latex.append(r'% Custom Commands')
    latex.append(r'\newcommand{\resumeItem}[1]{')
    latex.append(r'  \item\small{#1}')
    latex.append(r'}')
    latex.append('')
    
    latex.append(r'\newcommand{\resumeSubheading}[4]{')
    latex.append(r'  \vspace{-2pt}\item')
    latex.append(r'    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}')
    latex.append(r'      \textbf{#1} & #2 \\')
    latex.append(r'      \textit{\small#3} & \textit{\small #4} \\')
    latex.append(r'    \end{tabular*}\vspace{-7pt}')
    latex.append(r'}')
    latex.append('')
    
    latex.append(r'\newcommand{\resumeSubSubheading}[2]{')
    latex.append(r'    \item')
    latex.append(r'    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}')
    latex.append(r'      \textit{\small#1} & \textit{\small #2} \\')
    latex.append(r'    \end{tabular*}\vspace{-7pt}')
    latex.append(r'}')
    latex.append('')
    
    latex.append(r'\newcommand{\resumeProjectHeading}[2]{')
    latex.append(r'    \item')
    latex.append(r'    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}')
    latex.append(r'      \textbf{#1} & #2 \\')
    latex.append(r'    \end{tabular*}\vspace{-7pt}')
    latex.append(r'}')
    latex.append('')
    
    latex.append(r'\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}')
    latex.append('')
    
    latex.append(r'\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}')
    latex.append('')
    
    latex.append(r'\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}')
    latex.append(r'\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}')
    latex.append(r'\newcommand{\resumeItemListStart}{\begin{itemize}}')
    latex.append(r'\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}')
    latex.append('')
    
    # Hyperlink formatting
    latex.append(r'% Hyperlink formatting')
    latex.append(r'\hypersetup{')
    latex.append(r'    colorlinks=true,')
    latex.append(r'    linkcolor=blue,')
    latex.append(r'    filecolor=magenta,')
    latex.append(r'    urlcolor=cyan,')
    latex.append(r'}')
    latex.append('')
    
    # Document start
    latex.append(r'\begin{document}')
    latex.append('')
    
    # Header
    latex.append(r'% Header')
    latex.append(r'\begin{center}')
    latex.append(f'    \\textbf{{\\Huge \\scshape {data.get("name", "")}}} \\\\ \\vspace{{1pt}}')
    
    # Contact info
    contact = data.get("contact", {})
    location = data.get("location", "")
    contact_parts = []
    
    if phone := contact.get("phone", ""):
        contact_parts.append(f'{escape_latex(phone)}')
    
    if email := contact.get("email", ""):
        escaped_email = escape_latex(email)
        contact_parts.append(f'\\href{{mailto:{email}}}{{{escaped_email}}}')
    
    if linkedin := contact.get("linkedin", ""):
        # Ensure we have a clean LinkedIn URL
        if linkedin and not linkedin.startswith(('http://', 'https://')):
            linkedin_url = f'https://www.linkedin.com/in/{linkedin}'
        else:
            linkedin_url = linkedin
        contact_parts.append(f'\\href{{{escape_latex(linkedin_url)}}}{{LinkedIn}}')
    
    if location:
        contact_parts.append(escape_latex(location))
    
    if contact_parts:
        latex.append(f'    {" $|$ ".join(contact_parts)}')
    
    latex.append(r'\end{center}')
    latex.append('')
    
    # Summary/Objective section
    if summary := data.get("summary", ""):
        latex.append(r'\section{Summary}')
        latex.append(f'{escape_latex(summary)}')
        latex.append('')
    
    # Education Section
    if education := data.get("education", []):
        latex.append(r'\section{Education}')
        latex.append(r'\resumeSubHeadingListStart')
        
        for edu in education:
            institution = edu.get("institution", "")
            location = edu.get("location", "")
            degree = edu.get("degree", "")
            specialization = edu.get("specialization", "")
            start_date = edu.get("start_date", "")
            end_date = edu.get("end_date", "")
            gpa = edu.get("gpa", "")
            
            degree_spec = f"{degree} in {specialization}" if specialization else degree
            date_range = f"{start_date} - {end_date}" if start_date and end_date else end_date or start_date
            
            latex.append(f'    \\resumeSubheading')
            latex.append(f'      {{{escape_latex(institution)}}}{{{escape_latex(date_range)}}}')
            latex.append(f'      {{{escape_latex(degree_spec)}}}{{{escape_latex(location)}}}')
            
            if gpa:
                latex.append(f'      \\resumeItem{{GPA: {escape_latex(gpa)}}}')
            
            if coursework := edu.get("relevant_coursework", []):
                if isinstance(coursework, list) and coursework:
                    coursework_str = ", ".join(coursework)
                    latex.append(f'      \\resumeItem{{Relevant Coursework: {escape_latex(coursework_str)}}}')
                elif isinstance(coursework, str) and coursework:
                    latex.append(f'      \\resumeItem{{Relevant Coursework: {escape_latex(coursework)}}}')
        
        latex.append(r'\resumeSubHeadingListEnd')
        latex.append('')
    
    # Experience Section
    if work_experience := data.get("work_experience", []):
        latex.append(r'\section{Experience}')
        latex.append(r'\resumeSubHeadingListStart')
        
        for exp in work_experience:
            company = exp.get("company", "")
            location = exp.get("location", "")
            position = exp.get("position", "")
            start_date = exp.get("start_date", "")
            end_date = exp.get("end_date", "")
            
            date_range = f"{start_date} - {end_date}" if start_date and end_date else end_date or start_date
            
            latex.append(f'    \\resumeSubheading')
            latex.append(f'      {{{escape_latex(company)}}}{{{escape_latex(date_range)}}}')
            latex.append(f'      {{{escape_latex(position)}}}{{{escape_latex(location)}}}')
            
            if responsibilities := exp.get("responsibilities", []):
                latex.append(r'      \resumeItemListStart')
                
                for resp in responsibilities:
                    if resp:
                        # Replace & with \& for LaTeX compatibility
                        resp = resp.replace('&', '\\&')
                        latex.append(f'        \\resumeItem{{{escape_latex(resp)}}}')
                
                latex.append(r'      \resumeItemListEnd')
        
        latex.append(r'\resumeSubHeadingListEnd')
        latex.append('')
    
    # Projects Section
    if projects := data.get("projects", []):
        latex.append(r'\section{Projects}')
        latex.append(r'\resumeSubHeadingListStart')
        
        for proj in projects:
            title = proj.get("title", "")
            technologies = proj.get("technologies", [])
            tech_str = f" ({', '.join(technologies)})" if technologies else ""
            
            latex.append(f'    \\resumeProjectHeading')
            latex.append(f'      {{{escape_latex(title)}{tech_str}}}{{}}')
            
            if description := proj.get("description", []):
                latex.append(r'      \resumeItemListStart')
                
                if isinstance(description, list):
                    for desc in description:
                        if desc:
                            # Replace & with \& for LaTeX compatibility
                            desc = desc.replace('&', '\\&')
                            latex.append(f'        \\resumeItem{{{escape_latex(desc)}}}')
                elif description:
                    # Replace & with \& for LaTeX compatibility
                    description = description.replace('&', '\\&')
                    latex.append(f'        \\resumeItem{{{escape_latex(description)}}}')
                
                latex.append(r'      \resumeItemListEnd')
        
        latex.append(r'\resumeSubHeadingListEnd')
        latex.append('')
    
    # Skills Section
    if skills := data.get("skills", {}):
        latex.append(r'\section{Skills}')
        
        for category, skill_list in skills.items():
            if not skill_list:
                continue
                
            escaped_category = escape_latex(category)
            latex.append(f'\\textbf{{{escaped_category}}}: ')
            
            if isinstance(skill_list, list):
                # Escape LaTeX special characters in each skill
                formatted_skills = [escape_latex(s) for s in skill_list if s]
                if formatted_skills:
                    latex.append(f"{', '.join(formatted_skills)}")
            elif isinstance(skill_list, str):
                latex.append(f"{escape_latex(skill_list)}")
            
            latex.append('\\\\')
            latex.append('') # Add an extra line between skill categories
        
        # Remove the last two lines if they're a line break and empty line
        if latex[-1] == '' and latex[-2] == '\\\\':
            latex.pop()  # Remove empty line
            latex.pop()  # Remove line break
        
        latex.append('')
    
    # Certifications Section
    if certifications := data.get("certifications", []):
        latex.append(r'\section{Certifications}')
        latex.append(r'\resumeSubHeadingListStart')
        
        for cert in certifications:
            if isinstance(cert, dict):
                cert_name = cert.get("name", "")
                issuer = cert.get("issuer", "")
                date = cert.get("date", "")
                
                if cert_name:
                    if issuer and date:
                        latex.append(f'    \\resumeItem{{{escape_latex(cert_name)} - {escape_latex(issuer)} ({escape_latex(date)})}}')
                    elif issuer:
                        latex.append(f'    \\resumeItem{{{escape_latex(cert_name)} - {escape_latex(issuer)}}}')
                    elif date:
                        latex.append(f'    \\resumeItem{{{escape_latex(cert_name)} ({escape_latex(date)})}}')
                    else:
                        latex.append(f'    \\resumeItem{{{escape_latex(cert_name)}}}')
            elif isinstance(cert, str) and cert:
                latex.append(f'    \\resumeItem{{{escape_latex(cert)}}}')
        
        latex.append(r'\resumeSubHeadingListEnd')
        latex.append('')
    
    # Languages Section
    if languages := data.get("languages", []):
        latex.append(r'\section{Languages}')
        
        if isinstance(languages, list):
            # Replace & with \& for LaTeX compatibility
            formatted_languages = [lang.replace('&', '\\&') if isinstance(lang, str) else lang for lang in languages if lang]
            if formatted_languages:
                latex.append(f"{', '.join(formatted_languages)}")
        elif isinstance(languages, str) and languages:
            # Replace & with \& for LaTeX compatibility
            latex.append(f"{escape_latex(languages)}")
        
        latex.append('')
    
    # Document end
    latex.append(r'\end{document}')
    
    return '\n'.join(latex)

def generate_resume_latex(resume_data):
    """
    Generate LaTeX resume from resume data
    
    Args:
        resume_data (dict): Resume data
        
    Returns:
        str: LaTeX content
    """
    formatted_data = format_resume_data_for_template(resume_data)
    return generate_latex_content(formatted_data) 