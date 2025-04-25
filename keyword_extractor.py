"""
Keyword Extractor Module - Extracts keywords from job descriptions and resumes.
"""

import logging
import time

logger = logging.getLogger(__name__)

def extract(text):
    """
    Alias for extract_keywords for backward compatibility.
    
    Args:
        text: Input text to extract keywords from
        
    Returns:
        list: Extracted keywords
    """
    return extract_keywords(text)

def extract_keywords(text):
    """
    Extract keywords from text using NLP techniques.
    
    Args:
        text: Input text (job description or resume text)
        
    Returns:
        list: List of extracted keywords
    """
    logger.info(f"Extracting keywords from text ({len(text)} chars)")
    
    # In a real implementation, we would use NLP libraries
    # For testing, return dummy keywords based on text content
    time.sleep(0.3)  # Simulate processing time
    
    # Extract some common keywords from the text
    common_keywords = [
        "python", "javascript", "flask", "django", "react", "node.js",
        "machine learning", "data analysis", "cloud", "aws", "docker",
        "kubernetes", "ci/cd", "database", "sql", "nosql", "mongodb",
        "postgresql", "testing", "development", "agile", "devops"
    ]
    
    # Check which keywords are in the text
    found_keywords = []
    lower_text = text.lower()
    for keyword in common_keywords:
        if keyword in lower_text:
            found_keywords.append(keyword)
    
    # Add some general keywords
    general_keywords = ["software development", "programming", "problem solving", "communication"]
    found_keywords.extend(general_keywords)
    
    return found_keywords

def extract_keywords_from_text(text):
    """Alias for extract_keywords for compatibility"""
    return extract_keywords(text)

def keyword_match_score(resume_keywords, job_keywords):
    """
    Calculate match score between resume and job description keywords.
    
    Args:
        resume_keywords: List of keywords from resume
        job_keywords: List of keywords from job description
        
    Returns:
        dict: Match information with score and matched/missing keywords
    """
    if not resume_keywords or not job_keywords:
        return {
            "match_score": 0,
            "matching_keywords": [],
            "missing_keywords": job_keywords or []
        }
    
    # Find matching keywords
    matching = [k for k in job_keywords if k in resume_keywords]
    missing = [k for k in job_keywords if k not in resume_keywords]
    
    # Calculate score
    match_score = len(matching) / len(job_keywords) * 100 if job_keywords else 0
    
    return {
        "match_score": match_score,
        "matching_keywords": matching,
        "missing_keywords": missing
    }