import argparse
import json
from pathlib import Path
from typing import Any

import joblib

try:
    from .config import MODEL_PATH
    from .scoring import heuristic_insult_score
except ImportError:
    from config import MODEL_PATH
    from scoring import heuristic_insult_score


def load_artifact(path: Path = MODEL_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found: {path}. Run python3 model/train.py first.")
    return joblib.load(path)


def predict_text(text: str, artifact: dict[str, Any] | None = None) -> dict[str, Any]:
    artifact = artifact or load_artifact()
    if "coherence_model" not in artifact:
        raise RuntimeError("Model artifact is missing coherence_model. Run python3 model/train.py to retrain it.")

    toxicity_model = artifact["toxicity_model"]
    signal_model = artifact["signal_model"]
    coherence_model = artifact["coherence_model"]
    signal_labels = artifact["signal_labels"]
    threshold = artifact["toxicity_threshold"]

    toxicity_score = float(toxicity_model.predict_proba([text])[0][1])
    coherence_score = float(coherence_model.predict_proba([text])[0][1])
    signal_probabilities = signal_model.predict_proba([text])[0]
    signal_scores = {
        label: float(score)
        for label, score in zip(signal_labels, signal_probabilities, strict=True)
    }
    toxic = toxicity_score >= threshold
    insult_score, score_debug = heuristic_insult_score(
        text,
        toxicity_score,
        signal_scores,
        coherence_score=coherence_score,
        return_debug=True,
    )

    has_creative_structure = (
        score_debug.get("compound_bonus", 0.0) >= 0.65
        and score_debug.get("originality_bonus", 0.0) >= 0.6
    )

    if coherence_score < 0.35 and not has_creative_structure:
        decision = {"accepted": False, "reason": "incoherent_text"}
        insult_score = 0
    elif signal_scores.get("THREAT", 0.0) >= 0.75:
        decision = {"accepted": False, "reason": "threat"}
    elif insult_score <= 0:
        decision = {"accepted": False, "reason": "not_an_insult"}
    else:
        decision = {"accepted": True, "reason": "ok"}

    return {
        "text": text,
        "toxic": toxic,
        "toxicity_score": round(toxicity_score, 4),
        "label": "toxic" if toxic else "normal",
        "insult_score": insult_score,
        "insult_score_source": "heuristic",
        "coherence_score": round(coherence_score, 4),
        "decision": decision,
        "signals": {label.lower(): round(score, 4) for label, score in signal_scores.items()},
        "score_debug": score_debug,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict toxicity and monster insult score for text.")
    parser.add_argument("text", help="Text to classify.")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH, help="Path to a saved joblib artifact.")
    args = parser.parse_args()

    artifact = load_artifact(args.model_path)
    print(json.dumps(predict_text(args.text, artifact), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
