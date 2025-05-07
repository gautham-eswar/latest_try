

import logging
import uuid

from supabase import Client

from Services.database import get_db


logging.basicConfig(
    level=logging.INFO, format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
db = get_db()

def create_optimization_job(resume_id, user_id, job_description):

    logger.info("Creating job tracking at the database")
    job_id = uuid.uuid4().hex   
    response = db.table("optimization_jobs").insert({
        "id": job_id,
        "user_id": user_id,
        "resume_id": resume_id,
        "job_description": job_description, 
        "status": "Processing Keywords"
    }).execute()

    if not (hasattr(response, "data") and response.data):
        error_text = getattr(response, "error", "Unknown error")
        logger.warning(
            f"Error creating optimization job tracking: {error_text}. \
            Proceeding without database tracking.",
            exc_info=True,
        )
        return None
    
    logger.info(f"Database job tracking created successfully. Job ID: {job_id} ")
    return job_id


def update_optimization_job(job_id, data:dict):
    if not job_id:
        return
    
    response = db.table('optimization_jobs')\
        .update(data).eq("id", job_id).execute()
    
    if not (hasattr(response, "data") and response.data):
        error_text = getattr(response, "error", "Unknown error")
        logger.warning(
            f"Error updating optimization job: {error_text}",
            exc_info=True,
        )


def post_optimization_job(job):

    logger.info("Creating job tracking at the database")

    try: 
        job_id = job["id"]
        response = db.table("optimization_jobs").insert(job).execute()

        if not (hasattr(response, "data") and response.data):
            error_text = getattr(response, "error", "Unknown error")
            logger.warning(
                f"Error posting optimization job: {error_text}.",
                exc_info=True,
            )
            return None
        
        logger.info(f"Optimization Job successfully tracked in the database. Job ID: {job_id} ")
        return job_id
    
    except Exception as error:
        logger.info(f"Database job tracking failed: {job_id} ")
        return

