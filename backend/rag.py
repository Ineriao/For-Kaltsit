import json
import math
import re
import threading
import tarfile
import urllib.request
from array import array
from pathlib import Path

from database import Database


MODEL_NAME = "BAAI/bge-small-zh-v1.5"
MODEL_DIMENSION = 512
MODEL_ARCHIVE_URL = "https://storage.googleapis.com/qdrant-fastembed/fast-bge-small-zh-v1.5.tar.gz"
SUPPORTED_SOURCE_TYPES = {"txt", "md", "json"}


class RagService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.model_directory = database.data_directory / "models"
        self.manual_model_directory = self.model_directory / "manual-bge-small-zh-v1.5"
        self.downloaded_model_directory = self.model_directory / "fast-bge-small-zh-v1.5"
        self.ready_marker = self.model_directory / ".bge-small-zh-v1.5-ready"
        self._model = None
        self._model_lock = threading.Lock()

    def status(self) -> dict:
        manual_ready = self._manual_model_ready()
        downloaded_ready = self._downloaded_model_ready()
        return {
            "model": MODEL_NAME,
            "dimension": MODEL_DIMENSION,
            "ready": bool(self._model or manual_ready or downloaded_ready),
            "source": "manual" if manual_ready else "download" if downloaded_ready else None,
            "documents": len(self.database.list_documents()),
        }

    def download_model(self) -> dict:
        self.model_directory.mkdir(parents=True, exist_ok=True)
        if not self._downloaded_model_ready():
            self._download_model_archive()
        self._load_model(allow_download=False)
        self.ready_marker.touch(exist_ok=True)
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
        self._load_model(allow_download=False)
        self.index_pending_chunks()
        return self.status()

    def import_document(self, title: str, source_type: str, content: str) -> dict:
        normalized_type = source_type.lower().lstrip(".")
        if normalized_type not in SUPPORTED_SOURCE_TYPES:
            raise ValueError("仅支持 txt、md 和 json 文件")
        normalized_content = self._normalize_document(content, normalized_type)
        chunks = self._split_chunks(normalized_content)
        if not chunks:
            raise ValueError("文件中没有可索引的文本")

        document = self.database.create_document(title, normalized_type, chunks)
        model = self._load_model(allow_download=False)
        if model:
            self._index_document(document["id"], model)
            document = self.database.get_document(document["id"])
        return document

    def delete_document(self, document_id: str) -> bool:
        return self.database.delete_document(document_id)

    def index_pending_chunks(self) -> None:
        model = self._load_model(allow_download=False)
        if not model:
            return
        for document in self.database.list_documents():
            if document["indexed_count"] < document["chunk_count"]:
                self._index_document(document["id"], model)

    def retrieve(self, query: str, limit: int = 4) -> list[dict]:
        chunks = self.database.list_knowledge_chunks()
        if not chunks or not query.strip():
            return []

        query_terms = self._keyword_terms(query)
        query_embedding = None
        model = self._load_model(allow_download=False)
        if model:
            query_embedding = self._embed_texts(model, [query])[0]

        ranked = []
        for chunk in chunks:
            keyword_score = self._keyword_score(query_terms, chunk["content"])
            semantic_score = None
            if query_embedding is not None and chunk["embedding"]:
                stored_embedding = array("f")
                stored_embedding.frombytes(chunk["embedding"])
                if len(stored_embedding) == len(query_embedding):
                    semantic_score = self._cosine(query_embedding, stored_embedding)

            if semantic_score is None:
                score = keyword_score
            else:
                normalized_semantic = max(0.0, min(1.0, (semantic_score + 1.0) / 2.0))
                score = normalized_semantic * 0.72 + keyword_score * 0.28

            if score > 0.05:
                ranked.append((score, chunk))

        ranked.sort(key=lambda item: item[0], reverse=True)
        results = []
        for score, chunk in ranked[:limit]:
            results.append({
                "document_id": chunk["document_id"],
                "title": chunk["title"],
                "position": chunk["position"],
                "content": chunk["content"],
                "score": round(score, 4),
            })
        return results

    def _load_model(self, allow_download: bool):
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

    @staticmethod
    def _embed_texts(model, texts: list[str]) -> list[array]:
        vectors = []
        for embedding in model.embed(texts, batch_size=16):
            vector = array("f", (float(value) for value in embedding))
            vectors.append(vector)
        return vectors

    @staticmethod
    def _normalize_document(content: str, source_type: str) -> str:
        if source_type != "json":
            return content.replace("\r\n", "\n").replace("\r", "\n")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError("JSON 文件格式无效") from error

        lines = []

        def walk(value, path: str = "") -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    walk(child, f"{path}.{key}" if path else str(key))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, f"{path}[{index}]")
            elif value is not None:
                lines.append(f"{path}: {value}" if path else str(value))

        walk(parsed)
        return "\n".join(lines)

    @staticmethod
    def _split_chunks(content: str, target_size: int = 420, overlap: int = 60) -> list[str]:
        normalized = re.sub(r"[ \t]+", " ", content)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
        if not normalized:
            return []

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
        chunks = []
        buffer = ""
        for paragraph in paragraphs:
            pieces = [paragraph[index:index + target_size] for index in range(0, len(paragraph), target_size)]
            for piece in pieces:
                candidate = f"{buffer}\n\n{piece}".strip() if buffer else piece
                if len(candidate) <= target_size:
                    buffer = candidate
                    continue
                if buffer:
                    chunks.append(buffer)
                    prefix = buffer[-overlap:]
                    buffer = f"{prefix}\n{piece}".strip()
                else:
                    chunks.append(piece)
        if buffer:
            chunks.append(buffer)
        return [chunk for chunk in chunks if len(chunk.strip()) >= 2]

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
