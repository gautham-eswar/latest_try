import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from Pipeline.enhancer import ResumeEnhancer # Assuming ResumeEnhancer is in Pipeline.enhancer
from tests.conftest import MockCompletionsResponse, MockChoice # Import shared mock classes

# Sample data for testing ResumeEnhancer
SAMPLE_BULLET = "Managed a team of 5 engineers."
# For _execute_openai_bullet_enhancement, keywords_tuple is ( (kw1_str, kw1_ctx), (kw2_str, kw2_ctx), ... )
SAMPLE_KEYWORDS_TUPLE = (("team leadership", "Led project teams"), ("project management", "Managed project lifecycle"))
ENHANCED_BULLET_RESPONSE = "Successfully managed and led a team of 5 engineers using project management principles."

SAMPLE_RESUME_DATA_FOR_ENHANCER = {
    "Experience": [{
        "title": "Project Manager",
        "company": "Innovate LLC",
        "responsibilities/achievements": [
            SAMPLE_BULLET,
            "Delivered project on time and under budget."
        ]
    }],
    "Skills": {"Technical Skills": {"Software": ["MS Project"]}} # Example, can be more detailed
}
SAMPLE_MATCHES_BY_BULLET = {
    SAMPLE_BULLET: [
        {"keyword": "team leadership", "context": "Led project teams", "relevance_score": 0.9, "skill_type": "soft skill", "similarity_score": 0.8},
        {"keyword": "project management", "context": "Managed project lifecycle", "relevance_score": 0.85, "skill_type": "hard skill", "similarity_score": 0.75}
    ],
    "Delivered project on time and under budget.": [
         {"keyword": "budgeting", "context": "Managed project budget", "relevance_score": 0.9, "skill_type": "hard skill", "similarity_score": 0.8},
    ]
}
SAMPLE_FINAL_TECHNICAL_SKILLS = {"Software": ["MS Project", "JIRA"], "Methodologies": ["Agile"]}


@pytest.fixture
def resume_enhancer_instance(mock_openai_client):
    """Fixture to create an instance of ResumeEnhancer with a mocked OpenAI client."""
    with patch('Pipeline.enhancer.OpenAI', return_value=mock_openai_client):
        enhancer = ResumeEnhancer(api_key="test_key") # API key is required
        # Caches are no longer part of ResumeEnhancer instance
        return enhancer

@pytest.mark.asyncio
async def test_enhance_bullet_with_keywords_calls_api_and_model(resume_enhancer_instance, mock_openai_client):
    """Test that _enhance_bullet_with_keywords calls the API and uses the correct model (no caching)."""
    mock_openai_client.chat.completions.create.return_value = MockCompletionsResponse(
        choices=[MockChoice(content=ENHANCED_BULLET_RESPONSE)]
    )
    
    # Reconstruct keywords list as expected by _enhance_bullet_with_keywords
    keywords_list = [{'keyword': kw_tuple[0], 'context': kw_tuple[1]} for kw_tuple in SAMPLE_KEYWORDS_TUPLE]

    result1 = await resume_enhancer_instance._enhance_bullet_with_keywords(SAMPLE_BULLET, keywords_list)
    # Call again, should make another API call
    result2 = await resume_enhancer_instance._enhance_bullet_with_keywords(SAMPLE_BULLET, keywords_list)

    assert result1 == ENHANCED_BULLET_RESPONSE
    assert result2 == ENHANCED_BULLET_RESPONSE
    assert mock_openai_client.chat.completions.create.call_count == 2
    
    call_args = mock_openai_client.chat.completions.create.call_args # Args of the last call
    assert call_args.kwargs['model'] == "gpt-4.1-mini"


@pytest.mark.asyncio
async def test_enhance_resume_async_execution(resume_enhancer_instance, mock_openai_client):
    """
    Test the async execution flow of enhance_resume.
    Mocks are set up to return valid structures to allow the method to run to completion.
    Focuses on the concurrency of bullet enhancements.
    """
    # Mock the return value for the _execute_openai_bullet_enhancement calls (via the wrapper)
    # This will be called for each bullet that has matches and needs enhancement.
    mock_openai_client.chat.completions.create.return_value = MockCompletionsResponse(
        choices=[MockChoice(content=ENHANCED_BULLET_RESPONSE)] # Generic enhanced response
    )

    # Spy on the methods that are called by enhance_resume
    # We are testing the orchestration here.
    # _enhance_bullet_with_keywords_wrapper is the one directly called in the loop with asyncio.gather
    with patch.object(resume_enhancer_instance, '_enhance_bullet_with_keywords_wrapper', wraps=resume_enhancer_instance._enhance_bullet_with_keywords_wrapper) as spy_wrapper, \
         patch.object(resume_enhancer_instance, '_filter_matches_by_usage', wraps=resume_enhancer_instance._filter_matches_by_usage) as spy_filter_matches, \
         patch.object(resume_enhancer_instance, '_validate_enhancement', return_value=True) as spy_validate: # Assume validation always passes

        enhanced_resume_result, modifications_result = await resume_enhancer_instance.enhance_resume(
            resume_data=SAMPLE_RESUME_DATA_FOR_ENHANCER,
            matches_by_bullet=SAMPLE_MATCHES_BY_BULLET,
            final_technical_skills=SAMPLE_FINAL_TECHNICAL_SKILLS
        )

        # Assert that the main orchestration methods were called
        spy_filter_matches.assert_called_once()
        
        # Determine how many bullets should have been processed for enhancement
        # This depends on filtered_matches, which is complex.
        # Let's check based on SAMPLE_MATCHES_BY_BULLET for simplicity.
        # The wrapper is called for each bullet that has keywords in filtered_matches.
        # Our SAMPLE_MATCHES_BY_BULLET has 2 bullets with keywords.
        # The _filter_matches_by_usage might change this number.
        # For this test, let's assume _filter_matches_by_usage passes through these two.
        
        # Number of expected calls to the wrapper (and thus to OpenAI via the cached method)
        # based on SAMPLE_MATCHES_BY_BULLET before filtering.
        # This test is more about the async flow than precise counting after filtering.
        assert spy_wrapper.call_count >= 1 # Should be called for bullets with matches
        
        # Check if OpenAI's create was called.
        # The number of calls to the actual OpenAI API depends on caching and the number of unique bullets to enhance.
        # If SAMPLE_BULLET is the only one considered unique and enhanced:
        # If there are multiple bullets with matches, it could be more than 1.
        # Given the cache and the setup, it will be called for unique (bullet, keywords_tuple) pairs.
        # For this sample data, there are two distinct bullets with matches.
        # Assuming filter_matches preserves them and they are unique enough.
        # The number of calls to the actual OpenAI API (_enhance_bullet_with_keywords)
        # will depend on the number of bullets that have matches after filtering.
        # Let's assume _filter_matches_by_usage results in two bullets needing enhancement for this sample.
        # If SAMPLE_MATCHES_BY_BULLET results in two enhancement tasks after filtering:
        
        # To make this test more robust, we should mock _filter_matches_by_usage to return a predictable set.
        # For now, we'll assume it passes through the two items in SAMPLE_MATCHES_BY_BULLET.
        # Each call to _enhance_bullet_with_keywords_wrapper -> _enhance_bullet_with_keywords will call OpenAI once.
        
        # Count how many bullets have keyword suggestions in SAMPLE_MATCHES_BY_BULLET
        # This is a proxy for how many times the wrapper (and thus OpenAI) might be called,
        # assuming _filter_matches_by_usage doesn't filter them out.
        expected_openai_calls = 0
        # Simulate the behavior of _filter_matches_by_usage based on SAMPLE_MATCHES_BY_BULLET
        # This is a simplified simulation. A more robust test would mock _filter_matches_by_usage.
        temp_keyword_usage = {}
        max_keyword_usage_for_test = 2 # Matching default in enhance_resume
        
        # Simplified filtering logic to estimate calls (not perfect)
        sorted_bullets_for_test = sorted(SAMPLE_MATCHES_BY_BULLET.items(), key=lambda item: sum(m["relevance_score"] for m in item[1]), reverse=True)

        for bullet_text, matches in sorted_bullets_for_test:
            valid_keywords_for_bullet = 0
            temp_hard_skills = 0
            temp_soft_skills = 0
            
            sorted_matches = sorted(matches, key=lambda m: (m["relevance_score"] * 0.7 + m["similarity_score"] * 0.3), reverse=True)

            current_bullet_keywords = []
            for match in sorted_matches:
                kw = match["keyword"].lower()
                if temp_keyword_usage.get(kw, 0) < max_keyword_usage_for_test:
                    if match["skill_type"] == "hard skill" and temp_hard_skills < 2:
                        current_bullet_keywords.append(match)
                        temp_keyword_usage[kw] = temp_keyword_usage.get(kw, 0) + 1
                        temp_hard_skills +=1
                    elif match["skill_type"] == "soft skill" and temp_soft_skills < 1:
                        current_bullet_keywords.append(match)
                        temp_keyword_usage[kw] = temp_keyword_usage.get(kw, 0) + 1
                        temp_soft_skills +=1
                if len(current_bullet_keywords) >=3:
                    break
            if current_bullet_keywords: # If there are keywords to enhance with for this bullet
                 expected_openai_calls +=1
        
        if expected_openai_calls > 0:
            assert mock_openai_client.chat.completions.create.call_count == expected_openai_calls
            # Check model for the last call (assuming all calls use the same model)
            call_args = mock_openai_client.chat.completions.create.call_args
            assert call_args.kwargs['model'] == "gpt-4.1-mini"
        else:
            mock_openai_client.chat.completions.create.assert_not_called()


        # Check structure of results (basic check)
        assert "Experience" in enhanced_resume_result
        assert isinstance(modifications_result, list)
        
        # Check if the skills section was updated
        assert enhanced_resume_result["Skills"]["Technical Skills"] == SAMPLE_FINAL_TECHNICAL_SKILLS
        # Check if a modification entry for skills update was added
        assert any(mod.get("type") == "Technical Skills Update" for mod in modifications_result)


@pytest.mark.asyncio
async def test_enhance_resume_no_matches(resume_enhancer_instance, mock_openai_client):
    """Test enhance_resume when there are no matches, so no OpenAI calls for enhancement."""
    
    empty_matches_by_bullet = {}
    
    with patch.object(resume_enhancer_instance, '_enhance_bullet_with_keywords_wrapper', wraps=resume_enhancer_instance._enhance_bullet_with_keywords_wrapper) as spy_wrapper:
        enhanced_resume_result, modifications_result = await resume_enhancer_instance.enhance_resume(
            resume_data=SAMPLE_RESUME_DATA_FOR_ENHANCER,
            matches_by_bullet=empty_matches_by_bullet, # No matches
            final_technical_skills=SAMPLE_FINAL_TECHNICAL_SKILLS
        )
        
        spy_wrapper.assert_not_called() # Wrapper should not be called
        mock_openai_client.chat.completions.create.assert_not_called() # OpenAI should not be called for enhancements

        # Ensure skills section is still updated
        assert enhanced_resume_result["Skills"]["Technical Skills"] == SAMPLE_FINAL_TECHNICAL_SKILLS
        assert len(modifications_result) == 1 # Only skill update modification
        assert modifications_result[0]["type"] == "Technical Skills Update"

@pytest.mark.asyncio
async def test_enhance_resume_validation_fails(resume_enhancer_instance, mock_openai_client):
    """Test enhance_resume when OpenAI provides an enhancement but it fails validation."""
    mock_openai_client.chat.completions.create.return_value = MockCompletionsResponse(
        choices=[MockChoice(content="This enhanced bullet will fail validation.")]
    )

    with patch.object(resume_enhancer_instance, '_validate_enhancement', return_value=False) as spy_validate:
        enhanced_resume_result, modifications_result = await resume_enhancer_instance.enhance_resume(
            resume_data=SAMPLE_RESUME_DATA_FOR_ENHANCER,
            matches_by_bullet=SAMPLE_MATCHES_BY_BULLET,
            final_technical_skills=None # No skill update for simplicity here
        )
        
        # Assert that OpenAI was called (at least once for the first bullet attempt)
        assert mock_openai_client.chat.completions.create.call_count >= 1
        # Assert validation was called
        assert spy_validate.call_count >= 1
        
        # Assert no bullet modifications were recorded because validation failed
        bullet_modifications = [mod for mod in modifications_result if "section" not in mod]
        assert len(bullet_modifications) == 0
        
        # Check that the original bullet text was preserved in the resume
        original_bullet_text_from_sample = SAMPLE_RESUME_DATA_FOR_ENHANCER["Experience"][0]["responsibilities/achievements"][0]
        assert enhanced_resume_result["Experience"][0]["responsibilities/achievements"][0] == original_bullet_text_from_sample

@pytest.mark.asyncio
async def test_enhance_bullet_with_keywords_handles_api_error(resume_enhancer_instance, mock_openai_client):
    """Test that _enhance_bullet_with_keywords raises an error if the API call fails."""
    mock_openai_client.chat.completions.create.side_effect = Exception("OpenAI API Error")
    
    keywords_list = [{'keyword': kw_tuple[0], 'context': kw_tuple[1]} for kw_tuple in SAMPLE_KEYWORDS_TUPLE]

    with pytest.raises(Exception, match="OpenAI API Error"):
        await resume_enhancer_instance._enhance_bullet_with_keywords(
            SAMPLE_BULLET, keywords_list
        )
