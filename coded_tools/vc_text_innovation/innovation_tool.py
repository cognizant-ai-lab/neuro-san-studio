import os
import uuid
import logging
import pandas as pd

from typing import Dict, Any

from sentence_transformers import SentenceTransformer

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

from neuro_san.interfaces.coded_tool import CodedTool

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class ArxivRAG(CodedTool):
    def __init__(self):
        try:
            self.model = SentenceTransformer('sentence-transformers/all-roberta-large-v1')
            self.qdrant = QdrantClient(host="localhost", port=6333)
            self.collection_name = "papers"
            self.vector_size = self.model.get_sentence_embedding_dimension()
            self._ensure_collection()
            logger.info("Initialized DocumentProcessor with Qdrant")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise

    def _ensure_collection(self):
        collections = [c.name for c in self.qdrant.get_collections().collections]
        if self.collection_name not in collections:
            self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
            )
            logger.info(f"Created Qdrant collection: {self.collection_name}")
        else:
            logger.info(f"Qdrant collection '{self.collection_name}' already exists")

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
        action = args.get("action")

        if action == "load_csv":
            folder_path = args.get("folder_path", os.getenv("FOLDER_PATH", "load_files/"))
            return self.load_csv(folder_path)

        elif action == "query_documents":
            query = args.get("query", "")
            results = self.query_documents(query)
            print(f"Query results: {results}")
            return results
        else:
            return {"status": "failed", "error": f"Unknown action: {action}"}

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
        return self.invoke(args, sly_data)

    def load_csv(self, folder_path: str) -> Dict[str, Any]:
        if not os.path.isdir(folder_path):
            return {"status": "failed", "error": f"Folder not found: {folder_path}"}

        csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
        if not csv_files:
            return {"status": "failed", "error": f"No CSV files found in: {folder_path}"}

        results = []
        for file in csv_files:
            df = pd.read_csv(os.path.join(folder_path, file))
            df = df.drop_duplicates(subset=["title", "summary"])

            if 'title' not in df.columns or 'summary' not in df.columns:
                logger.warning(f"Skipping {file}, missing 'title' or 'summary'")
                continue

            points = []
            for _, row in df.iterrows():
                title, summary = row['title'], row['summary']
                if pd.isna(title) or pd.isna(summary):
                    continue
                text = f"{title} {summary}"
                embedding = self.model.encode(text)
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "title": title,
                        "summary": summary,
                        "source_file": file
                    }
                )
                points.append(point)

            for i in range(0, len(points), 100):
                self.qdrant.upsert(collection_name=self.collection_name, points=points[i:i+100])

            logger.info(f"Inserted {len(points)} vectors from {file}")
            results.extend(points)

        return {
            "status": "success",
            "output": self.collection_name,
            "results": {
                "document_count": len(results),
                "documents": [p.payload for p in results[:7]]
            }
        }

    def query_documents(self, query: str, limit: int = 7) -> Dict[str, Any]:
        if not query:
            return {"status": "failed", "error": "Empty query provided"}

        try:
            query_vector = self.model.encode(query).tolist()
            results = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                with_payload=True
            )
            return {
                "status": "success",
                "output": self.collection_name,
                "results": {
                    "document_count": len(results),
                    "documents": [
                        {
                            "title": r.payload.get("title"),
                            "summary": r.payload.get("summary"),
                            "source_file": r.payload.get("source_file"),
                            "score": r.score
                        }
                        for r in results
                    ]
                }
            }
        except Exception as e:
            logger.error(f"Query error: {e}")
            return {"status": "failed", "error": str(e)}
