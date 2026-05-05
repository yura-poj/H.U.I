# Model Agent Notes

## Scope

Work only inside the `model` directory unless the user explicitly allows edits elsewhere.

The `model/data` directory is the source of training data. Treat it as read-only unless the user explicitly asks to change the dataset.

Do not modify backend, Docker, frontend, or project root files from this directory-specific task unless the user explicitly expands the scope.

## Goal

Build a model that trains on the data stored in `model/data`.

The model work should stay backend-independent for now. It can expose clear training and prediction code that the Flask backend may call later, but do not wire it into the backend unless requested.

Current model goal: classify whether a submitted phrase is toxic for the monster interaction.

The classifier should answer a narrow question: is the text too toxic / abusive for the intended comic monster-insult game tone? It should not generate insults and should not decide game damage by itself unless the user later asks for that.

Secondary planned model goal: estimate an "insultiveness" score from `0` to `10` for monster-directed phrases.

This score should represent game-style insult intensity, not real-world harassment acceptability. A phrase can be non-toxic but still score high as a funny monster insult. A phrase can also be toxic and receive a high insultiveness score, but backend logic should be able to reject it because of toxicity.

## Current Implementation Status

The first implementation is present inside `model`.

Implemented behavior:

- train a toxicity classifier from local datasets;
- save the trained artifact under `model/artifacts`;
- predict toxicity and a heuristic `0..10` insultiveness score;
- keep backend integration out of scope.

## Expected Structure

Prefer a simple, explicit structure:

```text
model/
  agents.md
  data/
  train.py
  predict.py
  dataset.py
  config.py
  artifacts/
```

Only create files that are needed for the current task.

## Data Rules

- Read training data from `model/data`.
- Inspect the actual data format before choosing an implementation.
- Keep preprocessing deterministic and documented in code.
- Do not hardcode examples from the dataset into prediction logic.
- Avoid changing source data during training.

Known local data sources:

- `model/data/labeled.csv`: CSV with text comments and a `toxic` target column.
- `model/data/dataset.txt`: text dataset with labels in a fastText-like prefix format.

Planned data approach:

- Use `labeled.csv` as the first supervised baseline source because it already has a simple binary target.
- Consider `dataset.txt` as additional training data after label mapping is reviewed.
- Treat labels such as insult, threat, and obscenity carefully. For the game, "comic insult" and "harmful toxicity" may not be the same class.
- Keep a validation split so model quality can be measured before saving artifacts.
- The current known datasets provide toxicity-style labels, not true `0..10` insultiveness labels. A real supervised insultiveness score will need either manual score labels or a later calibration step.

## Model Rules

- Start with a simple baseline before adding complex ML code.
- Keep training, data loading, and prediction logic separate.
- Save trained artifacts under `model/artifacts`.
- Make prediction output stable and easy for the backend to consume later.
- If the model predicts insult damage or quality, clamp final damage-like values to the `0..100` range.

Planned baseline:

- Use a classical text classifier first: TF-IDF features plus Logistic Regression or Linear SVM.
- Return both a binary label and a confidence/probability-like score when possible.
- Prefer Russian text support through character and word n-grams rather than heavy neural dependencies at the first step.
- Use deterministic random seeds for train/validation splitting.
- For the first insultiveness baseline, map model confidence and simple text features into a `0..10` score, then clearly mark it as a heuristic score until scored training data exists.
- If scored examples are added later, replace the heuristic with a separate regression or ordinal classification model.

Planned output shape for future prediction code:

```json
{
  "text": "input text",
  "toxic": true,
  "score": 0.91,
  "label": "toxic",
  "insult_score": 8
}
```

For game integration later, the backend can reject or down-rank toxic text while still allowing absurd, non-hateful monster-directed jokes.

Planned score semantics:

- `0`: not an insult.
- `1..3`: weak teasing or mild negative wording.
- `4..6`: clear insult, likely usable for light monster damage.
- `7..8`: strong game-style insult.
- `9..10`: very strong insult intensity; should be checked carefully against toxicity rules.

Always clamp the final insult score to the `0..10` range.

## Implementation Preferences

- Use Python.
- Prefer lightweight, maintainable dependencies.
- Keep scripts runnable from the project root.
- Add concise comments only where they clarify non-obvious model or preprocessing choices.
- Do not add frontend scaffolding.

Planned file responsibilities, once implementation is requested:

- `model/dataset.py`: load and normalize datasets from `model/data`.
- `model/train.py`: train the classifier, print metrics, and save artifacts.
- `model/predict.py`: load artifacts and classify one text string or a small batch.
- `model/config.py`: keep paths, thresholds, and random seed in one place.
- `model/artifacts/`: store trained model artifacts only after training is run.

Keep future edits scoped to these responsibilities unless the user changes the model scope.

## Verification

After implementation, verify at least:

- training script can load data from `model/data`;
- training completes without errors;
- artifacts are saved in `model/artifacts`;
- prediction code can load saved artifacts and return a result.

Planned quality checks:

- Report accuracy, precision, recall, F1, and confusion matrix on validation data.
- Pay special attention to false positives: comic monster insults should not automatically be blocked if they are not hateful or abusive toward protected groups or real people.
- Pay special attention to false negatives: threats, harassment, hate, and severe personal abuse should be classified as toxic.
- For insultiveness scoring, manually inspect examples across the full `0..10` range and verify that toxic rejection and game intensity remain separate decisions.
- Test several hand-written examples that match the game tone before wiring the model into backend behavior.
