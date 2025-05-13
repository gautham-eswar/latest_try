import dotenv # Import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()

from typing import Dict, Any, Optional, List, Tuple
import re
import openai
import os
import json
import hashlib

# Default page height if not specified by the generator (e.g. if auto-sizing is off and no specific height is given)
DEFAULT_TEMPLATE_PAGE_HEIGHT_INCHES = 11.0 

# Cache for OpenAI API responses
API_CACHE: Dict[str, Any] = {}
OPENAI_CLIENT: Optional[openai.OpenAI] = None # Store the client instance
OPENAI_API_KEY_LOADED = False # Flag to check if API key was successfully loaded

def _initialize_openai_client() -> bool:
    """Initializes the OpenAI client if not already done. Returns True if successful or already initialized."""
    global OPENAI_CLIENT, OPENAI_API_KEY_LOADED
    if OPENAI_CLIENT is not None and OPENAI_API_KEY_LOADED:
        return True
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # Only print warning once, or find a better way to log this if it becomes noisy.
        # For now, let's assume it's okay to print if called when client is None.
        if OPENAI_CLIENT is None: # Avoid repeated warnings if called multiple times without key
            print("AI HINT: OPENAI_API_KEY environment variable not set. Skill/metric highlighting will be skipped.")
        OPENAI_API_KEY_LOADED = False
        return False
    
    try:
        OPENAI_CLIENT = openai.OpenAI(api_key=api_key)
        OPENAI_API_KEY_LOADED = True
        print("AI HINT: OpenAI client initialized successfully for skill/metric highlighting.")
        return True
    except Exception as e:
        if OPENAI_CLIENT is None: # Avoid repeated warnings
            print(f"AI HINT: Failed to initialize OpenAI client: {e}. Skill/metric highlighting will be skipped.")
        OPENAI_API_KEY_LOADED = False
        return False

def format_date_range(start_date: Optional[str], end_date: Optional[str]) -> str:
    """Format start and end dates into a consistent date range string."""
    if not start_date and not end_date:
        return ""
        
    formatted_start = fix_latex_special_chars(start_date) if start_date else ""
    formatted_end = fix_latex_special_chars(end_date) if end_date else ""
    
    # Check if end_date is "present" (case insensitive)
    if formatted_end and formatted_end.lower() == "present":
        formatted_end = "Present"
        
    if formatted_start and formatted_end:
        return f"{formatted_start} -- {formatted_end}"
    elif formatted_start:
        return formatted_start
    elif formatted_end:
        return formatted_end
    else:
        return ""

def fix_latex_special_chars(text: Optional[Any]) -> str:
    """
    Escapes LaTeX special characters in a given string.
    Also converts None to an empty string.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text) # Ensure it's a string

    # Order of replacements is critical.
    # Replace backslash first, then other characters including percent.
    replacements = [
        ("\\", r"\textbackslash{}"), # Must be first
        ("&", r"\&"),
        ("%", r"\%"), # Direct replacement for percent
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"), # Standard tilde (U+007E)
        ("^", r"\textasciicircum{}"),
        ("∼", r"\textasciitilde{}"), # Tilde operator (U+223C) -> also use textasciitilde
    ]

    for old, new in replacements:
        text = text.replace(old, new)
        
    return text


def _generate_header_section(personal_info: Optional[Dict[str, Any]]) -> Optional[str]:
    if not personal_info:
        return None
    
    name = fix_latex_special_chars(personal_info.get("name"))
    email = personal_info.get("email")  # Raw email, will handle special chars in href
    phone = fix_latex_special_chars(personal_info.get("phone"))
    
    # Get raw values for URLs, with a fallback for LinkedIn
    raw_linkedin = personal_info.get("linkedin") or personal_info.get("website/LinkedIn")
    raw_github = personal_info.get("github")
    raw_website = personal_info.get("website")
    
    location = fix_latex_special_chars(personal_info.get("location"))

    lines = []
    if name:
        lines.append(r"\begin{center}")
        # Make name larger, bolder, and with appropriate spacing
        lines.append(f"    \\textbf{{\\LARGE \\scshape {name}}} \\\\ \\vspace{{4pt}}")
    
    contact_parts = []
    if phone:
        contact_parts.append(phone)
    if email:
        email_display = email.replace("_", r"\_")
        contact_parts.append(f"\\href{{mailto:{email}}}{{\\underline{{{email_display}}}}}")
    
    if raw_linkedin:
        linkedin_display = fix_latex_special_chars(raw_linkedin)
        linkedin_url = raw_linkedin # Use raw value for URL
        if not linkedin_url.startswith("http"):
            linkedin_url = f"https://{linkedin_url}"
        contact_parts.append(f"\\href{{{linkedin_url}}}{{\\underline{{LinkedIn}}}}")
    
    if raw_github:
        github_display = fix_latex_special_chars(raw_github)
        github_url = raw_github # Use raw value for URL
        if not github_url.startswith("http"):
            github_url = f"https://{github_url}"
        contact_parts.append(f"\\href{{{github_url}}}{{\\underline{{GitHub}}}}")
        
    if raw_website:
        website_display = "Portfolio"  # Use a cleaner display text
        website_url = raw_website # Use raw value for URL
        if not website_url.startswith("http"): # Basic check for protocol
             website_url = f"http://{website_url}"
        contact_parts.append(f"\\href{{{website_url}}}{{\\underline{{{website_display}}}}}")

    # Add location to contact_parts if it exists
    if location:
        contact_parts.append(location)

    if contact_parts:
        lines.append(f"    \\small {' $|$ '.join(contact_parts)} \\vspace{{1pt}}")
    
    if name: # Only add end{center} if we started it
        lines.append(r"\end{center}")
        lines.append(r"\vspace{-8pt}") # Reduce space after header
        lines.append("") # Add a newline for spacing

    return "\n".join(lines) if lines else None


def _generate_objective_section(objective: Optional[str]) -> Optional[str]:
    if not objective: return None
    return fr"""\section*{{Summary}} % Using section* for unnumbered
  {fix_latex_special_chars(objective)}
"""

def _parse_location_dict(location_data: Any) -> str:
    """Helper function to parse a location, which can be a string or a dict."""
    if isinstance(location_data, dict):
        city = location_data.get("city")
        state = location_data.get("state")
        # country = location_data.get("country") # Optional: include country if needed
        parts = []
        if city and isinstance(city, str):
            parts.append(city)
        if state and isinstance(state, str):
            parts.append(state)
        return fix_latex_special_chars(", ".join(parts))
    elif isinstance(location_data, str):
        return fix_latex_special_chars(location_data)
    return "" # Return empty string if None or other type

def _generate_education_section(education_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not education_list: return None
    content_lines = []
    for edu in education_list:
        uni = fix_latex_special_chars(edu.get("institution") or edu.get("university"))
        # MODIFIED location handling
        raw_loc = edu.get("location")
        loc_str = _parse_location_dict(raw_loc)
        
        degree_parts = [fix_latex_special_chars(edu.get("degree"))]
        if edu.get("specialization"): degree_parts.append(fix_latex_special_chars(edu.get("specialization")))
        degree_str = ", ".join(filter(None, degree_parts))
        start_date = fix_latex_special_chars(edu.get("start_date", ""))
        end_date = fix_latex_special_chars(edu.get("end_date", ""))
        dates = f"{start_date} -- {end_date}" if start_date or end_date else ""
        if end_date and end_date.lower() == 'present': dates = f"{start_date} -- Present"
        elif not end_date and start_date: dates = start_date

        if uni and degree_str:
            content_lines.append(r"    \resumeSubheading")
            content_lines.append(f"      {{{uni}}}{{{loc_str}}}") # Use parsed loc_str
            content_lines.append(f"      {{{degree_str}}}{{{dates}}}")
            gpa = edu.get("gpa")
            honors = fix_latex_special_chars(edu.get("honors"))
            details_parts = []
            if gpa: details_parts.append(f"GPA: {fix_latex_special_chars(gpa)}")
            if honors: details_parts.append(f"Honors: {honors}")
            if details_parts: content_lines.append(f"    \\resumeSubSubheading{{{', '.join(details_parts)}}}{{}}")
            
            additional_info = edu.get("additional_info")
            relevant_coursework = edu.get("relevant_coursework")
            if additional_info:
                content_lines.append(r"      \resumeItemListStart")
                content_lines.append(f"        \\resumeItem{{{fix_latex_special_chars(additional_info)}}}")
                content_lines.append(r"      \resumeItemListEnd")
            elif relevant_coursework and isinstance(relevant_coursework, list):
                content_lines.append(r"      \resumeItemListStart")
                courses_str = ", ".join(fix_latex_special_chars(c) for c in relevant_coursework)
                content_lines.append(f"        \\resumeItem{{Relevant Coursework: {courses_str}}}")
                content_lines.append(r"      \resumeItemListEnd")
    if not content_lines: return None
    final_latex_parts = [r"\section{Education}", r"  \resumeSubHeadingListStart"] + content_lines + [r"  \resumeSubHeadingListEnd", ""]
    return "\n".join(final_latex_parts)

def _generate_experience_section(experience_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not experience_list:
        return None
    
    lines = []
    lines.append(r"\section{Experience}")
    
    for experience in experience_list:
        if not isinstance(experience, dict):
            print(f"Warning: Experience item is not a dictionary: {experience}")
            continue
            
        company = fix_latex_special_chars(experience.get("company", ""))
        position = fix_latex_special_chars(experience.get("position", ""))
        location = fix_latex_special_chars(experience.get("location", ""))
        
        start_date = experience.get("startDate", "")
        end_date = experience.get("endDate", "")
        date_str = format_date_range(start_date, end_date)
        
        # Handle description - ensure it's a list
        description = experience.get("description", [])
        if isinstance(description, str):
            # If it's a single string, convert to list
            description_list = [description]
        elif isinstance(description, list):
            description_list = description
        else:
            description_list = []
            
        # Begin the experience entry
        if company:
            lines.append(r"\resumeSubheading")
            lines.append(f"  {{{position}}}")
            lines.append(f"  {{{company}}}")
            
            if date_str:
                lines.append(f"  {{{date_str}}}")
            else:
                lines.append(r"  {}")
                
            if location:
                lines.append(f"  {{{location}}}")
            else:
                lines.append(r"  {}")
                
            # Add descriptions as bullet points with enhanced formatting
            if description_list:
                lines.append(r"  \begin{itemize}[leftmargin=*,labelsep=1.5mm,nosep]")
                for desc in description_list:
                    if desc:  # Check that the description isn't empty
                        # Enhance bullet formatting with better text
                        formatted_desc = fix_latex_special_chars(desc)
                        lines.append(f"    \\item {formatted_desc}")
                lines.append(r"  \end{itemize}")
                
            # Add a small space between experiences
            lines.append(r"  \vspace{2pt}")
    
    return "\n".join(lines) if lines else None

def _generate_projects_section(projects_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not projects_list:
        return None
    
    lines = []
    lines.append(r"\section{Projects}")
    
    for project in projects_list:
        if not isinstance(project, dict):
            print(f"Warning: Project item is not a dictionary: {project}")
            continue
            
        title = fix_latex_special_chars(project.get("title", ""))
        organization = fix_latex_special_chars(project.get("organization", ""))
        link = project.get("link", "")
        
        start_date = project.get("startDate", "")
        end_date = project.get("endDate", "")
        date_str = format_date_range(start_date, end_date)
        
        # Handle description - ensure it's a list
        description = project.get("description", [])
        if isinstance(description, str):
            # If it's a single string, convert to list
            description_list = [description]
        elif isinstance(description, list):
            description_list = description
        else:
            description_list = []
            
        # Begin the project entry
        if title:
            lines.append(r"\resumeSubheading")
            
            # Include hyperlink if provided
            if link and link.strip():
                title_with_link = f"\\href{{{link}}}{{{title}}}"
                lines.append(f"  {{{title_with_link}}}")
            else:
                lines.append(f"  {{{title}}}")
                
            if organization:
                lines.append(f"  {{{organization}}}")
            else:
                lines.append(r"  {}")
                
            if date_str:
                lines.append(f"  {{{date_str}}}")
            else:
                lines.append(r"  {}")
                
            # Empty placeholder for fourth position
            lines.append(r"  {}")
                
            # Add descriptions as bullet points with enhanced formatting
            if description_list:
                lines.append(r"  \begin{itemize}[leftmargin=*,labelsep=1.5mm,nosep]")
                for desc in description_list:
                    if desc:  # Check that the description isn't empty
                        formatted_desc = fix_latex_special_chars(desc)
                        lines.append(f"    \\item {formatted_desc}")
                lines.append(r"  \end{itemize}")
                
            # Add a small space between projects
            lines.append(r"  \vspace{2pt}")
    
    return "\n".join(lines) if lines else None


def _generate_skills_section(skills_data: Optional[Dict[str, Any]]) -> Optional[str]:
    """Generate a well-formatted skills section with categories and subcategories."""
    if not skills_data:
        return None

    lines = []
    lines.append(r"\section{Skills}")
    
    # If skills_data is a dictionary with categories
    if isinstance(skills_data, dict):
        # Skip rendering if no actual skills are found
        if not skills_data:
            return None
            
        # First approach: Use a table-like structure for skills
        lines.append(r"\begin{tabular}{@{}p{0.18\textwidth}p{0.82\textwidth}@{}}")
        
        # Process each category
        for category, subcategories in skills_data.items():
            category_name = fix_latex_special_chars(category)
            
            # Skip empty categories
            if not subcategories:
                continue
                
            if isinstance(subcategories, dict):
                # Handle nested subcategories
                all_skills = []
                
                for subcategory, skills_list in subcategories.items():
                    if skills_list and isinstance(skills_list, list):
                        formatted_skills = [fix_latex_special_chars(skill) for skill in skills_list if skill]
                        if formatted_skills:
                            all_skills.extend(formatted_skills)
                
                if all_skills:
                    skills_text = ", ".join(all_skills)
                    lines.append(f"\\textbf{{{category_name}}} & {skills_text} \\\\")
                    lines.append(f"& \\\\[-0.8em]")  # Add small spacing between categories
            
            elif isinstance(subcategories, list):
                # Handle flat list of skills
                formatted_skills = [fix_latex_special_chars(skill) for skill in subcategories if skill]
                if formatted_skills:
                    skills_text = ", ".join(formatted_skills)
                    lines.append(f"\\textbf{{{category_name}}} & {skills_text} \\\\")
                    lines.append(f"& \\\\[-0.8em]")  # Add small spacing between categories
        
        lines.append(r"\end{tabular}")
        
    # If skills_data is a list, format as a simple comma-separated list
    elif isinstance(skills_data, list):
        formatted_skills = [fix_latex_special_chars(skill) for skill in skills_data if skill]
        if formatted_skills:
            skills_text = ", ".join(formatted_skills)
            lines.append(skills_text)
    
    return "\n".join(lines) if lines else None


def _generate_languages_section(languages_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not languages_list: return None
    lang_items = []
    for lang_data in languages_list:
        name = fix_latex_special_chars(lang_data.get("name"))
        proficiency = fix_latex_special_chars(lang_data.get("proficiency"))
        if name: # Only add if name is present
            item_str = name
            if proficiency: item_str += f" ({proficiency})"
            lang_items.append(item_str)
    if not lang_items: return None
    final_latex_parts = [r"\section{Languages}", r" \begin{itemize}[leftmargin=0.15in, label={}]"]
    final_latex_parts.append(f"    \\small{{\\item{{{', '.join(lang_items)}}}}}")
    final_latex_parts.extend([r" \end{itemize}", ""])
    return "\n".join(final_latex_parts)


def _generate_certifications_section(cert_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not cert_list: return None
    content_lines = []
    for cert in cert_list:
        name = fix_latex_special_chars(cert.get("certification"))
        if not name: continue # Skip if no name
        institution = fix_latex_special_chars(cert.get("institution"))
        date = fix_latex_special_chars(cert.get("date"))
        content_lines.extend([
            r"    \resumeSubheading",
            f"      {{{name}}}{{{date}}}",
            f"      {{{institution}}}{{}}"
        ])
    if not content_lines: return None
    final_latex_parts = [r"\section{Certifications}", r"  \resumeSubHeadingListStart"]
    final_latex_parts.extend(content_lines)
    final_latex_parts.extend([r"  \resumeSubHeadingListEnd", ""])
    return "\n".join(final_latex_parts)

def _generate_awards_section(awards_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not awards_list: return None
    content_lines = []
    for award in awards_list:
        title = fix_latex_special_chars(award.get("title"))
        if not title: continue
        issuer = fix_latex_special_chars(award.get("issuer"))
        date = fix_latex_special_chars(award.get("date"))
        description = fix_latex_special_chars(award.get("description"))
        content_lines.extend([
            r"    \resumeSubheading",
            f"      {{{title}}}{{{date}}}",
            f"      {{{issuer}}}{{}}"
        ])
        if description:
            content_lines.extend([
                r"      \resumeItemListStart",
                f"        \\resumeItem{{{description}}}",
                r"      \resumeItemListEnd"
            ])
    if not content_lines: return None
    final_latex_parts = [r"\section{Awards}", r"  \resumeSubHeadingListStart"]
    final_latex_parts.extend(content_lines)
    final_latex_parts.extend([r"  \resumeSubHeadingListEnd", ""])
    return "\n".join(final_latex_parts)


def _generate_involvement_section(involvement_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not involvement_list: return None
    content_lines = []
    for item in involvement_list:
        organization = fix_latex_special_chars(item.get("organization"))
        position = fix_latex_special_chars(item.get("position"))
        if not organization and not position: continue
            
        date_val = item.get("date") # Get raw date value
        dates_str = ""
        if isinstance(date_val, dict): # If it's a dictionary, process start/end
            start = fix_latex_special_chars(date_val.get("start_date"))
            end = fix_latex_special_chars(date_val.get("end_date"))
            dates_str = f"{start} -- {end}" if start or end else ""
            if end and end.lower() == 'present': 
                dates_str = f"{start} -- Present"
            elif not end and start: 
                dates_str = start
        elif isinstance(date_val, str): # If it's a string, use it directly
            dates_str = fix_latex_special_chars(date_val)
        # If date_val is None or some other type, dates_str remains ""
            
        content_lines.extend([
            r"    \resumeSubheading",
            f"      {{{position}}}{{{dates_str}}}",
            f"      {{{organization}}}{{}}"
        ])
        responsibilities = item.get("responsibilities")
        if responsibilities and isinstance(responsibilities, list):
            content_lines.append(r"      \resumeItemListStart")
            for resp in responsibilities:
                if resp: content_lines.append(f"        \\resumeItem{{{fix_latex_special_chars(resp)}}}")
            content_lines.append(r"      \resumeItemListEnd")
    if not content_lines: return None
    final_latex_parts = [r"\section{Leadership \& Involvement}", r"  \resumeSubHeadingListStart"]
    final_latex_parts.extend(content_lines)
    final_latex_parts.extend([r"  \resumeSubHeadingListEnd", ""])
    return "\n".join(final_latex_parts)

def _generate_misc_leadership_section(misc_data: Optional[Dict[str, Any]]) -> Optional[str]:
    print(f"AI HINT: _generate_misc_leadership_section received misc_data of type: {type(misc_data)}, value: {misc_data}") # Detailed log
    if not misc_data or not isinstance(misc_data, dict):
        print(f"AI HINT: misc_data is not a valid dict or is empty. Type: {type(misc_data)}. Returning None.")
        return None

    processed_any_content = False
    leadership_data = misc_data.get("Leadership")
    if not leadership_data or not isinstance(leadership_data, dict): return None
    content_lines = []
    for event_name, details in leadership_data.items():
        name = fix_latex_special_chars(event_name)
        if not name: continue
            
        dates_val = details.get("dates") # Get raw dates value
        dates_str = ""
        if isinstance(dates_val, dict): # If it's a dictionary, process start/end
            start_date = fix_latex_special_chars(dates_val.get("start_date"))
            end_date = fix_latex_special_chars(dates_val.get("end_date"))
            dates_str = f"{start_date} -- {end_date}" if start_date or end_date else ""
            if end_date and end_date.lower() == 'present': 
                dates_str = f"{start_date} -- Present"
            elif not end_date and start_date: 
                dates_str = start_date
        elif isinstance(dates_val, str): # If it's a string, use it directly
            dates_str = fix_latex_special_chars(dates_val)
        # If dates_val is None or some other type, dates_str remains ""
        
        # Use the new single-line subheading command
        content_lines.append(fr"    \resumeSubheadingSingleLine{{{name}}}{{{dates_str}}}")

        responsibilities = details.get("responsibilities/achievements")
        if responsibilities and isinstance(responsibilities, list):
            content_lines.append(r"      \resumeItemListStart")
            for resp in responsibilities:
                if resp: content_lines.append(f"        \\resumeItem{{{fix_latex_special_chars(resp)}}}")
            content_lines.append(r"      \resumeItemListEnd")
            processed_any_content = True
    if not processed_any_content: return None
    final_latex_parts = [r"\section{Leadership \& Activities}", r"  \resumeSubHeadingListStart"]
    final_latex_parts.extend(content_lines)
    final_latex_parts.extend([r"  \resumeSubHeadingListEnd", ""])
    return "\n".join(final_latex_parts)


def generate_latex_document(resume_data: Dict[str, Any], style_config: Optional[Dict[str, Any]] = None) -> Tuple[str, List[str]]:
    if not resume_data:
        return "", ["Error: Empty resume data provided"]

    section_processing_log = []
    
    # Extract personal info
    personal_info = resume_data.get("info") or resume_data.get("personal_information") or resume_data.get("personal_info")
    
    # Extract other section data
    objective_data = resume_data.get("objective") or resume_data.get("summary")
    experience_data = resume_data.get("experience") or resume_data.get("professional_experience") or resume_data.get("work_experience")
    education_data = resume_data.get("education") or resume_data.get("academic_history")
    projects_data = resume_data.get("projects")
    certs_data = resume_data.get("certifications")
    skills_data = resume_data.get("skills")
    langs_data = resume_data.get("languages")
    awards_data = resume_data.get("awards")
    involvement_data = resume_data.get("involvements") or resume_data.get("activities") or resume_data.get("extracurricular")
    
    # Document preamble - setup the document
    document_parts = []
    
    # Enhanced preamble with better formatting options
    document_parts.extend([
        r"\documentclass[11pt,letterpaper]{article}",
        r"",
        r"% Package imports",
        r"\usepackage[empty]{fullpage}",
        r"\usepackage{xcolor}",
        r"\usepackage{hyperref}",
        r"\usepackage{enumitem}",  # For better bullet points
        r"\usepackage[scale=0.85]{geometry}",  # Adjust page margins
        r"\usepackage{fontawesome}",  # For icons if needed
        r"\usepackage{tabularx}",  # For better tables
        r"",
        r"% Configure hyperlinks",
        r"\hypersetup{",
        r"    colorlinks=true,",
        r"    linkcolor=blue,",
        r"    filecolor=magenta,",
        r"    urlcolor=blue,",
        r"}",
        r"",
        r"% Document formatting",
        r"\pagestyle{empty}",
        r"\raggedbottom",
        r"\raggedright",
        r"\setlength{\tabcolsep}{0in}",
        r"",
        r"% Adjust spacing",
        r"\linespread{1.0}",  # Slightly tighter line spacing
        r"\addtolength{\textheight}{0.8in}",  # More content space
        r"",
        r"% Section formatting",
        r"\newcommand{\sectionstyle}[1]{{\Large \textbf{#1}}}",
        r"",
        r"% Section command",
        r"\newcommand{\section}[1]{",
        r"  \vspace{6pt}",
        r"  {\sectionstyle{#1}}",
        r"  \vspace{-6pt}",
        r"  \rule{\textwidth}{0.4pt}",
        r"  \vspace{2pt}",
        r"}",
        r"",
        r"% Subheading formatting for experience, education, etc.",
        r"\newcommand{\resumeSubheading}[4]{",
        r"  \vspace{2pt}",
        r"  \item[]",
        r"    \begin{tabular*}{\textwidth}[t]{l@{\extracolsep{\fill}}r}",
        r"      \textbf{#1} & #3 \\",
        r"      \textit{#2} & \textit{#4} \\",
        r"    \end{tabular*}",
        r"}",
        r"",
        r"% Adjust itemize environment to be tighter",
        r"\setlist[itemize]{leftmargin=*,parsep=0pt,topsep=1pt,partopsep=0pt,label=$\bullet$}",
        r"",
        r"\begin{document}",
    ])
    
    # The rest of the code remains the same
    # ... existing code ...

    # Extract data based on schema (and handle Evelyn.json variations where noted)
    # The schema uses 'contact', Evelyn.json uses 'Personal Information'.
    # The schema uses 'objective' or 'summary', Evelyn.json uses 'Summary/Objective'.
    # The schema uses 'work_experience', Evelyn.json uses 'Experience'.
    # The schema uses 'skills' (dict), Evelyn.json uses 'Skills' (dict with sub-dicts).
    # The schema uses 'languages', Evelyn.json uses 'Languages'.
    # The schema uses 'certifications', Evelyn.json uses 'Certifications/Awards' (potentially mixed).
    # The schema uses 'awards', (see above).
    # The schema uses 'involvement' or 'leadership', Evelyn.json has 'Misc' -> 'Leadership'.

    # DEFENSIVE PROGRAMMING: Safely extract data with type checking for each section

    # Personal Info section
    personal_info_data = data.get("Personal Information") or data.get("contact")
    if personal_info_data and not isinstance(personal_info_data, dict):
        print(f"WARNING: Personal info data is not a dictionary. Type: {type(personal_info_data)}. Skipping.")
        personal_info_data = None
        
    name_from_data = data.get("name") # Top level name from schema.
    if name_from_data and personal_info_data and not personal_info_data.get('name'):
        personal_info_data['name'] = name_from_data # Inject if missing in contact dict

    # Objective/Summary section (string)
    objective_data = data.get("Summary/Objective") or data.get("objective") or data.get("summary")
    
    # Education section (list of dictionaries)
    education_data = data.get("Education") or data.get("education")
    if education_data and not isinstance(education_data, list):
        print(f"WARNING: Education data is not a list. Type: {type(education_data)}. Skipping.")
        education_data = None
        
    # Experience section (list of dictionaries)
    experience_data = data.get("Experience") or data.get("work_experience")
    if experience_data and not isinstance(experience_data, list):
        print(f"WARNING: Experience data is not a list. Type: {type(experience_data)}. Skipping.")
        experience_data = None
        
    # Projects section (list of dictionaries)
    projects_data = data.get("Projects") or data.get("projects")
    if projects_data and not isinstance(projects_data, list):
        print(f"WARNING: Projects data is not a list. Type: {type(projects_data)}. Skipping.")
        projects_data = None
        
    # Skills section (dictionary)
    skills_data = data.get("Skills") or data.get("skills")
    if skills_data and not isinstance(skills_data, dict):
        print(f"WARNING: Skills data is not a dictionary. Type: {type(skills_data)}. Skipping.")
        skills_data = None
        
    # Languages section (list of dictionaries)
    languages_data = data.get("Languages") or data.get("languages")
    if languages_data and not isinstance(languages_data, list):
        print(f"WARNING: Languages data is not a list. Type: {type(languages_data)}. Skipping.")
        languages_data = None
    
    # For certs/awards, Evelyn.json has "Certifications/Awards".
    # Schema has separate "certifications" and "awards".
    # We'll prefer direct keys first.
    certifications_data = data.get("certifications")
    if certifications_data and not isinstance(certifications_data, list):
        print(f"WARNING: Certifications data is not a list. Type: {type(certifications_data)}. Skipping.")
        certifications_data = None
        
    awards_data = data.get("awards")
    if awards_data and not isinstance(awards_data, list):
        print(f"WARNING: Awards data is not a list. Type: {type(awards_data)}. Skipping.")
        awards_data = None
        
    certs_and_awards_mixed = data.get("Certifications/Awards")

    # If specific keys are empty but mixed one exists, we might need to split them.
    # For now, this template won't try to split a mixed list. It will use dedicated lists if present.
    # If only the mixed list is present and non-empty, we might decide to pass it to one
    # or the other, or a combined section. Given the prompt, let's assume separate lists are preferred.

    involvement_data = data.get("involvement") or data.get("leadership") # Schema direct keys
    if involvement_data and not isinstance(involvement_data, list):
        print(f"WARNING: Involvement data is not a list. Type: {type(involvement_data)}. Skipping.")
        involvement_data = None
        
    # Corrected variable name to avoid conflict with outer scope if any
    misc_content_from_data = data.get("Misc") # For Evelyn.json specific "Misc" -> "Leadership"

    print("\n--- Section Generation Log ---")
    section_processing_log = []

    header_tex = _generate_header_section(personal_info_data)
    section_processing_log.append(f"Header section: {'Included' if header_tex else 'Skipped (no data or empty)'}")

    objective_tex = _generate_objective_section(objective_data)
    section_processing_log.append(f"Summary/Objective section: {'Included' if objective_tex else 'Skipped (no data or empty)'}")

    education_tex = _generate_education_section(education_data)
    section_processing_log.append(f"Education section: {'Included' if education_tex else 'Skipped (no data or empty)'}")

    experience_tex = _generate_experience_section(experience_data)
    section_processing_log.append(f"Experience section: {'Included' if experience_tex else 'Skipped (no data or empty)'}")

    projects_tex = _generate_projects_section(projects_data)
    section_processing_log.append(f"Projects section: {'Included' if projects_tex else 'Skipped (no data or empty)'}")

    skills_tex = _generate_skills_section(skills_data)
    section_processing_log.append(f"Skills section: {'Included' if skills_tex else 'Skipped (no data or empty)'}")

    languages_tex = _generate_languages_section(languages_data)
    section_processing_log.append(f"Languages section: {'Included' if languages_tex else 'Skipped (no data or empty)'}")

    certifications_tex = _generate_certifications_section(certifications_data)
    section_processing_log.append(f"Certifications section: {'Included' if certifications_tex else 'Skipped (no data or empty)'}")

    awards_tex = _generate_awards_section(awards_data)
    section_processing_log.append(f"Awards section: {'Included' if awards_tex else 'Skipped (no data or empty)'}")
    
    involvement_tex = None
    if involvement_data: # Prioritize schema's direct key
        involvement_tex = _generate_involvement_section(involvement_data)
        section_processing_log.append(f"Involvement/Leadership section (direct key): {'Included' if involvement_tex else 'Skipped (no data or empty)'}")
    elif misc_content_from_data and isinstance(misc_content_from_data, dict): # Fallback to Misc if it's a dict
        involvement_tex = _generate_misc_leadership_section(misc_content_from_data)
        section_processing_log.append(f"Misc/Leadership section (fallback, was dict): {'Included' if involvement_tex else 'Skipped (no data or empty)'}")
    elif misc_content_from_data: # It exists but is not a dict (e.g., it's a list)
        section_processing_log.append(f"Misc/Leadership section (fallback): Skipped (data found but type was {type(misc_content_from_data)} instead of dict)")
        # involvement_tex remains None
    else:
        section_processing_log.append("Involvement/Leadership/Misc section: Skipped (no relevant data found)")

    print("\n".join(section_processing_log))
    print("--- End Section Generation Log ---\n")

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
    return full_latex_doc, section_processing_log

def extract_highlights_from_resume(resume_data: Dict[str, Any]) -> tuple[List[str], List[str]]:
    """
    Extracts technical skills and metrics from resume bullet points using OpenAI API.

    Args:
        resume_data: The parsed resume JSON data.

    Returns:
        A tuple containing two lists: (technical_skills, metrics).
        Returns ([], []) if highlighting is skipped or an error occurs.
    """
    if not isinstance(resume_data, dict):
        print(f"AI HINT: resume_data is not a dictionary. Type: {type(resume_data)}. Skipping highlighting.")
        return [], []

    if not _initialize_openai_client() or not OPENAI_CLIENT:
        return [], []

    all_bullet_points: List[str] = []

    # Extract from Experience section
    experience_data = resume_data.get("Experience") or resume_data.get("work_experience")
    if experience_data and isinstance(experience_data, list):
        for exp_item in experience_data:
            if isinstance(exp_item, dict):
                responsibilities = exp_item.get("responsibilities") or exp_item.get("responsibilities/achievements")
                if isinstance(responsibilities, list):
                    for resp in responsibilities:
                        if isinstance(resp, str) and resp.strip():
                            all_bullet_points.append(resp.strip())
                elif isinstance(responsibilities, str) and responsibilities.strip():
                    all_bullet_points.append(responsibilities.strip())

    # Extract from Projects section
    projects_data = resume_data.get("Projects") or resume_data.get("projects")
    if projects_data and isinstance(projects_data, list):
        for proj_item in projects_data:
            if isinstance(proj_item, dict):
                description = proj_item.get("description")
                if isinstance(description, list):
                    for desc_item in description:
                        if isinstance(desc_item, str) and desc_item.strip():
                            all_bullet_points.append(desc_item.strip())
                elif isinstance(description, str) and description.strip():
                    all_bullet_points.append(description.strip())
    
    if not all_bullet_points:
        print("AI HINT: No bullet points found in Experience/Projects for highlighting.")
        return [], []

    # Create cache key
    # Sort bullets to ensure consistent hash for the same content regardless of order in JSON
    cache_key_string = "|".join(sorted(all_bullet_points))
    cache_key = hashlib.md5(cache_key_string.encode('utf-8')).hexdigest()

    if cache_key in API_CACHE:
        print(f"AI HINT: Using cached OpenAI response for key {cache_key[:8]}...")
        cached_data = API_CACHE[cache_key]
        return cached_data.get("technical_skills", []), cached_data.get("metrics", [])

    prompt = f"""
You are a specialized resume parser focusing on identifying two distinct categories from resume bullet points:

1. TECHNICAL_SKILLS: Hard technical skills, tools, technologies, programming languages, methodologies, frameworks, platforms, systems, and specialized knowledge domains. Include only specific, concrete technical terms.

2. METRICS: Quantitative achievements, percentages, numerical impacts, monetary values, time savings, efficiency improvements, and other quantifiable results. Include the full metric phrase (e.g., "increased efficiency by 40%", "$1.2M in savings", "reduced processing time by 20 hours").

Analyze the following resume bullet points and return ONLY a JSON object with two arrays:
{{
  "technical_skills": ["skill1", "skill2", ...],
  "metrics": ["metric phrase 1", "metric phrase 2", ...]
}}

TECHNICAL_SKILLS should be individual terms (e.g., "Python", "SQL", "TensorFlow"), while METRICS should be complete achievement phrases.

DO NOT include soft skills, generic business terms, or non-technical concepts in the technical_skills list.
ONLY include phrases with specific numerical values or percentages in the metrics list.

Resume bullet points:
{json.dumps(all_bullet_points, indent=2)}
"""
    
    print(f"AI HINT: Calling OpenAI API for {len(all_bullet_points)} bullet points...")
    try:
        response = OPENAI_CLIENT.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, # Low temperature for factual extraction
            response_format={"type": "json_object"} # Ensure JSON output if model supports
        )
        
        content = response.choices[0].message.content
        if content is None:
            print("AI HINT: OpenAI API returned empty content. Skipping highlighting.")
            return [], []
            
        parsed_json = json.loads(content)
        
        tech_skills = parsed_json.get("technical_skills", [])
        metrics = parsed_json.get("metrics", [])
        
        if not isinstance(tech_skills, list) or not all(isinstance(s, str) for s in tech_skills):
            print("AI HINT: 'technical_skills' from OpenAI is not a list of strings. Skipping.")
            tech_skills = [] # Default to empty if format is wrong
        if not isinstance(metrics, list) or not all(isinstance(m, str) for m in metrics):
            print("AI HINT: 'metrics' from OpenAI is not a list of strings. Skipping.")
            metrics = [] # Default to empty if format is wrong

        API_CACHE[cache_key] = {"technical_skills": tech_skills, "metrics": metrics}
        print(f"AI HINT: OpenAI call successful. Found {len(tech_skills)} skills, {len(metrics)} metrics.")
        return tech_skills, metrics

    except openai.APIError as e:
        print(f"AI HINT: OpenAI API Error: {e}. Skipping highlighting.")
    except json.JSONDecodeError as e:
        print(f"AI HINT: Error decoding JSON response from OpenAI: {e}. Response: {content[:500]}... Skipping highlighting.")
    except Exception as e:
        print(f"AI HINT: An unexpected error occurred during OpenAI call: {e}. Skipping highlighting.")
    
    return [], []

def _format_text_segment(text_segment_raw: str, all_identified_skills: List[str]) -> str:
    """
    Formats a raw text segment by bolding specified skills within it and escaping all text for LaTeX.
    Args:
        text_segment_raw: The raw text string (e.g., a metric phrase or a part of a bullet).
        all_identified_skills: A list of all unique skill strings identified by OpenAI.
    Returns:
        A LaTeX-ready string with specified skills bolded and all parts correctly escaped.
    """
    parts = []
    current_pos = 0

    # Find all occurrences of skills to bold within this specific segment
    # Order skills by length (descending) to handle cases like "Python" vs "Python 3" if both were skills.
    skill_highlights_in_segment = []
    for skill in sorted(all_identified_skills, key=len, reverse=True):
        for match in re.finditer(re.escape(skill), text_segment_raw):
            # Ensure this skill doesn't overlap with an already found longer skill match
            # This basic check helps but true non-overlapping requires more complex logic if skills can overlap
            # For now, assuming skills identified by OpenAI are distinct enough or longest match rule is sufficient.
            is_sub_match_of_existing = False
            for sh in skill_highlights_in_segment:
                if match.start() >= sh['start'] and match.end() <= sh['end'] and (match.start() != sh['start'] or match.end() != sh['end']):
                    is_sub_match_of_existing = True
                    break
            if not is_sub_match_of_existing:
                 # Remove any existing highlights that are sub-matches of the current one
                skill_highlights_in_segment = [sh for sh in skill_highlights_in_segment 
                                               if not (sh['start'] >= match.start() and sh['end'] <= match.end() and 
                                                       (sh['start'] != match.start() or sh['end'] != match.end()))]
                skill_highlights_in_segment.append({'start': match.start(), 'end': match.end(), 'text': skill})
    
    # Sort by start position to reconstruct the string
    skill_highlights_in_segment.sort(key=lambda x: x['start'])
    
    # Filter out overlapping skill highlights, keeping the one that appeared first (implicitly longest due to sort order above)
    final_skill_highlights = []
    last_highlight_end = -1
    for hl in skill_highlights_in_segment:
        if hl['start'] >= last_highlight_end:
            final_skill_highlights.append(hl)
            last_highlight_end = hl['end']

    last_processed_end = 0
    for hl in final_skill_highlights:
        if hl['start'] > last_processed_end:
            parts.append(fix_latex_special_chars(text_segment_raw[last_processed_end:hl['start']]))
        parts.append(f"\\textbf{{{fix_latex_special_chars(hl['text'])}}}")
        last_processed_end = hl['end']
    
    if last_processed_end < len(text_segment_raw):
        parts.append(fix_latex_special_chars(text_segment_raw[last_processed_end:]))
        
    return "".join(parts)

def format_bullet_with_highlights(bullet_text_raw: str, all_skills: List[str], all_metrics: List[str]) -> str:
    """
    Formats a raw bullet point string by applying bold to skills and italics to metrics.
    Skills within metrics are also bolded.
    Args:
        bullet_text_raw: The raw text of the bullet point.
        all_skills: A list of all unique skill strings identified by OpenAI.
        all_metrics: A list of all unique metric strings identified by OpenAI.
    Returns:
        A LaTeX-formatted string for the bullet point.
    """
    if not bullet_text_raw.strip():
        return "" # Should not happen if bullets are pre-stripped

    # Identify all top-level highlight segments (metrics and skills not inside other captured metrics)
    # Each element: {'start': int, 'end': int, 'text': str_raw, 'type': 'metric'|'skill'}
    highlights = []
    
    # 1. Find all metric occurrences
    for metric_raw in sorted(all_metrics, key=len, reverse=True): # Longest first
        for match in re.finditer(re.escape(metric_raw), bullet_text_raw):
            highlights.append({'start': match.start(), 'end': match.end(), 'text': metric_raw, 'type': 'metric'})
            
    # 2. Find all skill occurrences
    for skill_raw in sorted(all_skills, key=len, reverse=True): # Longest first
        for match in re.finditer(re.escape(skill_raw), bullet_text_raw):
            highlights.append({'start': match.start(), 'end': match.end(), 'text': skill_raw, 'type': 'skill'})
            
    # Sort all found highlights: by start index, then by length (longest first), then by type (metric preferred over skill for exact same span)
    highlights.sort(key=lambda x: (x['start'], -(x['end'] - x['start']), 0 if x['type'] == 'metric' else 1))
    
    # Filter for a set of non-overlapping highlights. Longest, then metric-preferred, takes precedence.
    final_non_overlapping_highlights = []
    covered_indices = [False] * len(bullet_text_raw)
    
    for hl in highlights:
        # Check if any part of this highlight is already covered by a previously selected one
        if not any(covered_indices[i] for i in range(hl['start'], hl['end'])):
            final_non_overlapping_highlights.append(hl)
            for i in range(hl['start'], hl['end']): # Mark this region as covered
                covered_indices[i] = True
                
    # Sort the chosen highlights by start position for sequential processing
    final_non_overlapping_highlights.sort(key=lambda x: x['start'])
    
    # Build the final string
    result_parts = []
    current_pos = 0
    for hl_to_apply in final_non_overlapping_highlights:
        # Append text before this highlight
        if hl_to_apply['start'] > current_pos:
            result_parts.append(fix_latex_special_chars(bullet_text_raw[current_pos:hl_to_apply['start']]))
        
        # Process and append the highlight itself
        if hl_to_apply['type'] == 'metric':
            # The metric text (hl_to_apply['text']) needs skills within it bolded
            # all_skills contains all skills identified from the entire resume batch
            metric_content_with_bolded_skills = _format_text_segment(hl_to_apply['text'], all_skills)
            result_parts.append(f"\\textit{{{metric_content_with_bolded_skills}}}")
        elif hl_to_apply['type'] == 'skill':
            # This is a skill that was not part of any chosen metric
            # Its text itself just needs to be escaped and bolded
            result_parts.append(f"\\textbf{{{fix_latex_special_chars(hl_to_apply['text'])}}}")
            
        current_pos = hl_to_apply['end']
        
    # Append any remaining text after the last highlight
    if current_pos < len(bullet_text_raw):
        result_parts.append(fix_latex_special_chars(bullet_text_raw[current_pos:]))
        
    return "".join(result_parts)

# Functions for formatting will go here next (_format_text_segment, format_bullet_with_highlights)

# --- Minimal test for the template if run directly (not typical use) ---
if __name__ == '__main__':
    # Sample data structure (simplified, matching some keys from schema and Evelyn.json)
    sample_resume_data = {
        "Personal Information": {
            "name": "Ruo-Yi Evelyn Liang",
            "email": "ruoyi_liang@berkeley.edu",
            "phone": "(510) 282-2716",
            "linkedin": "linkedin.com/in/Evelyn_Liang", # Assume schema wants full URL or just handle
            "location": "Berkeley, CA",
            "github": "github.com/evelyn"
        },
        "Summary/Objective": "Data Science Meets Product Strategy—Turning Analytics into Action. & a test of _ and % and $ and # and { and } and \\\\ and ~ and ^",
        "Education": [
            {
                "university": "University of California, Berkeley",
                "location": "Berkeley, CA",
                "degree": "Master of Analytics",
                "specialization": "IEOR, College of Engineering",
                "start_date": "Aug 2025",
                "end_date": "Present",
                "gpa": "3.7/4.0",
                "additional_info": "Courses: Machine Learning, Optimization, Design of Databases."
            },
            {
                "university": "National Taiwan University (NTU)",
                "degree": "Bachelor of Business Administration",
                "start_date": "June 2024", # No end date
                "gpa": "3.8/4.0",
                "relevant_coursework": ["Data Analysis", "Project Management"]
            }
        ],
        "Experience": [ # work_experience
            {
                "company": "Shopee Pte. Ltd.",
                "title": "Data Analysis Intern", # position
                "location": "Taipei, Taiwan",
                "dates": {"start_date": "June 2023", "end_date": "Dec 2023"},
                "responsibilities/achievements": [ # responsibilities
                    "Monitored performance & saved 5% costs.",
                    "Increased 2% sales via A/B testing."
                ]
            }
        ],
        "Projects": [
            {
                "title": "Capstone - Google Case Competition",
                "description": "Achieved a 16% profit boost.",
                "technologies_used": "Linear Programming", # technologies
                "date": "Spring 2023"
            }
        ],
        "Skills": { # skills (dict of categories to lists)
            "Technical Skills": {
                "Programming languages": ["Python", "SQL", "R", "C# & C++"],
                "Data Analysis": ["Pandas", "NumPy", "TensorFlow"],
                "Database": ["MySQL", "MongoDB"]
            },
            "Soft Skills": ["Communication", "Teamwork"]
        },
        "Languages": [ # languages (list of dicts)
            {"name": "Mandarin", "proficiency": "Native"},
            {"name": "English", "proficiency": "Fluent"}
        ],
        "Certifications/Awards": [], # Combined in Evelyn.json, schema is separate
        "certifications": [
            {"certification": "TensorFlow Developer Certificate", "institution": "Google", "date": "2022"}
        ],
        "awards": [
            {"title": "Dean's List", "issuer": "NTU", "date": "2021", "description": "Top 5% of students."}
        ],
        "involvement": [ # Schema's 'involvement' or 'leadership'
            {
                "organization": "Analytics Club", "position": "President",
                "date": {"start_date": "Jan 2022", "end_date": "Dec 2022"},
                "responsibilities": ["Led weekly meetings", "Organized workshops"]
            }
        ],
        "Misc": { # Evelyn.json's structure for leadership
            "Leadership": {
                "Event General Coordinator": {
                    "dates": {"start_date": "Apr 2023", "end_date": "May 2023"},
                    "responsibilities/achievements": ["Led a team of 100+", "Coordinated with 12 sponsors"]
                }
            }
        }
    }

    print("--- Generating LaTeX from sample data (page_height = None) ---")
    latex_output_default, log_default = generate_latex_document(sample_resume_data)
    # print(latex_output_default)
    with open("classic_template_test_default.tex", "w", encoding='utf-8') as f:
        f.write(latex_output_default)
    print("Saved to classic_template_test_default.tex")

    print("\n--- Generating LaTeX from sample data (page_height = 13.0 inches) ---")
    latex_output_custom_h, log_custom_h = generate_latex_document(sample_resume_data, page_height=13.0)
    # print(latex_output_custom_h)
    with open("classic_template_test_custom_h.tex", "w", encoding='utf-8') as f:
        f.write(latex_output_custom_h)
    print("Saved to classic_template_test_custom_h.tex")
    
    print("\n--- Testing fix_latex_special_chars ---")
    test_str = "Text with \\ backslash, {curly braces}, & ampersand, % percent, $ dollar, # hash, _ underscore, ~ tilde, ^ caret."
    print(f"Original: {test_str}")
    print(f"Escaped:  {fix_latex_special_chars(test_str)}")
    
    # Test with a more minimal data set to check optional sections
    minimal_data = {
        "Personal Information": {"name": "Test User", "email": "test@example.com"},
        "Education": [{"university": "Test Uni", "degree": "BS CS"}]
    }
    print("\n--- Generating LaTeX from minimal data ---")
    latex_minimal, log_minimal = generate_latex_document(minimal_data)
    with open("classic_template_test_minimal.tex", "w", encoding='utf-8') as f:
        f.write(latex_minimal)
    print("Saved to classic_template_test_minimal.tex")
