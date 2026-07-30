import streamlit as st
import pandas as pd
import numpy as np
import requests
import gzip
import io
import json
import plotly.express as px
import folium

from streamlit_folium import st_folium


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="전국 중학생 인구 지도",
    layout="wide"
)

st.title("🗺️ 전국 시군구별 중학생(14~16세) 인구 지도")

st.caption(
    "최신 인구 데이터를 기준으로 전국 시군구별 중학생 수를 단계구분도로 표현합니다."
)


# --------------------------------------------------
# 데이터 주소
# --------------------------------------------------

POPULATION_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/"
    "main/data/population_yearly.csv.gz"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/"
    "main/data/boundaries/sigungu_kr.geojson"
)


# --------------------------------------------------
# 데이터 불러오기 함수
# --------------------------------------------------

@st.cache_data
def load_population():

    # gzip CSV 다운로드
    response = requests.get(POPULATION_URL)
    response.raise_for_status()

    # 압축 해제 후 읽기
    df = pd.read_csv(
        gzip.GzipFile(
            fileobj=io.BytesIO(response.content)
        ),
        dtype={
            "코드": str
        }
    )

    # 코드가 숫자로 변환되는 문제 방지
    df["코드"] = df["코드"].astype(str)

    # 최신 연도 선택
    latest_year = df["연도"].max()

    df = df[df["연도"] == latest_year].copy()


    # --------------------------------------------------
    # 중학생 = 만 14세~16세
    # --------------------------------------------------

    age_columns = [
        "계_14세",
        "계_15세",
        "계_16세"
    ]

    for col in age_columns:
        if col not in df.columns:
            raise ValueError(
                f"{col} 열을 찾을 수 없습니다."
            )

    df["중학생수"] = (
        df["계_14세"]
        + df["계_15세"]
        + df["계_16세"]
    )


    # 읍면동 코드 앞 5자리 = 시군구 코드
    df["시군구코드"] = (
        df["코드"]
        .str[:5]
    )


    # 시군구별 합계
    result = (
        df.groupby(
            [
                "시군구코드"
            ],
            as_index=False
        )
        ["중학생수"]
        .sum()
    )

    result["중학생수"] = (
        result["중학생수"]
        .astype(int)
    )


    return result, latest_year



@st.cache_data
def load_geojson():

    response = requests.get(GEOJSON_URL)
    response.raise_for_status()

    geo = response.json()

    # 코드가 숫자로 읽힌 경우 문자열 변환
    for feature in geo["features"]:

        code = feature["properties"]["코드"]

        feature["properties"]["코드"] = str(code).zfill(5)

    return geo



# --------------------------------------------------
# 데이터 실행
# --------------------------------------------------

try:

    population, year = load_population()
    geojson = load_geojson()

except Exception as e:

    st.error(
        f"데이터를 불러오는 과정에서 오류가 발생했습니다.\n\n{e}"
    )

    st.stop()



# --------------------------------------------------
# 지도 데이터와 결합
# --------------------------------------------------

geo_codes = []

for f in geojson["features"]:

    geo_codes.append(
        f["properties"]["코드"]
    )


geo_df = pd.DataFrame(
    {
        "시군구코드": geo_codes
    }
)


# 코드 기준 결합
map_df = (
    geo_df
    .merge(
        population,
        on="시군구코드",
        how="left"
    )
)


# 혹시 누락 지역이 있으면 0 처리
map_df["중학생수"] = (
    map_df["중학생수"]
    .fillna(0)
    .astype(int)
)


# --------------------------------------------------
# 5단계 구간 만들기
# --------------------------------------------------

minimum = int(
    map_df["중학생수"].min()
)

maximum = int(
    map_df["중학생수"].max()
)


# 동일 간격 5등급
bins = np.linspace(
    minimum,
    maximum,
    6
)


labels = []

for i in range(5):

    start = int(np.floor(bins[i]))
    end = int(np.ceil(bins[i+1]))

    labels.append(
        f"{start:,}명 ~ {end:,}명"
    )


map_df["등급"] = pd.cut(
    map_df["중학생수"],
    bins=bins,
    labels=labels,
    include_lowest=True
)


# --------------------------------------------------
# GeoJSON에 학생수 정보 삽입
# --------------------------------------------------

value_dict = dict(
    zip(
        map_df["시군구코드"],
        map_df["중학생수"]
    )
)


for feature in geojson["features"]:

    code = feature["properties"]["코드"]

    value = value_dict.get(
        code,
        0
    )

    feature["properties"]["중학생수"] = value



# --------------------------------------------------
# 지도 생성
# --------------------------------------------------

st.subheader(
    f"📍 {year}년 전국 시군구별 중학생 수"
)


m = folium.Map(
    location=[
        36.5,
        127.8
    ],
    zoom_start=7,
    tiles=None
)


# 단계별 색상
colors = [
    "#edf8fb",
    "#b3cde3",
    "#8c96c6",
    "#8856a7",
    "#810f7c"
]


def get_color(value):

    for i in range(5):

        if value <= bins[i+1]:

            return colors[i]

    return colors[-1]



# 지도 경계 추가

for feature in geojson["features"]:

    value = feature["properties"]["중학생수"]

    folium.GeoJson(
        feature,
        style_function=lambda x,
            value=value: {

                "fillColor":
                    get_color(value),

                "color":
                    "gray",

                "weight":
                    0.5,

                "fillOpacity":
                    0.8
            },

        tooltip=folium.GeoJsonTooltip(
            fields=[
                "시군구",
                "시도",
                "중학생수"
            ],
            aliases=[
                "시군구",
                "시도",
                "중학생 수"
            ],
            localize=True
        )

    ).add_to(m)



st_folium(
    m,
    width=1100,
    height=650
)



# --------------------------------------------------
# 범례 표시
# --------------------------------------------------

st.markdown("### 🎨 지도 범례")

legend_df = pd.DataFrame(
    {
        "단계": [
            "1단계",
            "2단계",
            "3단계",
            "4단계",
            "5단계"
        ],
        "범위": labels
    }
)

st.table(
    legend_df
)



# --------------------------------------------------
# 광역지자체별 최대 / 최소 지역
# --------------------------------------------------

st.markdown(
    "## 🏙️ 광역지방자치단체별 중학생 수 최대·최소 지역"
)


# GeoJSON 속성에서 시도 정보 가져오기

geo_info = []

for f in geojson["features"]:

    geo_info.append(
        {
            "시군구코드":
                f["properties"]["코드"],

            "시군구":
                f["properties"]["시군구"],

            "시도":
                f["properties"]["시도"]
        }
    )


geo_info = pd.DataFrame(
    geo_info
)


summary = (
    map_df
    .merge(
        geo_info,
        on="시군구코드",
        how="left"
    )
)


rows = []

for sido, group in summary.groupby("시도"):

    max_row = (
        group
        .sort_values(
            "중학생수",
            ascending=False
        )
        .iloc[0]
    )


    min_row = (
        group
        .sort_values(
            "중학생수",
            ascending=True
        )
        .iloc[0]
    )


    rows.append(
        {
            "시도":
                sido,

            "중학생 수 가장 많은 지역":
                max_row["시군구"],

            "학생수":
                f'{max_row["중학생수"]:,}명',

            "중학생 수 가장 적은 지역":
                min_row["시군구"],

            "학생수(최소)":
                f'{min_row["중학생수"]:,}명'
        }
    )


summary_table = pd.DataFrame(rows)


st.dataframe(
    summary_table,
    use_container_width=True,
    hide_index=True
)
