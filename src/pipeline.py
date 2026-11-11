"""ETL pipeline: automobileEDA_dirty_training.csv -> automobileEDA_processed.csv

Extract  : baca CSV mentah dari data/raw/
Transform: inspeksi, cleaning, transformasi (Min-Max scaling + encoding)
Load     : simpan hasil ke data/processed/

Jalankan dari root project:  python src/pipeline.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "data" / "raw" / "automobileEDA_dirty_training.csv"
OUT_PATH = ROOT / "data" / "processed" / "automobileEDA_processed.csv"

CATEGORICAL_TEXT_COLS = ["make", "aspiration", "num-of-doors", "body-style",
                         "drive-wheels", "engine-location", "engine-type",
                         "num-of-cylinders", "fuel-system"]
NUMERIC_IMPUTE_MEDIAN = ["stroke", "horsepower", "price"]
SCALE_COLS = ["length", "width", "height", "curb-weight", "engine-size",
              "horsepower", "city-mpg", "highway-mpg", "price"]
ONEHOT_COLS = ["aspiration", "body-style", "drive-wheels", "engine-location",
               "fuel-system", "make"]
CYLINDER_MAP = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "eight": 8, "twelve": 12}
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%d-%b-%Y"]


# ----------------------------------------------------------------- EXTRACT --
def load_data(path: Path = RAW_PATH) -> pd.DataFrame:
    """Membaca dataset mentah. File raw tidak pernah diubah."""
    df = pd.read_csv(path)
    print(f"[EXTRACT] dibaca: {path.relative_to(ROOT)}  shape={df.shape}")
    return df


# --------------------------------------------------------------- INSPECTION --
def inspect_data(df: pd.DataFrame, title: str = "KONDISI AWAL") -> dict:
    """Menampilkan pemeriksaan awal ke terminal dan mengembalikan ringkasannya."""
    print(f"\n===== {title} =====")
    print("\n-- 5 baris pertama --")
    print(df.head().to_string())
    print(f"\n-- Ukuran: {df.shape[0]} baris x {df.shape[1]} kolom --")
    print("\n-- Nama kolom --")
    print(list(df.columns))
    print("\n-- Tipe data --")
    print(df.dtypes.to_string())
    missing = df.isna().sum()
    print("\n-- Missing values (hanya kolom yang ada) --")
    print(missing[missing > 0].to_string() if missing.any() else "tidak ada")
    n_dup = int(df.duplicated().sum())
    print(f"\n-- Duplicate records: {n_dup} --")
    print("\n-- Nilai unik kolom kategorikal --")
    for col in CATEGORICAL_TEXT_COLS:
        if col in df.columns:
            print(f"{col} ({df[col].nunique(dropna=True)}): "
                  f"{sorted(df[col].dropna().astype(str).unique())}")
    return {"shape": df.shape, "missing": missing[missing > 0].to_dict(),
            "duplicates": n_dup}


# ----------------------------------------------------------------- CLEANING --
def _parse_date(value):
    if pd.isna(value):
        return pd.NaT
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(value, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.NaT


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Cleaning: format teks, duplikat, tanggal, missing values."""
    df = df.copy()
    n0 = len(df)

    # 1. Seragamkan kategori: trim spasi + lowercase (mis. 'ALFA-ROMERO', 'dodge  ', 'SEDAN')
    for col in CATEGORICAL_TEXT_COLS + ["horsepower-binned"]:
        df[col] = df[col].astype("string").str.strip().str.lower()
    df["horsepower-binned"] = df["horsepower-binned"].str.capitalize()

    # 2. Hapus duplicate records (setelah teks diseragamkan agar duplikat tersembunyi ikut terdeteksi)
    df = df.drop_duplicates().reset_index(drop=True)
    print(f"[CLEAN] duplikat dihapus: {n0 - len(df)} baris")

    # 3. transaction_date: 4 format campur -> datetime tunggal; sisa NaT diisi interpolasi urutan harian
    df["transaction_date"] = df["transaction_date"].map(_parse_date)
    n_bad_date = int(df["transaction_date"].isna().sum())
    df["transaction_date"] = df["transaction_date"].interpolate(method="linear",
                                                                limit_direction="both")
    df["transaction_date"] = pd.to_datetime(df["transaction_date"]).dt.normalize()
    print(f"[CLEAN] tanggal tidak terbaca & diisi interpolasi: {n_bad_date}")

    # 4. Missing kategorikal: make -> 'unknown'; num-of-doors -> modus per body-style
    df["make"] = df["make"].fillna("unknown")
    mode_by_body = df.groupby("body-style")["num-of-doors"].agg(
        lambda s: s.mode().iat[0] if not s.mode().empty else np.nan)
    mask = df["num-of-doors"].isna()
    df.loc[mask, "num-of-doors"] = df.loc[mask, "body-style"].map(mode_by_body)
    df["num-of-doors"] = df["num-of-doors"].fillna(df["num-of-doors"].mode().iat[0])

    # 5. Missing numerik: median (robust terhadap outlier harga/horsepower)
    for col in NUMERIC_IMPUTE_MEDIAN:
        n_na = int(df[col].isna().sum())
        df[col] = df[col].fillna(df[col].median())
        print(f"[CLEAN] {col}: {n_na} NaN diisi median")

    # 6. horsepower-binned dihitung ulang dari horsepower (konsisten setelah imputasi)
    df["horsepower-binned"] = pd.cut(
        df["horsepower"], bins=np.linspace(df["horsepower"].min(), df["horsepower"].max(), 4),
        labels=["Low", "Medium", "High"], include_lowest=True).astype("string")

    # 7. Tipe data: kolom yang secara semantik integer
    for col in ["horsepower", "peak-rpm"]:
        df[col] = df[col].round().astype("int64")

    print(f"[CLEAN] selesai: {n0} -> {len(df)} baris, sisa NaN total = {int(df.isna().sum().sum())}")
    return df


# ----------------------------------------------------------- TRANSFORMATION --
def transform_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Transformasi: Min-Max scaling, ordinal map, one-hot encoding.

    Mengembalikan (df_transformed, sample_before_after) untuk dokumentasi.
    """
    df = df.copy()
    before = df[SCALE_COLS + ["num-of-cylinders", "body-style", "aspiration"]].head(5).copy()

    # 1. Min-Max Scaling -> kolom baru <kolom>_scaled (nilai asli tetap ada untuk perbandingan)
    for col in SCALE_COLS:
        lo, hi = df[col].min(), df[col].max()
        df[f"{col}_scaled"] = ((df[col] - lo) / (hi - lo)).round(4)

    # 2. Ordinal encoding num-of-cylinders (urutan alami angka silinder)
    df["num-of-cylinders_num"] = df["num-of-cylinders"].map(CYLINDER_MAP).astype("int64")

    # 3. One-Hot encoding kolom nominal
    dummies = pd.get_dummies(df[ONEHOT_COLS], dtype="int64")
    df = pd.concat([df, dummies], axis=1)

    # 4. Label encoding horsepower-binned (ordinal Low<Medium<High)
    df["horsepower-binned_code"] = df["horsepower-binned"].map({"Low": 0, "Medium": 1, "High": 2}).astype("int64")

    after_cols = ([f"{c}_scaled" for c in ["price", "horsepower", "curb-weight"]]
                  + ["num-of-cylinders_num", "body-style_sedan", "aspiration_turbo"])
    sample = pd.concat([before[["price", "horsepower", "curb-weight", "num-of-cylinders",
                                "body-style", "aspiration"]].reset_index(drop=True),
                        df[after_cols].head(5).reset_index(drop=True).round(4)], axis=1)
    print(f"[TRANSFORM] kolom: {df.shape[1]} (scaled={len(SCALE_COLS)}, one-hot={dummies.shape[1]})")
    return df, sample


# --------------------------------------------------------------------- LOAD --
def save_data(df: pd.DataFrame, path: Path = OUT_PATH) -> None:
    """Menyimpan processed dataset sebagai file baru (raw tidak disentuh)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"[LOAD] tersimpan: {path.relative_to(ROOT)}  shape={df.shape}")


# ----------------------------------------------------------------- PIPELINE --
def run_pipeline() -> pd.DataFrame:
    raw = load_data()
    inspect_data(raw, "KONDISI AWAL (RAW)")
    cleaned = clean_data(raw)
    inspect_data(cleaned, "SETELAH CLEANING")
    transformed, sample = transform_data(cleaned)
    print("\n-- Contoh sebelum vs sesudah transformasi (5 baris pertama) --")
    print(sample.to_string())
    save_data(transformed)
    print(f"\n[RINGKASAN] baris: {len(raw)} -> {len(transformed)} | kolom: {raw.shape[1]} -> {transformed.shape[1]}")
    return transformed


if __name__ == "__main__":
    run_pipeline()
