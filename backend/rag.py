import hashlib
import heapq
import math
import re
import threading
import tarfile
import urllib.request
from array import array
from pathlib import Path

from database import Database
from knowledge_parser import KnowledgeParser, SUPPORTED_SOURCE_TYPES


MODEL_NAME = "BAAI/bge-small-zh-v1.5"
MODEL_DIMENSION = 512
MODEL_ARCHIVE_URL = "https://storage.googleapis.com/qdrant-fastembed/fast-bge-small-zh-v1.5.tar.gz"
class RagService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.model_directory = database.data_directory / "models"
        self.manual_model_directory = self.model_directory / "manual-bge-small-zh-v1.5"
        self.downloaded_model_directory = self.model_directory / "fast-bge-small-zh-v1.5"
        self._model = None
        self._model_lock = threading.Lock()
        self._chunk_cache = None
        self._chunk_cache_lock = threading.Lock()
        self.parser = KnowledgeParser()

    def status(self) -> dict:
        manual_ready = self._manual_model_ready()
        downloaded_ready = self._downloaded_model_ready()
        return {
            "model": MODEL_NAME,
            "dimension": MODEL_DIMENSION,
            "ready": bool(self._model or manual_ready or downloaded_ready),
            "source": "manual" if manual_ready else "download" if downloaded_ready else None,
            "documents": len(self.database.list_documents()),
            "collections": len(self.database.list_collections()),
            "supported_types": sorted(SUPPORTED_SOURCE_TYPES),
            "ocr": self.parser.ocr_status(),
        }

    def download_model(self) -> dict:
        self.model_directory.mkdir(parents=True, exist_ok=True)
        if not self._downloaded_model_ready():
            self._download_model_archive()
        self._load_model()
        self.index_pending_chunks()
        return self.status()

    def reload_model(self) -> dict:
        with self._model_lock:
            self._model = None
        archive = self.model_directory / "fast-bge-small-zh-v1.5.tar.gz"
        if archive.is_file() and not self._downloaded_model_ready():
            self._extract_model_archive(archive)
        if not self._manual_model_ready() and not self._downloaded_model_ready():
            raise RuntimeError("未找到可用的本地向量模型")
        self._load_model()
        self.index_pending_chunks()
        return self.status()

    def import_document(
        self,
        title: str,
        source_type: str,
        data: bytes,
        collection_id: str = "default",
        source_path: str | None = None,
        source_modified_at: str | None = None,
    ) -> dict:
        normalized_type = source_type.lower().lstrip(".")
        if normalized_type not in SUPPORTED_SOURCE_TYPES:
            raise ValueError("不支持该资料格式")
        chunks, metadata = self.parser.parse(data, normalized_type)
        if not chunks:
            raise ValueError("文件中没有可索引的文本")

        document, import_status = self.database.upsert_document(
            title=title,
            source_type=normalized_type,
            chunks=chunks,
            collection_id=collection_id,
            source_path=source_path,
            source_hash=hashlib.sha256(data).hexdigest(),
            source_modified_at=source_modified_at,
            metadata=metadata,
        )
        self.invalidate_cache()
        model = self._load_model()
        if model and import_status != "unchanged":
            self._index_document(document["id"], model)
            document = self.database.get_document(document["id"])
        document["import_status"] = import_status
        return document

    def delete_document(self, document_id: str) -> bool:
        deleted = self.database.delete_document(document_id)
        if deleted:
            self.invalidate_cache()
        return deleted

    def invalidate_cache(self) -> None:
        with self._chunk_cache_lock:
            self._chunk_cache = None

    def index_pending_chunks(self) -> None:
        model = self._load_model()
        if not model:
            return
        for document in self.database.list_documents():
            if document["indexed_count"] < document["chunk_count"]:
                self._index_document(document["id"], model)

    def retrieve(self, query: str, limit: int = 4) -> list[dict]:
        if not query.strip():
            return []

        query_terms = self._keyword_terms(query)
        fts_results = self.database.search_knowledge_fts(query, limit=max(limit * 6, 24))
        fts_scores = {
            chunk["id"]: 1.0 / math.sqrt(index + 1)
            for index, chunk in enumerate(fts_results)
        }
        model = self._load_model()
        query_embedding = self._embed_texts(model, [query])[0] if model else None
        chunks = self._get_cached_chunks() if query_embedding is not None else fts_results
        if not chunks:
            return []

        ranked = []
        for chunk in chunks:
            keyword_score = self._keyword_score(query_terms, chunk["content"])
            fts_score = fts_scores.get(chunk["id"], 0.0)
            semantic_score = None
            if query_embedding is not None and chunk["embedding"]:
                stored_embedding = array("f")
                stored_embedding.frombytes(chunk["embedding"])
                if len(stored_embedding) == len(query_embedding):
                    semantic_score = self._cosine(query_embedding, stored_embedding)

            if semantic_score is None:
                score = fts_score * 0.78 + keyword_score * 0.22
            else:
                normalized_semantic = max(0.0, min(1.0, (semantic_score + 1.0) / 2.0))
                score = normalized_semantic * 0.64 + fts_score * 0.26 + keyword_score * 0.10

            if score > 0.05:
                ranked.append((score, chunk))

        results = []
        for score, chunk in heapq.nlargest(limit, ranked, key=lambda item: item[0]):
            results.append({
                "document_id": chunk["document_id"],
                "title": chunk["title"],
                "position": chunk["position"],
                "content": chunk["content"],
                "locator": chunk.get("locator", {}),
                "locator_text": chunk.get("locator_text", ""),
                "collection_id": chunk.get("collection_id"),
                "collection_name": chunk.get("collection_name"),
                "score": round(score, 4),
            })
        return results

    def _get_cached_chunks(self) -> list[dict]:
        with self._chunk_cache_lock:
            if self._chunk_cache is None:
                self._chunk_cache = self.database.list_knowledge_chunks()
            return self._chunk_cache

    def _load_model(self):
        if self._model is not None:
            return self._model
        local_model_directory = self._local_model_directory()
        if not local_model_directory:
            return None

        with self._model_lock:
            if self._model is not None:
                return self._model
            from fastembed import TextEmbedding

            self._model = TextEmbedding(
                model_name=MODEL_NAME,
                specific_model_path=str(local_model_directory),
                local_files_only=True,
            )
        return self._model

    def _manual_model_ready(self) -> bool:
        return self._model_files_ready(self.manual_model_directory)

    def _downloaded_model_ready(self) -> bool:
        return self._model_files_ready(self.downloaded_model_directory)

    def _local_model_directory(self) -> Path | None:
        if self._manual_model_ready():
            return self.manual_model_directory
        if self._downloaded_model_ready():
            return self.downloaded_model_directory
        return None

    @staticmethod
    def _model_files_ready(directory: Path) -> bool:
        return (
            (directory / "model_optimized.onnx").is_file()
            and (directory / "tokenizer.json").is_file()
        )

    def _download_model_archive(self) -> None:
        archive = self.model_directory / "fast-bge-small-zh-v1.5.tar.gz"
        partial = Path(f"{archive}.part")
        request = urllib.request.Request(
            MODEL_ARCHIVE_URL,
            headers={"User-Agent": "Kaltsit/1.0"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            with partial.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        if partial.stat().st_size < 10 * 1024 * 1024:
            raise RuntimeError("向量模型归档不完整")
        partial.replace(archive)

        self._extract_model_archive(archive)

    def _extract_model_archive(self, archive: Path) -> None:
        root = self.model_directory.resolve()
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle.getmembers():
                target = (root / member.name).resolve()
                if target != root and root not in target.parents:
                    raise RuntimeError("向量模型归档包含非法路径")
            bundle.extractall(root, filter="data")
        if not self._downloaded_model_ready():
            raise RuntimeError("向量模型归档缺少必要文件")

    def _index_document(self, document_id: str, model) -> None:
        chunks = self.database.get_document_chunks(document_id)
        pending = [chunk for chunk in chunks if not chunk["embedding"]]
        if not pending:
            return
        vectors = self._embed_texts(model, [chunk["content"] for chunk in pending])
        updates = []
        for chunk, vector in zip(pending, vectors, strict=True):
            updates.append((chunk["id"], vector.tobytes(), len(vector)))
        self.database.update_chunk_embeddings(updates)
        self.invalidate_cache()

    @staticmethod
    def _embed_texts(model, texts: list[str]) -> list[array]:
        vectors = []
        for embedding in model.embed(texts, batch_size=16):
            vector = array("f", (float(value) for value in embedding))
            vectors.append(vector)
        return vectors

    @staticmethod
    def _keyword_terms(text: str) -> set[str]:
        lowered = text.lower()
        words = set(re.findall(r"[a-z0-9_]{2,}", lowered))
        chinese_runs = re.findall(r"[\u4e00-\u9fff]+", lowered)
        for run in chinese_runs:
            words.update(run)
            words.update(run[index:index + 2] for index in range(len(run) - 1))
        return words

    @classmethod
    def _keyword_score(cls, query_terms: set[str], content: str) -> float:
        if not query_terms:
            return 0.0
        content_terms = cls._keyword_terms(content)
        matched = query_terms & content_terms
        return len(matched) / math.sqrt(len(query_terms) * max(1, len(content_terms)))

    @staticmethod
    def _cosine(left: array, right: array) -> float:
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if not left_norm or not right_norm:
            return 0.0
        return dot / (left_norm * right_norm)
