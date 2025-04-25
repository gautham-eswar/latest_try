"""
Resume Optimization Pipeline

This script integrates all components of the resume optimization pipeline:
1. Resume Parsing
2. Keyword Extraction
3. Semantic Matching
4. Resume Enhancement

It provides a unified interface to run the entire optimization process.
"""

import os
import json
import logging
import argparse
from typing import Dict, Any, Optional

# Import component modules - matching actual filenames and classes
from resume_parser import ResumeParser
from keyword_extractor import KeywordExtractor
from embeddings import SemanticMatcher
from enhancer import ResumeEnhancer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("resume_optimizer")


class ResumeOptimizationPipeline:
    """
    Orchestrates the complete resume optimization pipeline.
    """
    
    def __init__(self, api_key: Optional[str] = None, verbose: bool = False):
        """
        Initialize the pipeline with OpenAI API key.
        
        Args:
            api_key: OpenAI API key. If None, will try to get from environment variable.
            verbose: Whether to enable verbose logging.
        """
        # Set logging level
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            
        # Get API key from parameter or environment variable
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No OpenAI API key provided. Some functionality may be limited.")
        
        # Initialize component modules
        self.parser = ResumeParser(api_key=self.api_key)
        self.keyword_extractor = KeywordExtractor(api_key=self.api_key)
        self.matcher = SemanticMatcher(api_key=self.api_key)
        self.enhancer = ResumeEnhancer(api_key=self.api_key)
        
        # Storage for intermediate results
        self.resume_text = None
        self.resume_data = None
        self.keywords_data = None
        self.semantic_matches = None
        self.enhanced_resume = None
        self.modifications = None
        
    def run_pipeline(self, 
                    resume_file_path: str, 
                    job_description_text: str,
                    similarity_threshold: float = 0.75,
                    max_keyword_usage: int = 2,
                    output_dir: str = "output") -> Dict[str, Any]:
        """
        Run the complete optimization pipeline.
        
        Args:
            resume_file_path: Path to resume file (PDF, DOCX, or TXT)
            job_description_text: Job description text
            similarity_threshold: Threshold for semantic matching
            max_keyword_usage: Maximum times a keyword can be used
            output_dir: Directory to save results
            
        Returns:
            dict: Results summary
        """
        logger.info("Starting resume optimization pipeline")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Step 1: Parse resume
        logger.info("Step 1: Parsing resume")
        self.resume_text = self.parser.extract_text_from_file(resume_file_path)
        self.resume_data = self.parser.parse_resume(self.resume_text)
        
        # Save intermediate result
        with open(os.path.join(output_dir, "parsed_resume.json"), 'w', encoding='utf-8') as f:
            json.dump(self.resume_data, f, indent=2)
        
        # Step 2: Extract keywords from job description
        logger.info("Step 2: Extracting keywords from job description")
        self.keywords_data = self.keyword_extractor.extract_keywords(job_description_text)
        
        # Save intermediate result
        with open(os.path.join(output_dir, "extracted_keywords.json"), 'w', encoding='utf-8') as f:
            json.dump(self.keywords_data, f, indent=2)
            
        # Step 3: Semantic matching and deduplication
        logger.info("Step 3: Semantic matching and keyword deduplication")
        self.semantic_matches = self.matcher.process_keywords_and_resume(
            self.keywords_data,
            self.resume_data,
            similarity_threshold=similarity_threshold
        )
        
        # Save intermediate result
        with open(os.path.join(output_dir, "semantic_matches.json"), 'w', encoding='utf-8') as f:
            json.dump(self.semantic_matches, f, indent=2)
        
        # Step 4: Enhance resume
        logger.info("Step 4: Enhancing resume with keywords")
        self.enhanced_resume, self.modifications = self.enhancer.enhance_resume(
            self.resume_data,
            self.semantic_matches["matches_by_bullet"],
            max_keyword_usage=max_keyword_usage
        )
        
        # Save enhancement results
        enhancement_files = self.enhancer.save_results(
            self.enhanced_resume,
            self.modifications,
            output_dir
        )
        
        # Generate summary
        summary = {
            "statistics": {
                "keywords_extracted": len(self.keywords_data["keywords"]),
                "keywords_deduplicated": len(self.semantic_matches["deduplicated_keywords"]),
                "bullets_processed": self.semantic_matches["statistics"]["bullets_processed"],
                "bullets_with_matches": self.semantic_matches["statistics"]["bullets_with_matches"],
                "bullets_enhanced": len(self.modifications)
            },
            "file_paths": {
                "parsed_resume": os.path.join(output_dir, "parsed_resume.json"),
                "extracted_keywords": os.path.join(output_dir, "extracted_keywords.json"),
                "semantic_matches": os.path.join(output_dir, "semantic_matches.json"),
                "enhanced_resume": enhancement_files["enhanced_resume"],
                "modifications": enhancement_files["modifications"]
            }
        }
        
        # Save summary
        with open(os.path.join(output_dir, "optimization_summary.json"), 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        logger.info("Resume optimization pipeline complete")
        return summary


# Command-line interface
def main():
    parser = argparse.ArgumentParser(description="Resume Optimization Pipeline")
    
    parser.add_argument(
        "--resume", 
        type=str, 
        required=True,
        help="Path to resume file (PDF, DOCX, or TXT)"
    )
    
    parser.add_argument(
        "--jd", 
        type=str, 
        required=True,
        help="Path to job description file or the job description text"
    )
    
    parser.add_argument(
        "--api-key", 
        type=str, 
        default=os.getenv("OPENAI_API_KEY"),
        help="OpenAI API key (defaults to OPENAI_API_KEY environment variable)"
    )
    
    parser.add_argument(
        "--similarity", 
        type=float, 
        default=0.75,
        help="Similarity threshold for matching (0.0-1.0)"
    )
    
    parser.add_argument(
        "--max-usage", 
        type=int, 
        default=2,
        help="Maximum times a keyword can be used"
    )
    
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default="output",
        help="Output directory"
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Check if JD is a file path or direct text
    job_description_text = args.jd
    if os.path.isfile(args.jd):
        with open(args.jd, 'r', encoding='utf-8') as f:
            job_description_text = f.read()
    
    # Initialize pipeline
    pipeline = ResumeOptimizationPipeline(api_key=args.api_key, verbose=args.verbose)
    
    # Run pipeline
    summary = pipeline.run_pipeline(
        resume_file_path=args.resume,
        job_description_text=job_description_text,
        similarity_threshold=args.similarity,
        max_keyword_usage=args.max_usage,
        output_dir=args.output_dir
    )
    
    # Print summary
    print("\n" + "="*50)
    print("RESUME OPTIMIZATION SUMMARY")
    print("="*50)
    print(f"Keywords extracted: {summary['statistics']['keywords_extracted']}")
    print(f"Keywords after deduplication: {summary['statistics']['keywords_deduplicated']}")
    print(f"Resume bullets processed: {summary['statistics']['bullets_processed']}")
    print(f"Bullets with keyword matches: {summary['statistics']['bullets_with_matches']}")
    print(f"Bullets enhanced: {summary['statistics']['bullets_enhanced']}")
    print("\nOutput files:")
    for name, path in summary["file_paths"].items():
        print(f"- {name}: {path}")


if __name__ == "__main__":
    main()