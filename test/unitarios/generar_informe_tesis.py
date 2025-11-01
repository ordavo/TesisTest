import os, re
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# =========================================================
# CONFIGURA AQUÍ TU RUTA DE SALIDA
OUTPUT_DIR = r"C:\Users\kmilo\Documents\Tesis\test\test\results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# CSV de entrada (ajusta nombres si los tuyos difieren)
INPUT_FILES = {
    "ok_single":        os.path.join(OUTPUT_DIR, "test_ok_single.csv"),
    "denied_hmac":      os.path.join(OUTPUT_DIR, "test_denied_hmac.csv"),
    "session_expired":  os.path.join(OUTPUT_DIR, "test_session_expired.csv"),
    "unauthorized_uid": os.path.join(OUTPUT_DIR, "test_unauthorized_uid.csv"),
    "burst_load":       os.path.join(OUTPUT_DIR, "test_burst_load.csv"),
}

# Nombres de salidas
SUMMARY_CSV_PATH      = os.path.join(OUTPUT_DIR, "informe_estadistico_resumen.csv")
SUMMARY_EXP_CSV_PATH  = os.path.join(OUTPUT_DIR, "informe_estadistico_resumen_expandido.csv")
PDF_PATH              = os.path.join(OUTPUT_DIR, "Informe_Resultados_RFID_Mayerly_Garzon.pdf")
# =========================================================


# ---------- helpers ----------
def safe_read_csv(path):
    if not os.path.exists(path):
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        try:
            return pd.read_csv(path, sep=";")
        except Exception:
            return None

def extract_alias_from_raw(s):
    """Busca alias dentro de un texto tipo dict/JSON ('alias': 'XXXX' o "alias": "XXXX")."""
    if not isinstance(s, str): 
        return ""
    m = re.search(r"(?:'alias':\s*'|\"alias\":\s*\")(.*?)['\"]", s)
    return m.group(1) if m else ""

def normalize_columns(df: pd.DataFrame):
    cols_map = {c.lower().strip(): c for c in df.columns}
    # resultado
    result_col = next((cols_map[c] for c in ["result","resultado"] if c in cols_map), None)
    # razón / detalle
    reason_col = next((cols_map[c] for c in ["reason","details","detalle","detalles"] if c in cols_map), None)
    # duración
    dur_col = next((cols_map[c] for c in ["duration_s","duracion","duration","latency_s"] if c in cols_map), None)
    # alias directo
    alias_col = cols_map["alias"] if "alias" in cols_map else None
    # respuesta cruda
    raw_col = next((cols_map[c] for c in ["response_raw","raw","response"] if c in cols_map), None)
    return result_col, reason_col, dur_col, alias_col, raw_col

def compute_stats(name, df: pd.DataFrame):
    result_col, reason_col, dur_col, alias_col, raw_col = normalize_columns(df)
    total = len(df)

    # Conteos OK/DENIED/ERROR
    counts = df[result_col].fillna("").value_counts().to_dict() if result_col else {}
    ok_n = counts.get("OK", 0)
    pct_ok = (ok_n/total*100.0) if total > 0 else 0.0

    # Duraciones
    durations = []
    if dur_col:
        durations = pd.to_numeric(df[dur_col], errors="coerce").dropna().tolist()
    lat_mean = float(pd.Series(durations).mean()) if durations else 0.0
    lat_med  = float(pd.Series(durations).median()) if durations else 0.0
    lat_min  = float(pd.Series(durations).min()) if durations else 0.0
    lat_max  = float(pd.Series(durations).max()) if durations else 0.0
    lat_std  = float(pd.Series(durations).std(ddof=0)) if durations else 0.0
    total_time = sum(durations) if durations else 0.0
    throughput = (ok_n/total_time) if total_time > 0 else 0.0

    # Alias (si existen)
    aliases = []
    if alias_col and alias_col in df.columns:
        aliases = df[alias_col].dropna().astype(str).tolist()
    elif raw_col and raw_col in df.columns:
        aliases = df[raw_col].apply(extract_alias_from_raw).replace("", pd.NA).dropna().tolist()

    alias_counts = pd.Series(aliases).value_counts().to_dict() if aliases else {}
    alias_total  = len(aliases)
    alias_unique = sum(1 for v in alias_counts.values() if v == 1)
    alias_pct_unique = (alias_unique/alias_total*100.0) if alias_total > 0 else 0.0
    alias_collisions = {k:v for k,v in alias_counts.items() if v > 1}
    alias_top10 = dict(list(sorted(alias_counts.items(), key=lambda x: x[1], reverse=True)[:10])) if alias_counts else {}

    # Razones (si existen)
    reasons = df[reason_col].fillna("").value_counts().to_dict() if reason_col else {}

    return {
        "name": name,
        "total": total,
        "counts": counts,
        "ok": ok_n,
        "pct_ok": pct_ok,
        "lat_mean": lat_mean, "lat_median": lat_med, "lat_min": lat_min, "lat_max": lat_max, "lat_std": lat_std,
        "total_time": total_time, "throughput_ok_per_s": throughput,
        "alias_total": alias_total, "alias_unique": alias_unique, "alias_pct_unique": alias_pct_unique,
        "alias_collisions_count": len(alias_collisions),
        "alias_collisions_example": dict(list(alias_collisions.items())[:10]),
        "alias_top10": alias_top10,
        "reasons": reasons,
        "durations_list": durations,  # para gráficos
    }

def save_table_as_image(title, df_table: pd.DataFrame, filename: str):
    fig, ax = plt.subplots(figsize=(10, 0.6 + 0.35*max(1,len(df_table.index)) + 1.0))
    ax.axis('off')
    ax.set_title(title, fontsize=14, pad=12)
    tbl = ax.table(cellText=df_table.values, colLabels=df_table.columns, loc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.2)
    fig.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    return out_path

def bar_from_dict(d, title, filename, ylabel="Conteo", rotate_x=False, color="#3B82F6"):
    if not d: 
        return None
    keys = list(d.keys())
    vals = [d[k] for k in keys]
    fig, ax = plt.subplots(figsize=(7,4))
    ax.bar(keys, vals, color=color)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    if rotate_x:
        plt.xticks(rotation=45, ha='right')
    for i, v in enumerate(vals):
        ax.text(i, v, str(v), ha='center', va='bottom', fontsize=8)
    fig.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    return out_path

def hist_from_list(vals, title, filename, bins=20, color="#10B981"):
    if not vals:
        return None
    fig, ax = plt.subplots(figsize=(7,4))
    ax.hist(vals, bins=bins, color=color, edgecolor="white")
    ax.set_title(title)
    ax.set_xlabel("Duración (s)")
    ax.set_ylabel("Frecuencia")
    fig.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    return out_path


# ---------- procesamiento ----------
all_stats = []
dfs = {}
missing = []
for key, path in INPUT_FILES.items():
    df = safe_read_csv(path)
    dfs[key] = df
    if df is None:
        missing.append((key, path))
        continue
    st = compute_stats(key, df)
    all_stats.append(st)

# Resumen CSV compacto
summary_rows = []
for st in all_stats:
    summary_rows.append({
        "test": st["name"],
        "total_rows": st["total"],
        "OK": st["ok"],
        "pct_OK": round(st["pct_ok"], 2),
        "lat_mean_s": round(st["lat_mean"], 4),
        "lat_median_s": round(st["lat_median"], 4),
        "lat_min_s": round(st["lat_min"], 4),
        "lat_max_s": round(st["lat_max"], 4),
        "lat_std_s": round(st["lat_std"], 4),
        "throughput_OK_per_s": round(st["throughput_ok_per_s"], 4),
        "alias_total_seen": st["alias_total"],
        "alias_unique": st["alias_unique"],
        "alias_pct_unique": round(st["alias_pct_unique"], 2),
        "alias_collisions": st["alias_collisions_count"],
    })
summary_df = pd.DataFrame(summary_rows)
summary_df.to_csv(SUMMARY_CSV_PATH, index=False)

# Resumen expandido
expanded_rows = []
for st in all_stats:
    expanded_rows.append({
        "test": st["name"],
        "counts": st["counts"],
        "reasons": st["reasons"],
        "alias_top10": st["alias_top10"],
        "alias_collisions_example": st["alias_collisions_example"]
    })
pd.DataFrame(expanded_rows).to_csv(SUMMARY_EXP_CSV_PATH, index=False)

# Imagen con la tabla resumen
resumen_img = None
if not summary_df.empty:
    resumen_img = save_table_as_image("Resumen estadístico por prueba", summary_df, "00_resumen_tabla.png")

# Gráficos por prueba
pngs = []
for st in all_stats:
    name = st["name"]
    # barras de resultados
    p1 = bar_from_dict(st["counts"], f"Resultados por tipo – {name}", f"{name}_01_resultados.png", color="#8B5CF6")
    # histograma de latencias
    p2 = hist_from_list(st["durations_list"], f"Distribución de latencias – {name}", f"{name}_02_latencias.png", bins=20, color="#10B981")
    # top 10 alias
    p3 = bar_from_dict(st["alias_top10"], f"Top alias por frecuencia – {name}", f"{name}_03_alias_top10.png", rotate_x=True, color="#EF4444")
    for p in [p1,p2,p3]:
        if p: pngs.append(p)

# Gráficos comparativos (latencia media y %OK)
if not summary_df.empty:
    # latencia media
    fig, ax = plt.subplots(figsize=(8,4))
    ax.bar(summary_df["test"], summary_df["lat_mean_s"], color="#0EA5E9")
    ax.set_title("Comparativa: Latencia media por prueba")
    ax.set_ylabel("Segundos")
    for i, v in enumerate(summary_df["lat_mean_s"]):
        ax.text(i, v, f"{v:.3f}", ha='center', va='bottom', fontsize=8)
    fig.tight_layout()
    comp_lat_png = os.path.join(OUTPUT_DIR, "zz_comp_lat_mean.png")
    fig.savefig(comp_lat_png, dpi=200, bbox_inches='tight')
    plt.close(fig); pngs.append(comp_lat_png)

    # % OK
    fig, ax = plt.subplots(figsize=(8,4))
    ax.bar(summary_df["test"], summary_df["pct_OK"], color="#22C55E")
    ax.set_title("Comparativa: Porcentaje de OK por prueba")
    ax.set_ylabel("% OK")
    for i, v in enumerate(summary_df["pct_OK"]):
        ax.text(i, v, f"{v:.1f}%", ha='center', va='bottom', fontsize=8)
    fig.tight_layout()
    comp_ok_png = os.path.join(OUTPUT_DIR, "zz_comp_pct_ok.png")
    fig.savefig(comp_ok_png, dpi=200, bbox_inches='tight')
    plt.close(fig); pngs.append(comp_ok_png)

# PDF final (portada + tabla + gráficos)
with PdfPages(PDF_PATH) as pdf:
    # portada
    fig, ax = plt.subplots(figsize=(11,8.5))
    ax.axis('off')
    title = "Informe de Resultados – Pruebas de Autenticación RFID\nSENA – Mayerly Garzón"
    subtitle = f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ax.text(0.5, 0.70, title, ha='center', va='center', fontsize=20, weight='bold')
    ax.text(0.5, 0.62, subtitle, ha='center', va='center', fontsize=12)
    ax.text(0.5, 0.50, "Contenido:\n• Resumen estadístico por prueba\n• Gráficos de resultados, latencias y alias\n• Comparativos globales",
            ha='center', va='center', fontsize=12)
    pdf.savefig(fig); plt.close(fig)

    # inserta tabla resumen
    if resumen_img and os.path.exists(resumen_img):
        img = plt.imread(resumen_img)
        fig, ax = plt.subplots(figsize=(11,8.5))
        ax.imshow(img); ax.axis('off')
        pdf.savefig(fig); plt.close(fig)

    # inserta todos los PNG generados
    for path in pngs:
        if not os.path.exists(path): 
            continue
        img = plt.imread(path)
        fig, ax = plt.subplots(figsize=(11,8.5))
        ax.imshow(img); ax.axis('off')
        pdf.savefig(fig); plt.close(fig)

print("\n=== LISTO ===")
print(f"Resumen (CSV): {SUMMARY_CSV_PATH}")
print(f"Resumen expandido (CSV): {SUMMARY_EXP_CSV_PATH}")
print(f"PDF con tablas y gráficos: {PDF_PATH}")
if missing:
    print("\nATENCIÓN: No se encontraron algunos CSV de entrada:")
    for (k, p) in missing:
        print(f" - {k}: {p}")
