import asyncio
import logging
import os
import random
import time

try:  # pragma: no cover - optional dependency
    import chromadb
    from chromadb.config import Settings
except Exception:  # pragma: no cover - fallback to in-memory store
    chromadb = None
    Settings = None


class _InMemoryCollection:
    """Minimal stand-in for a Chroma collection."""

    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}

    # Chroma compatibility -------------------------------------------------
    def add(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        for doc, md, _id in zip(documents, metadatas, ids):
            self._docs[_id] = {"document": doc, "metadata": md}

    def query(
        self,
        query_texts: list[str] | None = None,
        query_embeddings: list[list[float]] | None = None,
        n_results: int = 10,
        where: dict | None = None,
    ) -> dict:
        docs = []
        metas = []
        for _id, data in self._docs.items():
            md = data["metadata"]
            if where and md.get("visibility") != where.get("visibility"):
                continue
            docs.append(data["document"])
            metas.append(md | {"id": _id})
            if len(docs) >= n_results:
                break
        return {"documents": [docs], "metadatas": [metas], "ids": [[_id for _id in self._docs]]}

    def get(self, ids: list[str]) -> dict:
        found = [_id for _id in ids if _id in self._docs]
        return {"ids": found}

    def delete(self, ids: list[str]) -> None:
        for _id in ids:
            self._docs.pop(_id, None)

    def count(self) -> int:  # pragma: no cover - trivial
        return len(self._docs)

    def persist(self) -> None:  # pragma: no cover - no-op
        return None


class _InMemoryClient:
    def get_or_create_collection(self, _name: str) -> _InMemoryCollection:  # pragma: no cover - simple
        return _InMemoryCollection()

_GLOBAL_CLIENT = None
from neuro_san.interfaces.coded_tool import CodedTool


class VectorDatabaseManager(CodedTool):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        host = os.getenv("CHROMA_HOST", "localhost")
        port = int(os.getenv("CHROMA_PORT", "8000"))
        global _GLOBAL_CLIENT
        if _GLOBAL_CLIENT is None:
            if chromadb is None:
                _GLOBAL_CLIENT = _InMemoryClient()
            else:
                try:
                    _GLOBAL_CLIENT = chromadb.HttpClient(host=host, port=port)
                except Exception as exc:  # pragma: no cover - offline fallback
                    logging.warning(
                        "Chroma HTTP client unavailable (%s); using local client", exc
                    )
                    _GLOBAL_CLIENT = chromadb.PersistentClient(path="/tmp/chroma")
        self.client = _GLOBAL_CLIENT
        self.collection = self.client.get_or_create_collection("legal_documents")
        self.msg_collection = self.client.get_or_create_collection("chat_messages")
        self.convo_collection = self.client.get_or_create_collection("conversations")
        self._query_cache: dict[tuple, dict] = {}
        self._msg_cache: dict[tuple, dict] = {}
        self._convo_cache: dict[tuple, dict] = {}

    def _invalidate_cache(self) -> None:
        self._query_cache.clear()
        self._msg_cache.clear()
        self._convo_cache.clear()

    # ---- retry helpers ----------------------------------------------------

    def _with_retry(self, func, *args, max_retries: int = 4, base_delay: float = 0.25, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # pragma: no cover - best effort
                last_exc = exc
                delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
                logging.warning("vector op failed (%s); retrying in %.2fs", exc, delay)
                time.sleep(delay)
        if last_exc:
            raise last_exc
        return None

    def persist(self) -> None:
        """Persist pending changes to the backing store."""
        try:
            self.client.persist()
            logging.info("Vector DB persisted")
        except AttributeError:
            logging.info("Vector client does not support explicit persistence")
        except Exception as exc:  # pragma: no cover - best effort
            logging.warning("Vector DB persist failed: %s", exc)

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
    ):
        """
        Adds documents to the vector database.

        :param documents: A list of documents to add.
        :param metadatas: A list of metadata dictionaries corresponding to the documents.
        :param ids: A list of unique IDs for the documents.
        """
        # Chroma requires a non-empty metadata dict for every document. Some
        # ingestion paths may supply missing or empty metadata, so normalise the
        # list here to guarantee valid placeholders are present. This protects
        # against `ValueError: Expected metadata to be a non-empty dict` without
        # modifying the upstream library.
        safe_docs: list[str] = []
        safe_metadatas: list[dict] = []
        safe_ids: list[str] = []
        safe_embeddings: list[list[float]] = []

        # Pad the metadata list to match documents length if needed
        if len(metadatas) < len(documents):
            metadatas = metadatas + [{}] * (len(documents) - len(metadatas))

        emb_iter = embeddings or [None] * len(documents)
        for doc, md, doc_id, emb in zip(documents, metadatas, ids, emb_iter):
            # Skip if ID already exists
            try:
                existing = self.collection.get(ids=[doc_id])
                if existing and existing.get("ids"):
                    logging.info("skip existing vector %s", doc_id)
                    continue
            except Exception:  # pragma: no cover - best effort
                pass

            # Similarity check to avoid near-duplicates
            try:
                if emb is not None:
                    res = self.collection.query(query_embeddings=[emb], n_results=1)
                else:
                    res = self.collection.query(query_texts=[doc], n_results=1)
                if res.get("ids") and res["ids"][0]:
                    if res.get("distances") and res["distances"][0][0] < 0.1:
                        logging.info("skip similar vector %s", doc_id)
                        continue
            except Exception:  # pragma: no cover - best effort
                pass

            safe_docs.append(doc)
            safe_ids.append(doc_id)
            if emb is not None:
                safe_embeddings.append(emb)
            if not isinstance(md, dict) or not md:
                safe_metadatas.append({"source": "unknown", "id": doc_id})
            else:
                cleaned = {k: v for k, v in md.items() if v}
                if cleaned:
                    safe_metadatas.append(cleaned)
                else:
                    safe_metadatas.append({"source": "unknown", "id": doc_id})

        if not safe_docs:
            return

        try:
            if embeddings:
                self._with_retry(
                    self.collection.add,
                    documents=safe_docs,
                    metadatas=safe_metadatas,
                    ids=safe_ids,
                    embeddings=safe_embeddings,
                )
            else:
                self._with_retry(
                    self.collection.add,
                    documents=safe_docs,
                    metadatas=safe_metadatas,
                    ids=safe_ids,
                )
        except ValueError as exc:
            logging.warning("Vector add failed (%s); retrying with placeholder metadata", exc)
            fallback = [{"source": "unknown", "id": i} for i in safe_ids]
            if embeddings:
                self._with_retry(
                    self.collection.add,
                    documents=safe_docs,
                    metadatas=fallback,
                    ids=safe_ids,
                    embeddings=safe_embeddings,
                )
            else:
                self._with_retry(
                    self.collection.add,
                    documents=safe_docs,
                    metadatas=fallback,
                    ids=safe_ids,
                )
        self._invalidate_cache()

    def add_documents_batched(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
        batch_size: int = 256,
    ) -> None:
        """Add many documents in batches with retry/backoff."""
        total = len(documents)
        if len(metadatas) < total:
            metadatas = metadatas + [{}] * (total - len(metadatas))
        emb_iter = None
        if embeddings is not None and len(embeddings) < total:
            embeddings = embeddings + [[]] * (total - len(embeddings))  # type: ignore
        emb_iter = embeddings

        for i in range(0, total, batch_size):
            j = min(i + batch_size, total)
            docs = documents[i:j]
            mds = metadatas[i:j]
            _ids = ids[i:j]
            embs = emb_iter[i:j] if emb_iter is not None else None
            self.add_documents(docs, mds, _ids, embs)
        try:
            self.persist()
        except Exception:
            pass

    async def aadd_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        await asyncio.to_thread(self.add_documents, documents, metadatas, ids, embeddings)

    def query(self, query_texts: list[str], n_results: int = 10, where: dict | None = None) -> dict:
        """
        Queries the vector database.

        :param query_texts: A list of query texts.
        :param n_results: The number of results to return.
        :param where: Optional metadata filter.
        :return: A dictionary containing the query results.
        """
        key = (tuple(query_texts), n_results, frozenset(where.items()) if where else None)
        if key in self._query_cache:
            return self._query_cache[key]
        result = self.collection.query(query_texts=query_texts, n_results=n_results, where=where)
        self._query_cache[key] = result
        return result

    def get_document_count(self) -> int:
        """
        Returns the number of documents in the vector database.

        :return: The number of documents.
        """
        return self.collection.count()

    def delete_documents(self, ids: list[str]):
        """
        Deletes documents from the vector database.

        :param ids: A list of document IDs to delete.
        """
        self.collection.delete(ids=ids)
        self._invalidate_cache()

    def add_messages(
        self,
        messages: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]],
    ) -> None:
        """Add chat messages to the vector database."""
        if len(metadatas) < len(messages):
            metadatas = metadatas + [{}] * (len(messages) - len(metadatas))
        safe_msgs: list[str] = []
        safe_ids: list[str] = []
        safe_md: list[dict] = []
        safe_embeddings: list[list[float]] = []
        for msg, md, mid, emb in zip(messages, metadatas, ids, embeddings):
            safe_msgs.append(msg)
            safe_ids.append(mid)
            if not isinstance(md, dict) or not md:
                safe_md.append({"message_id": mid, "visibility": "public"})
            else:
                if "visibility" not in md:
                    md["visibility"] = "public"
                safe_md.append(md)
            safe_embeddings.append(emb)
        self.msg_collection.add(
            documents=safe_msgs,
            metadatas=safe_md,
            ids=safe_ids,
            embeddings=safe_embeddings,
        )
        self._invalidate_cache()

    async def aadd_messages(
        self,
        messages: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]],
    ) -> None:
        await asyncio.to_thread(self.add_messages, messages, metadatas, ids, embeddings)

    def add_conversations(
        self,
        texts: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]],
    ) -> None:
        """Store conversation-level embeddings."""
        if len(metadatas) < len(texts):
            metadatas = metadatas + [{}] * (len(texts) - len(metadatas))
        self.convo_collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings,
        )
        self._invalidate_cache()

    async def aadd_conversations(
        self,
        texts: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]],
    ) -> None:
        await asyncio.to_thread(self.add_conversations, texts, metadatas, ids, embeddings)

    def query_messages(
        self,
        query_texts: list[str] | None = None,
        n_results: int = 10,
        where: dict | None = None,
        query_embeddings: list[list[float]] | None = None,
    ) -> dict:
        """Query stored chat messages."""
        key = (
            tuple(query_texts) if query_texts else None,
            n_results,
            frozenset(where.items()) if where else None,
            tuple(map(tuple, query_embeddings)) if query_embeddings else None,
        )
        if key in self._msg_cache:
            return self._msg_cache[key]
        result = self.msg_collection.query(
            query_texts=query_texts if query_embeddings is None else None,
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
        )
        self._msg_cache[key] = result
        return result

    def query_conversations(self, query_texts: list[str], n_results: int = 10, where: dict | None = None) -> dict:
        """Query stored conversation summaries."""
        key = (tuple(query_texts), n_results, frozenset(where.items()) if where else None)
        if key in self._convo_cache:
            return self._convo_cache[key]
        result = self.convo_collection.query(query_texts=query_texts, n_results=n_results, where=where)
        self._convo_cache[key] = result
        return result

    async def aquery(
        self, query_texts: list[str], n_results: int = 10, where: dict | None = None
    ) -> dict:
        return await asyncio.to_thread(self.query, query_texts, n_results, where)

    async def aquery_messages(
        self,
        query_texts: list[str] | None = None,
        n_results: int = 10,
        where: dict | None = None,
        query_embeddings: list[list[float]] | None = None,
    ) -> dict:
        return await asyncio.to_thread(
            self.query_messages, query_texts, n_results, where, query_embeddings
        )

    async def aquery_conversations(
        self, query_texts: list[str], n_results: int = 10, where: dict | None = None
    ) -> dict:
        return await asyncio.to_thread(self.query_conversations, query_texts, n_results, where)
