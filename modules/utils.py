import os
import pandas as pd
from datetime import datetime

def save_results(df, path="output/results.csv"):
    """
    Save screening results to CSV:
    - Append new results if file already exists.
    - Add timestamp.
    - Remove duplicates (Filename + Job Position).
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Tambahkan timestamp ke setiap record baru
    df["Date Processed"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Jika file sudah ada → baca dan gabungkan
    if os.path.exists(path):
        try:
            existing_df = pd.read_csv(path)
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            # 🔁 Hapus duplikat berdasarkan Filename + Job Position
            combined_df = combined_df.drop_duplicates(subset=["Filename", "Job Position"], keep="last")
            combined_df.to_csv(path, index=False)
        except Exception:
            # Jika gagal baca file lama, buat baru
            df.to_csv(path, index=False)
    else:
        # Jika file belum ada → buat baru
        df.to_csv(path, index=False)


def load_results(path="output/results.csv"):
    """Load results safely; return None if not found."""
    if os.path.exists(path):
        try:
            return pd.read_csv(path)
        except Exception:
            return None
    return None
