"""
Resume bullet enhancer module.

This module enhances resume bullet points by incorporating keywords
while maintaining the original meaning and facts.
"""

import os
import json
import logging
import copy
import re
from typing import Dict, List, Any, Optional, Tuple, Set

# Import OpenAI
try:
    from openai import OpenAI
except ImportError:
    raise ImportError("OpenAI Python package is required. Install with: pip install openai")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("resume_enhancer")


class ResumeEnhancer:
    """
    Enhance resume bullet points with keywords while preserving meaning.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the ResumeEnhancer with OpenAI API key.
        
        Args:
            api_key: OpenAI API key. If None, will try to get from environment variable.
        """
        # Get API key from parameter or environment variable
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Provide it as a parameter or set OPENAI_API_KEY environment variable.")
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)
        
        # Track which bullets have been modified
        self.modified_bullets = set()
        
        # Track keyword usage
        self.keyword_usage = {}
        
    def enhance_resume(self, 
                      resume_data: Dict[str, Any], 
                      matches_by_bullet: Dict[str, List[Dict[str, Any]]], 
                      max_keyword_usage: int = 2) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Enhance resume bullet points with matched keywords.
        
        Args:
            resume_data: Resume JSON data
            matches_by_bullet: Keywords matched to bullets
            max_keyword_usage: Maximum times a keyword can be used
            
        Returns:
            tuple: (Enhanced resume data, List of modifications made)
        """
        logger.info("Starting resume enhancement")
        
        # Create a deep copy of the resume to avoid modifying the original
        enhanced_resume = copy.deepcopy(resume_data)
        
        # Reset tracking data
        self.modified_bullets = set()
        self.keyword_usage = {}
        
        # Track all modifications for reporting
        modifications = []
        
        # Filter matches to limit keyword repetition
        filtered_matches = self._filter_matches_by_usage(matches_by_bullet, max_keyword_usage)
        
        # Process Experience section
        for exp_idx, experience in enumerate(enhanced_resume.get("Experience", [])):
            for bullet_idx, bullet in enumerate(experience.get("responsibilities/achievements", [])):
                # Skip if already modified
                if bullet in self.modified_bullets:
                    continue
                
                # Check if we have matches for this bullet
                if bullet in filtered_matches and filtered_matches[bullet]:
                    # Get keywords for this bullet
                    keywords_for_bullet = filtered_matches[bullet]
                    
                    # Skip if no keywords to add
                    if not keywords_for_bullet:
                        continue
                    
                    # Enhance the bullet with the keywords
                    enhanced_bullet = self._enhance_bullet_with_keywords(bullet, keywords_for_bullet)
                    
                    # Validate the enhancement
                    if self._validate_enhancement(bullet, enhanced_bullet, [kw["keyword"] for kw in keywords_for_bullet]):
                        # Update the resume
                        experience["responsibilities/achievements"][bullet_idx] = enhanced_bullet
                        
                        # Mark as modified
                        self.modified_bullets.add(bullet)
                        
                        # Update keyword usage
                        for keyword_data in keywords_for_bullet:
                            keyword = keyword_data["keyword"].lower()
                            self.keyword_usage[keyword] = self.keyword_usage.get(keyword, 0) + 1
                        
                        # Record the modification
                        modifications.append({
                            "company": experience.get("company", ""),
                            "position": experience.get("title", ""),
                            "original_bullet": bullet,
                            "enhanced_bullet": enhanced_bullet,
                            "keywords_added": [kw["keyword"] for kw in keywords_for_bullet],
                            "experience_idx": exp_idx,
                            "bullet_idx": bullet_idx
                        })
                        
                        logger.info(f"Enhanced bullet: '{bullet[:30]}...' with {len(keywords_for_bullet)} keywords")
        
        logger.info(f"Resume enhancement complete. Modified {len(modifications)} bullets.")
        return enhanced_resume, modifications
    
    def _filter_matches_by_usage(self, 
                               matches_by_bullet: Dict[str, List[Dict[str, Any]]],
                               max_keyword_usage: int = 2) -> Dict[str, List[Dict[str, Any]]]:
        """
        Filter matches to limit keyword repetition across all bullets.
        
        Args:
            matches_by_bullet: Matches grouped by bullet
            max_keyword_usage: Maximum times a keyword can be used
            
        Returns:
            dict: Filtered matches by bullet
        """
        logger.info("Filtering matches by keyword usage limits")
        
        # Sort bullets by match quality (best matches first)
        bullet_quality = []
        for bullet, matches in matches_by_bullet.items():
            if matches:
                # Calculate quality score based on relevance and similarity
                avg_relevance = sum(m["relevance_score"] for m in matches) / len(matches)
                avg_similarity = sum(m["similarity_score"] for m in matches) / len(matches)
                # Weight relevance more heavily
                quality_score = avg_relevance * 0.7 + avg_similarity * 0.3
                
                # Add number of matches as a factor
                quality_score *= min(1.0, len(matches) / 3.0)
            else:
                quality_score = 0
                
            bullet_quality.append((bullet, quality_score))
        
        # Sort bullets by quality score (descending)
        bullet_quality.sort(key=lambda x: x[1], reverse=True)
        
        # Filter matches by keyword usage
        filtered_matches = {}
        keyword_usage = {}  # Local tracking for this function
        
        for bullet, _ in bullet_quality:
            matches = matches_by_bullet.get(bullet, [])
            filtered_matches[bullet] = []
            
            # Sort matches by combined score of relevance and similarity
            matches.sort(key=lambda m: (m["relevance_score"] * 0.7 + m["similarity_score"] * 0.3), reverse=True)
            
            # First, add hard skills up to limit
            hard_skills = []
            for match in matches:
                if match["skill_type"] == "hard skill":
                    keyword = match["keyword"].lower()
                    
                    # Check if usage limit reached
                    if keyword_usage.get(keyword, 0) >= max_keyword_usage:
                        continue
                        
                    hard_skills.append(match)
                    keyword_usage[keyword] = keyword_usage.get(keyword, 0) + 1
                    
                    # Limit to 2 hard skills per bullet
                    if len(hard_skills) >= 2:
                        break
            
            # Then, add soft skills up to limit
            soft_skills = []
            for match in matches:
                if match["skill_type"] == "soft skill":
                    keyword = match["keyword"].lower()
                    
                    # Check if usage limit reached
                    if keyword_usage.get(keyword, 0) >= max_keyword_usage:
                        continue
                        
                    soft_skills.append(match)
                    keyword_usage[keyword] = keyword_usage.get(keyword, 0) + 1
                    
                    # Limit to 1 soft skill per bullet
                    if len(soft_skills) >= 1:
                        break
            
            # Combine hard and soft skills
            filtered_matches[bullet] = hard_skills + soft_skills
            
            # Re-sort by relevance and similarity
            filtered_matches[bullet].sort(key=lambda m: (m["relevance_score"], m["similarity_score"]), reverse=True)
            
            # Limit to total of 3 keywords per bullet
            filtered_matches[bullet] = filtered_matches[bullet][:3]
        
        # Log statistics
        total_keywords = sum(len(matches) for matches in filtered_matches.values())
        logger.info(f"Filtered to {total_keywords} keywords across {len(filtered_matches)} bullets")
        
        return filtered_matches
    
    def _enhance_bullet_with_keywords(self, bullet: str, keywords: List[Dict[str, Any]]) -> str:
        """
        Enhance a bullet point with multiple keywords.
        
        Args:
            bullet: Original bullet text
            keywords: Keywords to incorporate
            
        Returns:
            str: Enhanced bullet text
        """
        # Prepare keyword information for prompt
        keyword_text = ""
        for idx, kw in enumerate(keywords):
            keyword_text += f"{idx+1}. {kw['keyword']}\n   Context from job description: {kw['context']}\n"
        
        # Create prompt for bullet enhancement
        prompt = f"""
        Task: Enhance the following resume bullet point by naturally incorporating the specified keywords.

        Original bullet point:
        "{bullet}"

        Keywords to incorporate naturally:
        {keyword_text}

        Requirements:
        1. MUST include ALL the keywords in the enhanced bullet point
        2. MUST preserve ALL numbers, percentages, and metrics EXACTLY as they appear
        3. MUST maintain the original meaning, achievements, and scope of work
        4. MUST keep the same professional tone and tense
        5. Changes should be minimal and natural - only make changes needed to incorporate keywords
        6. Final bullet MUST sound natural and professional
        7. If impossible to include all keywords naturally, prioritize the ones listed first

        Enhanced bullet point:
        """
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional resume writer specializing in keyword optimization while maintaining factual accuracy."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent output
                max_tokens=512
            )
            
            # Extract the enhanced bullet
            enhanced_bullet = response.choices[0].message.content.strip()
            
            # Clean up the response (remove quotes if present)
            if enhanced_bullet.startswith('"') and enhanced_bullet.endswith('"'):
                enhanced_bullet = enhanced_bullet[1:-1]
            
            # Clean up any extra spaces
            enhanced_bullet = re.sub(r'\s+', ' ', enhanced_bullet).strip()
            
            return enhanced_bullet
            
        except Exception as e:
            logger.error(f"Error enhancing bullet: {str(e)}")
            # Return original if enhancement fails
            return bullet
    
    def _validate_enhancement(self, original: str, enhanced: str, keywords: List[str]) -> bool:
        """
        Validate that the enhanced bullet properly incorporates keywords and
        preserves the original meaning and metrics.
        
        Args:
            original: Original bullet text
            enhanced: Enhanced bullet text
            keywords: List of keywords that should be included
            
        Returns:
            bool: True if enhancement is valid, False otherwise
        """
        # Check 1: All keywords are present
        keywords_included = True
        missing_keywords = []
        
        for keyword in keywords:
            if keyword.lower() not in enhanced.lower():
                keywords_included = False
                missing_keywords.append(keyword)
        
        if not keywords_included:
            logger.warning(f"Enhancement validation failed: Missing keywords {missing_keywords}")
            return False
        
        # Check 2: All metrics are preserved
        # Extract numbers and percentages from original
        metric_pattern = r'\d+(?:\.\d+)?%|\$\d+(?:,\d+)*(?:\.\d+)?|\d+(?:,\d+)*(?:\.\d+)?'
        original_metrics = re.findall(metric_pattern, original)
        
        # Check if all original metrics are in enhanced
        metrics_preserved = True
        
        for metric in original_metrics:
            if metric not in enhanced:
                metrics_preserved = False
                logger.warning(f"Enhancement validation failed: Missing metric {metric}")
                break
        
        if not metrics_preserved:
            return False
        
        # Check 3: Length is reasonable
        if len(enhanced) > len(original) * 1.5:
            logger.warning(f"Enhancement validation failed: Too long (Original: {len(original)}, Enhanced: {len(enhanced)})")
            return False
        
        # Check 4: Doesn't deviate too much from original
        # Simple check using length as a proxy for now
        if abs(len(enhanced) - len(original)) > len(original) * 0.5:
            logger.warning(f"Enhancement validation failed: Too different in length")
            return False
        
        return True
    
    def save_results(self, 
                    enhanced_resume: Dict[str, Any], 
                    modifications: List[Dict[str, Any]], 
                    output_dir: str) -> Dict[str, str]:
        """
        Save enhancement results to files.
        
        Args:
            enhanced_resume: Enhanced resume data
            modifications: List of modifications made
            output_dir: Directory to save results to
            
        Returns:
            dict: Paths to saved files
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Output paths
        enhanced_resume_path = os.path.join(output_dir, "enhanced_resume.json")
        modifications_path = os.path.join(output_dir, "modifications.json")
        
        # Save enhanced resume
        with open(enhanced_resume_path, 'w', encoding='utf-8') as f:
            json.dump(enhanced_resume, f, indent=2)
        
        # Save modifications
        with open(modifications_path, 'w', encoding='utf-8') as f:
            json.dump(modifications, f, indent=2)
        
        logger.info(f"Enhanced resume saved to {enhanced_resume_path}")
        logger.info(f"Modifications saved to {modifications_path}")
        
        return {
            "enhanced_resume": enhanced_resume_path,
            "modifications": modifications_path
        }


# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhance resume bullets with keywords")
    parser.add_argument("--resume", type=str, required=True, help="Path to parsed resume JSON file")
    parser.add_argument("--matches", type=str, required=True, help="Path to semantic matches JSON file")
    parser.add_argument("--max-usage", type=int, default=2, help="Maximum times a keyword can be used")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    
    args = parser.parse_args()
    
    # Load input files
    with open(args.resume, 'r', encoding='utf-8') as f:
        resume_data = json.load(f)
        
    with open(args.matches, 'r', encoding='utf-8') as f:
        matches_data = json.load(f)
        
    # Get matches by bullet
    matches_by_bullet = matches_data.get("matches_by_bullet", {})
    
    # Initialize resume enhancer
    enhancer = ResumeEnhancer()
    
    # Enhance resume
    enhanced_resume, modifications = enhancer.enhance_resume(
        resume_data, 
        matches_by_bullet,
        max_keyword_usage=args.max_usage
    )
    
    # Save results
    enhancer.save_results(enhanced_resume, modifications, args.output_dir)
    
    # Print summary
    print(f"Resume enhancement complete.")
    print(f"Modified {len(modifications)} bullets.")
    print(f"Enhanced resume saved to {args.output_dir}/enhanced_resume.json")