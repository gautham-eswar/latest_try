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
            httpx_client = httpx.Client(trust_env=False)
            self.client = OpenAI(api_key=self.api_key, http_client=httpx_client)
            logger.info("SemanticMatcher: OpenAI client initialized successfully with custom httpx client.")
        except Exception as e:
            logger.error(f"SemanticMatcher: Failed to initialize OpenAI client: {e}", exc_info=True)
            # Depending on desired behavior, either raise the error or handle it
            # For now, let's raise it to make the failure clear
            raise RuntimeError(f"SemanticMatcher: Could not initialize OpenAI client - {e}") from e
            # self.client = None # Or set client to None if you want to handle errors downstream
        
        self.model = model
        self.generation_model = "gpt-3.5-turbo" # For categorization tasks
        
        # Default similarity threshold
        self.similarity_threshold = 0.75
        self.skill_similarity_threshold = 0.90 # For deduplicating skills
        
    def process_keywords_and_resume(self, 
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
        
        # --- Bullet Point Processing ---
        logger.info("Step 1: Generating embeddings for JD keywords (for bullets)")
        keywords_with_embeddings = self.generate_keyword_embeddings(keywords_data["keywords"])
        
        logger.info("Step 2: Deduplicating JD keywords (for bullets)")
        deduplicated_keywords_for_bullets = self.deduplicate_keywords(keywords_with_embeddings)
        
        logger.info("Step 3: Extracting bullet points from resume")
        bullet_points = self.extract_bullet_points(resume_data)
        
        logger.info(f"Step 4: Generating embeddings for {len(bullet_points)} bullet points")
        bullets_with_embeddings = self.generate_bullet_embeddings(bullet_points)
        
        logger.info("Step 5: Calculating similarity between JD keywords and resume bullets")
        similarity_results = self.calculate_similarity(deduplicated_keywords_for_bullets, bullets_with_embeddings)
        
        logger.info("Step 6: Grouping matches by bullet point")
        matches_by_bullet = self.group_matches_by_bullet(similarity_results)

        # --- Technical Skills Section Processing ---
        logger.info("Step 7: Extracting and embedding resume technical skills")
        resume_skills_structured = self.extract_resume_technical_skills(resume_data)
        
        logger.info("Step 8: Filtering JD keywords for hard skills relevant to skills section")
        jd_hard_skills_for_section = [
            kw for kw in keywords_with_embeddings # Use keywords_with_embeddings to have their embeddings ready
            if kw.get("skill_type") == "hard skill" and kw.get("relevance_score", 0) >= relevance_threshold
        ]
        logger.debug(f"Found {len(jd_hard_skills_for_section)} JD hard skills meeting relevance threshold {relevance_threshold}")

        resume_skill_categories = list(resume_skills_structured.keys())
        logger.info(f"Step 9: Categorizing {len(jd_hard_skills_for_section)} JD hard skills against resume categories: {resume_skill_categories}")
        categorized_jd_hard_skills = self._categorize_jd_skills_with_openai(jd_hard_skills_for_section, resume_skill_categories)

        logger.info("Step 10: Selecting final technical skills for resume section")
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
    
    def generate_keyword_embeddings(self, keywords: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for keywords with context.
        
        Args:
            keywords: List of keywords with metadata
            
        Returns:
            list: Keywords with embeddings added
        """
        keywords_with_embeddings = []
        
        for keyword in keywords:
            try:
                # Combine keyword and context for richer embedding
                text = f"{keyword['keyword']}: {keyword['context']}"
                
                # Generate embedding
                embedding = self.get_embedding(text)
                
                # Add embedding to keyword data
                keyword_with_embedding = keyword.copy()
                keyword_with_embedding["embedding"] = embedding
                keywords_with_embeddings.append(keyword_with_embedding)
                
            except Exception as e:
                logger.error(f"Error generating embedding for keyword '{keyword.get('keyword')}': {str(e)}")
                # Skip this keyword if embedding generation fails
        
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
                similarity = self.cosine_similarity(kw1["embedding"], kw2["embedding"])
                
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
    
    def generate_bullet_embeddings(self, bullet_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for bullet points.
        
        Args:
            bullet_points: List of bullet points with metadata
            
        Returns:
            list: Bullet points with embeddings added
        """
        bullets_with_embeddings = []
        
        for bullet in bullet_points:
            try:
                # Generate embedding for the bullet text
                embedding = self.get_embedding(bullet["bullet_text"])
                
                # Add embedding to bullet data
                bullet_with_embedding = bullet.copy()
                bullet_with_embedding["embedding"] = embedding
                bullets_with_embeddings.append(bullet_with_embedding)
                
            except Exception as e:
                logger.error(f"Error generating embedding for bullet '{bullet['bullet_text'][:30]}...': {str(e)}")
                # Skip this bullet if embedding generation fails
        
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
                similarity = self.cosine_similarity(keyword_embedding, bullet_embedding)
                
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
    
    def extract_resume_technical_skills(self, resume_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Extracts technical skills from the resume, preserving categories and structure.
        This version correctly navigates nested skill structures and is robust to null values.
        """
        logger.debug("Extracting technical skills from resume_data with robust parser.")
        structured_skills = {}
        
        skills_section = resume_data.get("Skills", {})
        if not isinstance(skills_section, dict):
            logger.warning(f"Resume 'Skills' section is not a dictionary. Type: {type(skills_section)}. Treating as empty.")
            return {}

        # The actual skills might be nested one level down under "Technical Skills"
        technical_skills_data = skills_section.get("Technical Skills", skills_section)
        if not isinstance(technical_skills_data, dict):
            logger.warning(f"Could not find a dictionary of skill categories. Data: {technical_skills_data}")
            return {}

        for category, skills_in_category in technical_skills_data.items():
            # Skip metadata fields like '_had_subcategories'
            if category.startswith('_'):
                continue

            if isinstance(skills_in_category, list):
                embedded_skills = []
                for skill_item in skills_in_category:
                    # Handle both simple strings and null/None values gracefully
                    if isinstance(skill_item, str) and skill_item.strip():
                        skill_name = skill_item.strip()
                        try:
                            embedding = self.get_embedding(skill_name)
                            embedded_skills.append({"skill": skill_name, "embedding": embedding})
                        except Exception as e:
                            logger.error(f"Failed to generate embedding for skill '{skill_name}' in category '{category}': {e}")
                
                if embedded_skills:
                    structured_skills[category] = {"skills": embedded_skills, "is_original": True}

        total_extracted = sum(len(cat_data.get('skills', [])) for cat_data in structured_skills.values())
        logger.info(f"Extracted and embedded {total_extracted} technical skills from {len(structured_skills)} resume categories.")
        return structured_skills

    def _categorize_jd_skills_with_openai(self, jd_hard_skills: List[Dict[str, Any]], resume_categories: List[str]) -> List[Dict[str, Any]]:
        """
        Categorizes JD hard skills using OpenAI based on existing resume skill categories.
        """
        logger.debug(f"Categorizing {len(jd_hard_skills)} JD hard skills using OpenAI. Resume categories: {resume_categories}")
        categorized_skills = []

        if not resume_categories: # No categories to map to, assign a default new category
            logger.warning("No existing resume skill categories provided for mapping JD skills. Assigning all to a default new category.")
            for skill_data in jd_hard_skills:
                skill_data_copy = skill_data.copy()
                skill_data_copy["assigned_category"] = "New Skills" # Default new category
                categorized_skills.append(skill_data_copy)
            return categorized_skills

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
            
            try:
                response = self.client.chat.completions.create(
                    model=self.generation_model,
                    messages=[
                        {"role": "system", "content": "You are an expert in categorizing technical skills."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=50
                )
                category_response = response.choices[0].message.content.strip()
                logger.debug(f"OpenAI category response for '{skill_name}': '{category_response}'")

                # Normalize noisy prefixes from model outputs
                normalized = category_response
                for prefix in ("Existing Category:", "Category:"):
                    if normalized.startswith(prefix):
                        normalized = normalized.replace(prefix, "", 1).strip()

                assigned_category = normalized
                if category_response.startswith("New Category:"):
                    assigned_category = category_response.replace("New Category:", "").strip()
                    if not assigned_category: # Handle empty new category name
                        assigned_category = f"New - {skill_name}" # Default if AI gives empty new cat name
                elif assigned_category not in resume_categories: # If AI hallucinates a category not in the list and not 'New Category:'
                    logger.warning(f"OpenAI suggested category '{category_response}' for skill '{skill_name}' which is not in existing resume categories or a 'New Category' format. Treating as a new category: '{category_response}'.")
                    # Decide if we want to force it into an existing one, or accept it as new. For now, accept.
                    # To be stricter, we might map it to the most similar existing one or a generic "Other New Skills"

                skill_data_copy = skill_data.copy()
                skill_data_copy["assigned_category"] = assigned_category
                categorized_skills.append(skill_data_copy)

            except Exception as e:
                logger.error(f"Error categorizing skill '{skill_name}' with OpenAI: {e}. Assigning to default 'Uncategorized'.")
                skill_data_copy = skill_data.copy()
                skill_data_copy["assigned_category"] = "Uncategorized JD Skills"
                categorized_skills.append(skill_data_copy)
        
        logger.info(f"Categorized {len(categorized_skills)} JD hard skills using OpenAI.")
        return categorized_skills

    def select_final_technical_skills(self,
                                     resume_skills_structured: Dict[str, Dict[str, Any]],
                                     categorized_jd_hard_skills: List[Dict[str, Any]],
                                     overall_skill_limit: int = 35) -> Tuple[Dict[str, List[str]], Dict[str, Any]]:
        """
        Selects the final list of technical skills by preserving the original resume's skills
        and appending new, non-duplicate skills from the job description.
        """
        log_details = {
            "message": "Using additive skill merge strategy: Preserve original skills and append new.",
            "input_resume_categories": list(resume_skills_structured.keys()),
            "input_resume_skill_counts": {cat: len(data['skills']) for cat, data in resume_skills_structured.items()},
            "input_jd_skill_count": len(categorized_jd_hard_skills),
            "overall_skill_limit": overall_skill_limit,
            "skill_decisions": [],
        }

        # 1. Start with a deep copy of the original skills, keeping only the skill names.
        final_skills_by_category = {}
        original_skill_names_lower = set()

        for category, data in resume_skills_structured.items():
            if category not in final_skills_by_category:
                final_skills_by_category[category] = []
            for skill_info in data.get('skills', []):
                skill_name = skill_info["skill"]
                final_skills_by_category[category].append(skill_name)
                original_skill_names_lower.add(skill_name.strip().lower())

        # 2. Identify new skills from the JD that are not already in the resume.
        new_skills_to_add = []
        for jd_skill in categorized_jd_hard_skills:
            jd_skill_name = jd_skill["keyword"]
            if jd_skill_name.strip().lower() not in original_skill_names_lower:
                new_skills_to_add.append(jd_skill)
                log_details["skill_decisions"].append({
                    "skill": jd_skill_name,
                    "decision": "Identified as new skill to be added.",
                    "category_suggestion": jd_skill.get("assigned_category")
                })

        # 3. Append the new skills to their assigned categories.
        for new_skill in new_skills_to_add:
            skill_name = new_skill["keyword"]
            category = new_skill.get("assigned_category", "New Skills")
            
            if category not in final_skills_by_category:
                final_skills_by_category[category] = []
            
            final_skills_by_category[category].append(skill_name)
            log_details["skill_decisions"].append({
                "skill": skill_name,
                "decision": f"Appended to category '{category}'.",
            })

        # (Optional) Apply a simple cap to prevent excessive skill additions
        total_skills = sum(len(skills) for skills in final_skills_by_category.values())
        if total_skills > overall_skill_limit:
            # This part could be enhanced with a more sophisticated trimming logic if needed,
            # but for now, we'll just log it. A simple implementation could trim from the largest categories.
            log_details["warning"] = f"Total skills ({total_skills}) exceeds limit ({overall_skill_limit}). Consider implementing trimming logic."


        # Final logging
        log_details["final_skill_counts_by_category"] = {cat: len(sks) for cat, sks in final_skills_by_category.items()}

        # --- Minimal post-processing: enforce category count and minimum size ---
        consolidated, consolidation_log = self._consolidate_skill_categories(
            final_skills_by_category, max_categories=7, min_per_category=3
        )
        log_details["consolidation"] = consolidation_log
        log_details["final_skill_counts_by_category"] = {cat: len(sks) for cat, sks in consolidated.items()}

        return consolidated, log_details

    def _consolidate_skill_categories(
        self,
        skills_by_category: Dict[str, List[str]],
        max_categories: int = 7,
        min_per_category: int = 3,
    ) -> Tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
        """
        Ensure each category has at least `min_per_category` skills and the total number of
        categories does not exceed `max_categories`. Small categories are merged into the
        most similar existing category by name token overlap; if no reasonable similarity
        is found, merge into the largest category.

        Returns the consolidated dict and a log of consolidation operations.
        """
        # Defensive copy and deduplicate entries while preserving order per category
        consolidated: Dict[str, List[str]] = {}
        for cat, items in (skills_by_category or {}).items():
            seen_lower: set = set()
            ordered: List[str] = []
            for s in items or []:
                if not isinstance(s, str):
                    continue
                key = s.strip()
                if not key:
                    continue
                low = key.lower()
                if low in seen_lower:
                    continue
                seen_lower.add(low)
                ordered.append(key)
            consolidated[cat] = ordered

        ops_log: List[Dict[str, Any]] = []

        def _tokens(name: str) -> set:
            import re
            return set([t for t in re.split(r"[^a-z0-9+]+", (name or "").lower()) if t])

        def _name_similarity(a: str, b: str) -> float:
            ta, tb = _tokens(a), _tokens(b)
            if not ta or not tb:
                return 0.0
            inter = len(ta.intersection(tb))
            union = len(ta.union(tb)) or 1
            return inter / union

        def _merge_into(src_cat: str, dst_cat: str):
            src_items = consolidated.get(src_cat, [])
            dst_items = consolidated.get(dst_cat, [])
            existing_lower = set([s.lower() for s in dst_items])
            added = []
            for s in src_items:
                if s.lower() not in existing_lower:
                    dst_items.append(s)
                    existing_lower.add(s.lower())
                    added.append(s)
            consolidated[dst_cat] = dst_items
            if src_cat in consolidated:
                del consolidated[src_cat]
            ops_log.append({
                "action": "merge_category",
                "from": src_cat,
                "to": dst_cat,
                "moved_skills": added,
            })

        # Step A: Merge categories below minimum size
        changed = True
        while changed:
            changed = False
            small_cats = [c for c, items in consolidated.items() if len(items) > 0 and len(items) < min_per_category]
            for cat in small_cats:
                candidates = [c for c in consolidated.keys() if c != cat]
                if not candidates:
                    continue
                # Pick the most similar by name; fallback to largest category
                best = None
                best_sim = -1.0
                for cand in candidates:
                    sim = _name_similarity(cat, cand)
                    if sim > best_sim:
                        best = cand
                        best_sim = sim
                if best is None:
                    # Fallback: largest category
                    best = max(candidates, key=lambda c: len(consolidated.get(c, [])))
                _merge_into(cat, best)
                changed = True

        # Step B: Enforce maximum number of categories
        if len(consolidated) > max_categories:
            # Keep largest categories; merge the rest into most similar kept category
            kept = sorted(consolidated.keys(), key=lambda c: len(consolidated[c]), reverse=True)[:max_categories]
            to_merge = [c for c in consolidated.keys() if c not in kept]
            for cat in to_merge:
                # Find most similar among kept
                best = max(kept, key=lambda c: (_name_similarity(cat, c), len(consolidated[c])))
                _merge_into(cat, best)

        # Final safety: if any categories remain with < min, and there's another category, merge them
        final_small = [c for c, items in consolidated.items() if len(items) > 0 and len(items) < min_per_category]
        for cat in final_small:
            candidates = [c for c in consolidated.keys() if c != cat]
            if not candidates:
                continue
            best = max(candidates, key=lambda c: (_name_similarity(cat, c), len(consolidated[c])))
            _merge_into(cat, best)

        return consolidated, ops_log

    def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text string.
        
        Args:
            text: Text to get embedding for
            
        Returns:
            list: Embedding vector
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error in get_embedding: {e}")
            raise
            
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
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
        
        # Calculate magnitudes
        vec1_norm = np.linalg.norm(v1)
        vec2_norm = np.linalg.norm(v2)
        
        if vec1_norm == 0 or vec2_norm == 0:
            return 0.0
            
        return np.dot(v1, v2) / (vec1_norm * vec2_norm)
    
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
    
    # Process keywords and resume
    results = matcher.process_keywords_and_resume(
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


def get_embedding_model(api_key: Optional[str] = None):
    """
    Factory function to get a SemanticMatcher instance.
    This function is a compatibility layer to resolve an import error
    in the enhancer module.
    """
    return SemanticMatcher(api_key=api_key)