"""
Anomaly Scorer
--------------
A small, honestly-evaluated classifier that distinguishes "normal
agent behaviour" from "rogue agent behaviour" using a handful of
interpretable features - not a black box. It's trained on scripted
synthetic sequences (see simulate.py) because real fraud data for
AI-agent-initiated payments doesn't exist yet for anyone to hand a
hackathon team. State that scope in the README and the pitch, not
just here - it's what keeps the metrics honest rather than inflated.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, confusion_matrix

FEATURE_NAMES = ["velocity_1min", "amount_zscore", "is_new_counterpart", "hour_of_day_sin", "hour_of_day_cos"]

# Bumped whenever the feature set, training data shape, or model type changes,
# so a decision from months ago stays attributable to the exact model that made
# it even after this one has since been retrained or replaced.
MODEL_VERSION = "anomaly-model-v1"

# Two tiers, not one. This model answers "is this agent behaving like itself",
# not "can it do this" (that's the policy engine's job). Below this score, a
# deviation is worth a human glance (HOLD). At or above it, the behavior has
# drifted far enough from the agent's own baseline that Witness blocks outright
# even though the request never broke a policy rule - three refunds a minute
# from brand-new counterparties at 3am is not made safe by being under the
# rupee ceiling.
EXTREME_ANOMALY_THRESHOLD = 0.85


def explain_signals(features: dict) -> list[str]:
    """Turn the raw feature vector into a few plain-English bullets - the
    "why" a human actually reads, not the score alone. Logistic regression's
    whole advantage over a black box is that this translation is possible;
    an explainable model that's never explained wastes the advantage."""
    notes = []
    velocity = features.get("velocity_1min", 0)
    if velocity >= 6:
        notes.append(f"⚠ {int(velocity)} actions from this agent in the last minute — well above normal pace.")
    elif velocity >= 3:
        notes.append(f"⚠ {int(velocity)} actions in the last minute — busier than a single routine action.")
    else:
        notes.append("✓ Velocity is within normal range for a single action.")

    z = features.get("amount_zscore", 0)
    if abs(z) >= 10:
        # A raw ratio stops being a useful number this far out (an agent with
        # almost no variance in its history makes the z-score explode even for
        # a moderate rupee jump) - say what actually matters instead of
        # printing a triple-digit multiplier that reads as a bug, not a signal.
        notes.append("⚠ Amount is far outside this agent's normal range — a severe outlier.")
    elif abs(z) >= 3:
        notes.append(f"⚠ Amount is {abs(z):.1f}× this agent's normal deviation — a significant outlier.")
    elif abs(z) >= 1.5:
        notes.append(f"⚠ Amount is {abs(z):.1f}× this agent's normal deviation — moderately unusual.")
    else:
        notes.append("✓ Amount is consistent with this agent's usual range.")

    if features.get("is_new_counterpart", 0) >= 1.0:
        notes.append("⚠ First time this agent has interacted with this counterparty/order.")
    else:
        notes.append("✓ Counterparty has been seen from this agent before.")

    return notes


@dataclass
class TrainingReport:
    precision: float
    recall: float
    false_positive_rate: float
    n_train: int
    n_test: int
    confusion: list

    def to_dict(self):
        return {
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "false_positive_rate": round(self.false_positive_rate, 3),
            "n_train": self.n_train,
            "n_test": self.n_test,
            "confusion_matrix": self.confusion,
            "note": "Evaluated on scripted normal-vs-rogue simulations, not real transaction data.",
        }


class AnomalyScorer:
    def __init__(self):
        self.model = LogisticRegression(class_weight="balanced")
        self._fitted = False
        self.last_training_report: Optional[TrainingReport] = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> TrainingReport:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42, stratify=y
        )
        self.model.fit(X_train, y_train)
        self._fitted = True

        y_pred = self.model.predict(X_test)
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred, labels=[0, 1]).ravel()
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        self.last_training_report = TrainingReport(
            precision=precision, recall=recall, false_positive_rate=fpr,
            n_train=len(X_train), n_test=len(X_test),
            confusion=[[int(tn), int(fp)], [int(fn), int(tp)]],
        )
        return self.last_training_report

    def score(self, features: dict) -> tuple[float, bool]:
        if not self._fitted:
            raise RuntimeError("AnomalyScorer.fit() must be called before score().")
        x = np.array([[features[name] for name in FEATURE_NAMES]])
        proba = float(self.model.predict_proba(x)[0][1])
        return proba, proba >= 0.5
