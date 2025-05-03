import json
import re

from Services.openai_interface import call_openai_api


def generate_latex_resume(resume_data):
    """Generate LaTeX resume from structured data"""
    system_prompt = "You are a LaTeX resume formatting assistant."
    user_prompt = f"""
    Generate a professional LaTeX resume from this data:
    
    {json.dumps(resume_data, indent=2)}
    
    Format your response as a complete LaTeX document using modern formatting.
    Use the article class with appropriate margins.
    Don't include the json input in your response.
    """
    
    result = call_openai_api(system_prompt, user_prompt)
    
    # Extract LaTeX from the result (might be wrapped in markdown code blocks)
    latex_match = re.search(r"```(?:latex)?\s*(.*?)```", result, re.DOTALL)
    latex_content = latex_match.group(1) if latex_match else result
    
    # Ensure it's a proper LaTeX document
    if not latex_content.strip().startswith("\\documentclass"):
        latex_content = f"""\\documentclass[11pt,letterpaper]{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{enumitem}}
\\usepackage{{hyperref}}

\\begin{{document}}
{latex_content}
\\end{{document}}"""
    
    return latex_content