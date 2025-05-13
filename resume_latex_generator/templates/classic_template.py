import os # Add os import for path operations
from typing import Dict, Any, Optional, List
import re

# Default page height if not specified by the generator (e.g. if auto-sizing is off and no specific height is given)
DEFAULT_TEMPLATE_PAGE_HEIGHT_INCHES = 11.0 

# --- Helper functions to generate LaTeX for each section (assumed to be defined below as before) ---
# e.g. fix_latex_special_chars, _generate_header_section, _generate_objective_section, etc.

def fix_latex_special_chars(text: Optional[Any]) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    protected_percentages = {}
    for i, match in enumerate(re.finditer(r'(\d+)%', text)):
        placeholder = f"__PCT_PLACEHOLDER_{i}__"
        text = text.replace(match.group(0), placeholder)
        protected_percentages[placeholder] = f"{match.group(1)}\\%"
    replacements = [
        ("\\", r"\textbackslash{}"),
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
    for placeholder, replacement in protected_percentages.items():
        text = text.replace(placeholder, replacement)
    return text

def _generate_header_section(personal_info: Optional[Dict[str, Any]]) -> str:
    if not personal_info: return ""
    name = fix_latex_special_chars(personal_info.get("name"))
    email = personal_info.get("email")
    phone = fix_latex_special_chars(personal_info.get("phone"))
    linkedin = fix_latex_special_chars(personal_info.get("linkedin"))
    website = fix_latex_special_chars(personal_info.get("website"))
    github = fix_latex_special_chars(personal_info.get("github"))
    location = fix_latex_special_chars(personal_info.get("location"))
    lines = []
    if name:
        lines.append(r"\begin{center}")
        lines.append(f"    \\textbf{{\\Huge \\scshape {name}}} \\\\ \\vspace{{1pt}}")
    contact_parts = []
    if phone: contact_parts.append(phone)
    if email:
        email_display = email.replace("_", r"\_")
        contact_parts.append(f"\\href{{mailto:{email}}}{{\\underline{{{email_display}}}}}")
    if linkedin:
        linkedin_url = linkedin if linkedin.startswith("http") else f"https://{linkedin}"
        contact_parts.append(f"\\href{{{linkedin_url}}}{{\\underline{{{linkedin}}}}}")
    if github:
        github_url = github if github.startswith("http") else f"https://{github}"
        contact_parts.append(f"\\href{{{github_url}}}{{\\underline{{{github}}}}}")
    if website:
        website_url = website if website.startswith("http") else f"http://{website}"
        contact_parts.append(f"\\href{{{website_url}}}{{\\underline{{{website}}}}}")
    if contact_parts: lines.append(f"    \\small {' $|$ '.join(contact_parts)}")
    if location and name: lines.append(f"    \\small {location}")
    elif location: lines.append(f"    \\small {location}") # if only location
    if name: lines.append(r"\end{center}")
    return "\n".join(lines)

def _generate_objective_section(objective: Optional[str]) -> str:
    if not objective: return ""
    return f"\\section*{{Summary}} % Using section* for unnumbered\n  {fix_latex_special_chars(objective)}"

def _generate_education_section(education_list: Optional[List[Dict[str, Any]]]) -> str:
    if not education_list: return ""
    lines = ["\\section{Education}", "  \\resumeSubHeadingListStart"]
    for edu in education_list:
        uni = fix_latex_special_chars(edu.get("institution") or edu.get("university"))
        loc = fix_latex_special_chars(edu.get("location"))
        degree_parts = [fix_latex_special_chars(d) for d in [edu.get("degree"), edu.get("specialization")] if d]
        degree_str = ", ".join(degree_parts)
        start_date = edu.get("start_date", "")
        end_date = edu.get("end_date", "")
        dates = f"{fix_latex_special_chars(start_date)} -- {fix_latex_special_chars(end_date)}" if start_date or end_date else ""
        if end_date and end_date.lower() == 'present': dates = f"{fix_latex_special_chars(start_date)} -- Present"
        elif not end_date and start_date: dates = fix_latex_special_chars(start_date)
        lines.append(f"    \\resumeSubheading{{{uni}}}{{{loc}}}{{{degree_str}}}{{{dates}}}")
        gpa = edu.get("gpa")
        honors = fix_latex_special_chars(edu.get("honors"))
        details_parts = [f"GPA: {fix_latex_special_chars(gpa)}" if gpa else None, f"Honors: {honors}" if honors else None]
        if any(details_parts): lines.append(f"    \\resumeSubSubheading{{{', '.join(filter(None, details_parts))}}}{{}}")
        additional_info = edu.get("additional_info")
        relevant_coursework = edu.get("relevant_coursework")
        if additional_info:
            lines.extend([r"      \\resumeItemListStart", f"        \\resumeItem{{{fix_latex_special_chars(additional_info)}}}", r"      \\resumeItemListEnd"])
        elif relevant_coursework and isinstance(relevant_coursework, list):
            courses_str = ", ".join(fix_latex_special_chars(c) for c in relevant_coursework)
            lines.extend([r"      \\resumeItemListStart", f"        \\resumeItem{{Relevant Coursework: {courses_str}}}", r"      \\resumeItemListEnd"])
    lines.extend(["  \\resumeSubHeadingListEnd", ""])
    return "\n".join(lines)

def _generate_experience_section(experience_list: Optional[List[Dict[str, Any]]]) -> str:
    if not experience_list: return ""
    lines = ["\\section{Experience}", "  \\resumeSubHeadingListStart"]
    for exp in experience_list:
        company = fix_latex_special_chars(exp.get("company"))
        position = fix_latex_special_chars(exp.get("position") or exp.get("title"))
        location = fix_latex_special_chars(exp.get("location"))
        dates_dict = exp.get("dates", {})
        start_date = fix_latex_special_chars(dates_dict.get("start_date"))
        end_date = fix_latex_special_chars(dates_dict.get("end_date"))
        dates_str = f"{start_date} -- {end_date}" if start_date or end_date else ""
        if end_date and end_date.lower() == 'present': dates_str = f"{start_date} -- Present"
        elif not end_date and start_date: dates_str = start_date
        lines.append(f"    \\resumeSubheading{{{position}}}{{{dates_str}}}{{{company}}}{{{location}}}")
        responsibilities = exp.get("responsibilities") or exp.get("responsibilities/achievements")
        if responsibilities and isinstance(responsibilities, list):
            lines.append(r"      \\resumeItemListStart")
            for resp in responsibilities: lines.append(f"        \\resumeItem{{{fix_latex_special_chars(resp)}}}")
            lines.append(r"      \\resumeItemListEnd")
    lines.extend(["  \\resumeSubHeadingListEnd", ""])
    return "\n".join(lines)

def _generate_projects_section(project_list: Optional[List[Dict[str, Any]]]) -> str:
    if not project_list: return ""
    lines = ["\\section{Projects}", "    \\resumeSubHeadingListStart"]
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
        elif isinstance(dates_val, str): dates_str = fix_latex_special_chars(dates_val)
        tech_used = proj.get("technologies") or proj.get("technologies_used")
        heading_title_part = f"\\textbf{{{title}}}"
        if tech_used:
            tech_str = ", ".join(fix_latex_special_chars(t) for t in tech_used) if isinstance(tech_used, list) else fix_latex_special_chars(tech_used)
            if tech_str: heading_title_part += f" $|$ \\emph{{{tech_str}}}"
        lines.append(f"      \\resumeProjectHeading{{{heading_title_part}}}{{{dates_str}}}")
        description = proj.get("description")
        if description:
            lines.append(r"          \\resumeItemListStart")
            if isinstance(description, list):
                for item in description: lines.append(f"            \\resumeItem{{{fix_latex_special_chars(item)}}}")
            else: lines.append(f"            \\resumeItem{{{fix_latex_special_chars(description)}}}")
            lines.append(r"          \\resumeItemListEnd")
    lines.extend(["    \\resumeSubHeadingListEnd", ""])
    return "\n".join(lines)

def _generate_skills_section(skills_dict_input: Optional[Dict[str, Any]]) -> str:
    if not skills_dict_input: return ""
    skills_dict = skills_dict_input
    if isinstance(skills_dict_input, list):
        skills_dict = {"Technical Skills": {"General": skills_dict_input}}
        print("AI HINT: Converted skills list to dictionary for _generate_skills_section.")
    lines = ["\\section{Technical Skills}"]
    technical_skills_data = skills_dict.get("Technical Skills")
    skills_to_process = technical_skills_data if isinstance(technical_skills_data, dict) else (skills_dict if isinstance(skills_dict, dict) and not technical_skills_data else {})
    if not skills_to_process:
        soft_skills = skills_dict.get("Soft Skills")
        if isinstance(soft_skills, list) and soft_skills:
            lines.extend([r" \begin{itemize}[leftmargin=0.15in, label={}]", r"    \small{\item{", f"     \\textbf{{Soft Skills}}{{: {fix_latex_special_chars(', '.join(soft_skills))}}} \\\\", r"    }}", r" \end{itemize}", ""])
            return "\n".join(lines)
        return ""
    lines.extend([r" \begin{itemize}[leftmargin=0.15in, label={}]", r"    \small{\item{"])
    category_lines = [f"     \\textbf{{{fix_latex_special_chars(cat)}}}{{: {fix_latex_special_chars(', '.join(slist))}}}" for cat, slist in skills_to_process.items() if isinstance(slist, list) and slist]
    lines.append(" \\\\ ".join(category_lines))
    lines.extend([r"    }}", r" \end{itemize}", ""])
    return "\n".join(lines)

def _generate_languages_section(languages_list: Optional[List[Dict[str, Any]]]) -> str:
    if not languages_list: return ""
    lang_items = [
        fix_latex_special_chars(lang.get('name')) + 
        (f" ({fix_latex_special_chars(lang.get('proficiency'))})" if lang.get("proficiency") else "") 
        for lang in languages_list if lang.get("name")
    ]
    if not lang_items: return ""
    return "\n".join(["\\section{Languages}", r" \begin{itemize}[leftmargin=0.15in, label={}]", f"    \\small{{\\item{{{', '.join(lang_items)}}}}}", r" \end{itemize}", ""])

def _generate_certifications_section(cert_list: Optional[List[Dict[str, Any]]]) -> str:
    if not cert_list: return ""
    lines = ["\\section{Certifications}", "  \\resumeSubHeadingListStart"]
    for cert in cert_list:
        name = fix_latex_special_chars(cert.get("certification"))
        institution = fix_latex_special_chars(cert.get("institution"))
        date = fix_latex_special_chars(cert.get("date"))
        lines.append(f"    \\resumeSubheading{{{name}}}{{{date}}}{{{institution}}}{{}}")
    lines.extend(["  \\resumeSubHeadingListEnd", ""])
    return "\n".join(lines)

def _generate_awards_section(awards_list: Optional[List[Dict[str, Any]]]) -> str:
    if not awards_list: return ""
    lines = ["\\section{Awards}", "  \\resumeSubHeadingListStart"]
    for award in awards_list:
        title = fix_latex_special_chars(award.get("title"))
        issuer = fix_latex_special_chars(award.get("issuer"))
        date = fix_latex_special_chars(award.get("date"))
        description = fix_latex_special_chars(award.get("description"))
        lines.append(f"    \\resumeSubheading{{{title}}}{{{date}}}{{{issuer}}}{{}}")
        if description: lines.extend([r"      \\resumeItemListStart", f"        \\resumeItem{{{description}}}", r"      \\resumeItemListEnd"])
    lines.extend(["  \\resumeSubHeadingListEnd", ""])
    return "\n".join(lines)

def _generate_involvement_section(involvement_list: Optional[List[Dict[str, Any]]]) -> str:
    if not involvement_list: return ""
    lines = ["\\section{Leadership \\& Involvement}", "  \\resumeSubHeadingListStart"]
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
        elif isinstance(date_val, str): dates_str = fix_latex_special_chars(date_val)
        lines.append(f"    \\resumeSubheading{{{position}}}{{{dates_str}}}{{{organization}}}{{}}")
        responsibilities = item.get("responsibilities")
        if responsibilities and isinstance(responsibilities, list):
            lines.append(r"      \\resumeItemListStart")
            for resp in responsibilities: lines.append(f"        \\resumeItem{{{fix_latex_special_chars(resp)}}}")
            lines.append(r"      \\resumeItemListEnd")
    lines.extend(["  \\resumeSubHeadingListEnd", ""])
    return "\n".join(lines)

def _generate_misc_leadership_section(misc_data: Optional[Dict[str, Any]]) -> str:
    if not misc_data or not isinstance(misc_data, dict): return ""
    leadership_data = misc_data.get("Leadership")
    if not leadership_data or not isinstance(leadership_data, dict): return ""
    lines = ["\\section{Leadership \\& Activities}", "  \\resumeSubHeadingListStart"]
    for event_name, details in leadership_data.items():
        name = fix_latex_special_chars(event_name)
        dates_dict = details.get("dates", {})
        start_date = fix_latex_special_chars(dates_dict.get("start_date"))
        end_date = fix_latex_special_chars(dates_dict.get("end_date"))
        dates_str = f"{start_date} -- {end_date}" if start_date or end_date else ""
        if end_date and end_date.lower() == 'present': dates_str = f"{start_date} -- Present"
        elif not end_date and start_date: dates_str = start_date
        lines.append(f"    \\resumeSubheading{{\\textbf{{{name}}}}}{{{dates_str}}}{{}}{{}}")
        responsibilities = details.get("responsibilities/achievements")
        if responsibilities and isinstance(responsibilities, list):
            lines.append(r"      \\resumeItemListStart")
            for resp in responsibilities: lines.append(f"        \\resumeItem{{{fix_latex_special_chars(resp)}}}")
            lines.append(r"      \\resumeItemListEnd")
    lines.extend(["  \\resumeSubHeadingListEnd", ""])
    return "\n".join(lines)

# Determine the script's directory to find classic_template_base.tex
_TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE_TEMPLATE_PATH = os.path.join(_TEMPLATE_DIR, "classic_template_base.tex")

def generate_latex_content(data: Dict[str, Any], page_height: Optional[float] = None) -> str:
    """
    Generates the full LaTeX document string by loading a base template
    and injecting generated content for each section.
    Args:
        data: The parsed JSON resume data.
        page_height: Optional page height in inches. If None, a template default is used.
    Returns:
        A string containing the complete LaTeX document.
    """
    try:
        with open(_BASE_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            template_content = f.read()
    except FileNotFoundError:
        # Fallback or error if template not found - this should not happen in a deployed app
        print(f"ERROR: Base template file not found at {_BASE_TEMPLATE_PATH}")
        return "" # Or raise an exception
    except Exception as e:
        print(f"ERROR: Could not read base template file: {e}")
        return ""

    current_physical_page_height = page_height if page_height is not None else DEFAULT_TEMPLATE_PAGE_HEIGHT_INCHES
    page_height_setting_for_doc_start = f"\\setlength{{\\pdfpageheight}}{{{current_physical_page_height:.2f}in}}" if page_height is not None else ""
    
    effective_top_margin = 0.5
    desired_bottom_margin = 0.5
    target_text_height = current_physical_page_height - effective_top_margin - desired_bottom_margin
    text_height_declaration = f"\\setlength{{\\textheight}}{{{target_text_height:.2f}in}}"

    # Replace dynamic height declarations
    template_content = template_content.replace("%%TEXT_HEIGHT_DECLARATION%%", text_height_declaration)
    template_content = template_content.replace("%%PAGE_HEIGHT_SETTING_FOR_DOC_START%%", page_height_setting_for_doc_start)

    # Extract data sections
    personal_info_data = data.get("Personal Information") or data.get("contact")
    if personal_info_data and data.get("name") and not personal_info_data.get('name'):
        personal_info_data['name'] = data.get("name")

    objective_data = data.get("Summary/Objective") or data.get("objective") or data.get("summary")
    education_data = data.get("Education") or data.get("education")
    experience_data = data.get("Experience") or data.get("work_experience")
    projects_data = data.get("Projects") or data.get("projects")
    skills_data = data.get("Skills") or data.get("skills") # This can be list or dict
    languages_data = data.get("Languages") or data.get("languages")
    certifications_data = data.get("certifications")
    awards_data = data.get("awards")
    involvement_data = data.get("involvement") or data.get("leadership")
    misc_data = data.get("Misc")

    # Generate LaTeX for each section and replace placeholders
    section_generators = {
        "%%HEADER_SECTION%%": (_generate_header_section, personal_info_data),
        "%%OBJECTIVE_SECTION%%": (_generate_objective_section, objective_data),
        "%%EDUCATION_SECTION%%": (_generate_education_section, education_data),
        "%%EXPERIENCE_SECTION%%": (_generate_experience_section, experience_data),
        "%%PROJECTS_SECTION%%": (_generate_projects_section, projects_data),
        "%%SKILLS_SECTION%%": (_generate_skills_section, skills_data),
        "%%LANGUAGES_SECTION%%": (_generate_languages_section, languages_data),
        "%%CERTIFICATIONS_SECTION%%": (_generate_certifications_section, certifications_data),
        "%%AWARDS_SECTION%%": (_generate_awards_section, awards_data),
    }

    for placeholder, (generator_func, section_data) in section_generators.items():
        section_tex = generator_func(section_data) if section_data is not None else ""
        template_content = template_content.replace(placeholder, section_tex)
    
    # Special handling for involvement/misc
    involvement_tex_str = ""
    if involvement_data:
        involvement_tex_str = _generate_involvement_section(involvement_data)
    elif misc_data: 
        involvement_tex_str = _generate_misc_leadership_section(misc_data)
    template_content = template_content.replace("%%INVOLVEMENT_SECTION%%", involvement_tex_str)

    return template_content

# --- Minimal test for the template if run directly (not typical use) ---
# (The __main__ block from the original file would go here if needed for direct testing)
# For brevity in this edit, it's omitted but should be retained if it was there.
    