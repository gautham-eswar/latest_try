"""
Semantic matcher for resume optimization.

This module handles embedding generation, keyword deduplication, 
and semantic matching between keywords and resume bullet points.
"""

import os
import json
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Set
import pandas as pd
import httpx
import copy
import asyncio
# Removed cachetools imports

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
logger = logging.getLogger("semantic_matcher")


class SemanticMatcher:
    """
    Generate embeddings, deduplicate keywords, and match keywords to resume bullets.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-ada-002"):
        """
        Initialize the SemanticMatcher with OpenAI API key.
        
        Args:
            api_key: OpenAI API key. If None, will try to get from environment variable.
            model: OpenAI model to use for embedding generation
        """
        # Get API key from parameter or environment variable
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not provided or found in environment variables")
        
        # Use explicit httpx client to avoid proxy issues on Render
        try:
            # Explicitly create httpx client, disabling environment proxy usage
            httpx_async_client = httpx.AsyncClient(trust_env=False)
            self.client = OpenAI(api_key=self.api_key, http_client=httpx_async_client)
            logger.info("SemanticMatcher: OpenAI client initialized successfully with custom httpx async client.")
        except Exception as e:
            logger.error(f"SemanticMatcher: Failed to initialize OpenAI async client: {e}", exc_info=True)
            # Depending on desired behavior, either raise the error or handle it
            # For now, let's raise it to make the failure clear
            raise RuntimeError(f"SemanticMatcher: Could not initialize OpenAI client - {e}") from e
            # self.client = None # Or set client to None if you want to handle errors downstream
        
        self.model = model
        self.generation_model = "gpt-4.1-mini" # Updated for categorization tasks to gpt-4.1-mini
        
        # Removed caches
        
        # Default similarity threshold
        self.similarity_threshold = 0.75
        self.skill_similarity_threshold = 0.90 # For deduplicating skills
        
    async def process_keywords_and_resume(self, 
                                   keywords_data: Dict[str, Any], 
                                   resume_data: Dict[str, Any],
                                   similarity_threshold: float = 0.75,
                                   relevance_threshold: float = 0.6,
                                   overall_skill_limit: int = 15) -> Dict[str, Any]:
        """
        Process keywords and resume data through the complete pipeline.
        
        Args:
            keywords_data: Extracted keywords with metadata
            resume_data: Parsed resume JSON
            similarity_threshold: Threshold for semantic matching (0-1) for bullets
            relevance_threshold: Minimum relevance score for JD skills to be considered for skills section
            overall_skill_limit: Target total number of technical skills in the enhanced resume
            
        Returns:
            dict: Results with deduplicated keywords, matches, statistics, and selected technical skills
        """
        logger.info("Starting semantic processing pipeline for bullets and skills")
        self.similarity_threshold = similarity_threshold
        
        # --- Bullet Point Processing & Initial Resume Skills Embedding ---
        logger.info("Concurrently generating embeddings for JD keywords, resume bullets, and resume skills...")
        
        # Extract bullet points from resume first as it's synchronous
        bullet_points = self.extract_bullet_points(resume_data)
        
        # Run keyword, bullet, and resume skill embedding generation concurrently
        concurrent_embedding_results = await asyncio.gather(
            self.generate_keyword_embeddings(keywords_data["keywords"]),
            self.generate_bullet_embeddings(bullet_points),
            self.extract_resume_technical_skills(resume_data), # Added resume skills embedding
            return_exceptions=True
        )
        
        # Handle results and potential errors from asyncio.gather
        keywords_with_embeddings = []
        if isinstance(concurrent_embedding_results[0], Exception):
            logger.error(f"Error generating keyword embeddings: {concurrent_embedding_results[0]}")
        else:
            keywords_with_embeddings = concurrent_embedding_results[0]
            
        bullets_with_embeddings = []
        if isinstance(concurrent_embedding_results[1], Exception):
            logger.error(f"Error generating bullet embeddings: {concurrent_embedding_results[1]}")
        else:
            bullets_with_embeddings = concurrent_embedding_results[1]

        resume_skills_structured = {} # Default to empty dict
        if isinstance(concurrent_embedding_results[2], Exception):
            logger.error(f"Error extracting and embedding resume technical skills: {concurrent_embedding_results[2]}")
        else:
            resume_skills_structured = concurrent_embedding_results[2]

        logger.info(f"Generated embeddings for {len(keywords_with_embeddings)} keywords, {len(bullets_with_embeddings)} bullets, and {sum(len(cat_data.get('skills', [])) for cat_data in resume_skills_structured.values())} resume skills.")

        logger.info("Step 2: Deduplicating JD keywords (for bullets)")
        deduplicated_keywords_for_bullets = self.deduplicate_keywords(keywords_with_embeddings)
        
        # Step 3 (Extracting bullet points) was done earlier
        logger.info(f"Extracted {len(bullet_points)} bullet points from resume")
        
        logger.info("Step 5: Calculating similarity between JD keywords and resume bullets")
        similarity_results = self.calculate_similarity(deduplicated_keywords_for_bullets, bullets_with_embeddings)
        
        logger.info("Step 6: Grouping matches by bullet point")
        matches_by_bullet = self.group_matches_by_bullet(similarity_results)

        # --- Technical Skills Section Processing ---
        # Step 7 (Extracting and embedding resume technical skills) was done concurrently above
        logger.info(f"Resume technical skills already extracted and embedded. Found {len(resume_skills_structured)} categories.")
        
        logger.info("Step 8: Filtering JD keywords for hard skills relevant to skills section")
        # Ensure keywords_with_embeddings is available and populated
        jd_hard_skills_for_section = [
            kw for kw in keywords_with_embeddings 
            if kw.get("skill_type") == "hard skill" and kw.get("relevance_score", 0) >= relevance_threshold
        ]
        logger.debug(f"Found {len(jd_hard_skills_for_section)} JD hard skills meeting relevance threshold {relevance_threshold}")

        resume_skill_categories = list(resume_skills_structured.keys())
        logger.info(f"Step 9: Categorizing {len(jd_hard_skills_for_section)} JD hard skills against resume categories: {resume_skill_categories}")
        categorized_jd_hard_skills = await self._categorize_jd_skills_with_openai(jd_hard_skills_for_section, resume_skill_categories)

        logger.info("Step 10: Selecting final technical skills for resume section")
        # select_final_technical_skills calls _get_embedding through consolidate_skills -> extract_resume_technical_skills (if not already embedded)
        # and deduplicate_within_category. So it also needs to be async.
        # However, current select_final_technical_skills expects embeddings to be there.
        # The skill objects passed to select_final_technical_skills (resume_skills_structured, categorized_jd_hard_skills)
        # should already have their embeddings generated by previous async calls.
        # So, select_final_technical_skills itself might not need to be async if its internal embedding calls are removed
        # or if it only uses pre-computed embeddings.
        # For now, assuming select_final_technical_skills does NOT make new embedding calls.
        # If it does, it needs to be made async and awaited.
        # Based on current structure, embeddings are generated *before* this step.
        final_technical_skills, skill_selection_log = self.select_final_technical_skills(
            resume_skills_structured,
            categorized_jd_hard_skills,
            overall_skill_limit=overall_skill_limit
        )
        logger.debug(f"Skill selection log: {skill_selection_log}")

        # Create result dictionary
        result = {
            "deduplicated_keywords_for_bullets": [k for k in deduplicated_keywords_for_bullets if "embedding" not in k],
            "similarity_results": similarity_results,
            "matches_by_bullet": matches_by_bullet,
            "final_technical_skills": final_technical_skills, # New addition
            "statistics": {
                "original_keywords": len(keywords_data["keywords"]),
                "deduplicated_keywords_for_bullets": len(deduplicated_keywords_for_bullets),
                "bullets_processed": len(bullet_points),
                "bullets_with_matches": sum(1 for matches in matches_by_bullet.values() if matches),
                "total_bullet_matches": sum(len(matches) for matches in matches_by_bullet.values()),
                "initial_resume_skill_categories_count": len(resume_skills_structured),
                "initial_resume_total_technical_skills": sum(len(sks['skills']) for sks in resume_skills_structured.values()),
                "jd_hard_skills_considered_for_section": len(jd_hard_skills_for_section),
                "final_skill_categories_count": len(final_technical_skills),
                "final_total_technical_skills": sum(len(sks) for sks in final_technical_skills.values()),
            },
            "skill_selection_process_log": skill_selection_log
        }
        
        logger.info(f"Semantic processing complete. Found {result['statistics']['total_bullet_matches']} bullet matches. Selected {result['statistics']['final_total_technical_skills']} technical skills.")
        return result
    
    async def generate_keyword_embeddings(self, keywords: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for keywords with context.
        
        Args:
            keywords: List of keywords with metadata
            
        Returns:
            list: Keywords with embeddings added
        """
        tasks = []
        for keyword in keywords:
            text = f"{keyword['keyword']}: {keyword['context']}"
            tasks.append(self._get_embedding(text))

        embeddings_results = await asyncio.gather(*tasks, return_exceptions=True)

        keywords_with_embeddings = []
        for i, result in enumerate(embeddings_results):
            keyword = keywords[i]
            if isinstance(result, Exception):
                logger.error(f"Error generating embedding for keyword '{keyword.get('keyword')}': {str(result)}")
                # Skip this keyword or handle as needed
            else:
                keyword_with_embedding = keyword.copy()
                keyword_with_embedding["embedding"] = result
                keywords_with_embeddings.append(keyword_with_embedding)
        
        return keywords_with_embeddings
    
    def deduplicate_keywords(self, keywords_with_embeddings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate keywords using embedding similarity.
        
        Args:
            keywords_with_embeddings: Keywords with embeddings
            
        Returns:
            list: Deduplicated keywords
        """
        # Skip if too few keywords
        if len(keywords_with_embeddings) <= 1:
            return keywords_with_embeddings
            
        # Group similar keywords
        # Track which keywords have been processed
        processed_indices = set()
        grouped_keywords = []
        
        # Process each keyword
        for i, kw1 in enumerate(keywords_with_embeddings):
            if i in processed_indices:
                continue
                
            # Find similar keywords
            similar_group = [kw1]
            processed_indices.add(i)
            
            for j, kw2 in enumerate(keywords_with_embeddings):
                if j in processed_indices or i == j:
                    continue
                    
                # Calculate cosine similarity between embeddings
                similarity = self._cosine_similarity(kw1["embedding"], kw2["embedding"])
                
                # If very similar (high threshold to be conservative)
                if similarity > 0.92:  # High threshold to avoid false matches
                    similar_group.append(kw2)
                    processed_indices.add(j)
            
            # Group the similar keywords
            if len(similar_group) > 1:
                # Sort by relevance score
                similar_group.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
                
                # Take the highest relevance keyword as primary
                primary = similar_group[0]
                
                # Create list of synonyms
                synonyms = [{"keyword": kw["keyword"], "context": kw["context"]} 
                           for kw in similar_group[1:]]
                
                # Add synonyms to the primary keyword
                primary_with_synonyms = primary.copy()
                primary_with_synonyms["synonyms"] = synonyms
                
                grouped_keywords.append(primary_with_synonyms)
            else:
                # No duplicates found, add the single keyword
                kw1_copy = kw1.copy()
                kw1_copy["synonyms"] = []
                grouped_keywords.append(kw1_copy)
        
        # Add any remaining unprocessed keywords
        for i, kw in enumerate(keywords_with_embeddings):
            if i not in processed_indices:
                kw_copy = kw.copy()
                kw_copy["synonyms"] = []
                grouped_keywords.append(kw_copy)
        
        return grouped_keywords
    
    def extract_bullet_points(self, resume_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract bullet points from resume JSON.
        
        Args:
            resume_data: Parsed resume JSON
            
        Returns:
            list: Extracted bullet points with metadata
        """
        bullet_points = []
        
        # Extract from Experience section
        for experience_idx, experience in enumerate(resume_data.get("Experience", [])):
            company = experience.get("company", "")
            position = experience.get("title", "")
            
            for bullet_idx, bullet in enumerate(experience.get("responsibilities/achievements", [])):
                bullet_points.append({
                    "bullet_text": bullet,
                    "company": company,
                    "position": position,
                    "section": "Experience",
                    "experience_idx": experience_idx,
                    "bullet_idx": bullet_idx
                })
        
        # Could also extract from other sections like Projects if needed
        logger.debug(f"Extracted {len(bullet_points)} bullet points from resume.")
        return bullet_points
    
    async def generate_bullet_embeddings(self, bullet_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for bullet points.
        
        Args:
            bullet_points: List of bullet points with metadata
            
        Returns:
            list: Bullet points with embeddings added
        """
        tasks = []
        for bullet in bullet_points:
            tasks.append(self._get_embedding(bullet["bullet_text"]))

        embeddings_results = await asyncio.gather(*tasks, return_exceptions=True)

        bullets_with_embeddings = []
        for i, result in enumerate(embeddings_results):
            bullet = bullet_points[i]
            if isinstance(result, Exception):
                logger.error(f"Error generating embedding for bullet '{bullet['bullet_text'][:30]}...': {str(result)}")
                # Skip this bullet or handle as needed
            else:
                bullet_with_embedding = bullet.copy()
                bullet_with_embedding["embedding"] = result
                bullets_with_embeddings.append(bullet_with_embedding)
        
        logger.debug(f"Generated embeddings for {len(bullets_with_embeddings)} bullet points.")
        return bullets_with_embeddings
    
    def calculate_similarity(self, 
                            keywords: List[Dict[str, Any]], 
                            bullets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculate cosine similarity between keywords and bullets.
        
        Args:
            keywords: Keywords with embeddings
            bullets: Bullets with embeddings
            
        Returns:
            list: Similarity results
        """
        similarity_results = []
        
        for keyword in keywords:
            keyword_embedding = keyword["embedding"]
            
            for bullet in bullets:
                bullet_embedding = bullet["embedding"]
                
                # Calculate cosine similarity
                similarity = self._cosine_similarity(keyword_embedding, bullet_embedding)
                
                # Only keep matches above threshold
                if similarity >= self.similarity_threshold:
                    # Create result without embeddings
                    result = {
                        "keyword": keyword["keyword"],
                        "keyword_context": keyword["context"],
                        "relevance_score": keyword["relevance_score"],
                        "skill_type": keyword["skill_type"],
                        "bullet_text": bullet["bullet_text"],
                        "company": bullet["company"],
                        "position": bullet["position"],
                        "section": bullet["section"],
                        "experience_idx": bullet["experience_idx"],
                        "bullet_idx": bullet["bullet_idx"],
                        "similarity_score": similarity,
                        "has_synonyms": len(keyword.get("synonyms", [])) > 0,
                        "synonyms": keyword.get("synonyms", [])
                    }
                    
                    similarity_results.append(result)
        
        # Sort by similarity score (descending)
        similarity_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        logger.debug(f"Calculated {len(similarity_results)} similarity scores above threshold {self.similarity_threshold}.")
        return similarity_results
    
    def group_matches_by_bullet(self, similarity_results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group matches by bullet point for enhancement.
        
        Args:
            similarity_results: Similarity results
            
        Returns:
            dict: Matches grouped by bullet text
        """
        matches_by_bullet = {}
        
        for result in similarity_results:
            bullet_text = result["bullet_text"]
            
            # Check if keyword already in the bullet text
            keyword = result["keyword"]
            if keyword.lower() in bullet_text.lower():
                continue  # Skip if keyword already present
                
            # Initialize if first match for this bullet
            if bullet_text not in matches_by_bullet:
                matches_by_bullet[bullet_text] = []
                
            # Add match to the bullet's list
            matches_by_bullet[bullet_text].append({
                "keyword": result["keyword"],
                "context": result["keyword_context"],
                "relevance_score": result["relevance_score"],
                "skill_type": result["skill_type"],
                "similarity_score": result["similarity_score"],
                "synonyms": result["synonyms"]
            })
        
        # Sort matches for each bullet by relevance score then similarity
        for bullet, matches in matches_by_bullet.items():
            matches.sort(key=lambda x: (x["relevance_score"], x["similarity_score"]), reverse=True)
            
            # Keep top matches per bullet based on our criteria (2 hard + 1 soft)
            hard_skills = [m for m in matches if m["skill_type"] == "hard skill"][:2]
            soft_skills = [m for m in matches if m["skill_type"] == "soft skill"][:1]
            
            # Combine and maintain sort order
            combined = hard_skills + soft_skills
            combined.sort(key=lambda x: (x["relevance_score"], x["similarity_score"]), reverse=True)
            
            # Limit to total of 3 keywords per bullet
            matches_by_bullet[bullet] = combined[:3]  # Maximum 3 keywords total
        
        logger.debug(f"Grouped matches for {len(matches_by_bullet)} bullets.")
        return matches_by_bullet
    
    def filter_keyword_usage(self, 
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
        # Track keyword usage count
        keyword_usage = {}
        
        # Track which bullets have been processed
        processed_bullets = set()
        
        # Result dictionary
        filtered_matches = {}
        
        # Process bullets in order of match quality (best matches first)
        bullet_quality = []
        for bullet, matches in matches_by_bullet.items():
            # Score based on average relevance and similarity
            if matches:
                avg_relevance = sum(m["relevance_score"] for m in matches) / len(matches)
                avg_similarity = sum(m["similarity_score"] for m in matches) / len(matches)
                quality_score = avg_relevance * 0.7 + avg_similarity * 0.3
            else:
                quality_score = 0
                
            bullet_quality.append((bullet, quality_score))
        
        # Sort bullets by quality score
        bullet_quality.sort(key=lambda x: x[1], reverse=True)
        
        # Process bullets in order
        for bullet, _ in bullet_quality:
            if bullet in processed_bullets:
                continue
                
            matches = matches_by_bullet[bullet]
            filtered_matches[bullet] = []
            
            for match in matches:
                keyword = match["keyword"].lower()
                
                # Check if keyword usage limit reached
                if keyword_usage.get(keyword, 0) >= max_keyword_usage:
                    continue
                    
                # Add to filtered matches
                filtered_matches[bullet].append(match)
                
                # Update usage count
                keyword_usage[keyword] = keyword_usage.get(keyword, 0) + 1
                
            processed_bullets.add(bullet)
        
        logger.debug(f"Filtered keyword usage, resulting in matches for {len(filtered_matches)} bullets.")
        return filtered_matches
    
    async def extract_resume_technical_skills(self, resume_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Extracts technical skills from the resume, preserving categories if they exist.
        Generates embeddings for each skill asynchronously.

        Args:
            resume_data: Parsed resume JSON.

        Returns:
            Dict[str, Dict[str, Any]]: 
                { 
                    "CategoryName": {
                        "skills": [{"skill": "SkillName", "embedding": [...]}, ...],
                        "is_original": True 
                    }, ...
                }
                If skills are not categorized, uses a default category like "_DEFAULT_TECHNICAL_SKILLS_".
        """
        logger.debug("Extracting technical skills from resume_data.")
        skills_section = resume_data.get("Skills", {})
        if not isinstance(skills_section, dict):
            logger.warning(f"Resume 'Skills' section is not a dictionary as expected, but type {type(skills_section)}. Treating as empty.")
            skills_section = {}

        technical_skills_data = skills_section.get("Technical Skills", [])
        structured_skills = {}
        
        # Prepare a list of all skill names and their category/original status
        all_skills_to_embed_info = [] # Stores tuples of (skill_name, category_name_or_default, is_flat_list_skill)

        if isinstance(technical_skills_data, dict): # Skills are already categorized
            logger.debug("Resume technical skills appear to be categorized.")
            for category, skills_in_category in technical_skills_data.items():
                if isinstance(skills_in_category, list):
                    for skill_name in skills_in_category:
                        if isinstance(skill_name, str) and skill_name.strip():
                            all_skills_to_embed_info.append((skill_name.strip(), category, False))
                        else:
                            logger.warning(f"Invalid skill item '{skill_name}' in category '{category}', skipping.")
                else:
                    logger.warning(f"Category '{category}' in Technical Skills does not contain a list of skills, skipping.")
        
        elif isinstance(technical_skills_data, list): # Skills are a flat list
            logger.debug("Resume technical skills appear to be a flat list. Using default category.")
            default_category_name = "_DEFAULT_TECHNICAL_SKILLS_"
            for skill_name in technical_skills_data:
                if isinstance(skill_name, str) and skill_name.strip():
                    all_skills_to_embed_info.append((skill_name.strip(), default_category_name, True))
                else:
                    logger.warning(f"Invalid skill item '{skill_name}' in flat list of technical skills, skipping.")
        else:
            logger.warning(f"'Technical Skills' data is not a recognized dict or list: {type(technical_skills_data)}. No skills extracted.")
            return {}

        if not all_skills_to_embed_info:
            logger.info("No valid technical skills found to extract and embed.")
            return {}

        # Create embedding tasks
        embedding_tasks = [self._get_embedding(skill_info[0]) for skill_info in all_skills_to_embed_info]
        embedding_results = await asyncio.gather(*embedding_tasks, return_exceptions=True)

        # Process results and structure them
        for i, embedding_or_exc in enumerate(embedding_results):
            skill_name, category_name, _ = all_skills_to_embed_info[i]

            if isinstance(embedding_or_exc, Exception):
                logger.error(f"Failed to generate embedding for resume skill '{skill_name}' in category '{category_name}': {embedding_or_exc}")
                continue

            if category_name not in structured_skills:
                structured_skills[category_name] = {"skills": [], "is_original": True}
            
            structured_skills[category_name]["skills"].append({
                "skill": skill_name,
                "embedding": embedding_or_exc
            })

        total_extracted = sum(len(cat_data['skills']) for cat_data in structured_skills.values())
        logger.info(f"Extracted and embedded {total_extracted} technical skills from {len(structured_skills)} resume categories.")
        return structured_skills

    async def _categorize_jd_skills_with_openai(self, jd_hard_skills: List[Dict[str, Any]], resume_categories: List[str]) -> List[Dict[str, Any]]:
        """
        Categorizes JD hard skills using OpenAI based on existing resume skill categories.
        OpenAI calls are made directly and concurrently.
        """
        logger.debug(f"Categorizing {len(jd_hard_skills)} JD hard skills using OpenAI. Resume categories: {resume_categories}")
        
        if not jd_hard_skills:
            return []

        if not resume_categories: # No categories to map to, assign a default new category
            logger.warning("No existing resume skill categories provided for mapping JD skills. Assigning all to a default new category.")
            categorized_skills_results = []
            for skill_data in jd_hard_skills:
                skill_data_copy = skill_data.copy()
                skill_data_copy["assigned_category"] = "New Skills" # Default new category
                categorized_skills_results.append(skill_data_copy)
            return categorized_skills_results

        tasks = []
        for skill_data in jd_hard_skills:
            skill_name = skill_data["keyword"]
            skill_context = skill_data.get("context", "N/A")
            
            prompt = (
                f"Given the skill '{skill_name}' (context from job description: '{skill_context}') "
                f"and the existing resume skill categories: {json.dumps(resume_categories)}.\n"
                f"Which of these categories does the skill best fit into? "
                f"If it doesn't fit well into any existing category, suggest 'New Category: [Appropriate New Category Name]' (e.g., 'New Category: Cloud Technologies'). "
                f"If it fits an existing category, just return that category name. "
                f"Be concise. Only return the category name or 'New Category: ...'."
            )
            
            # Create a task for each OpenAI call
            tasks.append(self.client.chat.completions.create(
                model=self.generation_model, # Using updated gpt-4.1-turbo
                messages=[
                    {"role": "system", "content": "You are an expert in categorizing technical skills."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=50
            ))

        openai_responses = await asyncio.gather(*tasks, return_exceptions=True)

        categorized_skills = []
        for i, response_or_exc in enumerate(openai_responses):
            skill_data = jd_hard_skills[i]
            skill_name = skill_data["keyword"]
            skill_data_copy = skill_data.copy()

            if isinstance(response_or_exc, Exception):
                logger.error(f"Error categorizing skill '{skill_name}' with OpenAI: {response_or_exc}. Assigning to default 'Uncategorized'.")
                skill_data_copy["assigned_category"] = "Uncategorized JD Skills"
            else:
                # response_or_exc is the successful OpenAI response object
                category_response = response_or_exc.choices[0].message.content.strip()
                logger.debug(f"OpenAI category response for '{skill_name}': '{category_response}'")
                
                assigned_category = category_response
                if category_response.startswith("New Category:"):
                    assigned_category = category_response.replace("New Category:", "").strip()
                    if not assigned_category: # Handle empty new category name
                        assigned_category = f"New - {skill_name}" # Default if AI gives empty new cat name
                elif category_response not in resume_categories: 
                    logger.warning(f"OpenAI suggested category '{category_response}' for skill '{skill_name}' which is not in existing resume categories {resume_categories} or a 'New Category' format. Treating as a new category: '{category_response}'.")
                
                skill_data_copy["assigned_category"] = assigned_category
            
            categorized_skills.append(skill_data_copy)
        
        logger.info(f"Categorized {len(categorized_skills)} JD hard skills using OpenAI with model {self.generation_model}.")
        return categorized_skills

    def select_final_technical_skills(self,
                                     resume_skills_structured: Dict[str, Dict[str, Any]],
                                     categorized_jd_hard_skills: List[Dict[str, Any]],
                                     overall_skill_limit: int = 15) -> Tuple[Dict[str, List[str]], Dict[str, Any]]:
        """
        Selects the final list of technical skills, combining resume and JD skills,
        respecting categories, deduplicating, and applying an overall limit.
        Uses a round-robin approach to fill categories.
        Outputs a dictionary of category names to lists of skill strings.
        """
        log_details = {
            "input_resume_categories": list(resume_skills_structured.keys()),
            "input_resume_skill_counts": {cat: len(data['skills']) for cat, data in resume_skills_structured.items()},
            "input_jd_skill_count": len(categorized_jd_hard_skills),
            "overall_skill_limit": overall_skill_limit,
            "deduplication_info": [],
            "category_skill_counts_before_limit": {},
            "final_skill_counts_by_category": {},
            "category_processing_order": []
        }
        
        # 1. Consolidate skills by category
        consolidated_skills = {} # category_name -> list of skill_dicts {'skill': str, 'embedding': [], 'relevance': float, 'is_original': bool, 'jd_context': str/None}
        
        # Add resume skills
        for category, data in resume_skills_structured.items():
            if category not in consolidated_skills:
                consolidated_skills[category] = []
            for skill_info in data.get('skills', []):
                consolidated_skills[category].append({
                    "skill": skill_info["skill"],
                    "embedding": skill_info["embedding"],
                    "relevance": 1.0, # Original skills get high relevance
                    "is_original": True,
                    "jd_context": None
                })

        # Add categorized JD skills
        for jd_skill_info in categorized_jd_hard_skills:
            category = jd_skill_info.get("assigned_category", "Uncategorized JD Skills")
            if category not in consolidated_skills:
                consolidated_skills[category] = []
            consolidated_skills[category].append({
                "skill": jd_skill_info["keyword"],
                "embedding": jd_skill_info["embedding"],
                "relevance": jd_skill_info.get("relevance_score", 0.5),
                "is_original": False,
                "jd_context": jd_skill_info.get("context")
            })
        
        logger.debug(f"Consolidated skills by category: { {cat: len(sks) for cat, sks in consolidated_skills.items()} }")

        # 2. Deduplicate within each category
        for category, skills_list in consolidated_skills.items():
            deduplicated_for_category = []
            processed_indices = set()
            for i, s1 in enumerate(skills_list):
                if i in processed_indices:
                    continue
                current_best_skill = s1
                duplicates_found = []
                for j in range(i + 1, len(skills_list)):
                    if j in processed_indices:
                        continue
                    s2 = skills_list[j]
                    # Check text similarity (case-insensitive, strip spaces)
                    s1_norm = s1["skill"].strip().lower()
                    s2_norm = s2["skill"].strip().lower()
                    if s1_norm == s2_norm or self._cosine_similarity(s1["embedding"], s2["embedding"]) > self.skill_similarity_threshold :
                        duplicates_found.append(s2)
                        processed_indices.add(j)
                        # Prefer original, then higher relevance for duplicates
                        if s2["is_original"] and not current_best_skill["is_original"]:
                            current_best_skill = s2
                        elif s2["relevance"] > current_best_skill["relevance"] and not current_best_skill["is_original"]:
                             current_best_skill = s2
                        # if both original, or both not, keep the one with higher relevance
                        elif s2["is_original"] == current_best_skill["is_original"] and s2["relevance"] > current_best_skill["relevance"]:
                            current_best_skill = s2


                deduplicated_for_category.append(current_best_skill)
                if duplicates_found:
                    log_details["deduplication_info"].append({
                        "category": category,
                        "kept": current_best_skill["skill"],
                        "discarded_duplicates": [d["skill"] for d in duplicates_found]
                    })
            consolidated_skills[category] = deduplicated_for_category
        
        logger.debug(f"Skills after deduplication: { {cat: len(sks) for cat, sks in consolidated_skills.items()} }")
        # Storing the objects post-deduplication for logging if needed, but log_details["deduplication_info"] captures changes.
        # log_details["deduplication_log"] = copy.deepcopy(consolidated_skills) # Be careful with deepcopy if embeddings are large

        log_details["category_skill_counts_before_limit"] = {cat: len(sks) for cat, sks in consolidated_skills.items()}

        # 2. Sort skills within each category (prioritize original, then relevance)
        for category in consolidated_skills:
            consolidated_skills[category].sort(key=lambda x: (x['is_original'], x['relevance']), reverse=True)

        # 3. Round-robin selection to fill final skills
        final_skills_by_category_dict = {} # Dict[str, List[str]]
        selected_skill_names_globally = set()
        current_total_skills = 0
        
        # Pointers for iterating through each category's sorted skill list
        skill_pointers = {category: 0 for category in consolidated_skills}
        
        # Determine category processing order (original categories first, then new ones alphabetically)
        original_category_keys = set(resume_skills_structured.keys()) # Use set for faster lookups
        
        # Sort all category keys: original ones first (sorted alphabetically among themselves), 
        # then new ones (also sorted alphabetically among themselves)
        all_category_keys_ordered = sorted(
            consolidated_skills.keys(),
            key=lambda c: (c not in original_category_keys, c) # False (original) comes before True (new), then alphabetically by c
        )
        log_details["category_processing_order"] = all_category_keys_ordered
        
        # Round-robin selection loop
        while current_total_skills < overall_skill_limit:
            skill_added_this_round = False
            for category_name in all_category_keys_ordered:
                if category_name not in consolidated_skills: # Should not happen if all_category_keys_ordered from consolidated_skills
                    continue

                skills_in_this_category = consolidated_skills[category_name]
                current_pointer = skill_pointers.get(category_name, 0)

                if current_pointer < len(skills_in_this_category):
                    skill_to_add = skills_in_this_category[current_pointer]
                    skill_name = skill_to_add["skill"]

                    if skill_name.lower() not in selected_skill_names_globally:
                        if category_name not in final_skills_by_category_dict:
                            final_skills_by_category_dict[category_name] = []
                        
                        final_skills_by_category_dict[category_name].append(skill_name)
                        selected_skill_names_globally.add(skill_name.lower())
                        current_total_skills += 1
                        skill_added_this_round = True
                    
                    skill_pointers[category_name] = current_pointer + 1 # Advance pointer regardless of global duplicate
                    
                    if current_total_skills >= overall_skill_limit:
                        break # Break from inner category loop (finished filling overall limit)
            
            if not skill_added_this_round or current_total_skills >= overall_skill_limit:
                # Break from outer while loop if no skills were added in a full round, or if limit is met
                break
        
        log_details["final_skill_counts_by_category"] = {cat: len(sks) for cat, sks in final_skills_by_category_dict.items()}
        
        # Clean up empty categories that might have resulted
        final_skills_by_category_dict = {k: v for k, v in final_skills_by_category_dict.items() if v}

        logger.info(f"Selected final {current_total_skills} technical skills across {len(final_skills_by_category_dict)} categories.")
        logger.debug(f"Final skills structure: {final_skills_by_category_dict}")
        
        return final_skills_by_category_dict, log_details

    async def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text using OpenAI API.
        
        Args:
            text: Text to get embedding for
            
        Returns:
            list: Embedding vector
        """
        # Removed cache miss logging
        response = await self.client.embeddings.create(
            input=text,
            model=self.model
        )
        return response.data[0].embedding
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            float: Cosine similarity (0-1)
        """
        # Convert to numpy arrays
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        # Calculate dot product
        dot_product = np.dot(v1, v2)
        
        # Calculate magnitudes
        mag1 = np.linalg.norm(v1)
        mag2 = np.linalg.norm(v2)
        
        # Avoid division by zero
        if mag1 == 0 or mag2 == 0:
            return 0
            
        # Calculate cosine similarity
        return dot_product / (mag1 * mag2)
    
    def save_results_to_file(self, results: Dict[str, Any], output_path: str) -> None:
        """
        Save results to a JSON file.
        
        Args:
            results: Results dictionary
            output_path: Path to save results to
        """
        # Create a clean version without large embeddings for some parts
        clean_results = {
            "deduplicated_keywords_for_bullets": results.get("deduplicated_keywords_for_bullets"),
            "similarity_results": results.get("similarity_results"), # These don't have embeddings
            "matches_by_bullet": results.get("matches_by_bullet"), # These don't have embeddings
            "final_technical_skills": results.get("final_technical_skills"), # This is just [str]
            "statistics": results.get("statistics"),
            "skill_selection_process_log": results.get("skill_selection_process_log")
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(clean_results, f, indent=2)
            
        logger.info(f"Results saved to {output_path}")
    
    def export_similarity_to_csv(self, similarity_results: List[Dict[str, Any]], output_path: str) -> None:
        """
        Export similarity results to CSV for analysis.
        
        Args:
            similarity_results: Similarity results
            output_path: Path to save CSV to
        """
        df = pd.DataFrame(similarity_results)
        df.to_csv(output_path, index=False)
        logger.info(f"Similarity results exported to {output_path}")


# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Semantic matching and keyword deduplication")
    parser.add_argument("--keywords", type=str, required=True, help="Path to keywords JSON file")
    parser.add_argument("--resume", type=str, required=True, help="Path to resume JSON file")
    parser.add_argument("--threshold", type=float, default=0.75, help="Similarity threshold (0-1)")
    parser.add_argument("--output", type=str, default="semantic_matches.json", help="Output file path")
    
    args = parser.parse_args()
    
    # Load input files
    with open(args.keywords, 'r', encoding='utf-8') as f:
        keywords_data = json.load(f)
        
    with open(args.resume, 'r', encoding='utf-8') as f:
        resume_data = json.load(f)
    
    # Initialize semantic matcher
    matcher = SemanticMatcher()
    
    # Process keywords and resume using asyncio.run
    async def main():
        results = await matcher.process_keywords_and_resume(
            keywords_data, 
            resume_data,
            similarity_threshold=args.threshold
        )
        
        # Save results
        matcher.save_results_to_file(results, args.output)
        
        # Export similarity results to CSV for analysis
        matcher.export_similarity_to_csv(results["similarity_results"], "similarity_results.csv")
        
        # Print summary
        print(f"Semantic processing complete.")
        print(f"Original keywords: {results['statistics']['original_keywords']}")
        print(f"Deduplicated keywords for bullets: {results['statistics']['deduplicated_keywords_for_bullets']}")
        print(f"Bullets processed: {results['statistics']['bullets_processed']}")
        print(f"Bullets with matches: {results['statistics']['bullets_with_matches']}")
        print(f"Total bullet matches: {results['statistics']['total_bullet_matches']}")
        print(f"Final total technical skills: {results['statistics']['final_total_technical_skills']}")
        print(f"Results saved to {args.output}")

    asyncio.run(main())