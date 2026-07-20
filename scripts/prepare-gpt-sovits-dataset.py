import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = ROOT / "assets" / "voice" / "凯尔希思衡托"
WORD_TABLE = (
    ROOT
    / "reference"
    / "ArknightsGameData-master"
    / "ArknightsGameData-master"
    / "zh_CN"
    / "gamedata"
    / "excel"
    / "charword_table.json"
)
OUTPUT_DIRECTORY = ROOT / ".build-tools" / "kaltsit-sovits" / "dataset"
WAV_DIRECTORY = OUTPUT_DIRECTORY / "wav"
LABEL_PATH = OUTPUT_DIRECTORY / "kaltsit2.list"
CHARACTER_ID = "char_1052_kalts2"
SPEAKER = "kaltsit2"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")


def get_duration(path: Path) -> float:
    result = run([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    return float(result.stdout.strip())


def get_silence_midpoints(path: Path) -> list[float]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            "silencedetect=noise=-40dB:d=0.22",
            "-f",
            "null",
            "-",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    starts = [float(value) for value in re.findall(r"silence_start: ([0-9.]+)", result.stderr)]
    ends = [float(value) for value in re.findall(r"silence_end: ([0-9.]+)", result.stderr)]
    return [(start + end) / 2 for start, end in zip(starts, ends)]


def normalize_text(text: str) -> str:
    return (
        text.replace("Dr.{@nickname}", "博士")
        .replace("{@nickname}", "博士")
        .replace("......", "……")
        .strip()
    )


def split_sentences(text: str) -> list[str]:
    if len(re.sub(r"\W", "", text)) <= 26:
        return [text]
    clauses = [
        part.strip()
        for part in re.split(r"(?<=[。！？!?；;，,])", text)
        if part.strip()
    ]
    groups = []
    current = ""
    for clause in clauses:
        current_length = len(re.sub(r"\W", "", current))
        clause_length = len(re.sub(r"\W", "", clause))
        if current and current_length >= 8 and current_length + clause_length > 24:
            groups.append(current)
            current = clause
        else:
            current += clause
    if current:
        if groups and len(re.sub(r"\W", "", current)) < 8:
            groups[-1] += current
        else:
            groups.append(current)
    return groups or [text]


def select_boundaries(sentences: list[str], duration: float, candidates: list[float]) -> list[float]:
    if len(sentences) < 2:
        return []
    weights = [max(1, len(re.sub(r"\W", "", sentence))) for sentence in sentences]
    total = sum(weights)
    targets = [duration * sum(weights[:index]) / total for index in range(1, len(weights))]
    available = [point for point in candidates if 0.8 <= point <= duration - 0.8]
    boundaries = []
    for index, target in enumerate(targets):
        remaining = len(targets) - index - 1
        valid = [
            point
            for point in available
            if point >= (boundaries[-1] + 0.8 if boundaries else 0.8)
            and point <= duration - 0.8 * (remaining + 1)
        ]
        if not valid:
            return []
        selected = min(valid, key=lambda point: abs(point - target))
        boundaries.append(selected)
        available.remove(selected)
    return boundaries


def write_segment(source: Path, destination: Path, start: float, end: float) -> None:
    run([
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{end - start:.3f}",
        "-i",
        str(source),
        "-ar",
        "32000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ])


def load_voice_lines() -> dict[str, str]:
    data = json.loads(WORD_TABLE.read_text(encoding="utf-8"))
    entries = (
        entry
        for entry in data["charWords"].values()
        if entry.get("charId") == CHARACTER_ID
    )
    return {
        entry["voiceTitle"]: normalize_text(entry["voiceText"])
        for entry in entries
    }


def main() -> None:
    if not SOURCE_DIRECTORY.is_dir() or not WORD_TABLE.is_file():
        raise FileNotFoundError("语音目录或官方台词表不存在")

    WAV_DIRECTORY.mkdir(parents=True, exist_ok=True)
    voice_lines = load_voice_lines()
    labels = []
    source_seconds = 0.0
    output_seconds = 0.0

    for source_index, source in enumerate(sorted(SOURCE_DIRECTORY.glob("*.wav")), start=1):
        text = voice_lines.get(source.stem)
        if not text:
            raise KeyError(f"未找到台词标注: {source.name}")
        duration = get_duration(source)
        source_seconds += duration
        sentences = split_sentences(text)
        boundaries = select_boundaries(sentences, duration, get_silence_midpoints(source))
        if len(boundaries) != len(sentences) - 1:
            sentences = [text]
            boundaries = []

        points = [0.0, *boundaries, duration]
        for segment_index, sentence in enumerate(sentences, start=1):
            destination = WAV_DIRECTORY / f"kaltsit2_{source_index:03d}_{segment_index:02d}.wav"
            write_segment(source, destination, points[segment_index - 1], points[segment_index])
            segment_duration = get_duration(destination)
            output_seconds += segment_duration
            labels.append(f"{destination.resolve()}|{SPEAKER}|zh|{sentence}")

    LABEL_PATH.write_text("\n".join(labels) + "\n", encoding="utf-8")
    print(f"source_files={source_index}")
    print(f"segments={len(labels)}")
    print(f"source_seconds={source_seconds:.2f}")
    print(f"output_seconds={output_seconds:.2f}")
    print(f"labels={LABEL_PATH}")


if __name__ == "__main__":
    main()
