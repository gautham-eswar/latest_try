import os
import uuid
import json
import logging
import time # Added for a potential small delay if needed

# Pipeline and Service imports
from Pipeline.embeddings import SemanticMatcher
from Pipeline.enhancer import ResumeEnhancer
from Pipeline.latex_generation import proactively_generate_pdf
from Services.database import get_db # To ensure Supabase client can be initialized by services

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    handlers=[
        logging.StreamHandler() # Log to console
    ]
)
logger = logging.getLogger(__name__)

# --- Sample Data ---
test_user_id = str(uuid.uuid4())
timestamp_id_part = int(time.time())
test_original_resume_id = f"test_orig_resume_{timestamp_id_part}"
test_enhanced_resume_id = f"test_enh_resume_{timestamp_id_part}"

sample_original_resume_parsed = {
    "Personal Information": {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "123-456-7890",
        "linkedin": "linkedin.com/in/johndoe",
        "github": "github.com/johndoe"
    },
    "Summary": "A highly motivated test individual with experience in testing things and documenting results.",
    "Experience": [
        {
            "company": "TestCorp",
            "title": "Lead Tester",
            "dates": "Jan 2023 - Present",
            "location": "Testville, TS",
            "responsibilities/achievements": [
                "Successfully tested numerous applications under tight deadlines.",
                "Developed comprehensive test plans and documented all findings meticulously.",
                "Collaborated with developers to identify and resolve software defects.",
                "Mentored junior testers in advanced testing methodologies."
            ]
        },
        {
            "company": "OldTest Inc.",
            "title": "Junior Tester",
            "dates": "Jun 2021 - Dec 2022",
            "location": "Testington, TS",
            "responsibilities/achievements": [
                "Executed test cases for various software modules.",
                "Reported bugs and tracked them to resolution.",
                "Learned to use automated testing tools effectively."
            ]
        }
    ],
    "Education": [
        {
            "institution": "University of Testing",
            "degree": "B.S. in Computer Science",
            "graduation_year": "2021",
            "relevant_coursework": ["Software Testing", "Quality Assurance", "Agile Development"]
        }
    ],
    "Skills": {
        "Technical Skills": {
            "Programming": ["Python", "Java", "JavaScript"],
            "Testing Tools": ["Selenium", "JUnit", "TestRail"],
            "Databases": ["SQL", "MongoDB"]
        },
        "Soft Skills": ["Problem-solving", "Attention to Detail", "Communication"]
    },
    "Projects": [
        {
            "name": "Automated Test Suite",
            "description": "Developed an automated test suite for a web application, reducing manual testing time by 40%.",
            "technologies_used": ["Python", "Selenium"],
            "link": "github.com/johndoe/testsuite"
        }
    ],
}

sample_keywords_data = {
    "keywords": [
        {"keyword": "Python", "context": "Developed scripts in Python for automation", "relevance_score": 0.9, "skill_type": "hard skill"},
        {"keyword": "Selenium", "context": "Used Selenium for UI automation testing", "relevance_score": 0.85, "skill_type": "hard skill"},
        {"keyword": "Agile Development", "context": "Worked in an Agile Development environment", "relevance_score": 0.7, "skill_type": "soft skill"},
        {"keyword": "Test Planning", "context": "Responsible for test planning and strategy", "relevance_score": 0.8, "skill_type": "hard skill"}
    ]
}

def run_test_pipeline():
    logger.info("--- Starting Test Pipeline ---")

    openai_key = os.getenv("OPENAI_API_KEY")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not all([openai_key, supabase_url, supabase_key]):
        logger.error("One or more environment variables (OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY) are missing!")
        logger.error("Ensure these are set in the Docker environment (they should be from the Dockerfile).")
        return

    logger.info("Environment variables are present.")

    # --- 1. Semantic Matching ---
    try:
        logger.info("Step 1: Semantic Matching...")
        matcher = SemanticMatcher() 
        match_results = matcher.process_keywords_and_resume(
            keywords_data=sample_keywords_data,
            resume_data=sample_original_resume_parsed,
            similarity_threshold=0.70
        )
        matches_by_bullet = match_results.get("matches_by_bullet", {})
        final_technical_skills = match_results.get("final_technical_skills", {})
        logger.info(f"Semantic Matching completed. Matches by bullet: {len(matches_by_bullet)} bullets. Final skills categories: {len(final_technical_skills)}")
    except Exception as e:
        logger.error(f"Error during Semantic Matching: {e}", exc_info=True)
        return

    # --- 2. Resume Enhancement ---
    try:
        logger.info("Step 2: Resume Enhancement...")
        enhancer = ResumeEnhancer() 
        enhanced_resume_parsed, modifications = enhancer.enhance_resume(
            resume_data=sample_original_resume_parsed,
            matches_by_bullet=matches_by_bullet,
            final_technical_skills=final_technical_skills
        )
        logger.info(f"Resume Enhancement completed. {len(modifications)} modifications made.")
    except Exception as e:
        logger.error(f"Error during Resume Enhancement: {e}", exc_info=True)
        return

    if enhanced_resume_parsed is None:
        logger.error("Resume enhancement resulted in None, cannot proceed to PDF generation.")
        return

    # --- 3. Proactive PDF Generation & Upload ---
    try:
        logger.info("Step 3: Proactive PDF Generation & Upload...")
        logger.info(f"Calling proactively_generate_pdf with user_id: {test_user_id}, enhanced_resume_id: {test_enhanced_resume_id}")
        
        supabase_pdf_path = proactively_generate_pdf(
            user_id=test_user_id,
            enhanced_resume_id=test_enhanced_resume_id,
            enhanced_resume_content=enhanced_resume_parsed
        )

        if supabase_pdf_path:
            logger.info(f"SUCCESS: Proactive PDF generated and uploaded to Supabase Storage!")
            logger.info(f"Supabase Storage Path: {supabase_pdf_path}")
            logger.info(f"You can typically find this in your Supabase dashboard under Storage > resume-pdfs > {test_user_id}/{test_enhanced_resume_id}/...")
        else:
            logger.error("FAILURE: Proactive PDF generation or upload failed.")
            logger.error("Check previous logs for errors from latex_generation or storage modules.")
            logger.error("This could be due to LaTeX compilation errors or Supabase upload issues.")

    except Exception as e:
        logger.error(f"Error during Proactive PDF Generation/Upload: {e}", exc_info=True)
        if "pdflatex" in str(e) and "No such file or directory" in str(e):
            logger.error("Critical: `pdflatex` command not found. Ensure LaTeX is correctly installed in the Docker image and accessible in PATH.")
        return
    
    logger.info("--- Test Pipeline Finished ---")

if __name__ == "__main__":
    run_test_pipeline() 