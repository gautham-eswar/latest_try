# LaTeX Resume Template

This is a complete, standalone LaTeX template for generating professional resumes. Simply replace the placeholders with your actual data and compile with any LaTeX engine.

## Template Code

```latex
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
\newcommand{\resumeItem}[1]{\item{#1}}
\newcommand{\resumeSubheading}[4]{
  \item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{0pt}
}
\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{0pt}
}
\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      #1 & #2 \\
    \end{tabular*}\vspace{2pt}
}
\newcommand{\resumeSubItem}[1]{{\resumeItem{{#1}}\vspace{{-4pt}}}}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newcommand{\resumeSubheadingSingleLine}[2]{
  \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textbf{{#1}} & #2 \\
    \end{tabular*}
}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}, itemsep=1pt, parsep=0pt, topsep=0pt]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}[itemsep=2pt, parsep=0pt, topsep=2pt]}
\newcommand{\resumeItemListEnd}{\end{itemize}}
\begin{document}
\begin{center}
    \textbf{\Huge \scshape {{FULL_NAME}}} \\ \vspace{1pt}
    \\[6pt]
    \small {{PHONE_NUMBER}} $|$ \href{mailto:{{EMAIL_ADDRESS}}}{\url{{{EMAIL_ADDRESS}}}} $|$ \href{{{LINKEDIN_URL}}}{Linkedin: \url{{{LINKEDIN_DISPLAY}}}} $|$ \href{{{GITHUB_URL}}}{\url{{{GITHUB_DISPLAY}}}} $|$ {{LOCATION}}
\end{center}
\vspace{-10pt}

\section*{Summary}
{{SUMMARY_OBJECTIVE_TEXT}}

\section{Education}
  \resumeSubHeadingListStart
    \resumeSubheading
      {{{UNIVERSITY_NAME_1}}}{{{GRADUATION_DATE_1}}}
      {{{DEGREE_1}}, {{SPECIALIZATION_1}}}{{{UNIVERSITY_LOCATION_1}}}
      \resumeSubSubheading{{{GPA_1}}}{{{HONORS_1}}}
      \resumeItemListStart
        \resumeItem{{{ADDITIONAL_INFO_1}}}
        \resumeItem{Relevant Coursework: {{RELEVANT_COURSEWORK_1}}}
      \resumeItemListEnd
    \resumeSubheading
      {{{UNIVERSITY_NAME_2}}}{{{GRADUATION_DATE_2}}}
      {{{DEGREE_2}}, {{SPECIALIZATION_2}}}{{{UNIVERSITY_LOCATION_2}}}
      \resumeSubSubheading{{{GPA_2}}}{{{HONORS_2}}}
      \resumeItemListStart
        \resumeItem{{{ADDITIONAL_INFO_2}}}
      \resumeItemListEnd
  \resumeSubHeadingListEnd

\section{Experience}
  \resumeSubHeadingListStart
    \resumeSubheading
      {{{COMPANY_NAME_1}}}{{{EMPLOYMENT_DATES_1}}}
      {{{JOB_TITLE_1}}}{{{COMPANY_LOCATION_1}}}
      \resumeItemListStart
        \resumeItem{{{RESPONSIBILITY_1_1}}}
        \resumeItem{{{RESPONSIBILITY_1_2}}}
        \resumeItem{{{RESPONSIBILITY_1_3}}}
      \resumeItemListEnd
    \resumeSubheading
      {{{COMPANY_NAME_2}}}{{{EMPLOYMENT_DATES_2}}}
      {{{JOB_TITLE_2}}}{{{COMPANY_LOCATION_2}}}
      \resumeItemListStart
        \resumeItem{{{RESPONSIBILITY_2_1}}}
        \resumeItem{{{RESPONSIBILITY_2_2}}}
        \resumeItem{{{RESPONSIBILITY_2_3}}}
      \resumeItemListEnd
  \resumeSubHeadingListEnd

\section{Projects}
    \resumeSubHeadingListStart
      \resumeProjectHeading
          {\textbf{{{PROJECT_NAME_1}}} $|$ \emph{{{PROJECT_TECHNOLOGIES_1}}}}{{{PROJECT_DATES_1}}}
          \resumeItemListStart
            \resumeItem{{{PROJECT_DESCRIPTION_1_1}}}
            \resumeItem{{{PROJECT_DESCRIPTION_1_2}}}
          \resumeItemListEnd
      \resumeProjectHeading
          {\textbf{{{PROJECT_NAME_2}}} $|$ \emph{{{PROJECT_TECHNOLOGIES_2}}}}{{{PROJECT_DATES_2}}}
          \resumeItemListStart
            \resumeItem{{{PROJECT_DESCRIPTION_2_1}}}
            \resumeItem{{{PROJECT_DESCRIPTION_2_2}}}
          \resumeItemListEnd
    \resumeSubHeadingListEnd

\section{Technical Skills}
\begin{itemize}[leftmargin=0.15in, label={}]
  \item \textbf{Technical Skills}: {{TECHNICAL_SKILLS_LIST}}
\end{itemize}

\section{Languages}
 \begin{itemize}[leftmargin=0.15in, label={}]
    \small{\item{{{LANGUAGE_1}} ({{PROFICIENCY_1}}), {{LANGUAGE_2}} ({{PROFICIENCY_2}}), {{LANGUAGE_3}} ({{PROFICIENCY_3}})}}
 \end{itemize}

\section{Certifications}
  \resumeSubHeadingListStart
    \resumeSubheading
      {{{CERTIFICATION_NAME_1}}}{{{CERTIFICATION_DATE_1}}}
      {{{CERTIFICATION_ISSUER_1}}}{}
    \resumeSubheading
      {{{CERTIFICATION_NAME_2}}}{{{CERTIFICATION_DATE_2}}}
      {{{CERTIFICATION_ISSUER_2}}}{}
  \resumeSubHeadingListEnd

\section{Awards}
  \resumeSubHeadingListStart
    \resumeSubheading
      {{{AWARD_TITLE_1}}}{{{AWARD_DATE_1}}}
      {{{AWARD_ISSUER_1}}}{}
    \resumeSubheading
      {{{AWARD_TITLE_2}}}{{{AWARD_DATE_2}}}
      {{{AWARD_ISSUER_2}}}{}
  \resumeSubHeadingListEnd

\section{Involvement}
  \resumeSubHeadingListStart
    \resumeSubheading
      {{{INVOLVEMENT_ORGANIZATION_1}}}{{{INVOLVEMENT_DATES_1}}}
      {{{INVOLVEMENT_POSITION_1}}}{{{INVOLVEMENT_LOCATION_1}}}
      \resumeItemListStart
        \resumeItem{{{INVOLVEMENT_DESCRIPTION_1_1}}}
        \resumeItem{{{INVOLVEMENT_DESCRIPTION_1_2}}}
      \resumeItemListEnd
  \resumeSubHeadingListEnd

\end{document}
```

## Placeholder Reference

### Header Section
- `{{FULL_NAME}}` - Your full name (will be displayed in large, bold text)
- `{{PHONE_NUMBER}}` - Your phone number
- `{{EMAIL_ADDRESS}}` - Your email address
- `{{LINKEDIN_URL}}` - Full LinkedIn URL (e.g., https://linkedin.com/in/yourprofile)
- `{{LINKEDIN_DISPLAY}}` - LinkedIn display text (e.g., linkedin.com/in/yourprofile)
- `{{GITHUB_URL}}` - Full GitHub URL (e.g., https://github.com/yourusername)
- `{{GITHUB_DISPLAY}}` - GitHub display text (e.g., github.com/yourusername)
- `{{LOCATION}}` - Your location (e.g., "San Francisco, CA")

### Summary/Objective Section
- `{{SUMMARY_OBJECTIVE_TEXT}}` - Your professional summary or objective statement

### Education Section
- `{{UNIVERSITY_NAME_1}}` - Name of your university/institution
- `{{GRADUATION_DATE_1}}` - Graduation date or expected graduation
- `{{DEGREE_1}}` - Your degree (e.g., "Bachelor of Science")
- `{{SPECIALIZATION_1}}` - Your major/specialization
- `{{UNIVERSITY_LOCATION_1}}` - University location
- `{{GPA_1}}` - Your GPA (e.g., "GPA: 3.8/4.0")
- `{{HONORS_1}}` - Any honors or distinctions
- `{{ADDITIONAL_INFO_1}}` - Additional information about your education
- `{{RELEVANT_COURSEWORK_1}}` - Comma-separated list of relevant courses

### Experience Section
- `{{COMPANY_NAME_1}}` - Company name
- `{{EMPLOYMENT_DATES_1}}` - Employment dates (e.g., "Jan 2022 -- Present")
- `{{JOB_TITLE_1}}` - Your job title
- `{{COMPANY_LOCATION_1}}` - Company location
- `{{RESPONSIBILITY_1_1}}` - First responsibility/achievement bullet point
- `{{RESPONSIBILITY_1_2}}` - Second responsibility/achievement bullet point
- `{{RESPONSIBILITY_1_3}}` - Third responsibility/achievement bullet point

### Projects Section
- `{{PROJECT_NAME_1}}` - Project name
- `{{PROJECT_TECHNOLOGIES_1}}` - Technologies used (comma-separated)
- `{{PROJECT_DATES_1}}` - Project dates
- `{{PROJECT_DESCRIPTION_1_1}}` - First project description bullet point
- `{{PROJECT_DESCRIPTION_1_2}}` - Second project description bullet point

### Technical Skills Section
- `{{TECHNICAL_SKILLS_LIST}}` - Comma-separated list of all technical skills

### Languages Section
- `{{LANGUAGE_1}}` - Language name
- `{{PROFICIENCY_1}}` - Proficiency level (e.g., "Native", "Fluent", "Conversational")

### Certifications Section
- `{{CERTIFICATION_NAME_1}}` - Certification name
- `{{CERTIFICATION_DATE_1}}` - Date received
- `{{CERTIFICATION_ISSUER_1}}` - Issuing organization

### Awards Section
- `{{AWARD_TITLE_1}}` - Award title
- `{{AWARD_DATE_1}}` - Date received
- `{{AWARD_ISSUER_1}}` - Issuing organization

### Involvement Section
- `{{INVOLVEMENT_ORGANIZATION_1}}` - Organization name
- `{{INVOLVEMENT_DATES_1}}` - Involvement dates
- `{{INVOLVEMENT_POSITION_1}}` - Your role/position
- `{{INVOLVEMENT_LOCATION_1}}` - Location
- `{{INVOLVEMENT_DESCRIPTION_1_1}}` - First description bullet point

## Usage Instructions

1. **Copy the LaTeX code** from the template section above
2. **Replace all placeholders** (text in double curly braces) with your actual information
3. **Remove sections** you don't need by deleting the entire section block
4. **Add more entries** by duplicating the pattern within each section (e.g., copy the education block and change the numbers)
5. **Compile** using any LaTeX engine (pdflatex, xelatex, etc.)

## Special Characters

If your content contains special LaTeX characters, escape them as follows:
- `&` → `\&`
- `%` → `\%`
- `$` → `\$`
- `#` → `\#`
- `_` → `\_`
- `{` → `\{`
- `}` → `\}`
- `~` → `\textasciitilde{}`
- `^` → `\textasciicircum{}`
- `\` → `\textbackslash{}`

## Customization Options

### Page Height
To adjust page height, add this line after the preamble (before `\begin{document}`):
```latex
\geometry{paperheight=13.0in}
```

### Font Size
Change the document class line to:
```latex
\documentclass[letterpaper,10.5pt]{article}  % for smaller font
```

### Margins
Modify the geometry package line:
```latex
\usepackage[left=0.5in, right=0.5in, top=0.5in, bottom=0.4in]{geometry}
```

This template is production-ready and will generate a professional, ATS-friendly resume when compiled with any standard LaTeX distribution. 