import streamlit as st
import pandas as pd
import json
import requests
import plotly.graph_objects as go

# ------------------------------------------------------------
# 페이지 설정
# ------------------------------------------------------------
st.set_page_config(
    page_title="전국 고령화 지도",
    layout="wide"
)

st.title("🧓 전국 시군구 고령화 지도")
st.caption("최신 연도 기준(65세 이상 인구 비율)")

# ------------------------------------------------------------
# 데이터 주소
# ------------------------------------------------------------
POP_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"

GEO_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"


# ------------------------------------------------------------
# 데이터 불러오기
# ------------------------------------------------------------
@st.cache_data
def load_population():

    # 코드는 문자열로 읽는다.
    df = pd.read_csv(
        POP_URL,
        compression="gzip",
        dtype={"코드": str}
    )

    return df


@st.cache_data
def load_geojson():

    geo = requests.get(GEO_URL).json()

    return geo


df = load_population()
geojson = load_geojson()

# ------------------------------------------------------------
# 최신 연도 선택
# ------------------------------------------------------------
latest_year = df["연도"].max()

df = df[df["연도"] == latest_year].copy()

# ------------------------------------------------------------
# 시군구 코드(앞 5자리)
# ------------------------------------------------------------
df["시군구코드"] = df["코드"].str[:5]

# ------------------------------------------------------------
# 65세 이상 인구 열 찾기
# ------------------------------------------------------------
elder_cols = []

for c in df.columns:

    if not c.startswith("계_"):
        continue

    age = c.replace("계_", "")

    if "이상" in age:
        elder_cols.append(c)

    else:
        try:
            if int(age.replace("세", "")) >= 65:
                elder_cols.append(c)
        except:
            pass

# ------------------------------------------------------------
# 전체 인구 열 찾기
# ------------------------------------------------------------
total_cols = []

for c in df.columns:

    if c.startswith("계_"):
        total_cols.append(c)

# ------------------------------------------------------------
# 읍면동 → 시군구 집계
# ------------------------------------------------------------
df["전체인구"] = df[total_cols].sum(axis=1)

df["65세이상"] = df[elder_cols].sum(axis=1)

sigungu = (
    df.groupby("시군구코드", as_index=False)
      .agg(
          전체인구=("전체인구", "sum"),
          고령인구=("65세이상", "sum")
      )
)

sigungu["고령화율"] = (
    sigungu["고령인구"] /
    sigungu["전체인구"] *
    100
)

# ------------------------------------------------------------
# GeoJSON 정보
# ------------------------------------------------------------
geo_info = []

for f in geojson["features"]:

    geo_info.append({
        "시군구코드": f["properties"]["코드"],
        "시군구": f["properties"]["시군구"],
        "시도": f["properties"]["시도"]
    })

geo_df = pd.DataFrame(geo_info)

# 코드 기준 병합
result = geo_df.merge(
    sigungu,
    on="시군구코드",
    how="left"
)

# ------------------------------------------------------------
# 5단계 등급 만들기
# ------------------------------------------------------------
def classify(v):

    if pd.isna(v):
        return None

    if v < 19:
        return "19% 미만"

    elif v < 23:
        return "19~23%"

    elif v < 28:
        return "23~28%"

    elif v < 38:
        return "28~38%"

    else:
        return "38% 이상"


result["등급"] = result["고령화율"].apply(classify)

# 단계별 숫자
grade_map = {
    "19% 미만": 0,
    "19~23%": 1,
    "23~28%": 2,
    "28~38%": 3,
    "38% 이상": 4
}

result["등급번호"] = result["등급"].map(grade_map)

# ------------------------------------------------------------
# Plotly 색상
# ------------------------------------------------------------
colorscale = [
    [0.00, "#f7fbff"],
    [0.20, "#f7fbff"],

    [0.20, "#c6dbef"],
    [0.40, "#c6dbef"],

    [0.40, "#6baed6"],
    [0.60, "#6baed6"],

    [0.60, "#3182bd"],
    [0.80, "#3182bd"],

    [0.80, "#08519c"],
    [1.00, "#08519c"]
]

# ------------------------------------------------------------
# 지도
# ------------------------------------------------------------
fig = go.Figure()

fig.add_choropleth(
    geojson=geojson,
    featureidkey="properties.코드",

    locations=result["시군구코드"],

    z=result["등급번호"],

    customdata=result[
        ["시군구", "시도", "고령화율"]
    ],

    colorscale=colorscale,

    zmin=0,
    zmax=4,

    marker_line_color="white",
    marker_line_width=0.5,

    hovertemplate=
    "<b>%{customdata[0]}</b><br>"
    "시도 : %{customdata[1]}<br>"
    "고령화율 : %{customdata[2]:.1f}%"
    "<extra></extra>",

    colorbar=dict(
        title="고령화율",

        tickvals=[0,1,2,3,4],

        ticktext=[
            "19% 미만",
            "19~23%",
            "23~28%",
            "28~38%",
            "38% 이상"
        ]
    )
)

fig.update_geos(

    fitbounds="locations",

    visible=False,

    showcountries=False,
    showcoastlines=False,
    showland=False,
    showframe=False,
    bgcolor="white"
)

fig.update_layout(
    margin=dict(l=0,r=0,t=0,b=0),
    height=850
)

st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------
# 상위/하위 10개
# ------------------------------------------------------------
st.markdown("---")

left, right = st.columns(2)

with left:

    st.subheader("고령화율 높은 시군구 TOP 10")

    top10 = (
        result.sort_values(
            "고령화율",
            ascending=False
        )[["시도","시군구","고령화율"]]
        .head(10)
    )

    top10["고령화율"] = top10["고령화율"].map(
        lambda x: f"{x:.1f}%"
    )

    st.dataframe(
        top10,
        use_container_width=True,
        hide_index=True
    )

with right:

    st.subheader("고령화율 낮은 시군구 TOP 10")

    bottom10 = (
        result.sort_values(
            "고령화율",
            ascending=True
        )[["시도","시군구","고령화율"]]
        .head(10)
    )

    bottom10["고령화율"] = bottom10["고령화율"].map(
        lambda x: f"{x:.1f}%"
    )

    st.dataframe(
        bottom10,
        use_container_width=True,
        hide_index=True
    )
