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
import httpx
import asyncio
# Removed cachetools

# Import OpenAI
try:
    from openai import OpenAI
except ImportError:
    raise ImportError("OpenAI Python package is required. Install with: pip install openai")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger("resume_enhancer")


class ResumeEnhancer:
    """
    Enhance resume bullet points with keywords while preserving meaning.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        """
        Initialize the ResumeEnhancer with OpenAI API key.
        
        Args:
            api_key: OpenAI API key. If None, will try to get from environment variable.
            model: OpenAI model to use
        """
        # Get API key from parameter or environment variable
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        # Use explicit httpx client to avoid proxy issues on Render
        try:
            # Explicitly create httpx async client, disabling environment proxy usage
            httpx_async_client = httpx.AsyncClient(trust_env=False)
            self.client = OpenAI(api_key=self.api_key, http_client=httpx_async_client)
            logger.info("ResumeEnhancer: OpenAI client initialized successfully with custom httpx async client.")
        except Exception as e:
            logger.error(f"ResumeEnhancer: Failed to initialize OpenAI async client: {e}", exc_info=True)
            raise RuntimeError(f"ResumeEnhancer: Could not initialize OpenAI async client - {e}") from e
        
        self.model = "gpt-4.1-mini" # Updated model to gpt-4.1-mini
        # Removed enhancement_cache initialization
        
        # Track which bullets have been modified
        self.modified_bullets = set()
        
        # Track keyword usage
        self.keyword_usage = {}
        
    async def enhance_resume(self, 
                      resume_data: Dict[str, Any], 
                      matches_by_bullet: Dict[str, List[Dict[str, Any]]], 
                      final_technical_skills: Optional[Dict[str, List[str]]] = None,
                      max_keyword_usage: int = 2) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Enhance resume bullet points with matched keywords and update technical skills section.
        
        Args:
            resume_data: Resume JSON data
            matches_by_bullet: Keywords matched to bullets
            final_technical_skills: Dictionary of categorized technical skills to update the resume with.
            max_keyword_usage: Maximum times a keyword can be used in bullet enhancements
            
        Returns:
            tuple: (Enhanced resume data, List of modifications made)
        """
        logger.info("Starting resume enhancement for bullets and skills section")
        
        enhanced_resume = copy.deepcopy(resume_data)
        self.modified_bullets = set() # Should ideally be instance variable if method is called multiple times on same instance for different resumes.
        self.keyword_usage = {}    # Same as above. For a single call, local is fine.
        
        modifications = []
        
        filtered_matches = self._filter_matches_by_usage(matches_by_bullet, max_keyword_usage)
        
        tasks = []
        # Prepare tasks for bullet enhancement
        for exp_idx, experience in enumerate(enhanced_resume.get("Experience", [])):
            for bullet_idx, bullet_text in enumerate(experience.get("responsibilities/achievements", [])):
                # We use bullet_text as the key for filtered_matches
                if bullet_text in filtered_matches and filtered_matches[bullet_text]:
                    keywords_for_bullet = filtered_matches[bullet_text]
                    if not keywords_for_bullet:
                        continue
                    # Ensure we don't try to enhance an already processed bullet (though with deepcopy and no shared state, this might be redundant here)
                    if bullet_text in self.modified_bullets: 
                        continue
                    tasks.append(self._enhance_bullet_with_keywords_wrapper(exp_idx, bullet_idx, bullet_text, keywords_for_bullet))

        if tasks:
            logger.info(f"Starting concurrent enhancement for {len(tasks)} bullets.")
            enhancement_results = await asyncio.gather(*tasks) # return_exceptions=True is implicit in wrapper
            logger.info(f"Finished concurrent enhancement. Processing {len(enhancement_results)} results.")

            for result_item in enhancement_results:
                exp_idx, bullet_idx, enhanced_text_or_exc, original_bullet, keywords_list = result_item
                
                current_experience_section = enhanced_resume.get("Experience", [])
                if exp_idx >= len(current_experience_section):
                    logger.error(f"Experience index {exp_idx} out of bounds. Skipping result.")
                    continue
                
                experience_entry = current_experience_section[exp_idx]
                
                if isinstance(enhanced_text_or_exc, Exception):
                    logger.error(f"Error enhancing bullet (exp:{exp_idx}, bullet:{bullet_idx}) '{original_bullet[:30]}...': {enhanced_text_or_exc}")
                    # Original bullet remains, no modification recorded for this attempt beyond error log
                    continue

                enhanced_bullet = enhanced_text_or_exc
                
                # Validate the enhancement
                # Note: _validate_enhancement expects a list of keyword strings
                keyword_strings = [kw["keyword"] for kw in keywords_list]
                if self._validate_enhancement(original_bullet, enhanced_bullet, keyword_strings):
                    experience_entry["responsibilities/achievements"][bullet_idx] = enhanced_bullet
                    self.modified_bullets.add(original_bullet) # Track original bullet text as modified
                    
                    for keyword_data in keywords_list:
                        keyword = keyword_data["keyword"].lower()
                        self.keyword_usage[keyword] = self.keyword_usage.get(keyword, 0) + 1
                    
                    modifications.append({
                        "company": experience_entry.get("company", ""),
                        "position": experience_entry.get("title", ""),
                        "original_bullet": original_bullet,
                        "enhanced_bullet": enhanced_bullet,
                        "keywords_added": keyword_strings,
                        "experience_idx": exp_idx,
                        "bullet_idx": bullet_idx
                    })
                    logger.info(f"Successfully enhanced bullet (exp:{exp_idx}, bullet:{bullet_idx}): '{original_bullet[:30]}...'")
                else:
                    logger.warning(f"Validation failed for enhanced bullet (exp:{exp_idx}, bullet:{bullet_idx}): '{original_bullet[:30]}...'. Original kept. Enhanced: '{enhanced_bullet[:50]}...'")
                    # Original bullet remains if validation fails

        bullet_mod_count = sum(1 for mod in modifications if "section" not in mod) # A bit fragile way to count bullet mods
        logger.info(f"Resume bullet point enhancement processing complete. Modified {bullet_mod_count} bullets.")

        # --- Technical Skills Section Update ---
        if final_technical_skills is not None:
            logger.info("Updating technical skills section.")
            original_skills_section_snapshot = copy.deepcopy(enhanced_resume.get("Skills", {}))
            
            if "Skills" not in enhanced_resume or not isinstance(enhanced_resume["Skills"], dict):
                enhanced_resume["Skills"] = {} # Ensure Skills section is a dict
            
            # The final_technical_skills is already structured as Dict[category, List[skill_names]]
            # We want to update/replace the "Technical Skills" part under "Skills"
            # The parsed resume might have Skills: {"Technical Skills": {"Category1": [], ...}} or 
            # Skills: {"Technical Skills": [] (flat list)}
            # The final_technical_skills provides the new structure for "Technical Skills"
            
            enhanced_resume["Skills"]["Technical Skills"] = final_technical_skills
            logger.debug(f"Updated 'Technical Skills' in resume to: {final_technical_skills}")

            modifications.append({
                "section": "Skills",
                "type": "Technical Skills Update",
                "original_skills_snapshot": original_skills_section_snapshot.get("Technical Skills", "Not present or not a dict"),
                "updated_skills_structure": final_technical_skills,
                "message": f"Technical skills section updated with {sum(len(sks) for sks in final_technical_skills.values())} skills across {len(final_technical_skills)} categories."
            })
            logger.info(f"Technical skills section updated successfully.")
        else:
            logger.info("No final technical skills data provided, skipping skills section update.")

        total_modifications = len(modifications)
        bullet_mods = sum(1 for mod in modifications if mod.get("type") != "Technical Skills Update")
        skill_sec_mods = total_modifications - bullet_mods

        logger.info(f"Resume enhancement process complete. Total modifications: {total_modifications} ({bullet_mods} bullet changes, {skill_sec_mods} skills section changes).")
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

    async def _enhance_bullet_with_keywords(self, bullet: str, keywords: List[Dict[str, Any]]) -> str:
        """
        Enhance a bullet point with multiple keywords. (No caching)
        Args:
            bullet: Original bullet text
            keywords: List of keyword dicts (with 'keyword' and 'context')
        Returns:
            str: Enhanced bullet text
        """
        logger.debug(f"Enhancing bullet (no cache): '{bullet[:50]}...'")
        
        keyword_text_for_prompt = ""
        for idx, kw_data in enumerate(keywords): 
            keyword_str = kw_data['keyword']
            context_str = kw_data.get('context', 'N/A')
            keyword_text_for_prompt += f"{idx+1}. {keyword_str}\\n   Context from job description: {context_str}\\n"

        prompt = f"""
        Task: Enhance the following resume bullet point by naturally incorporating the specified keywords.

        Original bullet point:
        "{bullet}"

        Keywords to incorporate naturally:
        {keyword_text_for_prompt}

        Requirements:
        1. MUST include ALL the keywords (from the keyword strings provided) in the enhanced bullet point
        2. MUST preserve ALL numbers, percentages, and metrics EXACTLY as they appear
        3. MUST maintain the original meaning, achievements, and scope of work
        4. MUST keep the same professional tone and tense
        5. Changes should be minimal and natural - only make changes needed to incorporate keywords
        6. Final bullet MUST sound natural and professional
        7. If impossible to include all keywords naturally, prioritize the ones listed first

        Enhanced bullet point:
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model, # self.model is "gpt-4.1-turbo"
                messages=[
                    {"role": "system", "content": "You are a professional resume writer specializing in keyword optimization while maintaining factual accuracy."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=512
            )
            
            enhanced_bullet = response.choices[0].message.content.strip()
            if enhanced_bullet.startswith('"') and enhanced_bullet.endswith('"'):
                enhanced_bullet = enhanced_bullet[1:-1]
            enhanced_bullet = re.sub(r'\s+', ' ', enhanced_bullet).strip()
            return enhanced_bullet
        except Exception as e:
            logger.error(f"Error enhancing bullet '{bullet[:30]}...' with OpenAI: {e}", exc_info=True)
            # Re-raise to be caught by the wrapper in enhance_resume for proper error handling per bullet
            raise e

    async def _enhance_bullet_with_keywords_wrapper(self, exp_idx: int, bullet_idx: int, bullet_text: str, keywords: List[Dict[str, Any]]):
        """
        Wrapper for _enhance_bullet_with_keywords to pass through indices and other data.
        """
        try:
            enhanced_text = await self._enhance_bullet_with_keywords(bullet_text, keywords)
            return exp_idx, bullet_idx, enhanced_text, bullet_text, keywords # Success case
        except Exception as e:
            # Return exception along with context, so gather can collect it and we can log appropriately
            return exp_idx, bullet_idx, e, bullet_text, keywords # Failure case
    
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

    # Define an async main function to run the enhancer
    async def main():
        # Enhance resume
        enhanced_resume, modifications = await enhancer.enhance_resume(
            resume_data, 
            matches_by_bullet,
            # final_technical_skills can be passed if available from semantic_matches.json or other source
            # For this example, assuming it might not be in args.matches by default.
            # If it is, it should be loaded, e.g., matches_data.get("final_technical_skills")
            final_technical_skills=matches_data.get("final_technical_skills"), 
            max_keyword_usage=args.max_usage
        )
        
        # Save results
        enhancer.save_results(enhanced_resume, modifications, args.output_dir)
        
        # Print summary
        # Calculate bullet modifications based on the structure of 'modifications' list
        bullet_modifications_count = sum(1 for mod in modifications if mod.get("type") != "Technical Skills Update" and "section" not in mod)
        print(f"Resume enhancement complete.")
        print(f"Modified {bullet_modifications_count} bullets.") # Adjusted to count only bullet mods
        print(f"Enhanced resume saved to {args.output_dir}/enhanced_resume.json")

    # Run the async main function
    asyncio.run(main())