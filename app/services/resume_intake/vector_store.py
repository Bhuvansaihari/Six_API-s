"""Vector store service for managing embeddings in Qdrant."""

import logging
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from config import get_settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Manages resume embeddings in Qdrant vector store."""
    
    def __init__(self):
        """
        Initialize Qdrant client and ensure collection exists.
        
        Raises:
            ValueError: If Qdrant credentials are not configured
        """
        settings = get_settings()
        
        if not settings.qdrant_url:
            raise ValueError("Qdrant URL not configured. Please set QDRANT_URL in .env file")
        
        if not settings.qdrant_api_key:
            raise ValueError("Qdrant API key not configured. Please set QDRANT_API_KEY in .env file")
        
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value(),
            timeout=60
        )
        self.collection_name = settings.qdrant_collection_name
        self.vector_size = settings.vector_size
        
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Ensure the collection exists in Qdrant."""
        try:
            if not self.client.collection_exists(self.collection_name):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                )
                # Create payload index for CandidateID
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="CandidateID",
                    field_schema="integer"
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            logger.debug(f"Collection already exists or error: {e}")
    
    def store(self, candidate_id: int, embeddings: List[float], payload: Dict[str, Any] = None) -> str:
        """
        Store embeddings in Qdrant.
        
        Args:
            candidate_id: Candidate ID
            embeddings: Vector embeddings (must match vector_size dimensions)
            payload: Additional metadata payload
            
        Returns:
            Success message
        """
        if payload is None:
            payload = {}
        
        # Prepare point for upsert
        point = PointStruct(
            id=candidate_id,
            vector=embeddings,
            payload={"CandidateID": candidate_id, **payload}
        )
        
        # Upsert to Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        
        return f"Successfully stored embeddings for Candidate ID: {candidate_id} in Qdrant"

