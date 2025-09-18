import re
from pathlib import Path

import pandas as pd
from flask import Flask, request, render_template, Response
from unidecode import unidecode
import folium
from folium.plugins import HeatMap
import branca.colormap as cm

app = Flask(__name__, template_folder="../templates")

# ---------- Carga de datos ----------
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "df.csv"
df = pd.read_csv(DATA_PATH)

# Asegurar tipo numérico
df["VOTOS"] = pd.to_numeric(df["VOTOS"], errors="coerce").fillna(0)

# ---------- Utils ----------
def _norm(s):
    if pd.isna(s):
        return ""
    s = unidecode(str(s)).upper().strip()
    s = re.sub(r"\s+", " ", s)
    return s

def preparar_por_local(df_in, comuna, lista):
    tmp = df_in[
        (df_in["COMUNA"].map(_norm) == _norm(comuna)) &
        (df_in["Lista"].map(_norm)  == _norm(lista))
    ].copy()

    agg = (
        tmp.groupby(
            ["LOCAL DE VOTACION", "CALLE", "NUMERO", "LATITUD", "LONGITUD"],
            dropna=False, as_index=False
        )["VOTOS"].sum()
    )

    agg = agg.dropna(subset=["LATITUD", "LONGITUD"])
    agg["LATITUD"] = pd.to_numeric(agg["LATITUD"], errors="coerce")
    agg["LONGITUD"] = pd.to_numeric(agg["LONGITUD"], errors="coerce")
    return agg.dropna(subset=["LATITUD", "LONGITUD"])

def construir_mapa(data, comuna, lista):
    lat_c = float(data["LATITUD"].mean())
    lon_c = float(data["LONGITUD"].mean())

    m = folium.Map(location=[lat_c, lon_c], zoom_start=13, tiles="cartodbpositron")

    vmin, vmax = float(data["VOTOS"].min()), float(data["VOTOS"].max())
    if vmin == vmax:
        vmin = 0.0
    cmap = cm.linear.YlOrRd_09.scale(vmin, vmax)
    cmap.caption = f"Votos Lista {lista} por local"

    for _, r in data.iterrows():
        v = float(r["VOTOS"])
        color = cmap(v)
        size = 6 + 8 * ((v - vmin) / (vmax - vmin) if vmax > vmin else 0)

        popup_html = (
            f"<b>{r['LOCAL DE VOTACION']}</b><br>"
            f"{r['CALLE']} {r['NUMERO']}<br>"
            f"Votos Lista {lista}: <b>{int(v)}</b>"
        )

        folium.CircleMarker(
            location=[float(r["LATITUD"]), float(r["LONGITUD"])],
            radius=size,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            opacity=0.85,
            tooltip=r["LOCAL DE VOTACION"]
        ).add_to(m)

    heat_data = data[["LATITUD", "LONGITUD", "VOTOS"]].astype(float).values.tolist()
    HeatMap(heat_data, name=f"Heat (Lista {lista})", radius=25, blur=15, max_zoom=18).add_to(m)

    cmap.add_to(m)
    m.fit_bounds(data[["LATITUD","LONGITUD"]].astype(float).values.tolist(), padding=(20, 20))
    folium.LayerControl().add_to(m)

    return m.get_root().render()

# ---------- Rutas ----------
@app.get("/")
def root():
    return render_template("index.html")

@app.get("/map")
def map_view():
    comuna = request.args.get("comuna", "").strip()
    lista  = request.args.get("lista", "").strip()

    if not comuna or not lista:
        return Response("Faltan parámetros ?comuna=&lista=", status=400)

    data = preparar_por_local(df, comuna, lista)
    if data.empty:
        return Response(f"No hay datos para comuna '{comuna}' y lista '{lista}'.", status=404)

    html = construir_mapa(data, comuna, lista)
    return Response(html, mimetype="text/html")
