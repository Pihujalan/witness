from app.anomaly import AnomalyScorer
from app.simulate import generate_dataset


def test_scorer_achieves_reasonable_precision_recall():
    X, y = generate_dataset(n_normal=600, n_rogue=300, seed=1)
    scorer = AnomalyScorer()
    report = scorer.fit(X, y)
    # Not claiming perfection - the dataset intentionally includes
    # borderline rogue cases. Assert it's meaningfully better than chance,
    # not that it's a rigged 100%.
    assert report.recall > 0.5
    assert report.precision > 0.5
    assert report.false_positive_rate < 0.3
