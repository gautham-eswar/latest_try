import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
# Removed keyword_extraction_cache import, OPENAI_MODEL is still imported to check against the new value
from Pipeline.keyword_extraction import extract_keywords, OPENAI_MODEL 
from tests.conftest import MockCompletionsResponse, MockChoice # Import shared mock classes

# Sample job description for testing
SAMPLE_JD = "We need a Python developer with experience in Django and REST APIs."
EXPECTED_KEYWORDS_RESPONSE = {"keywords": [{"keyword": "Python", "context": "developer", "relevance_score": 0.9, "skill_type": "hard skill"}]}

# Removed clear_keyword_cache fixture as it's no longer needed

@pytest.mark.asyncio
async def test_extract_keywords_basic_async_call(mocker):
    """Test that extract_keywords can be called and awaited, returning expected structure."""
    
    # Mock the OpenAI client and its response
    mock_chat_create = AsyncMock(return_value=MockCompletionsResponse(choices=[MockChoice(content=json.dumps(EXPECTED_KEYWORDS_RESPONSE))]))
    
    # Patch where OpenAI class is instantiated within extract_keywords
    # Assuming extract_keywords instantiates OpenAI like: client = OpenAI(...)
    # The patch should target 'Pipeline.keyword_extraction.OpenAI'
    mocker.patch('Pipeline.keyword_extraction.OpenAI', return_value=MagicMock(chat=MagicMock(completions=MagicMock(create=mock_chat_create))))

    result = await extract_keywords(SAMPLE_JD)
    
    assert result == EXPECTED_KEYWORDS_RESPONSE
    mock_chat_create.assert_called_once()

@pytest.mark.asyncio
async def test_extract_keywords_caching(mocker):
    """Test that extract_keywords caches results and calls OpenAI only once for the same input."""
    
    mock_chat_create = AsyncMock(return_value=MockCompletionsResponse(choices=[MockChoice(content=json.dumps(EXPECTED_KEYWORDS_RESPONSE))]))
    mocker.patch('Pipeline.keyword_extraction.OpenAI', return_value=MagicMock(chat=MagicMock(completions=MagicMock(create=mock_chat_create))))

    # Call extract_keywords twice with the same job description
    result1 = await extract_keywords(SAMPLE_JD)
    result2 = await extract_keywords(SAMPLE_JD) # Should hit the cache

    assert result1 == EXPECTED_KEYWORDS_RESPONSE
    assert result2 == EXPECTED_KEYWORDS_RESPONSE
    # OpenAI client's create method should be called once for this test.
    mock_chat_create.assert_called_once()

    # If called again, it should make another API call
    await extract_keywords(SAMPLE_JD + " new") # Different JD
    assert mock_chat_create.call_count == 2


@pytest.mark.asyncio
async def test_extract_keywords_uses_correct_model(mocker):
    """Test that extract_keywords uses the updated OPENAI_MODEL."""
    
    mock_chat_create = AsyncMock(return_value=MockCompletionsResponse(choices=[MockChoice(content=json.dumps(EXPECTED_KEYWORDS_RESPONSE))]))
    mocker.patch('Pipeline.keyword_extraction.OpenAI', return_value=MagicMock(chat=MagicMock(completions=MagicMock(create=mock_chat_create))))

    # The OPENAI_MODEL constant in Pipeline.keyword_extraction should now be "gpt-4.1-mini"
    # The function extract_keywords uses this as a default for its model parameter.
    await extract_keywords(SAMPLE_JD) 
    
    mock_chat_create.assert_called_once()
    call_args = mock_chat_create.call_args
    assert call_args.kwargs['model'] == "gpt-4.1-mini"

    # Test overriding the model
    await extract_keywords(SAMPLE_JD, model="another-model")
    call_args_override = mock_chat_create.call_args
    assert call_args_override.kwargs['model'] == "another-model"
    assert mock_chat_create.call_count == 2


@pytest.mark.asyncio
async def test_extract_keywords_empty_or_short_jd():
    """Test that extract_keywords returns empty list for short/empty JD without calling OpenAI."""
    # No need to mock OpenAI here as it shouldn't be called
    
    result_empty = await extract_keywords("")
    assert result_empty == {"keywords": []}
    
    result_short = await extract_keywords("Too short")
    assert result_short == {"keywords": []}

@pytest.mark.asyncio
async def test_extract_keywords_handles_openai_error(mocker):
    """Test that extract_keywords raises RuntimeError if OpenAI call fails."""
    mock_chat_create = AsyncMock(side_effect=Exception("OpenAI API Error"))
    mocker.patch('Pipeline.keyword_extraction.OpenAI', return_value=MagicMock(chat=MagicMock(completions=MagicMock(create=mock_chat_create))))

    with pytest.raises(RuntimeError, match="OpenAI API call failed: OpenAI API Error"):
        await extract_keywords(SAMPLE_JD)

@pytest.mark.asyncio
async def test_extract_keywords_handles_json_decode_error(mocker):
    """Test that extract_keywords raises ValueError if OpenAI returns malformed JSON and repair fails."""
    malformed_json_response = "This is not JSON" # No repair possible for this
    mock_chat_create = AsyncMock(return_value=MockCompletionsResponse(choices=[MockChoice(content=malformed_json_response)]))
    mocker.patch('Pipeline.keyword_extraction.OpenAI', return_value=MagicMock(chat=MagicMock(completions=MagicMock(create=mock_chat_create))))

    with pytest.raises(ValueError, match="OpenAI returned non-JSON response"):
        await extract_keywords(SAMPLE_JD)

    # Test with JSON that starts correctly but is malformed, and repair logic fails
    malformed_json_response_repair_fails = '{"keywords": [ {"keyword": "test", "context": "test context" ' # Incomplete JSON
    mock_chat_create.return_value = MockCompletionsResponse(choices=[MockChoice(content=malformed_json_response_repair_fails)])
    
    with pytest.raises(ValueError, match="Failed to parse keywords JSON from OpenAI response, and repair attempt failed"):
        await extract_keywords(SAMPLE_JD + " slightly different to avoid cache")


@pytest.mark.asyncio
async def test_extract_keywords_different_api_key_model_not_cached_separately_by_default_lambda(mocker):
    """
    Tests that the default cache key (job_description_text only) means calls with different
    api_key or model parameters (if not part of the lambda key) hit the same cache entry.
    The current lambda key is:
    lambda job_description_text, api_key=None, model=OPENAI_MODEL, max_tokens_response=KEYWORD_EXTRACTION_MAX_TOKENS: job_description_text
    So, different api_key, model, max_tokens_response will NOT create new cache entries if job_description_text is the same.
    This test verifies that understanding.
    """
    mock_chat_create = AsyncMock(return_value=MockCompletionsResponse(choices=[MockChoice(content=json.dumps(EXPECTED_KEYWORDS_RESPONSE))]))
    mocker.patch('Pipeline.keyword_extraction.OpenAI', return_value=MagicMock(chat=MagicMock(completions=MagicMock(create=mock_chat_create))))

    # Call 1
    await extract_keywords(SAMPLE_JD, api_key="key1", model="model1")
    mock_chat_create.assert_called_once()
    first_call_args = mock_chat_create.call_args
    assert first_call_args.kwargs['model'] == "model1" # Model was passed through

    # Call 2 with same JD but different API key and model - should hit cache due to lambda key
    # The mocked OpenAI won't be called again. The result will be from the first call.
    result2 = await extract_keywords(SAMPLE_JD, api_key="key2", model="model2")
    
    assert mock_chat_create.call_count == 1 # Still 1, due to cache key being only job_description_text
    assert result2 == EXPECTED_KEYWORDS_RESPONSE # Returns response from first call
    
