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
logger = logging.getLogger("semantic_matcher")


class SemanticMatcher:
    """
    Generate embeddings, deduplicate keywords, and match keywords to resume bullets.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the SemanticMatcher with OpenAI API key.
        
        Args:
            api_key: OpenAI API key. If None, will try to get from environment variable.
        """
        # Get API key from parameter or environment variable
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Provide it as a parameter or set OPENAI_API_KEY environment variable.")
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)
        
        # Default similarity threshold
        self.similarity_threshold = 0.75
        
    def process_keywords_and_resume(self, 
                                   keywords_data: Dict[str, Any], 
                                   resume_data: Dict[str, Any],
                                   similarity_threshold: float = 0.75) -> Dict[str, Any]:
        """
        Process keywords and resume data through the complete pipeline.
        
        Args:
            keywords_data: Extracted keywords with metadata
            resume_data: Parsed resume JSON
            similarity_threshold: Threshold for semantic matching (0-1)
            
        Returns:
            dict: Results with deduplicated keywords, matches, and statistics
        """
        logger.info("Starting semantic processing pipeline")
        self.similarity_threshold = similarity_threshold
        
        # Step 1: Generate embeddings for keywords
        logger.info("Generating embeddings for keywords")
        keywords_with_embeddings = self.generate_keyword_embeddings(keywords_data["keywords"])
        
        # Step 2: Deduplicate keywords
        logger.info("Deduplicating keywords")
        deduplicated_keywords = self.deduplicate_keywords(keywords_with_embeddings)
        
        # Step 3: Extract bullet points from resume
        logger.info("Extracting bullet points from resume")
        bullet_points = self.extract_bullet_points(resume_data)
        
        # Step 4: Generate embeddings for bullet points
        logger.info("Generating embeddings for bullet points")
        bullets_with_embeddings = self.generate_bullet_embeddings(bullet_points)
        
        # Step 5: Calculate similarity and find matches
        logger.info("Calculating similarity between keywords and bullets")
        similarity_results = self.calculate_similarity(deduplicated_keywords, bullets_with_embeddings)
        
        # Step 6: Group matches by bullet point
        logger.info("Grouping matches by bullet point")
        matches_by_bullet = self.group_matches_by_bullet(similarity_results)
        
        # Create result dictionary
        result = {
            "deduplicated_keywords": [k for k in deduplicated_keywords if "embedding" not in k],  # Remove embeddings for readability
            "similarity_results": similarity_results,
            "matches_by_bullet": matches_by_bullet,
            "statistics": {
                "original_keywords": len(keywords_data["keywords"]),
                "deduplicated_keywords": len(deduplicated_keywords),
                "bullets_processed": len(bullet_points),
                "bullets_with_matches": sum(1 for matches in matches_by_bullet.values() if matches),
                "total_matches": sum(len(matches) for matches in matches_by_bullet.values())
            }
        }
        
        logger.info(f"Semantic processing complete. Found {result['statistics']['total_matches']} matches across {result['statistics']['bullets_with_matches']} bullets.")
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
                embedding = self._get_embedding(text)
                
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
                embedding = self._get_embedding(bullet["bullet_text"])
                
                # Add embedding to bullet data
                bullet_with_embedding = bullet.copy()
                bullet_with_embedding["embedding"] = embedding
                bullets_with_embeddings.append(bullet_with_embedding)
                
            except Exception as e:
                logger.error(f"Error generating embedding for bullet '{bullet['bullet_text'][:30]}...': {str(e)}")
                # Skip this bullet if embedding generation fails
        
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
            
            matches_by_bullet[bullet] = combined[:3]  # Maximum 3 keywords total
        
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
        
        return filtered_matches
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text using OpenAI API.
        
        Args:
            text: Text to get embedding for
            
        Returns:
            list: Embedding vector
        """
        response = self.client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
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
        # Create a clean version without large embeddings
        clean_results = {
            "deduplicated_keywords": results["deduplicated_keywords"],
            "similarity_results": results["similarity_results"],
            "matches_by_bullet": results["matches_by_bullet"],
            "statistics": results["statistics"]
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
    print(f"Deduplicated keywords: {results['statistics']['deduplicated_keywords']}")
    print(f"Bullets processed: {results['statistics']['bullets_processed']}")
    print(f"Bullets with matches: {results['statistics']['bullets_with_matches']}")
    print(f"Total matches: {results['statistics']['total_matches']}")