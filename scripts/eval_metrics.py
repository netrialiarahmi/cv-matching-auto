import pandas as pd
import glob
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, classification_report

RESULTS_DIR = "../results/"

files = glob.glob(f"{RESULTS_DIR}/results_*.csv")
all_dfs = []
for f in files:
    df = pd.read_csv(f)
    all_dfs.append(df)

combined = pd.concat(all_dfs, ignore_index=True)

# Filter only labeled data (Candidate Status is not NaN)
labeled = combined[combined["Candidate Status"].notna()].copy()
print(f"Total data berlabel: {len(labeled)}")
print(f"Candidate Status distribution:")
print(labeled["Candidate Status"].value_counts())
print()

# Ground truth: OK = 1 (positif), Rejected = 0 (negatif)
labeled["y_true"] = (labeled["Candidate Status"] == "OK").astype(int)


# Prediction: Match Score > 80 = positif, KECUALI AE Japanese > 50
def predict(row):
    if "Japanese" in str(row["Job Position"]):
        return 1 if row["Match Score"] > 50 else 0
    else:
        return 1 if row["Match Score"] > 80 else 0


labeled["y_pred"] = labeled.apply(predict, axis=1)

print("=== OVERALL METRICS ===")
print(f"Accuracy:  {accuracy_score(labeled['y_true'], labeled['y_pred']):.4f}")
print(f"Precision: {precision_score(labeled['y_true'], labeled['y_pred'], zero_division=0):.4f}")
print(f"Recall:    {recall_score(labeled['y_true'], labeled['y_pred'], zero_division=0):.4f}")
print(f"F1 Score:  {f1_score(labeled['y_true'], labeled['y_pred'], zero_division=0):.4f}")
print()

print("=== CONFUSION MATRIX ===")
cm = confusion_matrix(labeled["y_true"], labeled["y_pred"])
print(f"                 Predicted Neg  Predicted Pos")
print(f"Actual Neg (Rej): {cm[0][0]:>10}  {cm[0][1]:>10}")
print(f"Actual Pos (OK):  {cm[1][0]:>10}  {cm[1][1]:>10}")
print()

print("=== CLASSIFICATION REPORT ===")
print(
    classification_report(
        labeled["y_true"],
        labeled["y_pred"],
        target_names=["Rejected", "OK"],
        zero_division=0,
    )
)
print()

# Per position breakdown
print("=== PER POSITION BREAKDOWN ===")
for pos in sorted(labeled["Job Position"].unique()):
    pos_data = labeled[labeled["Job Position"] == pos]
    if len(pos_data) < 2:
        continue
    y_t = pos_data["y_true"]
    y_p = pos_data["y_pred"]
    print(f"\n--- {pos} (n={len(pos_data)}) ---")
    print(f"  OK: {(y_t==1).sum()}, Rejected: {(y_t==0).sum()}")
    print(f"  Predicted Pos: {(y_p==1).sum()}, Predicted Neg: {(y_p==0).sum()}")
    print(f"  Accuracy:  {accuracy_score(y_t, y_p):.4f}")
    print(f"  Precision: {precision_score(y_t, y_p, zero_division=0):.4f}")
    print(f"  Recall:    {recall_score(y_t, y_p, zero_division=0):.4f}")
    print(f"  F1 Score:  {f1_score(y_t, y_p, zero_division=0):.4f}")

# Detail: Interview Status & Rejection Reason
print()
print("=== DETAIL: STATUS COMBINATIONS (labeled data) ===")
print(
    labeled[["Candidate Status", "Interview Status", "Rejection Reason"]]
    .value_counts(dropna=False)
    .to_string()
)

# Show misclassifications
print()
print("=== FALSE NEGATIVES (OK tapi diprediksi Neg) ===")
fn = labeled[(labeled["y_true"] == 1) & (labeled["y_pred"] == 0)]
if len(fn) > 0:
    print(fn[["Candidate Name", "Job Position", "Match Score", "Candidate Status", "Interview Status", "Rejection Reason"]].to_string())
else:
    print("Tidak ada")

print()
print("=== FALSE POSITIVES (Rejected tapi diprediksi Pos) ===")
fp = labeled[(labeled["y_true"] == 0) & (labeled["y_pred"] == 1)]
if len(fp) > 0:
    print(fp[["Candidate Name", "Job Position", "Match Score", "Candidate Status", "Interview Status", "Rejection Reason"]].to_string())
else:
    print("Tidak ada")
