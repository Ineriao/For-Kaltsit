import argparse
import json
import os
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
GPT_SOVITS_ROOT = ROOT / ".build-tools" / "GPT-SoVITS"
PYTHON = ROOT / ".build-tools" / "gpt-sovits-venv" / "Scripts" / "python.exe"
DATASET_ROOT = ROOT / ".build-tools" / "kaltsit-sovits" / "dataset"
LABEL_PATH = DATASET_ROOT / "kaltsit2.list"
WAV_DIRECTORY = DATASET_ROOT / "wav"
TRAINING_ROOT = ROOT / ".build-tools" / "kaltsit-sovits" / "training"
EXPERIMENT_ROOT = TRAINING_ROOT / "kaltsit2-v2"
CONFIG_ROOT = TRAINING_ROOT / "config"
WEIGHT_ROOT = TRAINING_ROOT / "weights"
PRETRAINED_ROOT = GPT_SOVITS_ROOT / "GPT_SoVITS" / "pretrained_models"
BERT_ROOT = PRETRAINED_ROOT / "chinese-roberta-wwm-ext-large"
HUBERT_ROOT = PRETRAINED_ROOT / "chinese-hubert-base"
PRETRAINED_V2_ROOT = PRETRAINED_ROOT / "gsv-v2final-pretrained"
PRETRAINED_S1 = PRETRAINED_V2_ROOT / "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"
PRETRAINED_S2D = PRETRAINED_V2_ROOT / "s2D2333k.pth"
PRETRAINED_S2G = PRETRAINED_V2_ROOT / "s2G2333k.pth"
G2PW_ROOT = GPT_SOVITS_ROOT / "GPT_SoVITS" / "text" / "G2PWModel"
EXPERIMENT_NAME = "kaltsit2-v2"


def run(command: list[str], environment: dict[str, str] | None = None) -> None:
    subprocess.run(
        command,
        cwd=GPT_SOVITS_ROOT,
        env=environment,
        check=True,
    )


def require_paths() -> None:
    required = [
        PYTHON,
        LABEL_PATH,
        WAV_DIRECTORY,
        BERT_ROOT / "pytorch_model.bin",
        HUBERT_ROOT / "pytorch_model.bin",
        PRETRAINED_S1,
        PRETRAINED_S2D,
        PRETRAINED_S2G,
        G2PW_ROOT,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("缺少训练依赖:\n" + "\n".join(missing))


def training_environment() -> dict[str, str]:
    environment = os.environ.copy()
    python_paths = [
        GPT_SOVITS_ROOT,
        GPT_SOVITS_ROOT / "GPT_SoVITS",
        GPT_SOVITS_ROOT / "GPT_SoVITS" / "BigVGAN",
        GPT_SOVITS_ROOT / "tools",
        GPT_SOVITS_ROOT / "tools" / "asr",
        GPT_SOVITS_ROOT / "tools" / "uvr5",
    ]
    if environment.get("PYTHONPATH"):
        python_paths.append(Path(environment["PYTHONPATH"]))
    environment.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONPATH": os.pathsep.join(str(path) for path in python_paths),
            "version": "v2",
            "inp_text": str(LABEL_PATH),
            "inp_wav_dir": str(WAV_DIRECTORY),
            "exp_name": EXPERIMENT_NAME,
            "opt_dir": str(EXPERIMENT_ROOT),
            "i_part": "0",
            "all_parts": "1",
            "_CUDA_VISIBLE_DEVICES": "0",
            "is_half": "True",
            "bert_pretrained_dir": str(BERT_ROOT),
            "cnhubert_base_dir": str(HUBERT_ROOT),
            "pretrained_s2G": str(PRETRAINED_S2G),
            "s2config_path": str(GPT_SOVITS_ROOT / "GPT_SoVITS" / "configs" / "s2.json"),
        }
    )
    return environment


def merge_text_features() -> None:
    source = EXPERIMENT_ROOT / "2-name2text-0.txt"
    destination = EXPERIMENT_ROOT / "2-name2text.txt"
    content = source.read_text(encoding="utf-8").strip()
    destination.write_text(content + "\n", encoding="utf-8")


def merge_semantic_features() -> None:
    source = EXPERIMENT_ROOT / "6-name2semantic-0.tsv"
    destination = EXPERIMENT_ROOT / "6-name2semantic.tsv"
    content = source.read_text(encoding="utf-8").strip()
    destination.write_text("item_name\tsemantic_audio\n" + content + "\n", encoding="utf-8")


def validate_features() -> None:
    expected = sum(1 for line in LABEL_PATH.read_text(encoding="utf-8").splitlines() if line.strip())
    text_count = sum(
        1
        for line in (EXPERIMENT_ROOT / "2-name2text.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    semantic_count = sum(
        1
        for line in (EXPERIMENT_ROOT / "6-name2semantic.tsv").read_text(encoding="utf-8").splitlines()[1:]
        if line.strip()
    )
    if text_count != expected or semantic_count != expected:
        raise RuntimeError(
            f"特征数量不完整: labels={expected}, text={text_count}, semantic={semantic_count}"
        )


def preprocess() -> None:
    environment = training_environment()
    scripts = GPT_SOVITS_ROOT / "GPT_SoVITS" / "prepare_datasets"
    run([str(PYTHON), "-s", str(scripts / "1-get-text.py")], environment)
    merge_text_features()
    run([str(PYTHON), "-s", str(scripts / "2-get-hubert-wav32k.py")], environment)
    run([str(PYTHON), "-s", str(scripts / "3-get-semantic.py")], environment)
    merge_semantic_features()
    validate_features()


def write_sovits_config() -> Path:
    source = GPT_SOVITS_ROOT / "GPT_SoVITS" / "configs" / "s2.json"
    config = json.loads(source.read_text(encoding="utf-8"))
    log_directory = EXPERIMENT_ROOT / "logs_s2_v2"
    weight_directory = WEIGHT_ROOT / "sovits"
    log_directory.mkdir(parents=True, exist_ok=True)
    weight_directory.mkdir(parents=True, exist_ok=True)
    config["train"].update(
        {
            "batch_size": 1,
            "epochs": 8,
            "text_low_lr_rate": 0.4,
            "pretrained_s2G": str(PRETRAINED_S2G),
            "pretrained_s2D": str(PRETRAINED_S2D),
            "if_save_latest": 0,
            "if_save_every_weights": True,
            "save_every_epoch": 4,
            "gpu_numbers": "0",
            "grad_ckpt": True,
        }
    )
    config["model"]["version"] = "v2"
    config["data"]["exp_dir"] = str(EXPERIMENT_ROOT)
    config["s2_ckpt_dir"] = str(EXPERIMENT_ROOT)
    config["save_weight_dir"] = str(weight_directory)
    config["name"] = EXPERIMENT_NAME
    config["version"] = "v2"
    destination = CONFIG_ROOT / "s2-kaltsit2-v2.json"
    destination.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def write_gpt_config() -> Path:
    source = GPT_SOVITS_ROOT / "GPT_SoVITS" / "configs" / "s1longer-v2.yaml"
    config = yaml.safe_load(source.read_text(encoding="utf-8"))
    output_directory = EXPERIMENT_ROOT / "logs_s1_v2"
    weight_directory = WEIGHT_ROOT / "gpt"
    output_directory.mkdir(parents=True, exist_ok=True)
    weight_directory.mkdir(parents=True, exist_ok=True)
    config["train"].update(
        {
            "batch_size": 2,
            "epochs": 12,
            "save_every_n_epoch": 4,
            "if_save_latest": False,
            "if_save_every_weights": True,
            "if_dpo": False,
            "half_weights_save_dir": str(weight_directory),
            "exp_name": EXPERIMENT_NAME,
        }
    )
    config["data"]["num_workers"] = 2
    config["pretrained_s1"] = str(PRETRAINED_S1)
    config["train_semantic_path"] = str(EXPERIMENT_ROOT / "6-name2semantic.tsv")
    config["train_phoneme_path"] = str(EXPERIMENT_ROOT / "2-name2text.txt")
    config["output_dir"] = str(output_directory)
    destination = CONFIG_ROOT / "s1-kaltsit2-v2.yaml"
    destination.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return destination


def train_sovits() -> None:
    config = write_sovits_config()
    run(
        [str(PYTHON), "-s", "GPT_SoVITS/s2_train.py", "--config", str(config)],
        training_environment(),
    )


def train_gpt() -> None:
    config = write_gpt_config()
    environment = training_environment()
    environment["hz"] = "25hz"
    run([str(PYTHON), "-s", "GPT_SoVITS/s1_train.py", "--config_file", str(config)], environment)


def main() -> None:
    parser = argparse.ArgumentParser(description="训练凯尔希思衡托 GPT-SoVITS v2 音色")
    parser.add_argument(
        "--stage",
        choices=("all", "preprocess", "sovits", "gpt"),
        default="all",
    )
    args = parser.parse_args()

    require_paths()
    CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    if args.stage in {"all", "preprocess"}:
        preprocess()
    if args.stage in {"all", "sovits"}:
        validate_features()
        train_sovits()
    if args.stage in {"all", "gpt"}:
        validate_features()
        train_gpt()


if __name__ == "__main__":
    main()
