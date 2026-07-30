import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import geopandas as gpd
import plotly.express as px


# -------------------------------------------------
# 기본 설정
# -------------------------------------------------
st.set_page_config(
    page_title="전국 중학생 인구 지도",
    layout="wide"
)

st.title("📚 전국 중학생(14~16세) 인구 지도")
st.caption("최신 인구 데이터를 기준으로 시군구별 중학생 수를 표시합니다.")


# -------------------------------------------------
# 데이터 주소
# -------------------------------------------------
POP_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/"
    "main/data/population_yearly.csv.gz"
)

GEO_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/"
    "main/data/boundaries/sigungu_kr.geojson"
)



# -------------------------------------------------
# 데이터 불러오기 함수
# -------------------------------------------------
@st.cache_data
def load_population():

    # 코드가 숫자로 변환되지 않도록 반드시 문자열 처리
    df = pd.read_csv(
        POP_URL,
        compression="gzip",
        dtype={"코드": str}
    )

    return df



@st.cache_data
def load_geojson():

    response = requests.get(GEO_URL)
    response.raise_for_status()

    geo = json.loads(response.text)

    return geo



# -------------------------------------------------
# 인구 데이터 처리
# -------------------------------------------------
@st.cache_data
def make_middle_population(df):

    # 최신 연도 선택
    latest_year = df["연도"].max()

    df = df[df["연도"] == latest_year].copy()


    # 코드 앞 5자리 = 시군구 코드
    df["시군구코드"] = (
        df["코드"]
        .astype(str)
        .str.zfill(10)
        .str[:5]
    )


    # 중학생 나이
    ages = [14, 15, 16]


    age_columns = []

    for age in ages:

        col = f"계_{age}세"

        if col in df.columns:
            age_columns.append(col)


    # 14~16세 합산
    df["중학생수"] = df[age_columns].sum(axis=1)



    # 시군구별 합계
    result = (
        df.groupby(
            ["시군구코드", "시도", "시군구"],
            as_index=False
        )["중학생수"]
        .sum()
    )


    # 혹시 코드가 숫자로 읽혀 사라진 경우 방지
    result["시군구코드"] = (
        result["시군구코드"]
        .astype(str)
        .str.zfill(5)
    )


    return latest_year, result



# -------------------------------------------------
# GeoJSON 처리
# -------------------------------------------------
@st.cache_data
def make_geo_dataframe():

    geo = load_geojson()

    gdf = gpd.GeoDataFrame.from_features(
        geo["features"]
    )


    # 코드 문자열 처리
    gdf["코드"] = (
        gdf["코드"]
        .astype(str)
        .str.zfill(5)
    )

    return gdf



# -------------------------------------------------
# 실행
# -------------------------------------------------

pop = load_population()

year, middle = make_middle_population(pop)

geo_df = make_geo_dataframe()



# -------------------------------------------------
# 지도 데이터 결합
# -------------------------------------------------

# 코드 기준으로만 연결
map_df = geo_df.merge(
    middle[
        [
            "시군구코드",
            "시도",
            "시군구",
            "중학생수"
        ]
    ],
    left_on="코드",
    right_on="시군구코드",
    how="left"
)


# 누락 지역은 0명 처리
map_df["중학생수"] = (
    map_df["중학생수"]
    .fillna(0)
    .astype(int)
)



# -------------------------------------------------
# 세종 오류 보정
# -------------------------------------------------
# 세종특별자치시는 실제 데이터가 여러 행정동으로 존재하므로
# 시군구 코드 기준으로 다시 합산하여 지도에 적용
#
# 만약 코드가 없는 경우 세종 전체 데이터에서 재계산


sejong_check = (
    middle[
        middle["시도"].str.contains(
            "세종",
            na=False
        )
    ]
)


if len(sejong_check) > 0:

    sejong_value = int(
        sejong_check["중학생수"].sum()
    )

    map_df.loc[
        map_df["시도"].str.contains(
            "세종",
            na=False
        ),
        "중학생수"
    ] = sejong_value



# -------------------------------------------------
# 5단계 구간 만들기
# -------------------------------------------------

min_value = int(map_df["중학생수"].min())
max_value = int(map_df["중학생수"].max())


# 동일 간격 5등급
bins = np.linspace(
    min_value,
    max_value,
    6
)


bins = np.unique(
    bins.astype(int)
)


if len(bins) < 6:
    bins = np.linspace(
        min_value,
        max_value + 1,
        6
    )


labels = []

for i in range(len(bins)-1):

    labels.append(
        f"{int(bins[i]):,}명 ~ {int(bins[i+1]):,}명"
    )



map_df["등급"] = pd.cut(
    map_df["중학생수"],
    bins=bins,
    labels=labels,
    include_lowest=True
)



# -------------------------------------------------
# 지도 출력
# -------------------------------------------------

fig = px.choropleth_mapbox(
    map_df,
    geojson=json.loads(
        gpd.GeoSeries(
            map_df.geometry
        ).to_json()
    ),
    locations=map_df.index,
    color="등급",
    hover_name="시군구",
    hover_data={
        "시도": True,
        "중학생수": ":,",
        "등급": True
    },
    color_discrete_sequence=[
        "#e8f5e9",
        "#a5d6a7",
        "#66bb6a",
        "#388e3c",
        "#1b5e20"
    ],
    mapbox_style="carto-positron",
    zoom=6,
    center={
        "lat":36.5,
        "lon":127.8
    },
    opacity=0.75
)


fig.update_layout(

    height=750,

    margin={
        "r":0,
        "t":0,
        "l":0,
        "b":0
    },

    mapbox={
        "style":"white-bg"
    },

    legend_title_text="중학생 수 단계"

)


st.plotly_chart(
    fig,
    use_container_width=True
)



st.info(
    f"기준 연도: {year}년 | "
    f"전국 시군구 최소 {min_value:,}명 ~ 최대 {max_value:,}명 기준 5단계 구분"
)



# -------------------------------------------------
# 광역지자체별 최대/최소 지역
# -------------------------------------------------

st.subheader(
    "📌 광역지자체별 중학생 수가 가장 많은 지역과 적은 지역"
)



summary = []


for sido, group in map_df.groupby("시도"):

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


    summary.append(
        {
            "광역지자체": sido,

            "중학생 수 최대 지역":
                max_row["시군구"],

            "최대 학생수":
                f"{int(max_row['중학생수']):,}명",

            "중학생 수 최소 지역":
                min_row["시군구"],

            "최소 학생수":
                f"{int(min_row['중학생수']):,}명"
        }
    )



summary_df = pd.DataFrame(summary)


st.dataframe(
    summary_df,
    use_container_width=True,
    hide_index=True
)
