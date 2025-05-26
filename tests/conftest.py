import pytest
from unittest.mock import AsyncMock, MagicMock

# Define a mock completion choice for chat models
class MockChoice:
    def __init__(self, content):
        self.message = MagicMock()
        self.message.content = content

# Define a mock embedding data for embedding models
class MockEmbeddingData:
    def __init__(self, embedding_vector):
        self.embedding = embedding_vector

class MockCompletionsResponse:
    def __init__(self, choices):
        self.choices = choices

class MockEmbeddingsResponse:
    def __init__(self, data):
        self.data = data

@pytest.fixture
def mock_openai_client(mocker):
    """Fixture to create a mock OpenAI client with async methods."""
    mock_client = MagicMock() # Using MagicMock as the base for the client itself

    # Mock for chat completions
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    # .create() is an async method, so it needs AsyncMock
    mock_client.chat.completions.create = AsyncMock()

    # Mock for embeddings
    mock_client.embeddings = MagicMock()
    # .create() is an async method
    mock_client.embeddings.create = AsyncMock()
    
    return mock_client
