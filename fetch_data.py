import yfinance as yf
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Load variabel dari file .env
load_dotenv()

# ── KONFIGURASI ──────────────────────────────────────────
SIMBOL_LIST = [
    "BBCA.JK",
    "BBRI.JK",
    "USDIDR=X",
    "GC=F",
]

PERIODE_HARI = 365

# ── EXTRACT ──────────────────────────────────────────────
def extract(simbol: str, periode_hari: int) -> pd.DataFrame:
    print(f"[EXTRACT] Mengambil data untuk: {simbol}")

    tanggal_akhir = datetime.today()
    tanggal_awal  = tanggal_akhir - timedelta(days=periode_hari)

    df = yf.download(
        simbol,
        start=tanggal_awal.strftime("%Y-%m-%d"),
        end=tanggal_akhir.strftime("%Y-%m-%d"),
        progress=False
    )

    # Flatten MultiIndex columns dari yfinance versi terbaru
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    return df

# ── TRANSFORM ────────────────────────────────────────────
def transform(df: pd.DataFrame, simbol: str) -> pd.DataFrame:
    print(f"[TRANSFORM] Memproses data untuk: {simbol}")

    df = df.dropna()
    df = df.reset_index()

    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["tanggal", "harga_buka", "tertinggi", "terendah", "harga_tutup", "volume"]

    df["tanggal"] = pd.to_datetime(df["tanggal"]).dt.strftime("%Y-%m-%d")

    df["simbol"]            = simbol
    df["perubahan_nominal"] = (df["harga_tutup"] - df["harga_buka"]).round(2)
    df["perubahan_persen"]  = ((df["harga_tutup"] - df["harga_buka"]) / df["harga_buka"] * 100).round(2)

    df["harga_buka"]  = df["harga_buka"].round(2)
    df["harga_tutup"] = df["harga_tutup"].round(2)
    df["tertinggi"]   = df["tertinggi"].round(2)
    df["terendah"]    = df["terendah"].round(2)

    print(f"[TRANSFORM] Berhasil: {len(df)} baris data siap diproses")
    return df

# ── LOAD ─────────────────────────────────────────────────
def load(df: pd.DataFrame):
    print(f"[LOAD] Mengupload {len(df)} baris ke Supabase...")

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor()

    # Susun data jadi list of tuples
    data = [
        (
            row["simbol"],
            row["tanggal"],
            row["harga_buka"],
            row["harga_tutup"],
            row["tertinggi"],
            row["terendah"],
            int(row["volume"]),
            row["perubahan_nominal"],
            row["perubahan_persen"],
        )
        for _, row in df.iterrows()
    ]

    query = """
        INSERT INTO harga_komoditas 
            (simbol, tanggal, harga_buka, harga_tutup, tertinggi, terendah, 
             volume, perubahan_nominal, perubahan_persen)
        VALUES %s
        ON CONFLICT (simbol, tanggal) DO NOTHING
    """

    execute_values(cur, query, data)
    conn.commit()

    cur.close()
    conn.close()

    print(f"[LOAD] ✅ Selesai! Data berhasil disimpan ke database.")

# ── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":
    semua_data = []

    for simbol in SIMBOL_LIST:
        df_raw    = extract(simbol, PERIODE_HARI)
        df_bersih = transform(df_raw, simbol)
        semua_data.append(df_bersih)

    df_final = pd.concat(semua_data, ignore_index=True)

    print(f"\n✅ Total data terkumpul: {len(df_final)} baris")

    load(df_final)