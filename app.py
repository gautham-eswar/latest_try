import os
import argparse
import json
import logging
from Pipeline.main import Pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    Main function to run the resume optimization pipeline.
    """
    parser = argparse.ArgumentParser(description="Resume Optimization Pipeline")
    parser.add_argument("--resume", type=str, required=True, help="Path to the resume JSON file")
    parser.add_argument("--job-desc", type=str, required=True, help="Path to the job description text file")
    parser.add_argument("--output", type=str, required=True, help="Path to the output directory to save results")
    args = parser.parse_args()

    # --- Configuration ---
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # --- Create and Run Pipeline ---
    try:
        pipeline = Pipeline(
            resume_path=args.resume,
            job_desc_path=args.job_desc,
            output_dir=args.output,
            config={
                'similarity_threshold': 0.75,
                'relevance_threshold': 0.6,
                'overall_skill_limit': 20,
                'max_keyword_usage': 2
            }
        )
        
        # Execute the pipeline
        pipeline.run()

        logger.info("--- Pipeline Execution Summary ---")
        logger.info(f"Results saved to: {args.output}")
        logger.info("Pipeline finished successfully.")

    except FileNotFoundError as e:
        logger.error(f"Error: Input file not found - {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Error: Invalid JSON format in resume file - {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main() 