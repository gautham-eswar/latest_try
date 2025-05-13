import dotenv # Import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()

from typing import Dict, Any, Optional, List
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
        lines.append(f"    \\textbf{{\\Huge \\scshape {name}}} \\\\ \\vspace{{1pt}}")
    
    contact_parts = []
    if phone:
        contact_parts.append(phone)
    if email:
        email_display = email.replace("_", r"\_")
        contact_parts.append(f"\\href{{mailto:{email}}}{{{email_display}}}")
    
    if raw_linkedin:
        linkedin_display = fix_latex_special_chars(raw_linkedin)
        linkedin_url = raw_linkedin # Use raw value for URL
        if not linkedin_url.startswith("http"):
            linkedin_url = f"https://{linkedin_url}"
        contact_parts.append(f"\\href{{{linkedin_url}}}{{{linkedin_display}}}")
    
    if raw_github:
        github_display = fix_latex_special_chars(raw_github)
        github_url = raw_github # Use raw value for URL
        if not github_url.startswith("http"):
            github_url = f"https://{github_url}"
        contact_parts.append(f"\\href{{{github_url}}}{{{github_display}}}")
        
    if raw_website:
        website_display = fix_latex_special_chars(raw_website)
        website_url = raw_website # Use raw value for URL
        if not website_url.startswith("http"): # Basic check for protocol
             website_url = f"http://{website_url}"
        contact_parts.append(f"\\href{{{website_url}}}{{{website_display}}}")

    # Add location to contact_parts if it exists
    if location:
        contact_parts.append(location)

    if contact_parts:
        lines.append(f"    \\small {' $|$ '.join(contact_parts)}")
    
    if name: # Only add end{center} if we started it
        lines.append(r"\end{center}")
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

def _generate_experience_section(experience_list: Optional[List[Dict[str, Any]]], identified_skills: List[str], identified_metrics: List[str]) -> Optional[str]:
    if not experience_list: return None
    content_lines = []
    for exp in experience_list:
        company = fix_latex_special_chars(exp.get("company"))
        position = fix_latex_special_chars(exp.get("position") or exp.get("title"))
        if not company and not position: continue
        # MODIFIED location handling
        raw_loc = exp.get("location")
        loc_str = _parse_location_dict(raw_loc)
        
        dates_val = exp.get("dates")
        dates_str = ""
        if isinstance(dates_val, dict):
            start_date = fix_latex_special_chars(dates_val.get("start_date"))
            end_date = fix_latex_special_chars(dates_val.get("end_date"))
            dates_str = f"{start_date} -- {end_date}" if start_date or end_date else ""
            if end_date and end_date.lower() == 'present': 
                dates_str = f"{start_date} -- Present"
            elif not end_date and start_date: 
                dates_str = start_date
        elif isinstance(dates_val, str):
            dates_str = fix_latex_special_chars(dates_val)
        
        content_lines.append(r"    \resumeSubheading")
        content_lines.append(f"      {{{position}}}{{{dates_str}}}")
        content_lines.append(f"      {{{company}}}{{{loc_str}}}") # Use parsed loc_str
        
        responsibilities_raw = exp.get("responsibilities") or exp.get("responsibilities/achievements")
        if responsibilities_raw and isinstance(responsibilities_raw, list):
            # Filter out empty or None responsibilities before processing
            valid_resps = [r for r in responsibilities_raw if isinstance(r, str) and r.strip()]
            if valid_resps:
                content_lines.append(r"      \resumeItemListStart")
                for resp_raw in valid_resps:
                    formatted_resp = format_bullet_with_highlights(resp_raw, identified_skills, identified_metrics)
                    content_lines.append(f"        \\resumeItem{{{formatted_resp}}}")
                content_lines.append(r"      \resumeItemListEnd")
        elif responsibilities_raw and isinstance(responsibilities_raw, str) and responsibilities_raw.strip(): # Handle single string responsibility
            content_lines.append(r"      \resumeItemListStart")
            formatted_resp = format_bullet_with_highlights(responsibilities_raw, identified_skills, identified_metrics)
            content_lines.append(f"        \\resumeItem{{{formatted_resp}}}")
            content_lines.append(r"      \resumeItemListEnd")
            
    if not content_lines: return None
    final_latex_parts = [r"\section{Experience}", r"  \resumeSubHeadingListStart"] + content_lines + [r"  \resumeSubHeadingListEnd", ""]
    return "\n".join(final_latex_parts)

def _generate_projects_section(project_list: Optional[List[Dict[str, Any]]], identified_skills: List[str], identified_metrics: List[str]) -> Optional[str]:
    if not project_list: return None
    content_lines = []
    for proj in project_list:
        title = fix_latex_special_chars(proj.get("title"))
        if not title: continue
            
        dates_val = proj.get("dates") or proj.get("date")
        dates_str = ""
        if isinstance(dates_val, dict):
            start = fix_latex_special_chars(dates_val.get("start_date"))
            end = fix_latex_special_chars(dates_val.get("end_date"))
            dates_str = f"{start} -- {end}" if start or end else ""
            if end and end.lower() == 'present': dates_str = f"{start} -- Present"
            elif not end and start: dates_str = start
        elif isinstance(dates_val, str): dates_str = fix_latex_special_chars(dates_val)
        
        tech_used = proj.get("technologies") or proj.get("technologies_used")
        heading_title_part = f"\\textbf{{{title}}}"
        if tech_used:
            processed_tech = []
            if isinstance(tech_used, list):
                for t in tech_used:
                    if isinstance(t, str) and t.strip():
                        # Apply highlighting to individual tech stack items if they are also in 'identified_skills'
                        # This is a simple direct check; more complex logic might be desired if tech_used items are phrases
                        if t in identified_skills:
                            processed_tech.append(format_bullet_with_highlights(t, identified_skills, identified_metrics))
                        else:
                            processed_tech.append(fix_latex_special_chars(t))
            elif isinstance(tech_used, str) and tech_used.strip():
                if tech_used in identified_skills:
                     processed_tech.append(format_bullet_with_highlights(tech_used, identified_skills, identified_metrics))
                else:
                    processed_tech.append(fix_latex_special_chars(tech_used))
            
            if processed_tech:
                 tech_str = ", ".join(processed_tech)
                 if tech_str: heading_title_part += f" $|$ \\emph{{{tech_str}}}" # Emphasize tech stack
            
        content_lines.append(r"      \resumeProjectHeading")
        content_lines.append(f"          {{{heading_title_part}}}{{{dates_str}}}")
        
        description_raw = proj.get("description")
        if description_raw:
            content_lines.append(r"          \resumeItemListStart")
            if isinstance(description_raw, list):
                valid_descs = [d for d in description_raw if isinstance(d, str) and d.strip()]
                for desc_item_raw in valid_descs:
                    formatted_desc = format_bullet_with_highlights(desc_item_raw, identified_skills, identified_metrics)
                    content_lines.append(f"            \\resumeItem{{{formatted_desc}}}")
            elif isinstance(description_raw, str) and description_raw.strip(): # Single string description
                formatted_desc = format_bullet_with_highlights(description_raw, identified_skills, identified_metrics)
                content_lines.append(f"            \\resumeItem{{{formatted_desc}}}")
            content_lines.append(r"          \resumeItemListEnd")
            
    if not content_lines: return None
    final_latex_parts = [r"\section{Projects}", r"    \resumeSubHeadingListStart"] + content_lines + [r"    \resumeSubHeadingListEnd", ""]
    return "\n".join(final_latex_parts)


def _generate_skills_section(skills_dict: Optional[Dict[str, Any]]) -> Optional[str]:
    if not skills_dict: return None
    technical_skills_data = skills_dict.get("Technical Skills")
    skills_to_process = {}
    if isinstance(technical_skills_data, dict): skills_to_process = technical_skills_data
    elif isinstance(skills_dict, dict) and not technical_skills_data : skills_to_process = skills_dict
    
    category_lines_content = []
    if skills_to_process:
        for category, skills_list in skills_to_process.items():
            if skills_list and isinstance(skills_list, list):
                skills_str = ", ".join(fix_latex_special_chars(s) for s in skills_list if s)
                if skills_str: category_lines_content.append(f"     \\textbf{{{fix_latex_special_chars(category)}}}{{: {skills_str}}}")
    
    soft_skills_list = skills_dict.get("Soft Skills")
    soft_skills_content_str = ""
    if soft_skills_list and isinstance(soft_skills_list, list):
        processed_soft_skills = [fix_latex_special_chars(s) for s in soft_skills_list if s]
        if processed_soft_skills: soft_skills_content_str = f"     \\textbf{{Soft Skills}}{{: {', '.join(processed_soft_skills)}}}"

    if not category_lines_content and not soft_skills_content_str: return None

    lines = [r"\section{Technical Skills}"]
    lines.append(r" \begin{itemize}[leftmargin=0.15in, label={}]")
    lines.append(r"    \small{\item{")
    if category_lines_content:
        lines.append(" \\\\ ".join(category_lines_content))
        if soft_skills_content_str: lines.append(r" \\ ")
    if soft_skills_content_str:
        lines.append(soft_skills_content_str)
    lines.append(r"    }}")
    lines.append(r" \end{itemize}")
    lines.append("")
    return "\n".join(lines)


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
    if not misc_data or not isinstance(misc_data, dict): return None
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
    if not content_lines: return None
    final_latex_parts = [r"\section{Leadership \& Activities}", r"  \resumeSubHeadingListStart"]
    final_latex_parts.extend(content_lines)
    final_latex_parts.extend([r"  \resumeSubHeadingListEnd", ""])
    return "\n".join(final_latex_parts)


def generate_latex_content(data: Dict[str, Any], page_height: Optional[float] = None) -> str:
    """
    Generates the full LaTeX document string for a classic resume.
    Args:
        data: The parsed JSON resume data.
        page_height: Optional page height in inches. If None, a template default is used.
    Returns:
        A string containing the complete LaTeX document.
    """
    
    tech_skills, metrics = extract_highlights_from_resume(data)

    # Determine page height for LaTeX geometry package
    page_height_setting_tex = "" # This will be set by the main generator script if needed for \setlength{\pdfpageheight}
    text_height_adjustment = "" # This will be populated based on page_height for \addtolength{\textheight}
    
    # This logic for text_height_adjustment should be the one from before the failed preamble edit.
    # It relies on the page_height argument, which the main script controls during auto-sizing.
    if page_height is not None:
        page_height_setting_tex = f"\\setlength{{\\pdfpageheight}}{{{page_height:.2f}in}}"
        if page_height > 15.0: text_height_adjustment_val = 5.0
        elif page_height > 14.0: text_height_adjustment_val = 4.5
        elif page_height > 13.0: text_height_adjustment_val = 4.0
        elif page_height > 12.0: text_height_adjustment_val = 3.0
        elif page_height > 11.0: text_height_adjustment_val = 2.0
        else: text_height_adjustment_val = 1.0 # Default for up to 11 inches if page_height is specified
        text_height_adjustment = f"\\addtolength{{\\textheight}}{{{text_height_adjustment_val:.2f}in}}"
    else: # Default if page_height is None (e.g. auto-sizing disabled, no specific height)
        text_height_adjustment_val = 1.0 # Corresponds to the old default logic
        text_height_adjustment = f"\\addtolength{{\\textheight}}{{{text_height_adjustment_val:.2f}in}}"

    # LaTeX Preamble from the state *before* the major refactor that broke things.
    # This includes [T1]{fontenc} and textcomp, and the correct fancyhdr/margin setup.
    preamble_parts = [
        r"\documentclass[letterpaper,11pt]{article}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage{latexsym}",
        r"\usepackage[left=0.75in, top=0.6in, right=0.75in, bottom=0.6in]{geometry}",
        r"\usepackage{titlesec}",
        r"\usepackage{marvosym}",
        r"\usepackage[usenames,dvipsnames]{color}",
        r"\usepackage{verbatim}",
        r"\usepackage{enumitem}",
        r"\usepackage[hidelinks]{hyperref}",
        r"\usepackage{fancyhdr}",
        r"\usepackage[english]{babel}",
        r"\usepackage{tabularx}",
        r"\usepackage{amsfonts}",
        r"\usepackage{textcomp}",
        r"\pagestyle{fancy}",
        r"\fancyhf{}", 
        r"\fancyfoot{}",
        r"\renewcommand{\headrulewidth}{0pt}",
        r"\renewcommand{\footrulewidth}{0pt}",
        r"\addtolength{\textheight}{0.7in}",
        r"\linespread{1.05}",
        r"\raggedbottom",
    ]
    
    preamble_parts.extend([
        r"\urlstyle{same}",
        r"\setlength{\tabcolsep}{0in}",
        r"\titleformat{\section}{",
        r"  \vspace{2pt}\scshape\raggedright\large",
        r"}{}{0em}{}[\color{black}\titlerule \vspace{3pt}]",
        r"\pdfgentounicode=1",
        r"\newcommand{\resumeItem}[1]{\item{\small #1}\vspace{1pt}}",
        r"\newcommand{\resumeSubheading}[4]{",
        r"  \vspace{-2pt}\item",
        r"    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}",
        r"      \textbf{#1} & #2 \\",
        r"      \textit{\small#3} & \textit{\small #4} \\",
        r"    \end{tabular*}\vspace{-7pt}",
        r"}",
        r"\newcommand{\resumeSubSubheading}[2]{",
        r"    \item",
        r"    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}",
        r"      \textit{\small#1} & \textit{\small #2} \\",
        r"    \end{tabular*}\vspace{-7pt}",
        r"}",
        r"\newcommand{\resumeProjectHeading}[2]{",
        r"    \item",
        r"    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}",
        r"      \small#1 & #2 \\",
        r"    \end{tabular*}\vspace{2pt}",
        r"}",
        r"\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}",
        r"\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}",
        r"\newcommand{\resumeSubheadingSingleLine}[2]{",
        r"  \vspace{-2pt}\item",
        r"    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}",
        r"      \textbf{#1} & #2 \\",
        r"    \end{tabular*}\vspace{-7pt}",
        r"}",
        r"\setlist[itemize]{itemsep=0pt, topsep=3pt, parsep=0pt, partopsep=0pt, leftmargin=0.15in}",
        r"\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}",
        r"\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}", 
        r"\newcommand{\resumeItemListStart}{\begin{itemize}[itemsep=2pt]}",
        r"\newcommand{\resumeItemListEnd}{\end{itemize}}"
    ])

    preamble = "\n".join(preamble_parts)

    doc_start = f"""\\begin{{document}}
{page_height_setting_tex} % This is still useful if main script wants to set pdfpageheight
"""

    # Extract data based on schema (and handle Evelyn.json variations where noted)
    # The schema uses 'contact', Evelyn.json uses 'Personal Information'.
    # The schema uses 'objective' or 'summary', Evelyn.json uses 'Summary/Objective'.
    # The schema uses 'work_experience', Evelyn.json uses 'Experience'.
    # The schema uses 'skills' (dict), Evelyn.json uses 'Skills' (dict with sub-dicts).
    # The schema uses 'languages', Evelyn.json uses 'Languages'.
    # The schema uses 'certifications', Evelyn.json uses 'Certifications/Awards' (potentially mixed).
    # The schema uses 'awards', (see above).
    # The schema uses 'involvement' or 'leadership', Evelyn.json has 'Misc' -> 'Leadership'.

    personal_info_data = data.get("Personal Information") or data.get("contact")
    name_from_data = data.get("name") # Top level name from schema.
    if name_from_data and personal_info_data and not personal_info_data.get('name'):
        personal_info_data['name'] = name_from_data # Inject if missing in contact dict

    objective_data = data.get("Summary/Objective") or data.get("objective") or data.get("summary")
    education_data = data.get("Education") or data.get("education")
    experience_data = data.get("Experience") or data.get("work_experience")
    projects_data = data.get("Projects") or data.get("projects")
    skills_data = data.get("Skills") or data.get("skills")
    languages_data = data.get("Languages") or data.get("languages")
    
    # For certs/awards, Evelyn.json has "Certifications/Awards".
    # Schema has separate "certifications" and "awards".
    # We'll prefer direct keys first.
    certifications_data = data.get("certifications")
    awards_data = data.get("awards")
    certs_and_awards_mixed = data.get("Certifications/Awards")

    # If specific keys are empty but mixed one exists, we might need to split them.
    # For now, this template won't try to split a mixed list. It will use dedicated lists if present.
    # If only the mixed list is present and non-empty, we might decide to pass it to one
    # or the other, or a combined section. Given the prompt, let's assume separate lists are preferred.

    involvement_data = data.get("involvement") or data.get("leadership") # Schema direct keys
    misc_data = data.get("Misc") # For Evelyn.json specific "Misc" -> "Leadership"

    print("\n--- Section Generation Log ---")
    section_processing_log = []

    header_tex = _generate_header_section(personal_info_data)
    section_processing_log.append(f"Header section: {'Included' if header_tex else 'Skipped (no data or empty)'}")

    objective_tex = _generate_objective_section(objective_data)
    section_processing_log.append(f"Summary/Objective section: {'Included' if objective_tex else 'Skipped (no data or empty)'}")

    education_tex = _generate_education_section(education_data)
    section_processing_log.append(f"Education section: {'Included' if education_tex else 'Skipped (no data or empty)'}")

    experience_tex = _generate_experience_section(experience_data, tech_skills, metrics)
    section_processing_log.append(f"Experience section: {'Included' if experience_tex else 'Skipped (no data or empty)'}")

    projects_tex = _generate_projects_section(projects_data, tech_skills, metrics)
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
    elif misc_data: # Fallback to Evelyn.json's Misc.Leadership structure
        involvement_tex = _generate_misc_leadership_section(misc_data)
        section_processing_log.append(f"Misc/Leadership section (fallback): {'Included' if involvement_tex else 'Skipped (no data or empty)'}")
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
    return full_latex_doc

def extract_highlights_from_resume(resume_data: Dict[str, Any]) -> tuple[List[str], List[str]]:
    """
    Extracts technical skills and metrics from resume bullet points using OpenAI API.

    Args:
        resume_data: The parsed resume JSON data.

    Returns:
        A tuple containing two lists: (technical_skills, metrics).
        Returns ([], []) if highlighting is skipped or an error occurs.
    """
    if not _initialize_openai_client() or not OPENAI_CLIENT:
        return [], []

    all_bullet_points: List[str] = []

    # Extract from Experience section
    experience_data = resume_data.get("Experience") or resume_data.get("work_experience")
    if isinstance(experience_data, list):
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
    if isinstance(projects_data, list):
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
    latex_output_default = generate_latex_content(sample_resume_data)
    # print(latex_output_default)
    with open("classic_template_test_default.tex", "w", encoding='utf-8') as f:
        f.write(latex_output_default)
    print("Saved to classic_template_test_default.tex")

    print("\n--- Generating LaTeX from sample data (page_height = 13.0 inches) ---")
    latex_output_custom_h = generate_latex_content(sample_resume_data, page_height=13.0)
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
    latex_minimal = generate_latex_content(minimal_data)
    with open("classic_template_test_minimal.tex", "w", encoding='utf-8') as f:
        f.write(latex_minimal)
    print("Saved to classic_template_test_minimal.tex")
