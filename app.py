"""GSCRI 3.0: evidence-labelled supply chain intelligence prototype."""
from datetime import datetime, timezone, timedelta
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import requests
import streamlit as st

st.set_page_config(page_title="GSCRI | Intelligence Workstation", page_icon="🌐", layout="wide")
WEIGHTS = {"Geopolitical": .35, "Logistics": .30, "Climate": .20, "Infrastructure": .15}
# Analyst-authored illustrative assumptions; NOT measured live risk.
CORRIDORS = [
    ("Red Sea / Bab el-Mandeb", 12.6, 43.3, 88, 76, 58, 65, "Energy, food, consumer goods"),
    ("Suez Canal", 30.5, 32.3, 78, 72, 50, 65, "Energy, manufactured goods"),
    ("Strait of Malacca", 2.5, 101.8, 60, 79, 62, 60, "Electronics, energy, food"),
    ("Panama Canal", 9.1, -79.7, 44, 68, 84, 66, "Food, manufactured goods"),
    ("Taiwan Strait", 24.4, 119.4, 90, 69, 48, 62, "Semiconductors, electronics"),
    ("Strait of Hormuz", 26.5, 56.4, 86, 66, 53, 67, "Crude oil, LNG"),
    ("Cape of Good Hope", -34.4, 18.5, 36, 59, 73, 58, "Energy, manufactured goods"),
    ("Turkish Straits", 41.1, 29.0, 65, 64, 47, 62, "Grain, energy"),
]
rows=[]
for name,lat,lon,g,l,c,i,goods in CORRIDORS:
    row={"Corridor":name,"lat":lat,"lon":lon,"Geopolitical":g,"Logistics":l,"Climate":c,"Infrastructure":i,"Goods exposure (illustrative)":goods}
    row["Score"] = round(sum(row[k]*w for k,w in WEIGHTS.items()),1)
    rows.append(row)
base=pd.DataFrame(rows)

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_usgs():
    """USGS past-day magnitude 2.5+ events; observation feed, not corridor impact."""
    url="https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
    try:
        response=requests.get(url,timeout=9,headers={"User-Agent":"GSCRI-research-prototype/3.0"})
        response.raise_for_status()
        payload=response.json()
        items=[]
        for f in payload.get("features",[]):
            coordinates=f.get("geometry",{}).get("coordinates",[])
            if len(coordinates)<2: continue
            p=f.get("properties",{})
            items.append({"Event":p.get("place","Unknown"),"Magnitude":p.get("mag"),"Longitude":coordinates[0],"Latitude":coordinates[1],"UTC":pd.to_datetime(p.get("time"),unit="ms",utc=True,errors="coerce")})
        return pd.DataFrame(items),payload.get("metadata",{}).get("generated"),None
    except (requests.RequestException,ValueError,KeyError) as exc:
        return pd.DataFrame(),None,str(exc)

st.markdown('''<style>
.block-container{padding-top:1.4rem;max-width:1550px}
[data-testid="stMetric"]{background:#102238;border:1px solid #29425d;border-radius:14px;padding:16px}
[data-testid="stMetricValue"]{color:#67D6FF}
h1,h2,h3{letter-spacing:-.03em}
.gs-head{padding:20px 24px;background:linear-gradient(105deg,#112E49,#0A1728);border:1px solid #2C4965;border-radius:16px;margin-bottom:14px}
.gs-eyebrow{color:#66D9FA;font-size:.76rem;letter-spacing:.15em;font-weight:700}
.gs-title{font-size:2rem;font-weight:750;color:#F2F8FF;margin:5px 0}
.gs-sub{color:#A5BCD0;font-size:.94rem}
.gs-note{color:#B7C7D7;font-size:.8rem}
</style>''',unsafe_allow_html=True)
st.markdown('''<div class="gs-head"><div class="gs-eyebrow">GSCRI / STRATEGIC INTELLIGENCE WORKSTATION / V3.0</div><div class="gs-title">Global Supply Chain & Societal Risk Intelligence</div><div class="gs-sub">Geospatial exposure • Transparent risk modelling • Scenario intelligence • Public evidence feeds</div></div>''',unsafe_allow_html=True)
st.warning("RESEARCH PROTOTYPE — Corridor scores and goods exposure are illustrative assumptions, not observed or validated real-time risk. USGS observations are independently sourced and do not establish trade disruption.",icon="⚠️")
with st.sidebar:
    st.title("⚙️ Analysis controls")
    threshold=st.slider("Minimum modelled risk",0,100,0,5)
    stress=st.slider("Scenario stress adjustment (points)",-30,30,0,1)
    dimension=st.selectbox("Stress dimension",list(WEIGHTS))
    st.caption("Scenario shifts one factor for every corridor; scores are bounded 0–100.")
    show_quakes=st.toggle("Show USGS earthquakes",value=True)
    st.markdown("---")
    st.caption("MODEL VERSION 0.1 · Transparent weighted index · Equal methodological status for all corridors")
    if st.button("Refresh public event feed"):
        fetch_usgs.clear()
        st.rerun()

df=base.copy()
df[dimension]=(df[dimension]+stress).clip(0,100)
df["Score"]=df.apply(lambda r:round(sum(float(r[k])*w for k,w in WEIGHTS.items()),1),axis=1)
df["Tier"]=pd.cut(df.Score,bins=[-1,49.999,74.999,100],labels=["WATCH","ELEVATED","HIGH"])
df=df[df.Score>=threshold].sort_values("Score",ascending=False)
quake_df,quake_generated,quake_error=fetch_usgs() if show_quakes else (pd.DataFrame(),None,None)

k1,k2,k3,k4=st.columns(4)
k1.metric("CORRIDORS IN VIEW",len(df),help="After risk filter")
k2.metric("HIGH MODELLED RISK",int((df.Score>=75).sum()),help="Illustrative score >=75")
k3.metric("MEAN MODELLED INDEX",f"{df.Score.mean():.1f} / 100" if len(df) else "N/A")
k4.metric("USGS EVENTS · 24H",len(quake_df) if not quake_error and show_quakes else "Unavailable" if show_quakes else "Off")

tab1,tab2,tab3,tab4=st.tabs(["🌍 Global command","📊 Risk diagnostics","🧭 Scenario & advisory","📚 Evidence & methodology"])
with tab1:
    left,right=st.columns([1.8,1],gap="large")
    with left:
        st.subheader("Geospatial risk overview")
        if not df.empty:
            pts=df.copy()
            pts["Color"]=pts.Score.apply(lambda s:[248,113,113,190] if s>=75 else [251,191,36,185] if s>=50 else [56,189,248,180])
            pts["Radius"]=pts.Score*3200+50000
            layers=[pdk.Layer("ScatterplotLayer",pts,get_position="[lon,lat]",get_radius="Radius",get_fill_color="Color",pickable=True,auto_highlight=True)]
            if show_quakes and not quake_df.empty:
                layers.append(pdk.Layer("ScatterplotLayer",quake_df,get_position="[Longitude,Latitude]",get_radius=35000,get_fill_color=[186,145,255,145],pickable=True))
            st.pydeck_chart(pdk.Deck(layers=layers,initial_view_state=pdk.ViewState(latitude=14,longitude=28,zoom=1.35),map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",tooltip={"html":"<b>{Corridor}</b><br/>Model score: {Score}<br/>{Event}","style":{"backgroundColor":"#14243b","color":"white"}}),use_container_width=True)
        else: st.info("No corridors match the current filter.")
        st.caption("● Coral = high (75+) · Amber = elevated (50–74.9) · Cyan = watch (<50) · Violet = observed USGS earthquake. Pins are representative corridor reference points, not actual ship tracks.")
    with right:
        st.subheader("Priority watchlist")
        if not df.empty:
            st.dataframe(df[["Corridor","Score","Tier"]],hide_index=True,use_container_width=True,height=365)
        else: st.info("Adjust minimum risk threshold.")
        st.caption("Ranking is based on hypothetical input factors, not a live incident severity assessment.")
    st.subheader("Public observation feed: seismic activity")
    if not show_quakes: st.info("USGS feed is switched off.")
    elif quake_error: st.error("USGS feed unavailable: "+quake_error)
    elif quake_df.empty: st.info("USGS returned no events for the requested feed window.")
    else:
        st.caption("USGS worldwide M2.5+ earthquakes over the last day; unrelated events may appear. Feed generated: "+(pd.to_datetime(quake_generated,unit="ms",utc=True).strftime("%Y-%m-%d %H:%M UTC") if quake_generated else "unknown"))
        st.dataframe(quake_df.sort_values("UTC",ascending=False).head(12),hide_index=True,use_container_width=True)
with tab2:
    st.subheader("Risk factor decomposition")
    if not df.empty:
        long=df.melt(id_vars="Corridor",value_vars=list(WEIGHTS),var_name="Dimension",value_name="Factor score")
        fig=px.bar(long,x="Corridor",y="Factor score",color="Dimension",barmode="group",color_discrete_sequence=["#67D6FF","#F9C74F","#B89BFA","#FA8072"])
        fig.update_layout(template="plotly_dark",paper_bgcolor="#07111F",plot_bgcolor="#07111F",height=460,xaxis_tickangle=-30,legend_orientation="h",legend_y=1.12)
        st.plotly_chart(fig,use_container_width=True)
        st.dataframe(df[["Corridor","Score","Tier",*WEIGHTS.keys()]],hide_index=True,use_container_width=True)
    else: st.info("No corridors match the current filter.")
with tab3:
    st.subheader("Scenario intelligence / executive advisory")
    if df.empty: st.info("Reduce the minimum risk filter to enable corridor selection.")
    else:
        selected=st.selectbox("Select strategic corridor",df.Corridor.tolist())
        r=df.loc[df.Corridor==selected].iloc[0]
        original=base.loc[base.Corridor==selected].iloc[0]
        delta=round(float(r.Score-original.Score),1)
        a,b=st.columns([1,1])
        with a:
            st.metric("Scenario model score",f"{r.Score:.1f}/100",delta=f"{delta:+.1f} points vs baseline",delta_color="inverse")
            st.markdown(f"**Scenario tier:** {r.Tier}  ")
            st.markdown(f"**Goods potentially exposed (illustrative):** {r['Goods exposure (illustrative)']}")
            st.markdown(f"**Largest weighted factor:** {max(WEIGHTS,key=lambda k:float(r[k])*WEIGHTS[k])}")
        with b:
            fig=go.Figure(go.Bar(x=list(WEIGHTS),y=[float(r[k])*WEIGHTS[k] for k in WEIGHTS],marker_color=["#67D6FF","#F9C74F","#B89BFA","#FA8072"]))
            fig.update_layout(title="Weighted contributions (index points)",template="plotly_dark",paper_bgcolor="#07111F",plot_bgcolor="#07111F",height=280,margin=dict(l=15,r=10,b=30,t=55))
            st.plotly_chart(fig,use_container_width=True)
        brief=f"""GSCRI 3.0 | RESEARCH SCENARIO BRIEF\nGenerated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}\nCorridor: {selected}\nIllustrative baseline index: {original.Score:.1f}/100\nIllustrative scenario index: {r.Score:.1f}/100\nScenario change: {delta:+.1f} index points\nDominant weighted stressor: {max(WEIGHTS,key=lambda k:float(r[k])*WEIGHTS[k])}\nPotentially exposed goods (unvalidated): {r['Goods exposure (illustrative)']}\n\nRecommended analytical next steps:\n1. Verify current corridor-specific disruption reports with independent primary sources.\n2. Quantify actual shipment dependence and substitute-route capacity before recommending diversion.\n3. Compare supplier lead times, inventory coverage, insurance quotes, and landed cost.\n4. Assess household exposure only after linking country-level import dependence and consumer price data.\n\nCAUTION: Hypothetical model inputs. Not a live operational or financial recommendation.\n"""
        st.download_button("Download strategic scenario brief",brief,file_name="gscri_scenario_brief.txt",mime="text/plain")
with tab4:
    st.subheader("Evidence register and model governance")
    st.markdown("**Verified external feed:** USGS Earthquake Hazards Program, daily M2.5+ GeoJSON. Earthquake observations are not proof of shipping disruption. [Official feed](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php)")
    st.markdown("**Illustrative analyst inputs:** Corridor coordinates, four factor scores, and goods exposure descriptors are demonstration assumptions embedded in source code. They are not sourced incident records.")
    st.markdown("**Index:** weighted arithmetic mean, with each dimension bounded to 0–100. This is a transparent prototype, not a validated probabilistic risk model.")
    st.code("GSCRI = 0.35 × Geopolitical + 0.30 × Logistics + 0.20 × Climate + 0.15 × Infrastructure")
    st.markdown("**Limitations:** No AIS vessel tracking, port throughput, shipping rates, insurance pricing, country-level import dependency, or validated household affordability impact. No historical backtest. No causal inference.")
    st.markdown("**Refresh policy:** USGS requests cached for 30 minutes; use sidebar refresh to invalidate cache. Public feed may fail or lag. No other inputs auto-refresh.")
    st.markdown("**Planned data expansion:** [UN Comtrade](https://comtradeapi.un.org/) · [Open-Meteo](https://open-meteo.com/) · [World Bank](https://data.worldbank.org/) · [GDELT](https://www.gdeltproject.org/). Not integrated in this release.")
    st.download_button("Export scenario risk table (CSV)",df.to_csv(index=False).encode(),file_name="gscri_scenario_scores.csv",mime="text/csv")
st.caption("GSCRI 3.0 · Public research demonstration · No endorsement by USGS or any data provider · Not for safety-critical navigation or investment decisions")
