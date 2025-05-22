from typing import Dict, Any, Optional, List
import re

# Default page height if not specified by the generator (e.g. if auto-sizing is off and no specific height is given)
DEFAULT_TEMPLATE_PAGE_HEIGHT_INCHES = 11.0 

def fix_latex_special_chars(text: Optional[Any]) -> str:
    """
    Escapes LaTeX special characters in a given string.
    Also converts None to an empty string.
    """
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
        ("\\", r"\textbackslash{}"), # Must be first
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
        lines.append(r"\begin{center}")
        lines.append(f"    \\textbf{{\\Huge \\scshape {name}}} \\\\ \\vspace{{1pt}}")
    
    contact_parts = []
    if phone:
        contact_parts.append(phone)
    if email:
        # Special handling for email to avoid underscore issues
        # Use the raw email for mailto but escape underscores properly for display
        email_display = email.replace("_", r"\_")  # Proper LaTeX escaping
        contact_parts.append(f"\\href{{mailto:{email}}}{{\\underline{{{email_display}}}}}")
    if linkedin: # Assuming 'linkedin' key from schema
        linkedin_url = linkedin
        if not linkedin.startswith("http"):
            linkedin_url = f"https://{linkedin}" # Basic assumption
        contact_parts.append(f"\\href{{{linkedin_url}}}{{\\underline{{{linkedin}}}}}")
    if github: # Assuming 'github' key
        github_url = github
        if not github.startswith("http"):
            github_url = f"https://{github}" # Basic assumption
        contact_parts.append(f"\\href{{{github_url}}}{{\\underline{{{github}}}}}")
    if website: # Assuming 'website' key
        website_url = website
        if not website.startswith("http"): # Basic check for protocol
             website_url = f"http://{website}"
        contact_parts.append(f"\\href{{{website_url}}}{{\\underline{{{website}}}}}")

    if contact_parts:
        lines.append(f"    \\small {' $|$ '.join(contact_parts)}")
    
    if location and not name: # If only location is there, might look odd with just center
         lines.append(f"    \\small {location}")
    elif location and name: # Add location if name is also present
        lines.append(f"    \\small {location}")


    if name: # Only add end{center} if we started it
        lines.append(r"\end{center}")
        lines.append("") # Add a newline for spacing

    return "\n".join(lines) if lines else None


def _generate_objective_section(objective: Optional[str]) -> Optional[str]:
    if not objective:
        return None
    
    return f"""\\section*{{Summary}} % Using section* for unnumbered
  {fix_latex_special_chars(objective)}
"""

def _generate_education_section(education_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not education_list:
        return None
    
    lines = ["\\section{Education}", "  \\resumeSubHeadingListStart"]
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
        if end_date and end_date.lower() == 'present': # Handle 'Present' for end date
             dates = f"{fix_latex_special_chars(start_date)} -- Present"
        elif not end_date and start_date: # If only start_date is present
             dates = fix_latex_special_chars(start_date)


        lines.append(f"    \\resumeSubheading")
        lines.append(f"      {{{uni}}}{{{loc}}}")
        lines.append(f"      {{{degree_str}}}{{{dates}}}")
        
        # Optional GPA and Honors
        gpa = edu.get("gpa")
        honors = fix_latex_special_chars(edu.get("honors"))
        
        details_parts = []
        if gpa:
            details_parts.append(f"GPA: {fix_latex_special_chars(gpa)}")
        if honors:
            details_parts.append(f"Honors: {honors}")
        
        if details_parts:
            lines.append(f"    \\resumeSubSubheading{{{', '.join(details_parts)}}}{{}}")

        # Relevant coursework / additional info
        # The schema has `relevant_coursework` as a list, and JSON has `additional_info` as a string.
        # Let's prioritize `additional_info` if present, then `relevant_coursework`.
        
        additional_info = edu.get("additional_info")
        relevant_coursework = edu.get("relevant_coursework")

        if additional_info:
            lines.append(r"      \resumeItemListStart")
            lines.append(f"        \\resumeItem{{{fix_latex_special_chars(additional_info)}}}")
            lines.append(r"      \resumeItemListEnd")
        elif relevant_coursework and isinstance(relevant_coursework, list):
            lines.append(r"      \resumeItemListStart")
            courses_str = ", ".join(fix_latex_special_chars(c) for c in relevant_coursework)
            lines.append(f"        \\resumeItem{{Relevant Coursework: {courses_str}}}")
            lines.append(r"      \resumeItemListEnd")
            
    lines.append("  \\resumeSubHeadingListEnd")
    lines.append("")
    return "\n".join(lines)

def _generate_experience_section(experience_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    # Placeholder: Needs to map JSON `work_experience` to `resumeSubheading` and `resumeItemList`
    if not experience_list:
        return None
    
    lines = ["\\section{Experience}", "  \\resumeSubHeadingListStart"]
    for exp in experience_list:
        company = fix_latex_special_chars(exp.get("company"))
        position = fix_latex_special_chars(exp.get("position") or exp.get("title")) # JSON has 'title'
        location = fix_latex_special_chars(exp.get("location"))
        
        dates_dict = exp.get("dates", {})
        start_date = fix_latex_special_chars(dates_dict.get("start_date"))
        end_date = fix_latex_special_chars(dates_dict.get("end_date"))
        dates_str = f"{start_date} -- {end_date}" if start_date or end_date else ""
        if end_date and end_date.lower() == 'present':
             dates_str = f"{start_date} -- Present"
        elif not end_date and start_date:
             dates_str = start_date


        lines.append(f"    \\resumeSubheading")
        lines.append(f"      {{{position}}}{{{dates_str}}}") # Position first, then dates
        lines.append(f"      {{{company}}}{{{location}}}")   # Company second, then location

        responsibilities = exp.get("responsibilities") or exp.get("responsibilities/achievements") # JSON has the latter
        if responsibilities and isinstance(responsibilities, list):
            lines.append(r"      \resumeItemListStart")
            for resp in responsibilities:
                lines.append(f"        \\resumeItem{{{fix_latex_special_chars(resp)}}}")
            lines.append(r"      \resumeItemListEnd")
            
    lines.append("  \\resumeSubHeadingListEnd")
    lines.append("")
    return "\n".join(lines)

def _generate_projects_section(project_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not project_list:
        return None
    
    lines = ["\\section{Projects}", "    \\resumeSubHeadingListStart"]
    for proj in project_list:
        title = fix_latex_special_chars(proj.get("title"))
        # Dates for projects can be a single 'date' or 'dates' dict
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

        tech_used = proj.get("technologies") or proj.get("technologies_used") # JSON has the latter
        
        # Combining title with technologies if they exist for the heading
        heading_title_part = f"\\textbf{{{title}}}"
        if tech_used:
            if isinstance(tech_used, list):
                tech_str = ", ".join(fix_latex_special_chars(t) for t in tech_used)
            else: # string
                tech_str = fix_latex_special_chars(tech_used)
            if tech_str: # Ensure not empty
                 heading_title_part += f" $|$ \\emph{{{tech_str}}}"

        lines.append(f"      \\resumeProjectHeading")
        lines.append(f"          {{{heading_title_part}}}{{{dates_str}}}")

        description = proj.get("description")
        if description:
            lines.append(r"          \resumeItemListStart")
            if isinstance(description, list):
                for item in description:
                    lines.append(f"            \\resumeItem{{{fix_latex_special_chars(item)}}}")
            else: # string
                lines.append(f"            \\resumeItem{{{fix_latex_special_chars(description)}}}")
            lines.append(r"          \resumeItemListEnd")
            
    lines.append("    \\resumeSubHeadingListEnd")
    lines.append("")
    return "\n".join(lines)


def _generate_skills_section(skills_dict: Optional[Dict[str, Any]]) -> Optional[str]:
    # The sample JSON has skills_dict: {"Soft Skills": [], "Technical Skills": {"Category": [item1, item2]}}
    # The schema has skills_dict: {"Category": [item1, item2]}
    # The sample LaTeX is more free-form.
    # Let's try to match the sample JSON structure and then the schema if that fails.

    if not skills_dict:
        return None

    lines = ["\\section{Technical Skills}"] # Default section title from sample
    
    # Check for "Technical Skills" sub-dictionary as in Evelyn.json
    technical_skills_data = skills_dict.get("Technical Skills")
    
    # If "Technical Skills" is not a sub-dict, assume skills_dict itself is the category->list_of_skills map
    # as per the prompt's schema definition.
    skills_to_process = {}
    if isinstance(technical_skills_data, dict):
        skills_to_process = technical_skills_data
    elif isinstance(skills_dict, dict) and not technical_skills_data: # skills_dict *is* the categories
        skills_to_process = skills_dict
    
    if not skills_to_process: # If still no processable skills (e.g. only "Soft Skills" or empty)
        # Try to see if there's a "Soft Skills" to list, or just output nothing.
        soft_skills = skills_dict.get("Soft Skills")
        if isinstance(soft_skills, list) and soft_skills:
            lines.append(r" \begin{itemize}[leftmargin=0.15in, label={}]")
            lines.append(r"    \small{\item{")
            lines.append(f"     \\textbf{{Soft Skills}}{{: {fix_latex_special_chars(', '.join(soft_skills))}}} \\\\")
            lines.append(r"    }}")
            lines.append(r" \end{itemize}")
            lines.append("")
            return "\n".join(lines)
        return None # No technical skills to list in the desired format

    lines.append(r" \begin{itemize}[leftmargin=0.15in, label={}]")
    lines.append(r"    \small{\item{")
    
    category_lines = []
    for category, skills_list in skills_to_process.items():
        if isinstance(skills_list, list) and skills_list: # Ensure it's a list and not empty
            skills_str = ", ".join(fix_latex_special_chars(s) for s in skills_list)
            category_lines.append(f"     \\textbf{{{fix_latex_special_chars(category)}}}{{: {skills_str}}}")
    
    lines.append(" \\\\ ".join(category_lines)) # Join categories with LaTeX newline
    
    lines.append(r"    }}")
    lines.append(r" \end{itemize}")
    lines.append("")
    return "\n".join(lines)


def _generate_languages_section(languages_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not languages_list:
        return None
    lines = ["\\section{Languages}", r" \begin{itemize}[leftmargin=0.15in, label={}]"]
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
         lines.append(f"    \\small{{\\item{{{', '.join(lang_items)}}}}}")

    lines.append(r" \end{itemize}")
    lines.append("")
    return "\n".join(lines) if lang_items else None


def _generate_certifications_section(cert_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    # Schema: certifications (list of dicts: `certification`, `institution`, `date`)
    # Evelyn.json: "Certifications/Awards": [] -> this implies it could be mixed.
    # Let's assume cert_list is purely certifications for now.
    if not cert_list:
        return None
    
    lines = ["\\section{Certifications}", "  \\resumeSubHeadingListStart"]
    for cert in cert_list:
        name = fix_latex_special_chars(cert.get("certification"))
        institution = fix_latex_special_chars(cert.get("institution"))
        date = fix_latex_special_chars(cert.get("date"))
        
        # Using resumeSubheading for a structured look, though it's typically for job/edu.
        # We can simplify if needed.
        lines.append(f"    \\resumeSubheading")
        lines.append(f"      {{{name}}}{{{date}}}") 
        lines.append(f"      {{{institution}}}{{}}") # Institution on the left, nothing on the right
            
    lines.append("  \\resumeSubHeadingListEnd")
    lines.append("")
    return "\n".join(lines)

def _generate_awards_section(awards_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    # Schema: awards (list of dicts: `title`, `issuer`, `date`, `description`)
    # Evelyn.json: "Certifications/Awards": []
    if not awards_list:
        return None
        
    lines = ["\\section{Awards}", "  \\resumeSubHeadingListStart"]
    for award in awards_list:
        title = fix_latex_special_chars(award.get("title"))
        issuer = fix_latex_special_chars(award.get("issuer"))
        date = fix_latex_special_chars(award.get("date"))
        description = fix_latex_special_chars(award.get("description"))

        lines.append(f"    \\resumeSubheading")
        lines.append(f"      {{{title}}}{{{date}}}")
        lines.append(f"      {{{issuer}}}{{}}") # Issuer on the left

        if description:
            lines.append(r"      \resumeItemListStart")
            lines.append(f"        \\resumeItem{{{description}}}")
            lines.append(r"      \resumeItemListEnd")
            
    lines.append("  \\resumeSubHeadingListEnd")
    lines.append("")
    return "\n".join(lines)


def _generate_involvement_section(involvement_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    # Schema: involvement or leadership (list of dicts: `organization`, `position`, `date`, `responsibilities` list)
    # Evelyn.json: "Misc": { "Leadership": { "Event Name": { "dates": ..., "responsibilities": ...}}}
    # This is quite different. The sample json has a nested structure under "Misc" -> "Leadership"
    # The schema expects a flat list of involvement dicts.
    # This template function will try to handle the schema's flat list first.
    # If that's not found, it will look for the Evelyn.json structure.

    if not involvement_list: # This is for the direct schema key 'involvement' or 'leadership'
        return None

    lines = ["\\section{Leadership \\& Involvement}", "  \\resumeSubHeadingListStart"] # Escape ampersand in section title
    
    for item in involvement_list: # Assuming schema-compliant list
        organization = fix_latex_special_chars(item.get("organization"))
        position = fix_latex_special_chars(item.get("position"))
        
        date_val = item.get("date") # Schema suggests 'date' (string) or 'dates' (dict)
        dates_str = ""
        if isinstance(date_val, dict):
            start = fix_latex_special_chars(date_val.get("start_date"))
            end = fix_latex_special_chars(date_val.get("end_date"))
            dates_str = f"{start} -- {end}" if start or end else ""
            if end and end.lower() == 'present': dates_str = f"{start} -- Present"
            elif not end and start : dates_str = start
        elif isinstance(date_val, str):
            dates_str = fix_latex_special_chars(date_val)

        lines.append(f"    \\resumeSubheading")
        lines.append(f"      {{{position}}}{{{dates_str}}}")
        lines.append(f"      {{{organization}}}{{}}")

        responsibilities = item.get("responsibilities")
        if responsibilities and isinstance(responsibilities, list):
            lines.append(r"      \resumeItemListStart")
            for resp in responsibilities:
                lines.append(f"        \\resumeItem{{{fix_latex_special_chars(resp)}}}")
            lines.append(r"      \resumeItemListEnd")
            
    lines.append("  \\resumeSubHeadingListEnd")
    lines.append("")
    return "\n".join(lines)

def _generate_misc_leadership_section(misc_data: Optional[Dict[str, Any]]) -> Optional[str]:
    """Specifically handles the Evelyn.json Misc.Leadership structure."""
    if not misc_data or not isinstance(misc_data, dict):
        return None
    
    leadership_data = misc_data.get("Leadership")
    if not leadership_data or not isinstance(leadership_data, dict):
        return None

    lines = ["\\section{Leadership \\& Activities}", "  \\resumeSubHeadingListStart"] # Escape ampersand in section title
    
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
        
        # Using resumeSubheading: Event Name on left, Dates on right.
        # No clear "position" or "organization" like in the schema, so event name is primary.
        lines.append(f"    \\resumeSubheading")
        lines.append(f"      {{\\textbf{{{name}}}}}{{{dates_str}}}") # Event name bolded
        lines.append(f"      {{}}{{}}") # Empty second line of subheading
        
        responsibilities = details.get("responsibilities/achievements") # From Evelyn.json
        if responsibilities and isinstance(responsibilities, list):
            lines.append(r"      \resumeItemListStart")
            for resp in responsibilities:
                lines.append(f"        \\resumeItem{{{fix_latex_special_chars(resp)}}}")
            lines.append(r"      \resumeItemListEnd")
            
    lines.append("  \\resumeSubHeadingListEnd")
    lines.append("")
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
    
    page_height_setting_for_doc_start = "" # For \pdfpageheight
    
    # Determine the physical page height for this compilation run
    current_physical_page_height = page_height if page_height is not None else DEFAULT_TEMPLATE_PAGE_HEIGHT_INCHES

    if page_height is not None:
        # This sets the physical media height at the start of the document
        page_height_setting_for_doc_start = f"\\setlength{{\\pdfpageheight}}{{{current_physical_page_height:.2f}in}}"

    # Calculate target text height based on the current physical page height
    # Assuming 0.5in for top margin (due to \addtolength{\topmargin}{-.5in}) and 0.5in for bottom margin
    effective_top_margin = 0.5
    desired_bottom_margin = 0.5
    target_text_height = current_physical_page_height - effective_top_margin - desired_bottom_margin
    text_height_declaration = f"\\setlength{{\\textheight}}{{{target_text_height:.2f}in}}"

    # LaTeX Preamble
    # The text_height_declaration is now part of this main preamble string
    preamble = rf"""
\documentclass[letterpaper,11pt]{{article}}

\usepackage{{latexsym}}
\usepackage[empty]{{fullpage}} % This sets margins to be minimal.
\usepackage{{titlesec}}
\usepackage{{marvosym}}
\usepackage[usenames,dvipsnames]{{color}}
\usepackage{{verbatim}}
\usepackage{{enumitem}}
\usepackage[hidelinks]{{hyperref}}
\usepackage{{fancyhdr}}
\usepackage[english]{{babel}}
\usepackage{{tabularx}}
\usepackage{{amsfonts}} % For \Huge, \scshape etc. sometimes needs amsfonts or similar

% Adjust margins and SET text height precisely
\addtolength{{\oddsidemargin}}{{-0.5in}}
\addtolength{{\evensidemargin}}{{-0.5in}}
\addtolength{{\textwidth}}{{1in}}
\addtolength{{\topmargin}}{{-0.5in}} % Moves the top of the text area up
{text_height_declaration}         % SET the text height based on physical page height and margins

% Page breaking penalties (from previous successful attempt to fill page)
\clubpenalty=8000
\widowpenalty=8000
\tolerance=1000
\setlength{{\emergencystretch}}{{1.5em}}

\urlstyle{{same}}
\raggedbottom 
\raggedright
\setlength{{\tabcolsep}}{{0in}}

% Sections formatting (from sample)
\titleformat{{\section}}{{
  \vspace{{-4pt}}\scshape\raggedright\large
}}{{}}{{0em}}{{}}[\color{{black}}\titlerule \vspace{{-5pt}}]

% Ensure that generated pdf is machine readable/ATS parsable
\pdfgentounicode=1

%-------------------------
% Custom commands (from sample)
\newcommand{{\resumeItem}}[1]{{
  \item\small{{
    {{#1 \vspace{{-2pt}}}}
  }}
}}

\newcommand{{\resumeSubheading}}[4]{{
  \vspace{{-2pt}}\item
    \begin{{tabular*}}{{0.97\textwidth}}[t]{{l@{{\extracolsep{{\fill}}}}r}}
      \textbf{{#1}} & #2 \\
      \textit{{\small#3}} & \textit{{\small #4}} \\
    \end{{tabular*}}\vspace{{-7pt}}
}}

\newcommand{{\resumeSubSubheading}}[2]{{
    \item
    \begin{{tabular*}}{{0.97\textwidth}}{{l@{{\extracolsep{{\fill}}}}r}}
      \textit{{\small#1}} & \textit{{\small #2}} \\
    \end{{tabular*}}\vspace{{-7pt}}
}}

\newcommand{{\resumeProjectHeading}}[2]{{
    \item
    \begin{{tabular*}}{{0.97\textwidth}}{{l@{{\extracolsep{{\fill}}}}r}}
      \small#1 & #2 \\
    \end{{tabular*}}\vspace{{-7pt}}
}}

\newcommand{{\resumeSubItem}}[1]{{\resumeItem{{#1}}\vspace{{-4pt}}}}

\renewcommand\labelitemii{{$\vcenter{{\hbox{{\tiny$\bullet$}}}}$}}

\newcommand{{\resumeSubHeadingListStart}}{{\begin{{itemize}}[leftmargin=0.15in, label={{}}]}}
\newcommand{{\resumeSubHeadingListEnd}}{{\end{{itemize}}}}
\newcommand{{\resumeItemListStart}}{{\begin{itemize}}}}
\newcommand{{\resumeItemListEnd}}{{\end{{itemize}}\vspace{{-5pt}}}}
""" 

    # Document body start
    doc_start = f"""\\begin{{document}}
{page_height_setting_for_doc_start}
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


    # Generate LaTeX for each section
    header_tex = _generate_header_section(personal_info_data)
    objective_tex = _generate_objective_section(objective_data)
    education_tex = _generate_education_section(education_data)
    experience_tex = _generate_experience_section(experience_data)
    projects_tex = _generate_projects_section(projects_data)
    skills_tex = _generate_skills_section(skills_data) # Handles complex skills structure
    languages_tex = _generate_languages_section(languages_data)
    certifications_tex = _generate_certifications_section(certifications_data)
    awards_tex = _generate_awards_section(awards_data)
    
    involvement_tex = None
    if involvement_data: # Prioritize schema's direct key
        involvement_tex = _generate_involvement_section(involvement_data)
    elif misc_data: # Fallback to Evelyn.json's Misc.Leadership structure
        involvement_tex = _generate_misc_leadership_section(misc_data)


    # Assemble the document
    content_parts = [
        preamble,
        doc_start,
        header_tex,
        objective_tex, # Or summary
        education_tex,
        experience_tex,
        projects_tex,
        skills_tex,
        languages_tex,
        certifications_tex,
        awards_tex,
        involvement_tex, # Covers leadership/misc as well
        r"""
\end{document}
"""
    ]
    
    # Filter out None parts (e.g., if a section is empty and its generate function returns None)
    # and join them.
    full_latex_doc = "\n".join(filter(None, content_parts))
    
    return full_latex_doc

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
