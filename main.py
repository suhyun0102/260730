import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import json

# =====================================================
# 전국 중학생(14~16세) 단계구분도
# =====================================================

st.set_page_config(
    page_title="전국 중학생 지도",
    layout="wide"
)

st.title("🧑‍🎓 전국 중학생(14~16세) 분포 지도")

# -----------------------------------------------------
# 데이터 주소
# -----------------------------------------------------

POP_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"

GEO_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"


# -----------------------------------------------------
# 인구 데이터 읽기
# -----------------------------------------------------
@st.cache_data
def load_population():

    df = pd.read_csv(
        POP_URL,
        compression="gzip",
        dtype={"코드": str}
    )

    return df


# -----------------------------------------------------
# GeoJSON 읽기
# -----------------------------------------------------
@st.cache_data
def load_geo():

    return pd.read_json(GEO_URL)


# -----------------------------------------------------
# 데이터 불러오기
# -----------------------------------------------------

with st.spinner("데이터 불러오는 중..."):

    pop = load_population()

# -----------------------------------------------------
# 가장 최신 연도 선택
# -----------------------------------------------------

latest_year = pop["연도"].max()

pop = pop[pop["연도"] == latest_year].copy()

# -----------------------------------------------------
# 중학생(14~16세) 계산
# -----------------------------------------------------

pop["학생수"] = (
    pop["계_14세"]
    + pop["계_15세"]
    + pop["계_16세"]
)

# -----------------------------------------------------
# 시군구 코드 만들기
# 코드 앞 5자리가 시군구
# -----------------------------------------------------

pop["시군구코드"] = pop["코드"].str[:5]

# -----------------------------------------------------
# 시군구별 합계
# -----------------------------------------------------

sigungu = (
    pop.groupby(
        ["시군구코드", "시도", "시군구"],
        as_index=False
    )["학생수"]
    .sum()
)

# -----------------------------------------------------
# GeoJSON 읽기
# -----------------------------------------------------

import requests

geojson = requests.get(GEO_URL).json()

# -----------------------------------------------------
# GeoJSON의 코드 목록 만들기
# -----------------------------------------------------

geo_df = pd.DataFrame([
    {
        "시군구코드": f["properties"]["코드"],
        "시도": f["properties"]["시도"],
        "시군구": f["properties"]["시군구"]
    }
    for f in geojson["features"]
])

# -----------------------------------------------------
# 지도 데이터 연결
# -----------------------------------------------------

map_df = geo_df.merge(
    sigungu,
    how="left",
    on="시군구코드"
)

map_df["학생수"] = map_df["학생수"].fillna(0).astype(int)

# -----------------------------------------------------
# 동일 간격 5단계 만들기
# -----------------------------------------------------

min_value = int(map_df["학생수"].min())
max_value = int(map_df["학생수"].max())

bins = np.linspace(min_value, max_value, 6)

labels = []

for i in range(5):

    low = int(round(bins[i]))
    high = int(round(bins[i + 1]))

    labels.append(f"{low:,}명 ~ {high:,}명")

map_df["구간"] = pd.cut(
    map_df["학생수"],
    bins=bins,
    labels=labels,
    include_lowest=True
)

# -----------------------------------------------------
# 색상 (5단계)
# -----------------------------------------------------

color_map = {
    labels[0]: "#eff3ff",
    labels[1]: "#bdd7e7",
    labels[2]: "#6baed6",
    labels[3]: "#3182bd",
    labels[4]: "#08519c",
}

# -----------------------------------------------------
# 지도
# -----------------------------------------------------

fig = px.choropleth(
    map_df,
    geojson=geojson,
    featureidkey="properties.코드",
    locations="시군구코드",
    color="구간",
    color_discrete_map=color_map,
    category_orders={"구간": labels},
    hover_data={
        "시도_x": False,
        "시군구_x": False,
        "학생수": True,
    },
)

fig.update_traces(
    hovertemplate=
    "<b>%{customdata[1]}</b><br>"
    "시도 : %{customdata[0]}<br>"
    "학생수 : %{customdata[2]:,}명<extra></extra>",
    customdata=np.stack(
        [
            map_df["시도_x"],
            map_df["시군구_x"],
            map_df["학생수"]
        ],
        axis=-1
    )
)

fig.update_geos(

    fitbounds="locations",

    visible=False,

    showcountries=False,

    showcoastlines=False,

    showland=False,

    showframe=False,
)

fig.update_layout(

    height=800,

    margin=dict(
        l=0,
        r=0,
        t=20,
        b=0
    ),

    legend_title="중학생 수"
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# -----------------------------------------------------
# 많은 지역 / 적은 지역
# -----------------------------------------------------

left, right = st.columns(2)

with left:

    st.subheader("📈 학생 수가 많은 지역 TOP10")

    top10 = (
        map_df.sort_values(
            "학생수",
            ascending=False
        )[
            ["시도_x", "시군구_x", "학생수"]
        ]
        .head(10)
        .rename(
            columns={
                "시도_x": "시도",
                "시군구_x": "시군구"
            }
        )
    )

    st.dataframe(
        top10,
        use_container_width=True,
        hide_index=True
    )

with right:

    st.subheader("📉 학생 수가 적은 지역 TOP10")

    bottom10 = (
        map_df.sort_values(
            "학생수"
        )[
            ["시도_x", "시군구_x", "학생수"]
        ]
        .head(10)
        .rename(
            columns={
                "시도_x": "시도",
                "시군구_x": "시군구"
            }
        )
    )

    st.dataframe(
        bottom10,
        use_container_width=True,
        hide_index=True
    )

st.caption(
    f"기준 연도 : {latest_year}년"
)
