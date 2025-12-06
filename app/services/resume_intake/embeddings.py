"""Embedding service for generating vector embeddings using OpenAI with async support."""

import logging
from typing import List
from openai import OpenAI, AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates embeddings using OpenAI's text-embedding-3-large model."""
    
    def __init__(self):
        """
        Initialize OpenAI clients (sync and async).
        
        Raises:
            ValueError: If OpenAI API key is not configured
        """
        settings = get_settings()
        
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY in .env file")
        
        api_key = settings.openai_api_key.get_secret_value()
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
    
    def generate(self, text_data: str) -> List[float]:
        """
        Generate embeddings for text data (sync).
        
        Args:
            text_data: Text to generate embeddings for
            
        Returns:
            List of embedding vectors (1536 dimensions)
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized")
        
        settings = get_settings()
        
        # Generate embeddings with configured dimensions to match Qdrant configuration
        response = self.client.embeddings.create(
            model="text-embedding-3-large",
            input=text_data,
            dimensions=settings.vector_size
        )
        
        return response.data[0].embedding
    
    async def generate_async(self, text_data: str) -> List[float]:
        """
        Generate embeddings for text data (async).
        
        Args:
            text_data: Text to generate embeddings for
            
        Returns:
            List of embedding vectors (1536 dimensions by default)
        """
        if not self.async_client:
            raise ValueError("OpenAI async client not initialized")
        
        settings = get_settings()
        
        # Generate embeddings (async) with configured dimensions to match Qdrant configuration
        response = await self.async_client.embeddings.create(
            model="text-embedding-3-large",
            input=text_data,
            dimensions=settings.vector_size
        )
        
        return response.data[0].embedding

