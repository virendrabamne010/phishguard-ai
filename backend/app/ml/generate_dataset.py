"""
generate_dataset.py — Fetches a real-world phishing/spam dataset (Enron Spam) and prepares it.
Replaces the old synthetic dataset generator.
"""

import os
import csv
from datasets import load_dataset

def generate_dataset(output_path: str, total_rows: int = 30000):
    """Fetch the Enron Spam corpus from HuggingFace and create a balanced subset."""
    print(f"[INFO] Downloading SetFit/enron_spam from HuggingFace ({total_rows} rows)...")
    # 'train' split has 33.7k examples
    dataset = load_dataset("SetFit/enron_spam", split="train")

    # The dataset has 'text' and 'label' columns (0 = ham, 1 = spam)
    # We want a balanced subset
    spam_count = total_rows // 2
    ham_count = total_rows - spam_count
    
    # Filter and extract
    spam_samples = dataset.filter(lambda example: example["label"] == 1).select(range(spam_count))
    ham_samples = dataset.filter(lambda example: example["label"] == 0).select(range(ham_count))

    rows = []
    
    for item in spam_samples:
        rows.append({"text": item["text"], "label": 1})
        
    for item in ham_samples:
        rows.append({"text": item["text"], "label": 0})
        
    import random
    random.seed(42)
    random.shuffle(rows)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Fetched and saved {len(rows)} real-world dataset rows -> {output_path}")
    print(f"     Spam/Phishing: {spam_count}, Legitimate: {ham_count}")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output = os.path.join(script_dir, "..", "..", "data", "phishing_dataset.csv")
    generate_dataset(output, total_rows=30000)
