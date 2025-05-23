#!/usr/bin/env python3
import json
import os
import logging
import time
import uuid
import subprocess

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import pipeline components
# from Pipeline.keyword_extraction import extract_keywords # We will mock this
from Pipeline.embeddings import SemanticMatcher
from Pipeline.enhancer import ResumeEnhancer
from Pipeline.latex_generation import generate_resume_pdf

# --- Fake Job Posting ---
FAKE_JOB_POSTING = """
Job Title: Data & BI Analyst
Company: Future Insights Corp.
Location: Berkeley, CA
Reports to: Lead Data Scientist

Job Summary:
Future Insights Corp. is seeking a motivated Data & BI Analyst to transform complex datasets into actionable business intelligence. You will be responsible for developing insightful dashboards, performing deep-dive data analysis, and optimizing data workflows to support our strategic initiatives. This role requires strong proficiency in Python, SQL, and Power BI, with a knack for identifying efficiency improvements and cost-saving opportunities.

Responsibilities:
- Develop and maintain ETL pipelines using Python for robust data integration.
- Design, create, and manage interactive Power BI dashboards for various business units, focusing on clarity and actionable metrics.
- Analyze large datasets using SQL and Python (Pandas, NumPy) to identify trends, anomalies, and insights related to vendor performance, operational efficiency, and financial risk.
- Automate data collection, processing, and reporting tasks to improve efficiency.
- Profile and clean data to ensure accuracy and reliability for analysis and reporting.
- Collaborate with cross-functional teams to understand data needs and deliver data-driven solutions and recommendations.
- Identify and implement opportunities for process optimization and cost savings through data analysis.
- Support ad-hoc data requests and analytical projects.

Qualifications:
- Bachelor's or Master's degree in Analytics, Data Science, Computer Science, Engineering, or a related quantitative field.
- 2+ years of hands-on experience as a Data Analyst, BI Developer, or in a similar analytical role.
- Strong proficiency in Python (especially Pandas, NumPy) for data manipulation and analysis.
- Advanced SQL skills for querying and data extraction.
- Proven experience in developing dashboards and reports with Power BI.
- Familiarity with ETL concepts and tools.
- Excellent analytical and problem-solving skills.
- Strong communication skills.

Preferred:
- Experience with Databricks or other cloud data platforms.
- Knowledge of statistical analysis or basic machine learning techniques (e.g., regression, decision trees).
- Experience with Microsoft Excel for data tasks.
"""

# --- Mock Keywords Data ---
MOCK_KEYWORDS_DATA = {
    "keywords": [
        {"keyword": "Python", "context": "Programming language for data analysis and ETL", "relevance_score": 0.95, "skill_type": "hard skill"},
        {"keyword": "SQL", "context": "Query language for data extraction", "relevance_score": 0.92, "skill_type": "hard skill"},
        {"keyword": "Power BI", "context": "BI tool for creating dashboards", "relevance_score": 0.90, "skill_type": "hard skill"},
        {"keyword": "ETL", "context": "Extract, Transform, Load processes for data integration", "relevance_score": 0.85, "skill_type": "hard skill"},
        {"keyword": "Data Analysis", "context": "Process of examining data sets to find insights", "relevance_score": 0.88, "skill_type": "hard skill"},
        {"keyword": "Pandas", "context": "Python library for data manipulation", "relevance_score": 0.87, "skill_type": "hard skill"},
        {"keyword": "NumPy", "context": "Python library for numerical computing", "relevance_score": 0.84, "skill_type": "hard skill"},
        {"keyword": "Data Integration", "context": "Combining data from different sources", "relevance_score": 0.82, "skill_type": "hard skill"},
        {"keyword": "Dashboards", "context": "Visual displays of key metrics", "relevance_score": 0.86, "skill_type": "hard skill"},
        {"keyword": "Vendor Performance", "context": "Analyzing vendor metrics and KPIs", "relevance_score": 0.75, "skill_type": "hard skill"},
        {"keyword": "Operational Efficiency", "context": "Optimizing business processes", "relevance_score": 0.77, "skill_type": "hard skill"},
        {"keyword": "Financial Risk", "context": "Assessing and mitigating financial risks", "relevance_score": 0.73, "skill_type": "hard skill"},
        {"keyword": "Process Optimization", "context": "Improving business processes", "relevance_score": 0.79, "skill_type": "hard skill"},
        {"keyword": "Cost Savings", "context": "Identifying opportunities to reduce costs", "relevance_score": 0.76, "skill_type": "hard skill"},
        {"keyword": "Databricks", "context": "Unified analytics platform", "relevance_score": 0.70, "skill_type": "hard skill"},
        {"keyword": "Microsoft Excel", "context": "Spreadsheet software for data tasks", "relevance_score": 0.72, "skill_type": "hard skill"}
    ],
    "categories": {
        "Programming Languages": ["Python", "SQL"],
        "BI Tools": ["Power BI", "Tableau"],
        "Libraries/Frameworks": ["Pandas", "NumPy", "Matplotlib", "Scikit-learn"],
        "Cloud/Data Platforms": ["Databricks"],
        "Concepts": [
            "ETL", "Data Integration", "Dashboards", "Data Analysis",
            "Vendor Performance", "Operational Efficiency", "Financial Risk",
            "Process Optimization", "Cost Savings", "Statistical Analysis", "Machine Learning"
        ],
        "Other Tools": ["Microsoft Excel"]
    },
    "job_title_keywords": ["Data Analyst", "BI Analyst"],
    "company_keywords": ["Future Insights Corp."]
}

def run_full_pipeline_test():
    logger.info("--- Starting Full Pipeline Test ---")

    # 1. Load Original Resume Data
    try:
        with open('abhiraj_resume.json', 'r', encoding='utf-8') as f:
            original_resume_data = json.load(f)
        logger.info("Successfully loaded Abhiraj's resume data.")
    except Exception as e:
        logger.error(f"Failed to load abhiraj_resume.json: {e}")
        return

    # 2. Optimization Phase (Simulated - calling core components)
    logger.info("--- Simulating Optimization Phase ---")
    
    # 2a. Use Mock Keywords from Job Description
    logger.info("Using mock keywords for job description...")
    keywords_data = MOCK_KEYWORDS_DATA
    # logger.info(f"Using keywords data: {json.dumps(keywords_data, indent=2)}")

    # 2b. Semantic Matching
    logger.info("Performing semantic matching...")
    matcher = SemanticMatcher() 
    match_results = matcher.process_keywords_and_resume(
        keywords_data,
        original_resume_data,
        similarity_threshold=0.70,
        relevance_threshold=0.5,
        overall_skill_limit=20
    )
    matches_by_bullet = match_results.get("matches_by_bullet", {})
    final_technical_skills = match_results.get("final_technical_skills", {})
    # Ensure final_technical_skills is a dictionary, even if empty from matcher
    if not isinstance(final_technical_skills, dict):
        logger.warning(f"final_technical_skills is not a dict: {type(final_technical_skills)}. Using empty dict.")
        final_technical_skills = {}
    logger.info(f"Semantic matching complete. Found matches for {len(matches_by_bullet)} bullets. Selected {sum(len(sks) for sks in final_technical_skills.values() if isinstance(sks, list))} final skills.")

    # 2c. Resume Enhancement
    logger.info("Enhancing resume...")
    enhancer = ResumeEnhancer()
    enhanced_resume_parsed, modifications = enhancer.enhance_resume(
        original_resume_data, 
        matches_by_bullet,
        final_technical_skills=final_technical_skills
    )
    logger.info(f"Resume enhancement complete. {len(modifications)} modifications made.")

    # 3. PDF Generation Phase (Using Enhanced Data)
    logger.info("--- Generating PDF from Enhanced Resume Data ---")
    output_dir = os.path.abspath('output_resumes') # Ensure output_dir is an absolute path
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.info(f"Created output directory: {output_dir}")
    else:
        logger.info(f"Output directory already exists: {output_dir}")
    
    timestamp = int(time.time())
    pdf_output_path = os.path.join(output_dir, f'abhiraj_enhanced_pipeline_test_{timestamp}.pdf')
    
    logger.info(f"Requesting PDF generation to path: {pdf_output_path}")
    pdf_path, success = generate_resume_pdf(enhanced_resume_parsed, pdf_output_path)
    logger.info(f"PDF generation completed. Path returned: {pdf_path}, Success: {success}")
    
    # Ensure the output directory still exists
    if not os.path.exists(output_dir):
        logger.warning(f"Output directory was deleted during PDF generation. Recreating: {output_dir}")
        os.makedirs(output_dir)
    
    # Check if the actual path exists (regardless of what was returned)
    output_dir_files = os.listdir(output_dir)
    logger.info(f"Files in output directory after generation: {output_dir_files}")
    
    # Check if returned path exists (might be different from requested path)
    if pdf_path and os.path.exists(pdf_path):
        logger.info(f"Confirmed: PDF file exists at returned path: {pdf_path}")
    elif pdf_path:
        logger.warning(f"Path was returned but file does not exist at: {pdf_path}")
    else:
        logger.warning("No valid path was returned from generate_resume_pdf")

    # 4. Analysis & Results
    logger.info("--- Analysis & Results ---")
    if os.path.exists(pdf_path):
        logger.info(f"✅ PDF file generated at: {os.path.abspath(pdf_path)}")
        try:
            # Ensure subprocess is imported if not already at the top
            import subprocess 
            result = subprocess.run(['pdfinfo', pdf_path], capture_output=True, text=True, check=True)
            for line in result.stdout.split('\n'):
                if line.startswith('Pages:'):
                    num_pages = int(line.split(':')[1].strip())
                    logger.info(f"Generated PDF has {num_pages} page(s).")
                    if num_pages == 1:
                        logger.info("Confirmation: Enhanced PDF is a single page.")
                    else:
                        logger.warning(f"Warning: Enhanced PDF has {num_pages} pages - does not fit on a single page.")
                    break
        except Exception as e:
            logger.warning(f"Could not check PDF page count using pdfinfo: {e}. Check manually.")
        
        if not success:
            logger.warning("Note: PDF was generated but adaptive sizing could not create a single-page version.")
    else:
        logger.error(f"❌ Failed to generate enhanced PDF. Path: {pdf_path}")

    logger.info("--- Full Pipeline Test Completed ---")

if __name__ == "__main__":
    # Need to ensure PYTHONPATH is set up if running from root or use relative imports carefully
    # For simplicity if running from root: export PYTHONPATH=.:$PYTHONPATH
    # Or adjust imports if this script is placed elsewhere.
    run_full_pipeline_test() 