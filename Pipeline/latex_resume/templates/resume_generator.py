import dotenv # Import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()

from typing import Dict, Any, Optional, List
import re
import openai
import os
import json
import hashlib
import logging # Add logging import
import copy # <<< ADD THIS IMPORT

# # === REMOVE BASIC CONFIG FROM THIS MODULE ===
# logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')
# # ==========================================

# Configure a logger for this module
logger = logging.getLogger(__name__) # Define module-level logger

# Default page height if not specified by the generator (e.g. if auto-sizing is off and no specific height is given)
DEFAULT_TEMPLATE_PAGE_HEIGHT_INCHES = 11.0 

# Cache for OpenAI API responses
API_CACHE: Dict[str, Any] = {}
OPENAI_CLIENT: Optional[openai.OpenAI] = None # Store the client instance
OPENAI_API_KEY_LOADED = False # Flag to check if API key was successfully loaded

def clear_api_cache_diagnostic(): # New function to clear cache
    """Clears the module-level API_CACHE."""
    global API_CACHE
    API_CACHE.clear()
    # Using print here as logger might not be visible based on past issues
    print("--- PRINT DIAGNOSTIC (resume_generator.py): API_CACHE cleared via utility function. ---", flush=True)

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
        lines.append(f"    \\textbf{{\\Huge \\scshape {name}}} \\ \\vspace{{1pt}}")
        lines.append(f"    \\\\[6pt]")
    
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
        inner_content = ' $|$ '.join(contact_parts)
        lines.append(f"    \\small {{{inner_content}}}")
    
    if name: # Only add end{center} if we started it
        lines.append(r"\end{center}")
        lines.append(r"\vspace{-10pt}") # Add negative space to bring sections closer
        lines.append("") # Add a newline for spacing

    return "\n".join(lines) if lines else None


def _generate_objective_section(objective: Optional[str]) -> Optional[str]:
    if not objective: return None
    escaped_obj = fix_latex_special_chars(objective)
    return f"\\section*{{Summary}} % Using section* for unnumbered\n  {escaped_obj}\n"

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
        start_date_raw = edu.get("dates", {}).get("start_date", "") if isinstance(edu.get("dates"), dict) else edu.get("start_date", "")
        end_date_raw = edu.get("dates", {}).get("end_date", "") if isinstance(edu.get("dates"), dict) else edu.get("end_date", "")
        start_date = fix_latex_special_chars(start_date_raw)
        end_date = fix_latex_special_chars(end_date_raw)
        dates_str = f"{start_date} -- {end_date}" if start_date or end_date else ""
        if end_date and end_date.lower() == 'present': dates_str = f"{start_date} -- Present"
        elif not end_date and start_date: dates_str = start_date

        if uni and degree_str:
            content_lines.append(f"    \\resumeSubheading{{{uni}}}{{{dates_str}}}{{{degree_str}}}{{{loc_str}}}")
            
            gpa_raw = edu.get("gpa")
            honors_raw = edu.get("honors")
            
            gpa_str = ""
            if gpa_raw:
                gpa_str = f"GPA: {fix_latex_special_chars(gpa_raw)}"
            
            honors_str = ""
            if honors_raw:
                honors_str = fix_latex_special_chars(honors_raw)

            if gpa_str or honors_str:
                # Using concatenation for safety, if one is empty, it's fine for LaTeX.
                line = "    \\resumeSubSubheading{{{{" + gpa_str + "}}}}{{{{" + honors_str + "}}}}"
                content_lines.append(line)

            additional_info_raw = edu.get("additional_info")
            relevant_coursework_raw = edu.get("relevant_coursework")
            
            item_list_content = []
            if additional_info_raw:
                item_list_content.append(f"        \\resumeItem{{{fix_latex_special_chars(additional_info_raw)}}}")
            
            if relevant_coursework_raw and isinstance(relevant_coursework_raw, list):
                courses_str = ", ".join(fix_latex_special_chars(c) for c in relevant_coursework_raw if c)
                if courses_str:
                    item_list_content.append(f"        \\resumeItem{{Relevant Coursework: {courses_str}}}")
            elif relevant_coursework_raw and isinstance(relevant_coursework_raw, str) and relevant_coursework_raw.strip():
                 item_list_content.append(f"        \\resumeItem{{Relevant Coursework: {fix_latex_special_chars(relevant_coursework_raw)}}}")

            if item_list_content:
                content_lines.append(r"      \resumeItemListStart")
                content_lines.extend(item_list_content)
                content_lines.append(r"      \resumeItemListEnd")
                
    if not content_lines: return None
    final_latex_parts = [r"\section{{Education}}", r"  \resumeSubHeadingListStart"] + content_lines + [r"  \resumeSubHeadingListEnd", ""]
    return "\n".join(final_latex_parts)

def _generate_experience_section(experience_list: Optional[List[Dict[str, Any]]], tech_skills: List[str], metrics: List[str]) -> Optional[str]:
    """
    Generates the LaTeX content for the experience section.
    Args:
        experience_list: A list of dictionaries containing experience information.
        tech_skills: A list of technical skills to highlight.
        metrics: A list of metrics to highlight.
    Returns:
        A string containing the LaTeX content for the experience section.
    """
    if not experience_list:
        return None

    print("--- PRINT DIAGNOSTIC (_generate_experience_section): Received experience_list ---", flush=True)
    print(json.dumps(experience_list, indent=2), flush=True)
    print("--- END PRINT DIAGNOSTIC (_generate_experience_section) ---", flush=True)

    section_title = "Experience"
    content_lines = [f"\\section{{{section_title}}}"]
    content_lines.append("  \\resumeSubHeadingListStart")

    for experience in experience_list:
        # Safely extract required fields (with fallbacks to empty strings)
        company = fix_latex_special_chars(experience.get("company", ""))
        position = fix_latex_special_chars(experience.get("position") or experience.get("title", ""))
        
        # Get dates
        dates = experience.get("dates", {})
        if isinstance(dates, dict):
            start_date = fix_latex_special_chars(dates.get("start_date", ""))
            end_date = fix_latex_special_chars(dates.get("end_date", ""))
            dates_str = f"{start_date} -- {end_date}" if start_date and end_date else ""
            if end_date and end_date.lower() == 'present': dates_str = f"{start_date} -- Present"
            elif not end_date and start_date: dates_str = start_date
        else:
            dates_str = fix_latex_special_chars(str(dates))

        # Get location
        raw_loc = experience.get("location")
        loc_str = _parse_location_dict(raw_loc)
        
        if company and position: 
            # Using string concatenation to avoid f-string linter issues
            line = "    \\resumeSubheading{{{{" + position + "}}}}{{{{" + dates_str + "}}}}{{{{" + company + "}}}}{{{{" + loc_str + "}}}}"
            content_lines.append(line)
            
            responsibilities = experience.get("responsibilities/achievements") or experience.get("responsibilities") or experience.get("achievements") or []
            if responsibilities:
                content_lines.append("      \\resumeItemListStart")
                for resp in responsibilities:
                    # Format bullet with skills and metrics highlighting
                    formatted_resp = format_bullet_with_highlights(resp, tech_skills, metrics)
                    content_lines.append(f"        \\resumeItem{{{formatted_resp}}}")
                content_lines.append("      \\resumeItemListEnd")

    content_lines.append("  \\resumeSubHeadingListEnd")
    print("--- PRINT DIAGNOSTIC (_generate_experience_section): Received tech_skills ---", flush=True)
    print(tech_skills, flush=True)
    print("--- END PRINT DIAGNOSTIC (_generate_experience_section tech_skills) ---", flush=True)

    return "\n".join(content_lines)

def _generate_projects_section(project_list: Optional[List[Dict[str, Any]]], tech_skills: List[str], metrics: List[str]) -> Optional[str]:
    if not project_list: return None
    print("--- PRINT DIAGNOSTIC (_generate_projects_section): Received tech_skills ---", flush=True)
    print(tech_skills, flush=True)
    print("--- END PRINT DIAGNOSTIC (_generate_projects_section tech_skills) ---", flush=True)

    content_lines = []
    for proj in project_list:
        title = fix_latex_special_chars(proj.get("title"))
        if not title: continue
            
        dates_val = proj.get("dates") or proj.get("date")
        start_date_raw = ""
        end_date_raw = ""
        if isinstance(dates_val, dict):
            start_date_raw = dates_val.get("start_date", "")
            end_date_raw = dates_val.get("end_date", "")
        elif isinstance(dates_val, str):
            if dates_val.lower() in ['present', 'ongoing'] or dates_val.isdigit() and len(dates_val) == 4:
                end_date_raw = dates_val
            else:
                start_date_raw = dates_val
        
        start_date = fix_latex_special_chars(start_date_raw)
        end_date = fix_latex_special_chars(end_date_raw)
        
        dates_str = f"{start_date} -- {end_date}" if start_date or end_date else start_date or end_date or ""
        if end_date and end_date.lower() == 'present': dates_str = f"{start_date} -- Present" if start_date else "Present"
        elif start_date and not end_date: dates_str = start_date
        elif end_date and not start_date: dates_str = end_date

        tech_used_list = proj.get("technologies_used") or proj.get("technologies")
        tech_str = ""
        if tech_used_list and isinstance(tech_used_list, list):
            tech_str = ", ".join(fix_latex_special_chars(t) for t in tech_used_list if t)
        elif tech_used_list and isinstance(tech_used_list, str):
            tech_str = fix_latex_special_chars(tech_used_list)

        heading_title_part = f"\\textbf{{{title}}}"
        if tech_str:
            heading_title_part += f" $|$ \\emph{{{tech_str}}}"

        content_lines.append(f"      \\resumeProjectHeading{{{heading_title_part}}}{{{dates_str}}}")
        
        description_raw = proj.get("description")
        if description_raw:
            content_lines.append(r"          \resumeItemListStart")
            if isinstance(description_raw, list):
                valid_descs = [d for d in description_raw if isinstance(d, str) and d.strip()]
                for desc_item_raw in valid_descs:
                    formatted_desc = format_bullet_with_highlights(desc_item_raw, tech_skills, metrics)
                    content_lines.append(f"            \\resumeItem{{{formatted_desc}}}")
            elif isinstance(description_raw, str) and description_raw.strip():
                formatted_desc = format_bullet_with_highlights(description_raw, tech_skills, metrics)
                content_lines.append(f"            \\resumeItem{{{formatted_desc}}}")
            content_lines.append(r"          \resumeItemListEnd")
            
    if not content_lines: return None
    final_latex_parts = [r"\section{{Projects}}", r"    \resumeSubHeadingListStart"] + content_lines + [r"    \resumeSubHeadingListEnd", ""]
    return "\n".join(final_latex_parts)


def _generate_skills_section(skills_dict: Optional[Dict[str, Any]], tech_skills: List[str]) -> Optional[str]:
    print("--- PRINT DIAGNOSTIC (_generate_skills_section): Received skills_dict ---", flush=True)
    try:
        print(json.dumps(skills_dict, indent=2), flush=True)
    except TypeError:
        print("PRINT DIAGNOSTIC (_generate_skills_section): Could not serialize skills_dict.", flush=True)
        print(str(skills_dict), flush=True)
    print("--- END PRINT DIAGNOSTIC (_generate_skills_section) ---", flush=True)

    print("--- PRINT DIAGNOSTIC (_generate_skills_section): Received tech_skills ---", flush=True)
    print(tech_skills, flush=True)
    print("--- END PRINT DIAGNOSTIC (_generate_skills_section tech_skills) ---", flush=True)

    if not skills_dict: return None
    
    lines = []
    technical_skills_list = skills_dict.get("Technical Skills")

    if technical_skills_list and isinstance(technical_skills_list, list):
        # TEMP DIAGNOSTIC: Simplify skills output
        skills_str = ", ".join(fix_latex_special_chars(s) for s in technical_skills_list if s)
        if skills_str:
            lines.append(r"\section{Technical Skills}") # Add section title here
            lines.append(r"\begin{itemize}[leftmargin=0.15in, label={}]")
            lines.append(r"  \item \textbf{Technical Skills}: " + skills_str)
            lines.append(r"\end{itemize}")
            lines.append("")
        else:
            return None # No technical skills to list
    else:
        return None # No "Technical Skills" list found

    return "\n".join(lines) if lines else None


def _generate_languages_section(languages_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not languages_list: return None
    lang_items = []
    for lang_data in languages_list:
        name = fix_latex_special_chars(lang_data.get("name"))
        proficiency = fix_latex_special_chars(lang_data.get("proficiency"))
        if name: # Only add if name is present
            item_str = name
            if proficiency: item_str += f" ({{proficiency}})"
            lang_items.append(item_str)
    if not lang_items: return None
    final_latex_parts = [r"\section{{Languages}}", r" \begin{itemize}[leftmargin=0.15in, label={{}}]"]
    final_latex_parts.append(f"    \\\\small{{\\\\item{{{{{{\', \'.join(lang_items)}}}}}}}}")
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
        content_lines.append(f"    \\resumeSubheading{{{{ {name} }}}}{{{{ {date} }}}}{{{{ {institution} }}}}{{{{}}}}")
    if not content_lines: return None
    final_latex_parts = [r"\section{{Certifications}}", r"  \resumeSubHeadingListStart"]
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
        # Using string concatenation to avoid f-string linter issue for \resumeSubheading
        line = "    \\resumeSubheading{{{{" + title + "}}}}{{{{" + date + "}}}}{{{{" + issuer + "}}}}{{{{}}}}"
        content_lines.append(line)
        if description:
            content_lines.extend([
                r"      \resumeItemListStart",
                f"        \\resumeItem{{{description}}}",
                r"      \resumeItemListEnd"
            ])
    if not content_lines: return None
    final_latex_parts = [r"\section{{Awards}}", r"  \resumeSubHeadingListStart"]
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
            
        # Corrected resumeSubheading: Use {{}} for the missing 4th argument (location)
        # Organization is now the 3rd arg (like degree/title), position is 1st (like company/uni)
        # Using string concatenation for subheading_command to avoid f-string linter issues:
        subheading_command = "    \\resumeSubheading{{{{" + position + "}}}}{{{{" + dates_str + "}}}}{{{{" + organization + "}}}}{{{{}}}}"
        content_lines.append(subheading_command)

        responsibilities = item.get("responsibilities")
        if responsibilities and isinstance(responsibilities, list):
            content_lines.append(r"      \resumeItemListStart")
            for resp in responsibilities:
                if resp: content_lines.append(f"        \\resumeItem{{{ fix_latex_special_chars(resp) }}}")
            content_lines.append(r"      \resumeItemListEnd")
    if not content_lines: return None
    final_latex_parts = [r"\section{{Leadership \& Involvement}}", r"  \resumeSubHeadingListStart"]
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
            dates_str = f"{{start_date}} -- {{end_date}}" if start_date or end_date else ""
            if end_date and end_date.lower() == 'present': 
                dates_str = f"{{start_date}} -- Present"
            elif not end_date and start_date: 
                dates_str = start_date
        elif isinstance(dates_val, str): # If it's a string, use it directly
            dates_str = fix_latex_special_chars(dates_val)
        # If dates_val is None or some other type, dates_str remains ""
        
        # Use the new single-line subheading command
        content_lines.append(fr"    \resumeSubheadingSingleLine{{{{{name}}}}} {{{{{dates_str}}}}}")

        responsibilities = details.get("responsibilities/achievements")
        if responsibilities and isinstance(responsibilities, list):
            content_lines.append(r"      \resumeItemListStart")
            for resp in responsibilities:
                if resp: content_lines.append(f"        \\resumeItem{{{fix_latex_special_chars(resp)}}}")
            content_lines.append(r"      \resumeItemListEnd")
    if not content_lines: return None
    final_latex_parts = [r"\section{{Leadership \& Activities}}", r"  \resumeSubHeadingListStart"]
    final_latex_parts.extend(content_lines)
    final_latex_parts.extend([r"  \resumeSubHeadingListEnd", ""])
    return "\n".join(final_latex_parts)


def generate_latex_content(data: Dict[str, Any], template_path: Optional[str] = None, target_paper_height_value_str: Optional[str] = None, reduce_font_size: bool = False) -> str:
    """
    Generates the full LaTeX document string for a classic resume.
    Args:
        data: The parsed JSON resume data.
        template_path: Optional path to a custom LaTeX template (currently unused).
        target_paper_height_value_str: Optional string representing the target paper height in inches for this specific generation.
        reduce_font_size: Whether to reduce the font size of the document.
    Returns:
        A string containing the complete LaTeX document.
    """
    current_data_source = copy.deepcopy(data) 
    # ... (rest of the data extraction as before)
    # ... (name, email, linkedin, github, phone, website, objective, education, experience, projects, skills_data, etc.)

    # ---- Handle common variations in key casing / naming ----
    def _ci_get(source: Dict[str, Any], *possible_keys, default=None):
        """Case-insensitive get: returns the first match for any of the provided keys."""
        for key in possible_keys:
            if key in source:
                return source[key]
            # Try case variants
            for k in source.keys():
                if k.lower() == key.lower():
                    return source[k]
        return default

    # Personal-info can live at top level or inside a nested dict
    personal_info_raw = _ci_get(current_data_source, "Personal Information", "personal_information", default={}) or {}

    name = _ci_get(current_data_source, "name", default="") or personal_info_raw.get("name", "")
    name = name.upper()
    email = _ci_get(current_data_source, "email", default="") or personal_info_raw.get("email", "")
    linkedin = _ci_get(current_data_source, "linkedin_url", "linkedin", "website/LinkedIn", default="") or personal_info_raw.get("linkedin", "") or personal_info_raw.get("website/LinkedIn", "")
    github = _ci_get(current_data_source, "github_url", "github", default="") or personal_info_raw.get("github", "")
    phone = _ci_get(current_data_source, "phone", default="") or personal_info_raw.get("phone", "")
    website = _ci_get(current_data_source, "website", default="") or personal_info_raw.get("website", "")

    objective = _ci_get(current_data_source, "objective", "summary", "Summary/Objective", default=None)

    education_list = _ci_get(current_data_source, "education", "Education", default=[])
    experience_list = _ci_get(current_data_source, "experience", "Experience", default=[])
    projects_list = _ci_get(current_data_source, "projects", "Projects", default=[])
    skills_data = _ci_get(current_data_source, "skills", "Skills", default={})
    languages_list = _ci_get(current_data_source, "languages", "Languages", default=[])
    certifications_list = _ci_get(current_data_source, "certifications", "Certifications", "Certifications/Awards", default=[])
    awards_list = _ci_get(current_data_source, "awards", "Awards", default=[])

    involvement_list = _ci_get(current_data_source, "Involvement", "involvement", "Leadership", "leadership", "misc", "Misc", default=[])

    # Initialize OpenAI client here, before it's potentially used
    _initialize_openai_client()

    # Call the (currently no-op) highlighting function
    tech_skills, metrics = extract_highlights_from_resume(current_data_source)

    # Determine font size
    font_size_pt = "10.5pt" if reduce_font_size else "11pt"

    # Construct the LaTeX document string
    preamble_parts = [
        f"\\documentclass[letterpaper,{font_size_pt}]{{article}}",
        "\\usepackage[T1]{fontenc}",
        "\\usepackage{latexsym}",
        "\\usepackage{titlesec}",
        "\\usepackage{marvosym}",
        "\\usepackage[usenames,dvipsnames]{color}",
        "\\usepackage{verbatim}",
        "\\usepackage{enumitem}",
        "\\usepackage[hidelinks]{hyperref}",
        "\\usepackage{fancyhdr}",
        "\\usepackage[english]{babel}",
        "\\usepackage{tabularx}",
        "\\usepackage{amsfonts}",
        "\\usepackage{textcomp}", # Required for \textdegree
        "\\usepackage[left=0.4in, right=0.4in, top=0.4in, bottom=0.35in, footskip=25pt]{geometry}",
        "\\pagestyle{fancy}",
        "\\fancyhf{}",
        "\\fancyfoot{}",
        "\\renewcommand{\\headrulewidth}{0pt}",
        "\\renewcommand{\\footrulewidth}{0pt}",
        "\\urlstyle{same}",
        "\\raggedbottom",
        "\\raggedright",
        "\\setlength{\\tabcolsep}{0in}",
        "\\titleformat{\\section}{\\scshape\\raggedright\\large}{}{0pt}{}[\\titlerule]",
        "\\titlespacing{\\section}{0pt}{5pt}{2pt}",
        "\\pdfgentounicode=1", # For better unicode support in PDF
    ]

    if target_paper_height_value_str:
        preamble_parts.append(f"\\geometry{{paperheight={target_paper_height_value_str}in}}")
    
    # Resume specific \newcommand definitions
    preamble_parts.extend([
        r"\newcommand{\resumeItem}[1]{\item{#1}}",
        r"\newcommand{\resumeSubheading}[4]{",
        r"  \item",
        r"    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}",
        r"      \textbf{#1} & #2 \\",
        r"      \textit{\small#3} & \textit{\small #4} \\",
        r"    \end{tabular*}\vspace{0pt}",
        r"}",
        r"\newcommand{\resumeSubSubheading}[2]{",
        r"    \item",
        r"    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}",
        r"      \textit{\small#1} & \textit{\small #2} \\",
        r"    \end{tabular*}\vspace{0pt}",
        r"}",
        r"\newcommand{\resumeProjectHeading}[2]{",
        r"    \item",
        r"    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}",
        r"      #1 & #2 \\",
        r"    \end{tabular*}\vspace{2pt}",
        r"}",
        r"\newcommand{\resumeSubItem}[1]{{\resumeItem{{#1}}\vspace{{-4pt}}}}",
        r"\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}",
        r"\newcommand{\resumeSubheadingSingleLine}[2]{",
        r"  \item",
        r"    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}",
        r"      \textbf{{#1}} & #2 \\",
        r"    \end{tabular*}",
        r"}",
        r"\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}, itemsep=1pt, parsep=0pt, topsep=0pt]}",
        r"\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}",
        r"\newcommand{\resumeItemListStart}{\begin{itemize}[itemsep=2pt, parsep=0pt, topsep=2pt]\sloppy}",
        r"\newcommand{\resumeItemListEnd}{\end{itemize}}"
    ])

    # --- DIAGNOSTIC PRINT OF PREAMBLE ---
    print("--- AI DEBUG: Final Preamble Parts Being Used ---", flush=True)
    for i, part in enumerate(preamble_parts):
        print(f"Preamble Part [{i}]: {part}", flush=True)
    print("--- AI DEBUG: End of Preamble Parts ---", flush=True)
    # --- END DIAGNOSTIC --- 

    doc_body_parts = ["\\begin{document}"]
    
    # Create personal_info dictionary for the header section
    personal_info_dict = {
        "name": name,
        "email": email,
        "linkedin": linkedin, # Use the variable 'linkedin' which holds linkedin_url
        "github": github,   # Use the variable 'github' which holds github_url
        "phone": phone,
        "website": website,
        "location": _ci_get(current_data_source, "location", default="") or personal_info_raw.get("location", "")
    }
    doc_body_parts.append(_generate_header_section(personal_info_dict))

    if objective:
        doc_body_parts.append(_generate_objective_section(objective))

    if education_list:
        doc_body_parts.append(_generate_education_section(education_list))

    if experience_list:
        doc_body_parts.append(_generate_experience_section(experience_list, tech_skills, metrics))

    if projects_list:
        doc_body_parts.append(_generate_projects_section(projects_list, tech_skills, metrics))

    if skills_data:
        doc_body_parts.append(_generate_skills_section(skills_data, tech_skills))

    if languages_list:
        doc_body_parts.append(_generate_languages_section(languages_list))

    if certifications_list:
        doc_body_parts.append(_generate_certifications_section(certifications_list))

    if awards_list:
        doc_body_parts.append(_generate_awards_section(awards_list))

    if involvement_list:
        doc_body_parts.append(_generate_involvement_section(involvement_list))

    doc_body_parts.append("\\end{document}")

    valid_doc_body_parts = [part for part in doc_body_parts if part is not None]
    return "\n".join(preamble_parts + valid_doc_body_parts)

def extract_highlights_from_resume(resume_data: Dict[str, Any]) -> tuple[List[str], List[str]]:
    """
    Extract technical skills and metrics from resume bullet points using OpenAI.
    Returns two lists: (technical_skills, metrics). Returns empty lists if API unavailable.
    """
    if not _initialize_openai_client() or not OPENAI_CLIENT:
        print("AI HINT DEBUG: OpenAI client not initialized or API key issue. Returning empty for highlights.", flush=True)
        return [], []

    all_bullets: List[str] = []

    # Gather bullets from Experience and Projects sections
    for section_key in ["Experience", "work_experience", "Projects", "projects"]:
        section_data = resume_data.get(section_key)
        if not section_data or not isinstance(section_data, list):
            continue
        for item in section_data:
            if not isinstance(item, dict):
                continue
            bullet_field = None
            if section_key.lower().startswith("experience") or section_key.startswith("work"):
                bullet_field = item.get("responsibilities") or item.get("responsibilities/achievements")
            else:
                bullet_field = item.get("description")

            if isinstance(bullet_field, list):
                all_bullets.extend([b for b in bullet_field if isinstance(b, str) and b.strip()])
            elif isinstance(bullet_field, str) and bullet_field.strip():
                all_bullets.append(bullet_field.strip())

    if not all_bullets:
        logger.info("AI HINT: No bullet points found for highlighting.")
        print("AI HINT DEBUG: No bullet points gathered. Returning empty for highlights.", flush=True)
        return [], []

    print(f"AI HINT DEBUG: Sending these bullets to OpenAI ({len(all_bullets)} total):", flush=True)
    for i, bullet in enumerate(all_bullets):
        print(f"  Bullet {i+1}: {bullet}", flush=True)

    # Use cache to avoid repeated API calls
    cache_key = hashlib.md5("|".join(sorted(all_bullets)).encode("utf-8")).hexdigest()
    if cache_key in API_CACHE:
        cached = API_CACHE[cache_key]
        return cached.get("technical_skills", []), cached.get("metrics", [])

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
+{json.dumps(all_bullets, indent=2)}
"""

    try:
        response = OPENAI_CLIENT.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        print(f"AI HINT DEBUG: Raw OpenAI JSON response:\n{content}", flush=True)

        if not content:
            print("AI HINT DEBUG: OpenAI returned empty content. Returning empty for highlights.", flush=True)
            return [], []
        parsed = json.loads(content)
        tech_skills = parsed.get("technical_skills", [])
        metrics = parsed.get("metrics", [])
        if not isinstance(tech_skills, list):
            print(f"AI HINT DEBUG: 'technical_skills' from OpenAI was not a list (type: {type(tech_skills)}). Forcing to empty list.", flush=True)
            tech_skills = []
        if not isinstance(metrics, list):
            print(f"AI HINT DEBUG: 'metrics' from OpenAI was not a list (type: {type(metrics)}). Forcing to empty list.", flush=True)
            metrics = []
        
        # Filter out very short skills to avoid erroneous highlighting of common letters/bigrams
        MIN_SKILL_LEN = 3
        original_skill_count = len(tech_skills)
        tech_skills = [skill for skill in tech_skills if len(skill) >= MIN_SKILL_LEN]
        if len(tech_skills) != original_skill_count:
            print(f"AI HINT DEBUG: Filtered OpenAI skills from {original_skill_count} to {len(tech_skills)} (min length {MIN_SKILL_LEN}).", flush=True)
            
        API_CACHE[cache_key] = {"technical_skills": tech_skills, "metrics": metrics}
        print(f"AI HINT DEBUG: Parsed technical_skills from OpenAI (post-filter): {tech_skills}", flush=True)
        print(f"AI HINT DEBUG: Parsed metrics from OpenAI: {metrics}", flush=True)
        return tech_skills, metrics
    except Exception as e:
        logger.info(f"AI HINT: OpenAI call failed: {e}. Skipping highlighting, using fallback.")
        print(f"AI HINT DEBUG: OpenAI call failed: {e}. Using fallback.", flush=True)
        # Fallback: derive technical skills from skills section if available
        fallback_skills = set() # Use a set to avoid duplicates initially
        skills_root = resume_data.get("Skills") or resume_data.get("skills")

        def extract_from_skill_list(skill_list: List[Any]):
            for skill_item in skill_list:
                if isinstance(skill_item, str):
                    # Split skills like "Python (Numpy, Pandas, Matplotlib)"
                    # and also handle simple skills
                    parts = re.split(r'[\\s,(/&]+', skill_item) # Split by spaces, commas, slashes, ampersands, parentheses
                    for part in parts:
                        cleaned_part = re.sub(r'[^\w\s+#-]', '', part).strip() # Clean common non-alpha chars, keep # + -
                        if cleaned_part and len(cleaned_part) >= 3: # Apply 3-char filter here
                            fallback_skills.add(cleaned_part)
                elif isinstance(skill_item, dict): # Handle cases like {"name": "Python", "level": "Advanced"}
                    name = skill_item.get("name")
                    if name and isinstance(name, str) and len(name) >=3:
                         fallback_skills.add(name)


        if isinstance(skills_root, dict):
            # Handles structures like:
            # "Skills": { "Technical Skills": ["Python", "Java"], "Tools": ["Git"] }
            # "Skills": { "Technical Skills": { "Programming": ["Python"], "Databases": ["SQL"] } }
            # "Skills": ["Python", "Java"] (though less common for root to be a list)
            for key, value in skills_root.items():
                if isinstance(value, list):
                    extract_from_skill_list(value)
                elif isinstance(value, dict): # e.g. "Technical Skills": { "Languages": ["Python"], ... }
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, list):
                            extract_from_skill_list(sub_value)
                        elif isinstance(sub_value, str) and len(sub_value) >=3: # Single skill string as value
                             fallback_skills.add(sub_value)
                elif isinstance(value, str) and len(value) >=3: # skill string directly under a category
                    fallback_skills.add(value)

        elif isinstance(skills_root, list): # "Skills": ["Python", "Java"]
            extract_from_skill_list(skills_root)
            
        logger.info(f"AI HINT: Fallback skills extracted: {list(fallback_skills)}")
        return list(fallback_skills), []

def _format_text_segment(text_segment_raw: str, all_skills: List[str]) -> str:
    """
    Formats a raw text segment by bolding specified skills within it and escaping all text for LaTeX.
    Args:
        text_segment_raw: The raw text string (e.g., a metric phrase or a part of a bullet).
        all_skills: A list of all unique skill strings identified by OpenAI.
    Returns:
        A LaTeX-ready string with specified skills bolded and all parts correctly escaped.
    """
    parts = []
    current_pos = 0

    # Find all occurrences of skills to bold within this specific segment
    # Order skills by length (descending) to handle cases like "Python" vs "Python 3" if both were skills.
    skill_highlights_in_segment = []
    for skill in sorted(all_skills, key=len, reverse=True):
        for match in re.finditer(re.escape(skill), text_segment_raw, flags=re.IGNORECASE):
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
                skill_highlights_in_segment.append({'start': match.start(), 'end': match.end(), 'text': match.group(0)})
    
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
        return ""

    print(f"AI HINT DEBUG (format_bullet_with_highlights): Processing bullet: '{bullet_text_raw}'", flush=True)
    print(f"AI HINT DEBUG (format_bullet_with_highlights): Using all_skills: {all_skills}", flush=True)
    print(f"AI HINT DEBUG (format_bullet_with_highlights): Using all_metrics: {all_metrics}", flush=True)

    # Identify all top-level highlight segments (metrics and skills not inside other captured metrics)
    # Each element: {'start': int, 'end': int, 'text': str_raw, 'type': 'metric'|'skill'}
    highlights = []
    
    # 1. Find all metric occurrences
    for metric_raw in sorted(all_metrics, key=len, reverse=True): # Longest first
        for match in re.finditer(re.escape(metric_raw), bullet_text_raw, flags=re.IGNORECASE):
            highlights.append({'start': match.start(), 'end': match.end(), 'text': match.group(0), 'type': 'metric'})
            
    # 2. Find all skill occurrences
    for skill_raw in sorted(all_skills, key=len, reverse=True): # Longest first
        for match in re.finditer(re.escape(skill_raw), bullet_text_raw, flags=re.IGNORECASE):
            highlights.append({'start': match.start(), 'end': match.end(), 'text': match.group(0), 'type': 'skill'})
            
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
    print(f"AI HINT DEBUG (format_bullet_with_highlights): Final non-overlapping highlights: {final_non_overlapping_highlights}", flush=True)

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
            # Its text itself just needs to be escaped and bolded/italicized
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
        "Summary/Objective": "Data Science Meets Product Strategy—Turning Analytics into Action. & a test of _ and % and $ and # and {{ and }} and \\\\ and ~ and ^",
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
            {"title": "Dean'''s List", "issuer": "NTU", "date": "2021", "description": "Top 5% of students."}
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
    latex_output_custom_h = generate_latex_content(sample_resume_data, target_paper_height_value_str="13.0")
    # print(latex_output_custom_h)
    with open("classic_template_test_custom_h.tex", "w", encoding='utf-8') as f:
        f.write(latex_output_custom_h)
    print("Saved to classic_template_test_custom_h.tex")
    
    print("\n--- Testing fix_latex_special_chars ---")
    test_str = "Text with \\ backslash, {{curly braces}}, & ampersand, % percent, $ dollar, # hash, _ underscore, ~ tilde, ^ caret."
    print(f"Original: {{test_str}}")
    print(f"Escaped:  {{fix_latex_special_chars(test_str)}}")
    
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