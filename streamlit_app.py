# streamlit_app.py
import requests
import streamlit as st
import pandas as pd

import folium
from streamlit_folium import st_folium

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather(latitude: float, longitude: float):
    """
    Open-Meteo API에서 현재 날씨 + 시간별 예보를 가져오는 함수.
    - current_weather=true  → 현재 날씨
    - hourly=...            → 시간별 기온/습도/강수/풍속
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": True,  # 현재 날씨 포함  [oai_citation:0‡tutorials.21-lessons.com](https://tutorials.21-lessons.com/tutorials/week-11?utm_source=chatgpt.com)
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "timezone": "auto",      # 선택한 위치의 로컬 타임존으로 시간 맞추기  [oai_citation:1‡open-meteo.com](https://open-meteo.com/?utm_source=chatgpt.com)
    }

    resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def make_hourly_df(weather_json: dict) -> pd.DataFrame:
    """
    Open-Meteo의 hourly 데이터를 pandas DataFrame으로 변환해서
    시간별 기온/습도/강수/풍속을 한 번에 보기 좋게 정리.
    """
    hourly = weather_json.get("hourly", {})
    if not hourly:
        return pd.DataFrame()

    df = pd.DataFrame(hourly)
    # time 컬럼을 datetime으로 변환
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")

    # 컬럼 이름 한글로 보기 좋게 변경
    rename_map = {
        "temperature_2m": "Temperature (°C)",
        "relative_humidity_2m": "Humidity (%)",
        "precipitation": "Precipitation (mm)",
        "wind_speed_10m": "Wind speed (km/h)",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    return df


def main():
    st.set_page_config(
        page_title="Open-Meteo Interactive Weather Dashboard",
        layout="wide",
    )

    st.title("Open-Meteo Interactive Weather Dashboard")
    st.write(
        "Open-Meteo의 무료 날씨 API를 활용한 인터랙티브 대시보드 예제입니다.  \n"
        "지도를 클릭하면 해당 위치의 위도/경도를 가져와서 현재 날씨와 시간별 예보를 보여줍니다."
    )

    col_map, col_data = st.columns([2, 1])

    # -------------------------------
    # 왼쪽: 지도 (Folium + streamlit-folium)
    # -------------------------------
    with col_map:
        st.subheader("1. 지도에서 위치 선택하기")

        st.markdown(
            "지도 위 아무 곳이나 클릭해 보세요.  \n"
            "**선택한 좌표의 날씨 데이터**를 오른쪽에서 볼 수 있습니다."
        )

        # 동아시아 중심 (대략 한반도 근처)
        default_lat, default_lon = 36.5, 127.8

        # Folium 지도 생성
        m = folium.Map(
            location=[default_lat, default_lon],
            zoom_start=4,
            tiles="OpenStreetMap",
        )

        # streamlit_folium으로 렌더링 + 클릭 정보 받기
        map_data = st_folium(
            m,
            width="100%",
            height=550,
            returned_objects=["last_clicked"],
        )

        last_clicked = None
        if map_data and map_data.get("last_clicked"):
            last_clicked = map_data["last_clicked"]

    # -------------------------------
    # 오른쪽: 날씨 상세 정보
    # -------------------------------
    with col_data:
        st.subheader("2. 선택한 위치의 날씨 데이터")

        if not last_clicked:
            st.info("왼쪽 지도를 클릭해서 위치를 먼저 선택해 주세요.")
            return

        lat = last_clicked["lat"]
        lon = last_clicked["lng"]

        st.markdown(
            f"**선택한 위치:**  \n"
            f"- 위도 (Latitude): `{lat:.4f}`  \n"
            f"- 경도 (Longitude): `{lon:.4f}`"
        )

        # API 호출
        try:
            with st.spinner("날씨 데이터를 불러오는 중입니다..."):
                weather_json = fetch_weather(lat, lon)
        except Exception as e:
            st.error(f"Open-Meteo API 요청 중 오류가 발생했습니다: {e}")
            return

        # -------- 현재 날씨 --------
        current = weather_json.get("current_weather") or weather_json.get("current", {})
        if current:
            st.markdown("### 🌤 현재 날씨")

            temp = current.get("temperature")
            windspeed = current.get("windspeed")
            winddir = current.get("winddirection")
            weathercode = current.get("weathercode")

            # 간단 카드 스타일
            st.metric("Temperature (°C)", f"{temp} °C" if temp is not None else "-")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Wind speed (km/h)", f"{windspeed}" if windspeed is not None else "-")
            with col2:
                st.metric("Wind direction (°)", f"{winddir}" if winddir is not None else "-")

            if weathercode is not None:
                st.caption(f"Weather code: {weathercode}  (Open-Meteo weathercode)")

        else:
            st.warning("현재 날씨 정보(current_weather)를 가져오지 못했습니다.")

        # -------- 시간별 예보 --------
        st.markdown("### ⏱ 시간별 예보 (Temperature / Humidity / Precipitation / Wind)")

        df_hourly = make_hourly_df(weather_json)
        if df_hourly.empty:
            st.info("시간별 예보 데이터가 없습니다.")
        else:
            # 최근 48시간만 보여주기
            df_plot = df_hourly.iloc[:48]

            tab_temp, tab_hum, tab_prec, tab_wind = st.tabs(
                ["Temperature", "Humidity", "Precipitation", "Wind speed"]
            )

            if "Temperature (°C)" in df_plot.columns:
                with tab_temp:
                    st.line_chart(df_plot["Temperature (°C)"])

            if "Humidity (%)" in df_plot.columns:
                with tab_hum:
                    st.line_chart(df_plot["Humidity (%)"])

            if "Precipitation (mm)" in df_plot.columns:
                with tab_prec:
                    st.line_chart(df_plot["Precipitation (mm)"])

            if "Wind speed (km/h)" in df_plot.columns:
                with tab_wind:
                    st.line_chart(df_plot["Wind speed (km/h)"])

            st.markdown("#### Raw hourly data")
            st.dataframe(df_hourly.head(72))


if __name__ == "__main__":
    main()
