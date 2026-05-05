import csv
import re
from dataclasses import dataclass
from pathlib import Path

try:
    from .config import DATASET_TXT_PATH, LABELED_CSV_PATH
except ImportError:
    from config import DATASET_TXT_PATH, LABELED_CSV_PATH


LABEL_RE = re.compile(r"__label__([A-Z_]+)")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class TextSample:
    text: str
    toxic: int
    source: str
    labels: tuple[str, ...]


def normalize_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text or "").strip()


def load_labeled_csv(path: Path = LABELED_CSV_PATH) -> list[TextSample]:
    samples: list[TextSample] = []
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            text = normalize_text(row.get("comment", ""))
            if not text:
                continue
            toxic = 1 if float(row.get("toxic", 0.0)) >= 0.5 else 0
            labels = ("TOXIC",) if toxic else ("NORMAL",)
            samples.append(TextSample(text=text, toxic=toxic, source="labeled_csv", labels=labels))
    return samples


def parse_dataset_line(line: str) -> TextSample | None:
    line = line.strip()
    if not line:
        return None

    labels = tuple(LABEL_RE.findall(line))
    if not labels:
        return None

    text = normalize_text(LABEL_RE.sub("", line).replace(",", " "))
    if not text:
        return None

    toxic = 0 if labels == ("NORMAL",) else 1
    return TextSample(text=text, toxic=toxic, source="dataset_txt", labels=labels)


def load_dataset_txt(path: Path = DATASET_TXT_PATH) -> list[TextSample]:
    samples: list[TextSample] = []
    with path.open(encoding="utf-8") as file:
        for line in file:
            sample = parse_dataset_line(line)
            if sample is not None:
                samples.append(sample)
    return samples


def load_training_samples() -> list[TextSample]:
    return load_labeled_csv() + load_dataset_txt()


def split_fields(samples: list[TextSample]) -> tuple[list[str], list[int]]:
    return [sample.text for sample in samples], [sample.toxic for sample in samples]
