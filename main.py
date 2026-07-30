# main.py
# 전국 중학생(14~16세) 인구 단계구분도
# Streamlit Cloud 배포용

import streamlit as st
import pandas as pd
import numpy as np
import requests
import gzip
import io
import json
import plotly.express as px


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="전국 중학생 인구 지도",
    layout="wide"
)

st.title("🗺️ 전국 시군구별 중학생(14~16세) 인구 지도")

st.caption(
    "최신 연도 기준 읍·면·동 인구 데이터를 시군구 단위로 합산한 지도입니다."
)


# ---------------------------------------------------------
# 데이터 주소
# ---------------------------------------------------------

POPULATION_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/data/"
    "population_yearly.csv.gz"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/data/"
    "boundaries/sigungu_kr.geojson"
)


# ---------------------------------------------------------
# 데이터 불러오기 함수
# ---------------------------------------------------------

@st.cache_data
def load_population():

    # 압축 csv 다운로드
    response = requests.get(POPULATION_URL)
    response.raise_for_status()

    # gzip 압축 해제 후 읽기
    df = pd.read_csv(
        gzip.GzipFile(
            fileobj=io.BytesIO(response.content)
        ),
        dtype={
            "코드": str
        }
    )

    # 코드가 숫자로 변환되는 것을 방지
    df["코드"] = df["코드"].astype(str)

    # 혹시 앞자리 0이 사라진 경우 보정
    df["코드"] = df["코드"].str.zfill(10)

    return df



@st.cache_data
def load_geojson():

    response = requests.get(GEOJSON_URL)
    response.raise_for_status()

    return response.json()



# ---------------------------------------------------------
# 최신 연도 데이터 선택
# ---------------------------------------------------------

pop = load_population()

latest_year = pop["연도"].max()

pop = pop[
    pop["연도"] == latest_year
].copy()


# ---------------------------------------------------------
# 중학생 인구 계산
# ---------------------------------------------------------

age_columns = [
    "계_14세",
    "계_15세",
    "계_16세"
]


# 필요한 열 존재 확인
missing = [
    c for c in age_columns
    if c not in pop.columns
]

if missing:
    st.error(
        f"필요한 나이 열이 없습니다: {missing}"
    )
    st.stop()


# 시군구 코드 생성
# 읍면동 코드 앞 5자리 = 시군구 코드
pop["시군구코드"] = (
    pop["코드"]
    .astype(str)
    .str[:5]
)


# 시군구별 합산
sigungu_pop = (
    pop
    .groupby(
        ["시군구코드"],
        as_index=False
    )[age_columns]
    .sum()
)


sigungu_pop["중학생수"] = (
    sigungu_pop["계_14세"]
    +
    sigungu_pop["계_15세"]
    +
    sigungu_pop["계_16세"]
)



# ---------------------------------------------------------
# GeoJSON 준비
# ---------------------------------------------------------

geojson = load_geojson()


features = geojson["features"]

geo_df = pd.DataFrame(
    [
        {
            "코드": str(f["properties"]["코드"]).zfill(5),
            "시군구": f["properties"]["시군구"],
            "시도": f["properties"]["시도"]
        }
        for f in features
    ]
)



# ---------------------------------------------------------
# 지도 데이터 결합
# ---------------------------------------------------------

map_data = geo_df.merge(
    sigungu_pop,
    left_on="코드",
    right_on="시군구코드",
    how="left"
)


# 인구 없는 지역 확인
# (세종 등 코드 오류 방지)
map_data["중학생수"] = (
    map_data["중학생수"]
    .fillna(0)
    .astype(int)
)



# ---------------------------------------------------------
# 3단계 등급 만들기
# ---------------------------------------------------------

minimum = int(map_data["중학생수"].min())
maximum = int(map_data["중학생수"].max())


# 동일 간격 3등분
step = (maximum - minimum) / 3


if step == 0:
    bins = [
        minimum,
        minimum + 1,
        minimum + 2,
        maximum + 1
    ]
else:
    bins = [
        minimum,
        minimum + step,
        minimum + step * 2,
        maximum + 1
    ]


labels = [
    f"{int(bins[0]):,}명 ~ {int(bins[1]):,}명",
    f"{int(bins[1]):,}명 초과 ~ {int(bins[2]):,}명",
    f"{int(bins[2]):,}명 초과 ~ {maximum:,}명"
]


map_data["등급"] = pd.cut(
    map_data["중학생수"],
    bins=bins,
    labels=labels,
    include_lowest=True
)



# ---------------------------------------------------------
# 지도 그리기
# ---------------------------------------------------------

fig = px.choropleth_mapbox(
    map_data,
    geojson=geojson,
    locations="코드",
    featureidkey="properties.코드",
    color="등급",
    color_discrete_map={
        labels[0]: "#d9ecff",
        labels[1]: "#74a9ff",
        labels[2]: "#08519c"
    },
    hover_name="시군구",
    hover_data={
        "시도": True,
        "중학생수": ":,",
        "코드": False,
        "등급": False
    },
    mapbox_style="white-bg",
    zoom=6,
    center={
        "lat": 36.5,
        "lon": 127.8
    },
    opacity=0.75
)


# 배경 지도 타일 제거
fig.update_layout(
    mapbox={
        "style": "white-bg",
        "layers": [
            {
                "source": geojson,
                "type": "line",
                "color": "black",
                "line": {
                    "width": 1
                }
            }
        ]
    },
    legend_title_text="중학생 수 단계",
    margin={
        "r":0,
        "t":30,
        "l":0,
        "b":0
    }
)


st.plotly_chart(
    fig,
    use_container_width=True
)



# ---------------------------------------------------------
# 지역별 최대 / 최소 지역
# ---------------------------------------------------------

st.subheader(
    "📊 광역지방자치단체별 중학생 수 최대·최소 지역"
)


result = []


for sido, group in map_data.groupby("시도"):

    max_row = group.loc[
        group["중학생수"].idxmax()
    ]

    min_row = group.loc[
        group["중학생수"].idxmin()
    ]


    result.append(
        {
            "시도": sido,

            "중학생 수 가장 많은 시군구":
                max_row["시군구"],

            "최대 학생수":
                f'{int(max_row["중학생수"]):,}명',

            "중학생 수 가장 적은 시군구":
                min_row["시군구"],

            "최소 학생수":
                f'{int(min_row["중학생수"]):,}명'
        }
    )


result_df = pd.DataFrame(result)


st.dataframe(
    result_df,
    use_container_width=True,
    hide_index=True
)



# ---------------------------------------------------------
# 데이터 확인용
# ---------------------------------------------------------

with st.expander("데이터 확인"):

    st.write(
        f"사용 연도: {latest_year}년"
    )

    st.write(
        f"전국 시군구 수: {len(map_data)}개"
    )

    st.write(
        f"최대 중학생 수: {maximum:,}명"
    )

    st.write(
        f"최소 중학생 수: {minimum:,}명"
    )
