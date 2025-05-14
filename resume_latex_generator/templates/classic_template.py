import os # Add os import for path operations
from typing import Dict, Any, Optional, List
import re

# Default page height if not specified by the generator (e.g. if auto-sizing is off and no specific height is given)
DEFAULT_TEMPLATE_PAGE_HEIGHT_INCHES = 11.0 

# --- Helper functions to generate LaTeX for each section (assumed to be defined below as before) ---
# e.g. fix_latex_special_chars, _generate_header_section, _generate_objective_section, etc.

def sanitize_latex(lines: List[str]) -> List[str]:
    cleaned = []
    for L in lines:
        # Skip empty lines
        if not L.strip():
            continue
            
        # Pattern 1: Lines that consist of only multiple backslashes
        if L.strip() == r"\\\\" or L.strip() == r"\\" or L.strip().startswith(r"\\") and L.strip().count('\\') > 1:
            continue
            
        # Pattern 2: Fix lines ending with multiple backslashes (e.g., "\\ \\")
        # which often cause "no line here to end" errors
        if L.rstrip().endswith(r"\\ \\"):
            L = L.rstrip()[:-4] + r"\\"  # Replace "\\ \\" with a single "\\"
            
        # Pattern 3: Fix lines containing consecutive backslashes "\\\\", often improperly escaped
        # Replace "\\\\" with "\\" when not part of a LaTeX command
        if r"\\\\" in L and not any(cmd in L for cmd in [r"resumeItem", r"begin", r"end"]):
            L = L.replace(r"\\\\", r"\\")
            
        # Add the cleaned line
        cleaned.append(L)
    return cleaned

def fix_latex_special_chars(text: Optional[Any]) -> str:

    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text) # Ensure it's a string

    # Process percentage signs specially to handle common patterns like "5%" correctly
    # First, find and protect patterns like "X%" where X is a number
    protected_percentages = {}
    for i, match in enumerate(re.finditer(r'(\d+)%', text)):
        placeholder = f"__PCT_PLACEHOLDER_{i}__"
        text = text.replace(match.group(0), placeholder)
        protected_percentages[placeholder] = f"{match.group(1)}\\%"

    # Now handle standard LaTeX special characters
    replacements = [
        ("\\", r"\textbackslash{}"), # Corrected: Python string for single backslash
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]

    for old, new in replacements:
        text = text.replace(old, new)
        
    # Finally, restore the protected percentage patterns
    for placeholder, replacement in protected_percentages.items():
        text = text.replace(placeholder, replacement)
        
    return text

def _generate_header_section(personal_info: Optional[Dict[str, Any]]) -> Optional[str]:
    if not personal_info:
        return None
    
    name = fix_latex_special_chars(personal_info.get("name"))
    email = personal_info.get("email")  # Raw email, will handle special chars in href
    phone = fix_latex_special_chars(personal_info.get("phone"))
    linkedin = fix_latex_special_chars(personal_info.get("linkedin")) # Assuming 'linkedin' key
    website = fix_latex_special_chars(personal_info.get("website")) # Assuming 'website' key
    github = fix_latex_special_chars(personal_info.get("github")) # Assuming 'github' key
    location = fix_latex_special_chars(personal_info.get("location"))

    lines = []
    if name:
        lines.append(r"\\begin{center}")
        lines.append(f"    \\\\textbf{{\\\\\\\\Huge \\\\\\\\scshape {name}}} \\\\\\\\ \\\\vspace{{1pt}}") 
    
    contact_parts = []
    if phone:
        contact_parts.append(phone)
    if email:
        email_display = email.replace("_", r"\\_")
        safe_email_display = fix_latex_special_chars(email_display)
        contact_parts.append(f"\\\\href{{mailto:{email}}}{{\\\\\\\\underline{{{safe_email_display}}}}}")
    if linkedin: 
        linkedin_url = linkedin
        if not linkedin.startswith("http"):
            linkedin_url = f"https://{linkedin}"
        safe_linkedin_display = fix_latex_special_chars(linkedin)
        contact_parts.append(f"\\\\href{{{linkedin_url}}}{{\\\\\\\\underline{{{safe_linkedin_display}}}}}")
    if github: 
        github_url = github
        if not github.startswith("http"):
            github_url = f"https://{github}"
        safe_github_display = fix_latex_special_chars(github)
        contact_parts.append(f"\\\\href{{{github_url}}}{{\\\\\\\\underline{{{safe_github_display}}}}}")
    if website: 
        website_url = website
        if not website.startswith("http"): 
             website_url = f"http://{website}"
        safe_website_display = fix_latex_special_chars(website)
        contact_parts.append(f"\\\\href{{{website_url}}}{{\\\\\\\\underline{{{safe_website_display}}}}}")

    if contact_parts:
        joined_contacts = ' $|$ '.join(filter(None, contact_parts))
        if joined_contacts.strip():
            lines.append(f"    \\\\\\\\small{{{joined_contacts}}}")
    
    if location:
        if name:
            lines.append(f"    \\\\\\\\small {location}")
        else:
             lines.append(r"\\begin{center}")
             lines.append(f"    \\\\\\\\small {location}")
             lines.append(r"\\end{center}")


    if name and not (location and not contact_parts):
        lines.append(r"\\end{center}")

    return "\\n".join(lines) if lines else None


def _generate_objective_section(objective: Optional[str]) -> Optional[str]:
    if not objective:
        return None
    
    return f"""\\\\section*{{Summary}} % Using section* for unnumbered
  {fix_latex_special_chars(objective)}
"""

def _generate_education_section(education_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not education_list:
        return None
    
    lines = ["\\\\section{Education}", "  \\\\resumeSubHeadingListStart"]
    for edu in education_list:
        uni = fix_latex_special_chars(edu.get("institution") or edu.get("university"))
        loc = fix_latex_special_chars(edu.get("location"))
        degree_parts = [fix_latex_special_chars(edu.get("degree"))]
        if edu.get("specialization"):
            degree_parts.append(fix_latex_special_chars(edu.get("specialization")))
        degree_str = ", ".join(filter(None, degree_parts))
        
        start_date = edu.get("start_date", "")
        end_date = edu.get("end_date", "")
        dates = f"{fix_latex_special_chars(start_date)} -- {fix_latex_special_chars(end_date)}" if start_date or end_date else ""
        if end_date and end_date.lower() == 'present': 
             dates = f"{fix_latex_special_chars(start_date)} -- Present"
        elif not end_date and start_date: 
             dates = fix_latex_special_chars(start_date)

        lines.append(f"    \\\\resumeSubheading")
        lines.append(f"      {{{uni}}}{{{loc}}}")
        lines.append(f"      {{{degree_str}}}{{{dates}}}")
        
        gpa = edu.get("gpa")
        honors = fix_latex_special_chars(edu.get("honors"))
        
        details_parts = []
        if gpa:
            details_parts.append(f"GPA: {fix_latex_special_chars(gpa)}")
        if honors:
            details_parts.append(f"Honors: {honors}")
        
        if details_parts:
            lines.append(f"    \\\\resumeSubSubheading{{{', '.join(details_parts)}}}{{}}")
        
        additional_info = edu.get("additional_info")
        relevant_coursework = edu.get("relevant_coursework")

        if additional_info:
            lines.append(r"      \\\\resumeItemListStart")
            lines.append(f"        \\\\resumeItem{{{fix_latex_special_chars(additional_info)}}}")
            lines.append(r"      \\\\resumeItemListEnd")
        elif relevant_coursework and isinstance(relevant_coursework, list):
            lines.append(r"      \\\\resumeItemListStart")
            courses_str = ", ".join(fix_latex_special_chars(c) for c in relevant_coursework)
            lines.append(f"        \\\\resumeItem{{Relevant Coursework: {courses_str}}}")
            lines.append(r"      \\\\resumeItemListEnd")
            
    lines.append("  \\\\resumeSubHeadingListEnd")
    return "\n".join(lines)

def _generate_experience_section(experience_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not experience_list:
        return None
    
    lines = ["\\\\section{Experience}", "  \\\\resumeSubHeadingListStart"]
    for exp in experience_list:
        company = fix_latex_special_chars(exp.get("company"))
        position = fix_latex_special_chars(exp.get("position") or exp.get("title")) 
        location = fix_latex_special_chars(exp.get("location"))
        
        dates_dict = exp.get("dates", {})
        start_date = fix_latex_special_chars(dates_dict.get("start_date"))
        end_date = fix_latex_special_chars(dates_dict.get("end_date"))
        dates_str = f"{start_date} -- {end_date}" if start_date or end_date else ""
        if end_date and end_date.lower() == 'present':
             dates_str = f"{start_date} -- Present"
        elif not end_date and start_date:
             dates_str = start_date

        lines.append(f"    \\\\resumeSubheading")
        lines.append(f"      {{{position}}}{{{dates_str}}}") 
        lines.append(f"      {{{company}}}{{{location}}}")   

        responsibilities = exp.get("responsibilities") or exp.get("responsibilities/achievements") 
        if responsibilities and isinstance(responsibilities, list):
            lines.append(r"      \\\\resumeItemListStart")
            for resp in responsibilities:
                lines.append(f"        \\\\resumeItem{{{fix_latex_special_chars(resp)}}}")
            lines.append(r"      \\\\resumeItemListEnd")
            
    lines.append("  \\\\resumeSubHeadingListEnd")
    return "\n".join(lines)

def _generate_projects_section(project_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not project_list:
        return None
    
    lines = ["\\\\section{Projects}", "    \\\\resumeSubHeadingListStart"]
    for proj in project_list:
        title = fix_latex_special_chars(proj.get("title"))
        dates_val = proj.get("dates") or proj.get("date")
        dates_str = ""
        if isinstance(dates_val, dict):
            start = fix_latex_special_chars(dates_val.get("start_date"))
            end = fix_latex_special_chars(dates_val.get("end_date"))
            dates_str = f"{start} -- {end}" if start or end else ""
            if end and end.lower() == 'present': dates_str = f"{start} -- Present"
            elif not end and start : dates_str = start
        elif isinstance(dates_val, str):
            dates_str = fix_latex_special_chars(dates_val)

        tech_used = proj.get("technologies") or proj.get("technologies_used") 
        
        heading_title_part = f"\\\\textbf{{{title}}}"
        if tech_used:
            if isinstance(tech_used, list):
                tech_str = ", ".join(fix_latex_special_chars(t) for t in tech_used)
            else: 
                tech_str = fix_latex_special_chars(tech_used)
            if tech_str: 
                 heading_title_part += f" $|$ \\\\emph{{{tech_str}}}"

        lines.append(f"      \\\\resumeProjectHeading")
        lines.append(f"          {{{heading_title_part}}}{{{dates_str}}}")

        description = proj.get("description")
        if description:
            lines.append(r"          \\\\resumeItemListStart")
            if isinstance(description, list):
                for item in description:
                    lines.append(f"            \\\\resumeItem{{{fix_latex_special_chars(item)}}}")
            else: 
                lines.append(f"            \\\\resumeItem{{{fix_latex_special_chars(description)}}}")
            lines.append(r"          \\\\resumeItemListEnd")
            
    lines.append("    \\\\resumeSubHeadingListEnd")
    return "\n".join(lines)


def _generate_skills_section(skills_dict: Optional[Dict[str, Any]]) -> Optional[str]:
    if not skills_dict:
        return None

    lines = ["\\\\section{Technical Skills}"] 
    
    technical_skills_data = skills_dict.get("Technical Skills")
    
    skills_to_process = {}
    if isinstance(technical_skills_data, dict):
        skills_to_process = technical_skills_data
    elif isinstance(skills_dict, dict) and not technical_skills_data: 
        skills_to_process = skills_dict
    
    if not skills_to_process: 
        soft_skills = skills_dict.get("Soft Skills")
        if isinstance(soft_skills, list) and soft_skills:
            lines.append(r" \\\\begin{itemize}[leftmargin=0.15in, label={}]")
            lines.append(r"    \\\\small{\\\\item{")
            lines.append(f"     \\\\textbf{{Soft Skills}}{{:{fix_latex_special_chars(', '.join(soft_skills))}}}")
            lines.append(r"    }}")
            lines.append(r" \\\\end{itemize}")
            return "\n".join(lines)
        return None 

    lines.append(r" \\\\begin{itemize}[leftmargin=0.15in, label={}]")
    lines.append(r"    \\\\small{\\\\item{")
    
    category_lines = []
    for category, skills_list in skills_to_process.items():
        if isinstance(skills_list, list) and skills_list: 
            skills_str = ", ".join(fix_latex_special_chars(s) for s in skills_list)
            category_lines.append(f"     \\\\textbf{{{fix_latex_special_chars(category)}}}{{:{skills_str}}}")
    
    lines.append(" \\\\\\\\ ".join(category_lines)) 
    
    lines.append(r"    }}")
    lines.append(r" \\\\end{itemize}")
    return "\n".join(lines)


def _generate_languages_section(languages_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not languages_list:
        return None
    lines = ["\\\\section{Languages}", r" \\\\begin{itemize}[leftmargin=0.15in, label={}]"]
    lang_items = []
    for lang_data in languages_list:
        name = fix_latex_special_chars(lang_data.get("name"))
        proficiency = fix_latex_special_chars(lang_data.get("proficiency"))
        if name:
            item_str = name
            if proficiency:
                item_str += f" ({proficiency})"
            lang_items.append(item_str)
    if lang_items:
         lines.append(f"    \\\\small{{\\\\item{{{', '.join(lang_items)}}}}}")

    lines.append(r" \\\\end{itemize}")
    return "\n".join(lines) if lang_items else None


def _generate_certifications_section(cert_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not cert_list:
        return None
    
    lines = ["\\\\section{Certifications}", "  \\\\resumeSubHeadingListStart"]
    for cert in cert_list:
        name = fix_latex_special_chars(cert.get("certification"))
        institution = fix_latex_special_chars(cert.get("institution"))
        date = fix_latex_special_chars(cert.get("date"))
        
        lines.append(f"    \\\\resumeSubheading")
        lines.append(f"      {{{name}}}{{{date}}}") 
        lines.append(f"      {{{institution}}}{{}}") 
            
    lines.append("  \\\\resumeSubHeadingListEnd")
    return "\n".join(lines)

def _generate_awards_section(awards_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not awards_list:
        return None
        
    lines = ["\\\\section{Awards}", "  \\\\resumeSubHeadingListStart"]
    for award in awards_list:
        title = fix_latex_special_chars(award.get("title"))
        issuer = fix_latex_special_chars(award.get("issuer"))
        date = fix_latex_special_chars(award.get("date"))
        description = fix_latex_special_chars(award.get("description"))

        lines.append(f"    \\\\resumeSubheading")
        lines.append(f"      {{{title}}}{{{date}}}")
        lines.append(f"      {{{issuer}}}{{}}") 

        if description:
            lines.append(r"      \\\\resumeItemListStart")
            lines.append(f"        \\\\resumeItem{{{fix_latex_special_chars(description)}}}")
            lines.append(r"      \\\\resumeItemListEnd")
            
    lines.append("  \\\\resumeSubHeadingListEnd")
    return "\n".join(lines)


def _generate_involvement_section(involvement_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not involvement_list: 
        return None

    lines = ["\\\\section{Leadership \\\\& Involvement}", "  \\\\resumeSubHeadingListStart"] 
    
    for item in involvement_list:
        organization = fix_latex_special_chars(item.get("organization"))
        position = fix_latex_special_chars(item.get("position"))
            
        date_val = item.get("date") 
        dates_str = ""
        if isinstance(date_val, dict):
            start = fix_latex_special_chars(date_val.get("start_date"))
            end = fix_latex_special_chars(date_val.get("end_date"))
            dates_str = f"{start} -- {end}" if start or end else ""
            if end and end.lower() == 'present': dates_str = f"{start} -- Present"
            elif not end and start : dates_str = start
        elif isinstance(date_val, str):
            dates_str = fix_latex_special_chars(date_val)

        lines.append(f"    \\\\resumeSubheading")
        lines.append(f"      {{{position}}}{{{dates_str}}}")
        lines.append(f"      {{{organization}}}{{}}")
            
        responsibilities = item.get("responsibilities")
        if responsibilities and isinstance(responsibilities, list):
            lines.append(r"      \\\\resumeItemListStart")
            for resp in responsibilities:
                lines.append(f"        \\\\resumeItem{{{fix_latex_special_chars(resp)}}}")
            lines.append(r"      \\\\resumeItemListEnd")
            
    lines.append("  \\\\resumeSubHeadingListEnd")
    return "\n".join(lines)

def _generate_misc_leadership_section(misc_data: Optional[Dict[str, Any]]) -> Optional[str]:
    """Specifically handles the Evelyn.json Misc.Leadership structure."""
    if not misc_data or not isinstance(misc_data, dict):
        return None
    
    leadership_data = misc_data.get("Leadership")
    if not leadership_data or not isinstance(leadership_data, dict):
        return None

    lines = ["\\\\section{Leadership \\\\& Activities}", "  \\\\resumeSubHeadingListStart"] 
    
    for event_name, details in leadership_data.items():
        name = fix_latex_special_chars(event_name)
        
        dates_dict = details.get("dates", {})
        start_date = fix_latex_special_chars(dates_dict.get("start_date"))
        end_date = fix_latex_special_chars(dates_dict.get("end_date"))
        dates_str = f"{start_date} -- {end_date}" if start_date or end_date else ""
        if end_date and end_date.lower() == 'present':
             dates_str = f"{start_date} -- Present"
        elif not end_date and start_date:
             dates_str = start_date
        
        lines.append(f"    \\\\resumeSubheading")
        lines.append(f"      {{\\\\textbf{{{name}}}}}{{{dates_str}}}") 
        lines.append(f"      {{}}{{}}") 
        
        responsibilities = details.get("responsibilities/achievements") 
        if responsibilities and isinstance(responsibilities, list):
            lines.append(r"      \\\\resumeItemListStart")
            for resp in responsibilities:
                lines.append(f"        \\\\resumeItem{{{fix_latex_special_chars(resp)}}}")
            lines.append(r"      \\\\resumeItemListEnd")
            
    lines.append("  \\\\resumeSubHeadingListEnd")
    return "\n".join(lines)


def generate_latex_content(data: Dict[str, Any], page_height: Optional[float] = None) -> str:
    """
    Generates the full LaTeX document string for a classic resume.
    Args:
        data: The parsed JSON resume data.
        page_height: Optional page height in inches. If None, a template default is used.
    Returns:
        A string containing the complete LaTeX document.
    """
    
    page_height_setting_for_doc_start = "" 
    
    current_physical_page_height = page_height if page_height is not None else DEFAULT_TEMPLATE_PAGE_HEIGHT_INCHES

    if page_height is not None:
        page_height_setting_for_doc_start = f"\\setlength{{\\pdfpageheight}}{{{current_physical_page_height:.2f}in}}"

    effective_top_margin = 0.5
    desired_bottom_margin = 0.5
    target_text_height = current_physical_page_height - effective_top_margin - desired_bottom_margin
    text_height_declaration = f"\\setlength{{\\textheight}}{{{target_text_height:.2f}in}}"

    preamble = r"""
\documentclass[letterpaper,11pt]{article}

\usepackage{latexsym}
\usepackage[empty]{fullpage} 
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

\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-0.5in} 
""" + text_height_declaration + r"""         

\clubpenalty=8000
\widowpenalty=8000
\tolerance=1000
\setlength{\emergencystretch}{1.5em}

\urlstyle{same}
\raggedbottom 
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

\pdfgentounicode=1

\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
"""

    doc_start = r"\begin{document}" + f"\n{page_height_setting_for_doc_start}"

    personal_info_data = data.get("Personal Information") or data.get("contact")
    name_from_data = data.get("name") 
    if name_from_data and personal_info_data and not personal_info_data.get('name'):
        personal_info_data['name'] = name_from_data 

    objective_data = data.get("Summary/Objective") or data.get("objective") or data.get("summary")
    education_data = data.get("Education") or data.get("education")
    experience_data = data.get("Experience") or data.get("work_experience")
    projects_data = data.get("Projects") or data.get("projects")
    skills_data = data.get("Skills") or data.get("skills")
    languages_data = data.get("Languages") or data.get("languages")
    
    certifications_data = data.get("certifications")
    awards_data = data.get("awards")
    
    involvement_data = data.get("involvement") or data.get("leadership") 
    misc_data = data.get("Misc") 

    header_tex = _generate_header_section(personal_info_data)
    objective_tex = _generate_objective_section(objective_data)
    education_tex = _generate_education_section(education_data)
    experience_tex = _generate_experience_section(experience_data)
    projects_tex = _generate_projects_section(projects_data)
    skills_tex = _generate_skills_section(skills_data)
    languages_tex = _generate_languages_section(languages_data)
    certifications_tex = _generate_certifications_section(certifications_data)
    awards_tex = _generate_awards_section(awards_data)
    
    involvement_tex = None
    if involvement_data: 
        involvement_tex = _generate_involvement_section(involvement_data)
    elif misc_data: 
        involvement_tex = _generate_misc_leadership_section(misc_data)

    content_parts = [
        preamble,
        doc_start,
        header_tex,
        objective_tex,
        education_tex,
        experience_tex,
        projects_tex,
        skills_tex,
        languages_tex,
        certifications_tex,
        awards_tex,
        involvement_tex,
        r"\end{document}"
    ]
    
    full_latex_doc = "\n".join(filter(None, content_parts))
    
    # +++ Instruction A: Apply sanitize_latex +++
    full_latex_doc = "\n".join(sanitize_latex(full_latex_doc.splitlines()))
    # +++ End Instruction A +++
    
    return full_latex_doc