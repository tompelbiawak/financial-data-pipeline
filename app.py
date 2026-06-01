import streamlit as st
import pandas as pd
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# ── KONFIGURASI HALAMAN ───────────────────────────────────
st.set_page_config(
    page_title="Financial & Commodity Monitor",
    page_icon="📈",
    layout="wide"
)

# ── KONEKSI & AMBIL DATA ──────────────────────────────────
@st.cache_data(ttl=600)  # Cache 10 menit
def load_data(simbol: str) -> pd.DataFrame:
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    query = """
        SELECT tanggal, harga_buka, harga_tutup, tertinggi, terendah,
               volume, perubahan_nominal, perubahan_persen
        FROM harga_komoditas
        WHERE simbol = %s
        ORDER BY tanggal ASC
    """
    df = pd.read_sql(query, conn, params=(simbol,))
    conn.close()
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    return df

# ── SIDEBAR ───────────────────────────────────────────────
st.sidebar.title("⚙️ Filter Data")

SIMBOL_OPTIONS = {
    "Bank BCA (BBCA.JK)"         : "BBCA.JK",
    "Bank BRI (BBRI.JK)"         : "BBRI.JK",
    "USD/IDR (USDIDR=X)"         : "USDIDR=X",
    "Emas / Gold Futures (GC=F)" : "GC=F",
}

pilihan_label  = st.sidebar.selectbox("Pilih Aset", list(SIMBOL_OPTIONS.keys()))
pilihan_simbol = SIMBOL_OPTIONS[pilihan_label]

rentang_hari = st.sidebar.slider("Rentang Hari", min_value=7, max_value=365, value=90, step=7)

# ── LOAD & FILTER DATA ────────────────────────────────────
df = load_data(pilihan_simbol)
df_filtered = df.tail(rentang_hari).copy()

# ── HEADER ────────────────────────────────────────────────
st.title("📊 Financial & Commodity Monitor")
st.caption(f"Data untuk: **{pilihan_label}** | {rentang_hari} hari terakhir")
st.divider()

# ── METRIC CARDS ──────────────────────────────────────────
harga_terakhir   = df_filtered["harga_tutup"].iloc[-1]
perubahan_nominal = df_filtered["perubahan_nominal"].iloc[-1]
perubahan_persen  = df_filtered["perubahan_persen"].iloc[-1]
harga_tertinggi  = df_filtered["tertinggi"].max()
harga_terendah   = df_filtered["terendah"].min()

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("💰 Harga Terakhir",  f"{harga_terakhir:,.2f}")
col2.metric("📈 Perubahan",       f"{perubahan_nominal:,.2f}", f"{perubahan_persen:.2f}%")
col3.metric("🔺 Tertinggi",       f"{harga_tertinggi:,.2f}")
col4.metric("🔻 Terendah",        f"{harga_terendah:,.2f}")
col5.metric("📅 Total Hari Data", f"{len(df_filtered)} hari")

st.divider()

# ── GRAFIK HARGA ──────────────────────────────────────────
st.subheader("📉 Tren Harga Penutupan")
st.line_chart(df_filtered.set_index("tanggal")["harga_tutup"])

# ── GRAFIK VOLUME ─────────────────────────────────────────
st.subheader("📦 Volume Perdagangan")
st.bar_chart(df_filtered.set_index("tanggal")["volume"])

st.divider()

# ── TABEL DATA ────────────────────────────────────────────
st.subheader("🗃️ Data Historis")

df_display = df_filtered.copy()
df_display["tanggal"] = df_display["tanggal"].dt.strftime("%Y-%m-%d")
df_display.columns = ["Tanggal", "Buka", "Tutup", "Tertinggi", 
                       "Terendah", "Volume", "Perubahan (Rp/USD)", "Perubahan (%)"]

st.dataframe(df_display, use_container_width=True, hide_index=True)

# ── DOWNLOAD BUTTON ───────────────────────────────────────
csv = df_display.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Download CSV",
    data=csv,
    file_name=f"{pilihan_simbol}_{rentang_hari}hari.csv",
    mime="text/csv"
)