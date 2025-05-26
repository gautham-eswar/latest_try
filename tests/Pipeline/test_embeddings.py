import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from Pipeline.embeddings import SemanticMatcher
from tests.conftest import MockCompletionsResponse, MockChoice, MockEmbeddingsResponse, MockEmbeddingData

# Sample data for testing SemanticMatcher
SAMPLE_TEXT_FOR_EMBEDDING = "This is a test sentence for embedding."
SAMPLE_EMBEDDING_VECTOR = [0.1, 0.2, 0.3, 0.4, 0.5]

SAMPLE_SKILL_NAME = "Python Programming"
SAMPLE_SKILL_CONTEXT = "Developed web applications using Python."
SAMPLE_RESUME_CATEGORIES = ("Languages", "Frameworks") # Tuple as used in cache key

SAMPLE_KEYWORDS_DATA = {"keywords": [
    {"keyword": "Python", "context": "Experience with Python", "relevance_score": 0.9, "skill_type": "hard skill"},
    {"keyword": "Django", "context": "Built APIs with Django", "relevance_score": 0.8, "skill_type": "hard skill"}
]}
SAMPLE_RESUME_DATA = {
    "Experience": [{
        "title": "Software Engineer",
        "company": "Tech Corp",
        "responsibilities/achievements": [
            "Developed a web app using Python and Django.",
            "Implemented RESTful APIs."
        ]
    }],
    "Skills": {
        "Technical Skills": {
            "Programming Languages": ["Python", "Java"],
            "Web Frameworks": ["Django", "Spring"]
        }
    }
}


@pytest.fixture
def semantic_matcher_instance(mock_openai_client):
    """Fixture to create an instance of SemanticMatcher with a mocked OpenAI client."""
    # Patch the OpenAI class globally for the duration of this test if SemanticMatcher instantiates it directly
    # If OpenAI client is passed to __init__, then just pass mock_openai_client
    with patch('Pipeline.embeddings.OpenAI', return_value=mock_openai_client):
        matcher = SemanticMatcher(api_key="test_key") # API key is required by __init__
        # Caches are no longer part of SemanticMatcher instance
        return matcher

@pytest.mark.asyncio
async def test_get_embedding_calls_api(semantic_matcher_instance, mock_openai_client):
    """Test that _get_embedding calls the OpenAI API correctly (no caching)."""
    mock_openai_client.embeddings.create.return_value = MockEmbeddingsResponse(
        data=[MockEmbeddingData(embedding_vector=SAMPLE_EMBEDDING_VECTOR)]
    )

    result1 = await semantic_matcher_instance._get_embedding(SAMPLE_TEXT_FOR_EMBEDDING)
    # Call again with same text, should still call API
    result2 = await semantic_matcher_instance._get_embedding(SAMPLE_TEXT_FOR_EMBEDDING) 

    assert result1 == SAMPLE_EMBEDDING_VECTOR
    assert result2 == SAMPLE_EMBEDDING_VECTOR
    assert mock_openai_client.embeddings.create.call_count == 2
    mock_openai_client.embeddings.create.assert_any_call(
        input=SAMPLE_TEXT_FOR_EMBEDDING,
        model=semantic_matcher_instance.model 
    )

# The test for _execute_single_skill_categorization is removed as the method itself was removed.
# Its logic is now part of _categorize_jd_skills_with_openai, and model usage is tested
# within test_process_keywords_and_resume_async_execution.

@pytest.mark.asyncio
async def test_process_keywords_and_resume_async_execution(semantic_matcher_instance, mock_openai_client):
    """
    Test the async execution flow of process_keywords_and_resume.
    This is an integration test for the async flow within the method.
    Mocks are set up to return valid structures to allow the method to run to completion.
    """
    # Mock return values for embedding calls
    mock_openai_client.embeddings.create.return_value = MockEmbeddingsResponse(
        data=[MockEmbeddingData(embedding_vector=SAMPLE_EMBEDDING_VECTOR)]
    )
    
    # Mock return value for skill categorization (called by _categorize_jd_skills_with_openai)
    mock_openai_client.chat.completions.create.return_value = MockCompletionsResponse(
        choices=[MockChoice(content="New Category: Cloud Technologies")] # Example response
    )

    # Spy on the methods that are called by process_keywords_and_resume
    # We are not testing their internal logic here, just that they are awaited.
    with patch.object(semantic_matcher_instance, 'generate_keyword_embeddings', wraps=semantic_matcher_instance.generate_keyword_embeddings) as spy_gen_kw_embed, \
         patch.object(semantic_matcher_instance, 'generate_bullet_embeddings', wraps=semantic_matcher_instance.generate_bullet_embeddings) as spy_gen_bullet_embed, \
         patch.object(semantic_matcher_instance, 'extract_resume_technical_skills', wraps=semantic_matcher_instance.extract_resume_technical_skills) as spy_extract_resume_skills, \
         patch.object(semantic_matcher_instance, '_categorize_jd_skills_with_openai', wraps=semantic_matcher_instance._categorize_jd_skills_with_openai) as spy_categorize_skills, \
         patch.object(semantic_matcher_instance, 'deduplicate_keywords', return_value=[]) as spy_dedup, \
         patch.object(semantic_matcher_instance, 'calculate_similarity', return_value=[]) as spy_calc_sim, \
         patch.object(semantic_matcher_instance, 'group_matches_by_bullet', return_value={}) as spy_group_matches, \
         patch.object(semantic_matcher_instance, 'select_final_technical_skills', return_value=({}, {})) as spy_select_final_skills:

        # Call the main processing method
        results = await semantic_matcher_instance.process_keywords_and_resume(
            keywords_data=SAMPLE_KEYWORDS_DATA,
            resume_data=SAMPLE_RESUME_DATA
        )

        # Assert that the results dictionary has the expected top-level keys
        expected_top_level_keys = [
            "deduplicated_keywords_for_bullets", 
            "similarity_results", 
            "matches_by_bullet", 
            "final_technical_skills", 
            "statistics",
            "skill_selection_process_log"
        ]
        for key in expected_top_level_keys:
            assert key in results

        # Assert that the async methods were called (awaited)
        spy_gen_kw_embed.assert_awaited_once()
        spy_gen_bullet_embed.assert_awaited_once()
        spy_extract_resume_skills.assert_awaited_once()
        spy_categorize_skills.assert_awaited_once()
        
        # Assert that synchronous methods wrapped in spies were called
        spy_dedup.assert_called_once()
        spy_calc_sim.assert_called_once()
        spy_group_matches.assert_called_once()
        spy_select_final_skills.assert_called_once()

        # Verify that the embedding generation calls within the gathered tasks were made
        # The number of calls depends on the sample data
        num_jd_keywords = len(SAMPLE_KEYWORDS_DATA["keywords"])
        num_resume_bullets = sum(len(exp.get("responsibilities/achievements", [])) for exp in SAMPLE_RESUME_DATA.get("Experience", []))
        
        num_resume_tech_skills = 0
        tech_skills_section = SAMPLE_RESUME_DATA.get("Skills", {}).get("Technical Skills", {})
        if isinstance(tech_skills_section, dict):
            for category_skills in tech_skills_section.values():
                num_resume_tech_skills += len(category_skills)
        elif isinstance(tech_skills_section, list): # Flat list of skills
             num_resume_tech_skills += len(tech_skills_section)

        # Total calls to client.embeddings.create (used by _get_embedding)
        # Since caching is removed, each call to _get_embedding (even with same text) results in an API call.
        # The number of calls will be the sum of:
        # - JD keywords
        # - Resume bullets
        # - Resume technical skills
        # This count assumes that each item in these lists results in one call to _get_embedding.
        # If generate_keyword_embeddings, generate_bullet_embeddings, or extract_resume_technical_skills
        # call _get_embedding multiple times for the *same text string*, the count would be higher.
        # Assuming each text processed by _get_embedding is unique for this calculation.
        
        num_jd_keywords = len(SAMPLE_KEYWORDS_DATA["keywords"])
        num_resume_bullets = sum(len(exp.get("responsibilities/achievements", [])) for exp in SAMPLE_RESUME_DATA.get("Experience", []))
        
        num_resume_tech_skills = 0
        tech_skills_section = SAMPLE_RESUME_DATA.get("Skills", {}).get("Technical Skills", {})
        if isinstance(tech_skills_section, dict): # Categorized skills
            for skills_in_category in tech_skills_section.values():
                num_resume_tech_skills += len(skills_in_category)
        elif isinstance(tech_skills_section, list): # Flat list of skills
            num_resume_tech_skills += len(tech_skills_section)
            
        expected_embedding_calls = num_jd_keywords + num_resume_bullets + num_resume_tech_skills
        assert mock_openai_client.embeddings.create.call_count == expected_embedding_calls
        
        # Verify skill categorization model usage (called via _categorize_jd_skills_with_openai)
        # The number of calls to chat.completions.create will be equal to the number of jd_hard_skills_for_section,
        # as caching is removed for skill categorization as well.
        jd_hard_skills_for_section = [
            kw for kw in SAMPLE_KEYWORDS_DATA['keywords'] 
            if kw.get("skill_type") == "hard skill" # This is simplified; actual filtering uses relevance_score
        ]
        
        # Check if resume_categories is empty or not, as _categorize_jd_skills_with_openai has a condition for this
        resume_categories_exist = bool(SAMPLE_RESUME_DATA.get("Skills", {}).get("Technical Skills"))

        if jd_hard_skills_for_section and resume_categories_exist:
            assert mock_openai_client.chat.completions.create.call_count == len(jd_hard_skills_for_section)
            # Check model for any of these calls (they all use the same model)
            categorization_call_args = mock_openai_client.chat.completions.create.call_args
            assert categorization_call_args.kwargs['model'] == "gpt-4.1-mini" # Updated model name
        else: # No hard skills or no resume categories to map to, so no categorization calls.
            assert mock_openai_client.chat.completions.create.call_count == 0
