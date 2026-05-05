from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ARTIFACTS_DIR = BASE_DIR / "artifacts"

LABELED_CSV_PATH = DATA_DIR / "labeled.csv"
DATASET_TXT_PATH = DATA_DIR / "dataset.txt"
MODEL_PATH = ARTIFACTS_DIR / "toxicity_model.joblib"

RANDOM_SEED = 42
TEST_SIZE = 0.2
TOXICITY_THRESHOLD = 0.5

SIGNAL_LABELS = ("INSULT", "NORMAL", "OBSCENITY", "THREAT")

