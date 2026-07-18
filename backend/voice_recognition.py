import audioop
import os
import tarfile
import threading
import urllib.request
import wave
from array import array
from io import BytesIO
from pathlib import Path

from database import Database


MODEL_NAME = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
MODEL_ARCHIVE_URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{MODEL_NAME}.tar.bz2"
MIN_ARCHIVE_SIZE = 140 * 1024 * 1024


class VoiceRecognitionService:
    def __init__(self, database: Database) -> None:
        self.model_directory = database.data_directory / "models"
        self.downloaded_directory = self.model_directory / MODEL_NAME
        self.manual_directory = self.model_directory / "manual-sensevoice"
        self.archive_path = self.model_directory / f"{MODEL_NAME}.tar.bz2"
        self._recognizer = None
        self._recognizer_language = None
        self._lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def status(self) -> dict:
        source = self._model_source()
        return {
            "model": "SenseVoice Small INT8",
            "ready": source is not None,
            "loaded": self._recognizer is not None,
            "source": "manual" if source == self.manual_directory else "download" if source else None,
            "languages": ["auto", "zh", "en", "ja", "ko", "yue"],
            "sample_rate": 16000,
            "archive_ready": self.archive_path.is_file() and self.archive_path.stat().st_size >= MIN_ARCHIVE_SIZE,
        }

    def download_model(self) -> dict:
        self.model_directory.mkdir(parents=True, exist_ok=True)
        if not self.archive_path.is_file() or self.archive_path.stat().st_size < MIN_ARCHIVE_SIZE:
            partial = Path(f"{self.archive_path}.part")
            request = urllib.request.Request(MODEL_ARCHIVE_URL, headers={"User-Agent": "Kaltsit/1.0"})
            with urllib.request.urlopen(request, timeout=90) as response, partial.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if partial.stat().st_size < MIN_ARCHIVE_SIZE:
                raise RuntimeError("语音识别模型归档不完整")
            partial.replace(self.archive_path)
        return self.reload_model()

    def reload_model(self) -> dict:
        with self._lock:
            self._recognizer = None
            self._recognizer_language = None
        if self.archive_path.is_file() and not self._model_files_ready(self.downloaded_directory):
            self._extract_archive()
        if not self._model_source():
            raise RuntimeError("未找到可用的 SenseVoice 模型")
        self._load_recognizer()
        return self.status()

    def transcribe(self, wav_data: bytes, language: str = "auto") -> dict:
        if len(wav_data) > 12 * 1024 * 1024:
            raise ValueError("录音不能超过 12 MB")
        samples, sample_rate, duration = self._decode_wav(wav_data)
        if duration < 0.18:
            raise ValueError("录音时间过短")
        if duration > 60:
            raise ValueError("单次录音不能超过 60 秒")

        with self._inference_lock:
            recognizer = self._load_recognizer(language)
            stream = recognizer.create_stream()
            stream.accept_waveform(sample_rate, samples)
            recognizer.decode_stream(stream)
            result = stream.result
        return {
            "text": (result.text or "").strip(),
            "language": getattr(result, "lang", ""),
            "emotion": getattr(result, "emotion", ""),
            "event": getattr(result, "event", ""),
            "duration": round(duration, 3),
        }

    def _load_recognizer(self, language: str = "auto"):
        if language not in {"auto", "zh", "en", "ja", "ko", "yue"}:
            language = "auto"
        with self._lock:
            if self._recognizer is not None and self._recognizer_language == language:
                return self._recognizer
            source = self._model_source()
            if not source:
                raise RuntimeError("本地语音识别模型尚未安装")
            import sherpa_onnx

            self._recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(source / "model.int8.onnx"),
                tokens=str(source / "tokens.txt"),
                num_threads=max(1, min(os.cpu_count() or 2, 4)),
                language=language,
                use_itn=True,
                debug=False,
            )
            self._recognizer_language = language
            return self._recognizer

    def _model_source(self) -> Path | None:
        if self._model_files_ready(self.manual_directory):
            return self.manual_directory
        if self._model_files_ready(self.downloaded_directory):
            return self.downloaded_directory
        return None

    @staticmethod
    def _model_files_ready(directory: Path) -> bool:
        return (directory / "model.int8.onnx").is_file() and (directory / "tokens.txt").is_file()

    def _extract_archive(self) -> None:
        root = self.model_directory.resolve()
        with tarfile.open(self.archive_path, "r:bz2") as bundle:
            for member in bundle.getmembers():
                target = (root / member.name).resolve()
                if target != root and root not in target.parents:
                    raise RuntimeError("语音识别模型归档包含非法路径")
            bundle.extractall(root, filter="data")
        if not self._model_files_ready(self.downloaded_directory):
            raise RuntimeError("语音识别模型归档缺少必要文件")

    @staticmethod
    def _decode_wav(data: bytes) -> tuple[array, int, float]:
        try:
            with wave.open(BytesIO(data), "rb") as source:
                channels = source.getnchannels()
                sample_width = source.getsampwidth()
                sample_rate = source.getframerate()
                frame_count = source.getnframes()
                frames = source.readframes(frame_count)
        except (wave.Error, EOFError) as error:
            raise ValueError("录音不是有效的 PCM WAV") from error

        if channels not in (1, 2) or sample_width not in (1, 2, 3, 4) or sample_rate < 8000:
            raise ValueError("录音格式不受支持")
        if channels == 2:
            frames = audioop.tomono(frames, sample_width, 0.5, 0.5)
        if sample_width != 2:
            frames = audioop.lin2lin(frames, sample_width, 2)
        if sample_rate != 16000:
            frames, _ = audioop.ratecv(frames, 2, 1, sample_rate, 16000, None)
            sample_rate = 16000

        pcm = array("h")
        pcm.frombytes(frames)
        samples = array("f", (value / 32768.0 for value in pcm))
        duration = len(samples) / sample_rate if sample_rate else 0.0
        return samples, sample_rate, duration
