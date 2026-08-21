"""
train_model.py — Train TF-IDF + Logistic Regression on phishing dataset.
Includes feature scaling, evaluation metrics, and metadata serialization.
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
    """Extract numeric handcrafted features from raw email text."""
    urls = extract_urls(text)
    urgency_count, _ = count_urgency_keywords(text)
    caps = calc_caps_ratio(text)
    punct = calc_punctuation_ratio(text)
    return [len(urls), urgency_count, caps, punct]


def train():
    """Train the phishing detection model and save artifacts & metadata."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, "..", "..", "data", "phishing_dataset.csv")
    artifacts_dir = os.path.join(base_dir, "model_artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    if not os.path.exists(data_path):
        print("[INFO] Dataset not found. Generating synthetic dataset...")
        from ml.generate_dataset import generate_dataset
        generate_dataset(data_path, total_rows=5000)

    print("[INFO] Loading dataset...")
    df = pd.read_csv(data_path)
    df["text"] = df["text"].fillna("")
    print(f"   Total samples: {len(df)}")
    print(f"   Phishing: {(df['label'] == 1).sum()}, Legitimate: {(df['label'] == 0).sum()}")

    df["cleaned"] = df["text"].apply(clean_text)

    print("[INFO] Extracting handcrafted features...")
    handcrafted = np.array(df["text"].apply(extract_handcrafted_features).tolist())

    print("[INFO] Fitting TF-IDF Vectorizer...")
    vectorizer = TfidfVectorizer(max_features=3000, ngram_range=(1, 2), stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(df["cleaned"])

    X = hstack([tfidf_matrix, csr_matrix(handcrafted)])
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("[INFO] Tuning Hyperparameters with GridSearchCV...")
    param_grid = {
        'C': [0.1, 1.0, 10.0],
        'solver': ['liblinear', 'lbfgs']
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    base_model = LogisticRegression(random_state=42, max_iter=1000, class_weight='balanced')
    grid_search = GridSearchCV(base_model, param_grid, cv=cv, scoring='f1', n_jobs=-1, verbose=1)
    grid_search.fit(X_train, y_train)
    
    print(f"[INFO] Best Parameters: {grid_search.best_params_}")
    model = grid_search.best_estimator_

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred))
    rec = float(recall_score(y_test, y_pred))
    f1 = float(f1_score(y_test, y_pred))
    auc = float(roc_auc_score(y_test, y_proba))

    print("\n[RESULTS] Model Evaluation Metrics:")
    print(f"   Accuracy:  {acc:.4f}")
    print(f"   Precision: {prec:.4f}")
    print(f"   Recall:    {rec:.4f}")
    print(f"   F1 Score:  {f1:.4f}")
    print(f"   ROC-AUC:   {auc:.4f}")
    print(f"\n{classification_report(y_test, y_pred, target_names=['Legitimate', 'Phishing'])}")

    # Extract Feature Importance
    print("[INFO] Extracting top features...")
    vocab = vectorizer.get_feature_names_out()
    handcrafted_names = ["url_count", "urgency_count", "caps_ratio", "punctuation_ratio"]
    all_feature_names = np.concatenate([vocab, handcrafted_names])
    
    coefs = model.coef_[0]
    top_indices = np.argsort(coefs)[-20:][::-1] # Top 20 positive coefs (predicting Phishing)
    top_features = {all_feature_names[i]: float(coefs[i]) for i in top_indices}
    
    print(f"[INFO] Top 5 Phishing Indicators: {list(top_features.keys())[:5]}")

    # Save artifacts
    model_path = os.path.join(artifacts_dir, "model.pkl")
    vectorizer_path = os.path.join(artifacts_dir, "vectorizer.pkl")
    meta_path = os.path.join(artifacts_dir, "metadata.json")

    joblib.dump(model, model_path)
    joblib.dump(vectorizer, vectorizer_path)

    metadata = {
        "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_samples": len(df),
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "roc_auc": auc,
        "features": ["tfidf_ngram_1_2", "url_count", "urgency_count", "caps_ratio", "punctuation_ratio"],
        "top_phishing_indicators": top_features
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"[SAVED] Model saved to {model_path}")
    print(f"[SAVED] Vectorizer saved to {vectorizer_path}")
    print(f"[SAVED] Metadata saved to {meta_path}")
    print("\n[OK] Production model training complete!")


if __name__ == "__main__":
    train()
