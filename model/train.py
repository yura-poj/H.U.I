import json
import random
import re
from collections import Counter

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import MultiLabelBinarizer

try:
    from .config import ARTIFACTS_DIR, MODEL_PATH, RANDOM_SEED, SIGNAL_LABELS, TEST_SIZE, TOXICITY_THRESHOLD
    from .dataset import load_dataset_txt, load_training_samples, split_fields
except ImportError:
    from config import ARTIFACTS_DIR, MODEL_PATH, RANDOM_SEED, SIGNAL_LABELS, TEST_SIZE, TOXICITY_THRESHOLD
    from dataset import load_dataset_txt, load_training_samples, split_fields


COHERENCE_SAMPLE_LIMIT = 60_000
COHERENCE_NEGATIVE_TOKENS = (
    "а",
    "ва",
    "вао",
    "т",
    "ы",
    "овд",
    "тлфдыват",
    "рпло",
    "шва",
    "кц",
    "длы",
    "мва",
    "жтр",
)
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")


def build_features() -> FeatureUnion:
    return FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=30_000,
                    sublinear_tf=True,
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=2,
                    max_features=30_000,
                    sublinear_tf=True,
                ),
            ),
        ]
    )


def build_toxicity_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("features", build_features()),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1_000,
                    random_state=RANDOM_SEED,
                    solver="liblinear",
                ),
            ),
        ]
    )


def build_signal_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("features", build_features()),
            (
                "classifier",
                OneVsRestClassifier(
                    LogisticRegression(
                        class_weight="balanced",
                        max_iter=1_000,
                        random_state=RANDOM_SEED,
                        solver="liblinear",
                    )
                ),
            ),
        ]
    )


def build_coherence_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("features", build_features()),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1_000,
                    random_state=RANDOM_SEED,
                    solver="liblinear",
                ),
            ),
        ]
    )


def evaluate_toxicity(model: Pipeline, texts: list[str], labels: list[int]) -> dict[str, object]:
    predictions = model.predict(texts)
    return {
        "accuracy": accuracy_score(labels, predictions),
        "precision": precision_score(labels, predictions, zero_division=0),
        "recall": recall_score(labels, predictions, zero_division=0),
        "f1": f1_score(labels, predictions, zero_division=0),
        "confusion_matrix": confusion_matrix(labels, predictions).tolist(),
        "classification_report": classification_report(labels, predictions, target_names=["normal", "toxic"], zero_division=0),
    }


def make_gibberish_negative(rng: random.Random) -> str:
    token_count = rng.randint(5, 12)
    tokens = [rng.choice(COHERENCE_NEGATIVE_TOKENS) for _ in range(token_count)]
    if rng.random() < 0.45:
        tokens.insert(0, rng.choice(("хуй", "пизд", "сука")))
    return " ".join(tokens)


def make_shuffled_negative(text: str, rng: random.Random) -> str | None:
    words = WORD_RE.findall(text.lower())
    if len(words) < 6:
        return None
    words = words[: min(len(words), 18)]
    rng.shuffle(words)
    return " ".join(words)


def build_coherence_dataset(texts: list[str]) -> tuple[list[str], list[int]]:
    rng = random.Random(RANDOM_SEED)
    positives = list(texts)
    rng.shuffle(positives)
    positives = positives[:COHERENCE_SAMPLE_LIMIT]

    negatives: list[str] = []
    for text in positives:
        shuffled = make_shuffled_negative(text, rng)
        negatives.append(shuffled or make_gibberish_negative(rng))
        if len(negatives) < len(positives) and rng.random() < 0.5:
            negatives.append(make_gibberish_negative(rng))
    negatives = negatives[: len(positives)]

    coherence_texts = positives + negatives
    coherence_labels = [1] * len(positives) + [0] * len(negatives)
    return coherence_texts, coherence_labels


def evaluate_binary(model: Pipeline, texts: list[str], labels: list[int]) -> dict[str, object]:
    predictions = model.predict(texts)
    return {
        "accuracy": accuracy_score(labels, predictions),
        "precision": precision_score(labels, predictions, zero_division=0),
        "recall": recall_score(labels, predictions, zero_division=0),
        "f1": f1_score(labels, predictions, zero_division=0),
        "confusion_matrix": confusion_matrix(labels, predictions).tolist(),
    }


def main() -> None:
    samples = load_training_samples()
    texts, labels = split_fields(samples)
    dataset_samples = load_dataset_txt()
    signal_texts = [sample.text for sample in dataset_samples]

    mlb = MultiLabelBinarizer(classes=SIGNAL_LABELS)
    signal_targets = mlb.fit_transform([sample.labels for sample in dataset_samples])

    train_texts, validation_texts, train_labels, validation_labels = train_test_split(
        texts,
        labels,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=labels,
    )

    toxicity_model = build_toxicity_pipeline()
    toxicity_model.fit(train_texts, train_labels)
    metrics = evaluate_toxicity(toxicity_model, validation_texts, validation_labels)

    signal_model = build_signal_pipeline()
    signal_model.fit(signal_texts, signal_targets)

    coherence_texts, coherence_labels = build_coherence_dataset(texts)
    (
        coherence_train_texts,
        coherence_validation_texts,
        coherence_train_labels,
        coherence_validation_labels,
    ) = train_test_split(
        coherence_texts,
        coherence_labels,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=coherence_labels,
    )
    coherence_model = build_coherence_pipeline()
    coherence_model.fit(coherence_train_texts, coherence_train_labels)
    coherence_metrics = evaluate_binary(coherence_model, coherence_validation_texts, coherence_validation_labels)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "toxicity_model": toxicity_model,
        "signal_model": signal_model,
        "coherence_model": coherence_model,
        "signal_labels": list(mlb.classes_),
        "toxicity_threshold": TOXICITY_THRESHOLD,
        "metrics": metrics,
        "coherence_metrics": coherence_metrics,
        "training_summary": {
            "total_samples": len(samples),
            "toxicity_distribution": dict(Counter(labels)),
            "dataset_txt_samples": len(dataset_samples),
            "signal_distribution": np.asarray(signal_targets).sum(axis=0).astype(int).tolist(),
            "coherence_samples": len(coherence_texts),
            "coherence_distribution": dict(Counter(coherence_labels)),
        },
    }
    joblib.dump(artifact, MODEL_PATH)

    print(json.dumps({k: v for k, v in metrics.items() if k != "classification_report"}, ensure_ascii=False, indent=2))
    print(metrics["classification_report"])
    print(json.dumps({"coherence_metrics": coherence_metrics}, ensure_ascii=False, indent=2))
    print(f"saved_artifact={MODEL_PATH}")


if __name__ == "__main__":
    main()
