import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import plotly.express as px
import geopandas as gpd
from io import BytesIO


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="전국 중학생 분포 지도",
    layout="wide"
)

st.title("🗺️ 전국 중학생(14~16세) 분포 지도")
st.caption("최신 인구 데이터를 기준으로 시군구별 중학생 수를 표시합니다.")


# --------------------------------------------------
# 데이터 주소
# --------------------------------------------------

POP_URL = (
    "https://raw.githubusercontent.com/"
    "greatsong/modudata/main/data/"
    "population_yearly.csv.gz"
)

GEO_URL = (
    "https://raw.githubusercontent.com/"
    "greatsong/modudata/main/data/"
    "boundaries/sigungu_kr.geojson"
)



# --------------------------------------------------
# 데이터 불러오기 함수
# --------------------------------------------------

@st.cache_data
def load_population():

    # 인구 데이터 읽기
    df = pd.read_csv(
        POP_URL,
        compression="gzip",
        dtype={
            "코드": str
        }
    )

    # 코드가 숫자로 변환된 경우 대비
    df["코드"] = (
        df["코드"]
        .astype(str)
        .str.zfill(10)
    )

    return df



@st.cache_data
def load_boundary():

    # GeoJSON 읽기
    response = requests.get(GEO_URL)
    geojson = response.json()

    gdf = gpd.GeoDataFrame.from_features(
        geojson["features"]
    )

    # 코드 역시 문자열 처리
    gdf["코드"] = (
        gdf["코드"]
        .astype(str)
        .str.zfill(5)
    )

    return gdf



# --------------------------------------------------
# 중학생 수 계산
# --------------------------------------------------

def make_middle_population(df):

    # 최신 연도 선택
    latest_year = df["연도"].max()

    df = df[
        df["연도"] == latest_year
    ].copy()


    # 중학생 나이
    ages = [14, 15, 16]


    # 계_14세 + 계_15세 + 계_16세
    middle_cols = [
        f"계_{age}세"
        for age in ages
    ]


    # 혹시 열 이름 확인
    missing = [
        c for c in middle_cols
        if c not in df.columns
    ]

    if missing:
        st.error(
            f"없는 열이 있습니다: {missing}"
        )
        st.stop()


    # 읍면동별 중학생 계산
    df["중학생수"] = (
        df[middle_cols]
        .sum(axis=1)
    )


    # 코드 앞 5자리 = 시군구 코드
    df["시군구코드"] = (
        df["코드"]
        .str[:5]
    )


    # 시군구 단위 합계
    result = (
        df.groupby(
            [
                "시군구코드",
                "시도"
            ],
            as_index=False
        )
        ["중학생수"]
        .sum()
    )


    return result, latest_year



# --------------------------------------------------
# 단계 구간 만들기
# --------------------------------------------------

def make_grade(value, minimum, maximum):

    if maximum == minimum:
        return 1

    step = (
        maximum - minimum
    ) / 5

    grade = int(
        (value - minimum)
        / step
    ) + 1

    if grade > 5:
        grade = 5

    return grade



# --------------------------------------------------
# 실행
# --------------------------------------------------

with st.spinner("데이터를 불러오는 중입니다..."):

    population = load_population()

    boundary = load_boundary()

    middle, year = make_middle_population(
        population
    )



# --------------------------------------------------
# 지도 데이터 연결
# --------------------------------------------------

map_df = boundary.merge(
    middle,
    left_on="코드",
    right_on="시군구코드",
    how="left"
)


# 인구 없는 지역 0 처리
map_df["중학생수"] = (
    map_df["중학생수"]
    .fillna(0)
)



# --------------------------------------------------
# 단계구분 등급 계산
# --------------------------------------------------

minimum = map_df["중학생수"].min()
maximum = map_df["중학생수"].max()


map_df["등급"] = map_df["중학생수"].apply(
    lambda x:
    make_grade(
        x,
        minimum,
        maximum
    )
)



# --------------------------------------------------
# 범례용 문구 만들기
# --------------------------------------------------

step = (
    maximum - minimum
) / 5


legend_labels = {}

for i in range(1,6):

    low = int(
        minimum + step*(i-1)
    )

    high = int(
        minimum + step*i
    )

    legend_labels[i] = (
        f"{low:,}명 ~ {high:,}명"
    )



map_df["구간"] = (
    map_df["등급"]
    .map(legend_labels)
)



# --------------------------------------------------
# 지도 그리기
# --------------------------------------------------

st.subheader(
    f"📌 {year}년 기준 시군구별 중학생 수"
)


fig = px.choropleth_map(
    map_df,
    geojson=map_df.geometry,
    locations=map_df.index,
    color="등급",
    hover_name="시군구",
    hover_data={
        "시도": True,
        "중학생수": ":,",
        "등급": False
    },
    color_continuous_scale=[
        "#edf8fb",
        "#b2e2e2",
        "#66c2a4",
        "#238b45",
        "#005824"
    ],
    range_color=[
        1,
        5
    ],
    labels={
        "등급": "단계"
    }
)


fig.update_geos(
    fitbounds="locations",
    visible=False
)


fig.update_layout(
    height=700,
    margin={
        "r":0,
        "t":0,
        "l":0,
        "b":0
    },
    coloraxis_colorbar=dict(
        title="중학생 수",
        tickvals=[
            1,2,3,4,5
        ],
        ticktext=[
            legend_labels[i]
            for i in range(1,6)
        ]
    )
)


st.plotly_chart(
    fig,
    use_container_width=True
)



# --------------------------------------------------
# 광역자치단체별 최대 / 최소 지역
# --------------------------------------------------

st.subheader(
    "📊 광역지방자치단체별 중학생 수 최대·최소 지역"
)


max_region = (
    middle.sort_values(
        "중학생수",
        ascending=False
    )
    .groupby(
        "시도"
    )
    .first()
    .reset_index()
)


min_region = (
    middle.sort_values(
        "중학생수",
        ascending=True
    )
    .groupby(
        "시도"
    )
    .first()
    .reset_index()
)



summary = pd.DataFrame({

    "시도":
    max_region["시도"],

    "중학생 수 가장 많은 시군구":
    max_region["시군구코드"]
    .map(
        dict(
            zip(
                map_df["시군구코드"],
                map_df["시군구"]
            )
        )
    ),

    "최대 학생수":
    max_region["중학생수"],


    "중학생 수 가장 적은 시군구":
    min_region["시군구코드"]
    .map(
        dict(
            zip(
                map_df["시군구코드"],
                map_df["시군구"]
            )
        )
    ),

    "최소 학생수":
    min_region["중학생수"]

})



summary = summary.sort_values(
    "시도"
)


st.dataframe(
    summary,
    use_container_width=True,
    hide_index=True
)



# --------------------------------------------------
# 데이터 확인용
# --------------------------------------------------

with st.expander(
    "📁 데이터 확인"
):

    st.write(
        f"사용 연도: {year}"
    )

    st.write(
        f"전국 최대 중학생 수: {maximum:,.0f}명"
    )

    st.write(
        f"전국 최소 중학생 수: {minimum:,.0f}명"
    )
