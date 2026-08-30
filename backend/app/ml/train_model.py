"""
train_model.py — Train phishing detection model on multi-source dataset.

Enhancements over v1:
  - 10,000 TF-IDF features with trigrams and sublinear TF scaling
  - 7 handcrafted features (was 4): + text_length, link_to_text_ratio, has_html
  - Dual-model evaluation: Logistic Regression vs Random Forest
  - Best model selected by F1 score via GridSearchCV
  - Dataset source tracking in metadata
"""

import os
import sys
import json
import datetime
import numpy as np
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, GridSearchCV, StratifiedKFold
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    classification_report,
)
from scipy.sparse import hstack, csr_matrix

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ml.preprocess import (
    clean_text,
    extract_urls,
    count_urgency_keywords,
    calc_caps_ratio,
    calc_punctuation_ratio,
)


def extract_handcrafted_features(text: str) -> list:
    """
    Extract numeric handcrafted features from raw email text.

    Features (7 total):
      0. url_count        — number of URLs found
      1. urgency_count    — high-confidence phishing phrases matched
      2. caps_ratio       — uppercase character ratio
      3. punctuation_ratio— exclamation/question mark ratio
      4. text_length      — log-scaled character count (normalised)
      5. link_to_text_ratio — urls per 100 words (0 if empty)
      6. has_html         — 1 if text contains HTML tags, else 0
    """
    urls = extract_urls(text)
    urgency_count, _ = count_urgency_keywords(text)
    caps = calc_caps_ratio(text)
    punct = calc_punctuation_ratio(text)

    # New features
    text_length = np.log1p(len(text))  # log-scaled to reduce skew
    word_count = max(len(text.split()), 1)
    link_to_text_ratio = len(urls) / word_count * 100
    has_html = 1.0 if ("<a " in text.lower() or "<img" in text.lower()
                        or "<table" in text.lower() or "<div" in text.lower()
                        or "<html" in text.lower()) else 0.0

    return [len(urls), urgency_count, caps, punct,
            text_length, link_to_text_ratio, has_html]


HANDCRAFTED_FEATURE_NAMES = [
    "url_count", "urgency_count", "caps_ratio", "punctuation_ratio",
    "text_length", "link_to_text_ratio", "has_html",
]


def train():
    """Train the phishing detection model and save artifacts & metadata."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, "..", "..", "data", "phishing_dataset.csv")
    artifacts_dir = os.path.join(base_dir, "model_artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: Generate multi-source dataset if not present
    # ------------------------------------------------------------------
    dataset_sources = []
    if not os.path.exists(data_path):
        print("[INFO] Dataset not found. Generating multi-source dataset...")
        from ml.generate_dataset import generate_dataset
        dataset_sources = generate_dataset(data_path, total_rows=50000)
    else:
        # Check if the existing dataset is the small 5K one — regenerate
        # NOTE: Use pandas to count actual rows, NOT raw line counting,
        # because email text fields contain embedded newlines.
        df_check = pd.read_csv(data_path)
        row_count = len(df_check)
        if row_count < 10000:
            print(f"[INFO] Existing dataset is small ({row_count} rows). Regenerating...")
            del df_check  # free memory before downloading
            from ml.generate_dataset import generate_dataset
            dataset_sources = generate_dataset(data_path, total_rows=50000)
        else:
            print(f"[INFO] Using existing dataset ({row_count} rows)")
            del df_check

    # ------------------------------------------------------------------
    # Step 2: Load and prepare data
    # ------------------------------------------------------------------
    print("[INFO] Loading dataset...")
    df = pd.read_csv(data_path)
    df["text"] = df["text"].fillna("")
    # Drop very short texts that add noise
    df = df[df["text"].str.len() >= 20].reset_index(drop=True)

    print(f"   Total samples: {len(df)}")
    print(f"   Phishing: {(df['label'] == 1).sum()}, Legitimate: {(df['label'] == 0).sum()}")

    df["cleaned"] = df["text"].apply(clean_text)

    # ------------------------------------------------------------------
    # Step 3: Extract features
    # ------------------------------------------------------------------
    print("[INFO] Extracting handcrafted features (7 features)...")
    handcrafted = np.array(df["text"].apply(extract_handcrafted_features).tolist())

    print("[INFO] Fitting TF-IDF Vectorizer (10K features, trigrams, sublinear TF)...")
    vectorizer = TfidfVectorizer(
        max_features=10000,
        ngram_range=(1, 3),
        stop_words="english",
        sublinear_tf=True,       # log(1 + tf) — reduces impact of word repetition
        min_df=2,                # ignore ultra-rare terms
        max_df=0.95,             # ignore terms in >95% of docs
    )
    tfidf_matrix = vectorizer.fit_transform(df["cleaned"])

    X = hstack([tfidf_matrix, csr_matrix(handcrafted)])
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"   Train: {X_train.shape[0]} samples, Test: {X_test.shape[0]} samples")
    print(f"   Feature dimensions: {X_train.shape[1]} (TF-IDF: {tfidf_matrix.shape[1]} + Handcrafted: {handcrafted.shape[1]})")

    # ------------------------------------------------------------------
    # Step 4: Train and evaluate multiple models
    # ------------------------------------------------------------------
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # --- Model A: Logistic Regression ---
    print("\n[INFO] Training Model A: Logistic Regression (GridSearchCV)...")
    lr_param_grid = {
        'C': [0.1, 1.0, 10.0],
        'solver': ['liblinear', 'lbfgs'],
    }
    lr_base = LogisticRegression(random_state=42, max_iter=1000, class_weight='balanced')
    lr_grid = GridSearchCV(lr_base, lr_param_grid, cv=cv, scoring='f1', n_jobs=-1, verbose=1)
    lr_grid.fit(X_train, y_train)

    lr_model = lr_grid.best_estimator_
    lr_pred = lr_model.predict(X_test)
    lr_proba = lr_model.predict_proba(X_test)[:, 1]
    lr_f1 = f1_score(y_test, lr_pred)

    print(f"   LR Best Params: {lr_grid.best_params_}")
    print(f"   LR F1: {lr_f1:.4f}")

    # --- Model B: Random Forest ---
    print("\n[INFO] Training Model B: Random Forest (GridSearchCV)...")
    rf_param_grid = {
        'n_estimators': [200, 300],
        'max_depth': [30, 50, None],
        'min_samples_split': [2, 5],
    }
    rf_base = RandomForestClassifier(random_state=42, class_weight='balanced', n_jobs=-1)
    rf_grid = GridSearchCV(rf_base, rf_param_grid, cv=cv, scoring='f1', n_jobs=-1, verbose=1)
    rf_grid.fit(X_train, y_train)

    rf_model = rf_grid.best_estimator_
    rf_pred = rf_model.predict(X_test)
    rf_proba = rf_model.predict_proba(X_test)[:, 1]
    rf_f1 = f1_score(y_test, rf_pred)

    print(f"   RF Best Params: {rf_grid.best_params_}")
    print(f"   RF F1: {rf_f1:.4f}")

    # ------------------------------------------------------------------
    # Step 5: Pick the best model
    # ------------------------------------------------------------------
    if rf_f1 > lr_f1:
        model = rf_model
        y_pred = rf_pred
        y_proba = rf_proba
        best_params = rf_grid.best_params_
        model_type = "RandomForest"
        print(f"\n[WINNER] Random Forest (F1={rf_f1:.4f} > LR F1={lr_f1:.4f})")
    else:
        model = lr_model
        y_pred = lr_pred
        y_proba = lr_proba
        best_params = lr_grid.best_params_
        model_type = "LogisticRegression"
        print(f"\n[WINNER] Logistic Regression (F1={lr_f1:.4f} >= RF F1={rf_f1:.4f})")

    # ------------------------------------------------------------------
    # Step 6: Final evaluation
    # ------------------------------------------------------------------
    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred))
    rec = float(recall_score(y_test, y_pred))
    f1 = float(f1_score(y_test, y_pred))
    auc = float(roc_auc_score(y_test, y_proba))

    print("\n" + "=" * 60)
    print("[RESULTS] Best Model Evaluation Metrics:")
    print("=" * 60)
    print(f"   Model:     {model_type}")
    print(f"   Accuracy:  {acc:.4f}")
    print(f"   Precision: {prec:.4f}")
    print(f"   Recall:    {rec:.4f}")
    print(f"   F1 Score:  {f1:.4f}")
    print(f"   ROC-AUC:   {auc:.4f}")
    print(f"\n{classification_report(y_test, y_pred, target_names=['Legitimate', 'Phishing'])}")

    # ------------------------------------------------------------------
    # Step 7: Extract feature importance
    # ------------------------------------------------------------------
    print("[INFO] Extracting top phishing indicators...")
    vocab = vectorizer.get_feature_names_out()
    all_feature_names = np.concatenate([vocab, HANDCRAFTED_FEATURE_NAMES])

    if model_type == "LogisticRegression":
        coefs = model.coef_[0]
        top_indices = np.argsort(coefs)[-20:][::-1]
        top_features = {all_feature_names[i]: float(coefs[i]) for i in top_indices}
    else:
        importances = model.feature_importances_
        top_indices = np.argsort(importances)[-20:][::-1]
        top_features = {all_feature_names[i]: float(importances[i]) for i in top_indices}

    print(f"[INFO] Top 10 Phishing Indicators: {list(top_features.keys())[:10]}")

    # ------------------------------------------------------------------
    # Step 8: Compare with previous model (if exists)
    # ------------------------------------------------------------------
    meta_path = os.path.join(artifacts_dir, "metadata.json")
    prev_metrics = None
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            prev_metrics = json.load(f)

    # ------------------------------------------------------------------
    # Step 9: Save artifacts
    # ------------------------------------------------------------------
    model_path = os.path.join(artifacts_dir, "model.pkl")
    vectorizer_path = os.path.join(artifacts_dir, "vectorizer.pkl")

    joblib.dump(model, model_path)
    joblib.dump(vectorizer, vectorizer_path)

    metadata = {
        "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model_type": model_type,
        "best_params": {k: str(v) for k, v in best_params.items()},
        "total_samples": len(df),
        "train_samples": X_train.shape[0],
        "test_samples": X_test.shape[0],
        "tfidf_features": tfidf_matrix.shape[1],
        "handcrafted_features": len(HANDCRAFTED_FEATURE_NAMES),
        "total_features": X.shape[1],
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "roc_auc": auc,
        "dataset_sources": dataset_sources if dataset_sources else "pre-existing",
        "features": ["tfidf_ngram_1_3"] + HANDCRAFTED_FEATURE_NAMES,
        "models_evaluated": {
            "LogisticRegression": {"f1": float(lr_f1), "params": {k: str(v) for k, v in lr_grid.best_params_.items()}},
            "RandomForest": {"f1": float(rf_f1), "params": {k: str(v) for k, v in rf_grid.best_params_.items()}},
        },
        "top_phishing_indicators": top_features,
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[SAVED] Model saved to {model_path}")
    print(f"[SAVED] Vectorizer saved to {vectorizer_path}")
    print(f"[SAVED] Metadata saved to {meta_path}")

    # ------------------------------------------------------------------
    # Step 10: Print comparison with previous model
    # ------------------------------------------------------------------
    if prev_metrics:
        print("\n" + "=" * 60)
        print("[COMPARISON] Previous vs New Model:")
        print("=" * 60)
        for metric in ["accuracy", "precision", "recall", "f1_score", "roc_auc"]:
            old = prev_metrics.get(metric, 0)
            new = metadata[metric]
            delta = new - old
            arrow = "UP" if delta > 0 else ("DOWN" if delta < 0 else "--")
            print(f"   {metric:12s}: {old:.4f} -> {new:.4f}  {arrow} ({delta:+.4f})")
        print(f"   {'samples':12s}: {prev_metrics.get('total_samples', '?')} -> {metadata['total_samples']}")
        print(f"   {'model':12s}: {prev_metrics.get('model_type', 'LogisticRegression')} -> {metadata['model_type']}")

    print("\n[OK] Production model training complete!")


if __name__ == "__main__":
    train()
