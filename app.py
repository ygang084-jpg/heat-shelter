# -*- coding: utf-8 -*-
"""서울시 폭염대응 시설 대시보드 — 무더위쉼터 + 그늘막 통합 (Streamlit + pandas)"""

import pandas as pd
import streamlit as st

CSV_PATH = "서울시 무더위쉼터.csv"
SHADE_PATH = "폭염저감시설_그늘막_2026년.csv"

SHELTER = "무더위쉼터"
SHADE = "그늘막"

# ── 2025년 폭염으로 인한 온열질환 신고현황 연보 (질병관리청) 반영 ──
# 서울 광역 합계: 신고 378명 / 사망 3명  (표25. 지역별 진료결과별 신고현황)
# 자치구별 사망자수: 표4. 2025년 온열질환 추정 사망 신고사례에서 서울 사례 집계
#   → 중랑구·강동구·관악구 각 1명 (총 3명)
# ※ 자치구별 '신고수'는 연보에 광역(시도) 단위까지만 있어 미제공(서울 합계 378명만 존재)
SEOUL_HEAT_2025 = {"신고수": 378, "사망자수": 3}
SEOUL_GU_DEATHS_2025 = {"중랑구": 1, "강동구": 1, "관악구": 1}

st.set_page_config(page_title="서울시 폭염대응시설", page_icon="🌤️", layout="wide")


def _extract_gu(addr):
    """도로명주소 문자열에서 자치구(○○구) 추출."""
    if isinstance(addr, str):
        for token in addr.split():
            if token.endswith("구") and len(token) >= 2:
                return token
    return "기타"


@st.cache_data
def load_shelter(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="cp949")
    df.columns = [c.strip() for c in df.columns]
    for col in ["시설면적", "이용가능인원", "경도", "위도"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["자치구"] = df["도로명주소"].apply(_extract_gu)
    out = pd.DataFrame({
        "데이터종류": SHELTER,
        "명칭": df["쉼터명칭"],
        "자치구": df["자치구"],
        "세부유형": df["시설구분1"],
        "도로명주소": df["도로명주소"],
        "lat": df["위도"],
        "lon": df["경도"],
    })
    return out


@st.cache_data
def load_shade(path: str) -> pd.DataFrame:
    # 엑셀 원본을 정리해 저장한 CSV (헤더/좌표 정제 완료)
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df[df["연번"].notna()].copy()
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    out = pd.DataFrame({
        "데이터종류": SHADE,
        "명칭": df["설치장소명"],
        "자치구": df["시군구"].astype(str).str.strip(),
        "세부유형": df["종류"],
        "도로명주소": df["도로명주소"],
        "lat": df["위도"],
        "lon": df["경도"],
    })
    return out


shelter = load_shelter(CSV_PATH)
shade = load_shade(SHADE_PATH)
all_df = pd.concat([shelter, shade], ignore_index=True)

st.title("🌤️ 서울시 폭염대응시설 현황")
st.caption(f"무더위쉼터 {len(shelter):,}개 · 그늘막 {len(shade):,}개 · 합계 {len(all_df):,}개")

# ── 사이드바 필터 ───────────────────────────────────────────
st.sidebar.header("🔎 필터")

sel_kinds = st.sidebar.multiselect(
    "데이터종류", [SHELTER, SHADE], default=[SHELTER, SHADE])

gu_list = sorted(g for g in all_df["자치구"].dropna().unique() if g != "기타")
sel_gu = st.sidebar.multiselect("자치구", gu_list, default=[])

keyword = st.sidebar.text_input("명칭 검색", "")

# ── 필터 적용 ──────────────────────────────────────────────
fdf = all_df.copy()
if sel_kinds:
    fdf = fdf[fdf["데이터종류"].isin(sel_kinds)]
if sel_gu:
    fdf = fdf[fdf["자치구"].isin(sel_gu)]
if keyword:
    fdf = fdf[fdf["명칭"].astype(str).str.contains(keyword, case=False, na=False)]

# ── 요약 지표 ──────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("전체 시설", f"{len(fdf):,}")
c2.metric("무더위쉼터", f"{(fdf['데이터종류'] == SHELTER).sum():,}")
c3.metric("그늘막", f"{(fdf['데이터종류'] == SHADE).sum():,}")
c4.metric("자치구 수", f"{fdf['자치구'].nunique():,}")

st.divider()

# ── 자치구별 겹침 비교 ─────────────────────────────────────
st.subheader("🏙️ 자치구별 시설 수 비교 (겹치는 부분)")

pivot = (
    fdf.pivot_table(index="자치구", columns="데이터종류",
                    values="명칭", aggfunc="count", fill_value=0)
    .drop(index="기타", errors="ignore")
)
for k in (SHELTER, SHADE):
    if k not in pivot.columns:
        pivot[k] = 0
pivot = pivot[[c for c in (SHELTER, SHADE) if c in pivot.columns]]
pivot["합계"] = pivot.sum(axis=1)
pivot = pivot.sort_values("합계", ascending=False)

st.caption("두 시설이 모두 있는 자치구는 막대가 나란히 표시됩니다. (🟠 무더위쉼터 · 🟢 그늘막)")
chart_df = pivot.drop(columns="합계")
# 지도와 동일한 대비 색상: 무더위쉼터=빨강, 그늘막=파랑
bar_colors = [{SHELTER: "#F4A6A0", SHADE: "#9BD4C7"}[c] for c in chart_df.columns]
st.bar_chart(chart_df, color=bar_colors)

# 자치구별 온열질환 사망자수(2025 연보) 병합
pivot["온열질환 사망자수(2025)"] = (
    pivot.index.to_series().map(SEOUL_GU_DEATHS_2025).fillna(0).astype(int)
)

# 두 시설이 모두 존재하는(겹치는) 자치구 강조
if SHELTER in pivot.columns and SHADE in pivot.columns:
    both = pivot[(pivot[SHELTER] > 0) & (pivot[SHADE] > 0)]
    st.markdown(
        f"**무더위쉼터와 그늘막이 모두 있는 자치구: {len(both)}곳**  "
        f"(전체 {pivot.shape[0]}개 자치구 중)"
    )
    st.dataframe(
        both.rename_axis("자치구").reset_index(),
        width="stretch", hide_index=True,
    )

st.divider()

# ── 2025년 온열질환 신고현황 (질병관리청 연보) ──────────────
st.subheader("🌡️ 2025년 서울 온열질환 신고현황 (질병관리청 연보)")

m1, m2, m3 = st.columns(3)
m1.metric("서울 온열질환 신고수", f"{SEOUL_HEAT_2025['신고수']:,}명")
m2.metric("서울 온열질환 사망자수", f"{SEOUL_HEAT_2025['사망자수']:,}명")
m3.metric("사망 발생 자치구", f"{len(SEOUL_GU_DEATHS_2025)}곳")

st.caption(
    "⚠️ 연보의 신고수는 광역(시도) 단위까지만 집계되어 서울 합계(378명)만 존재합니다. "
    "자치구별 세부 수치는 '추정 사망 신고사례'의 사망자수만 확인 가능합니다."
)

death_df = (
    pd.Series(SEOUL_GU_DEATHS_2025, name="사망자수")
    .rename_axis("자치구").reset_index()
    .sort_values("사망자수", ascending=False)
)
st.markdown("**자치구별 온열질환 사망자수** (지도에도 표시됩니다)")
st.dataframe(death_df, width="stretch", hide_index=True)

st.divider()

# ── 통합 지도 (시설 + 온열질환 신고수/사망자수) ─────────────
st.subheader("🗺️ 통합 위치 지도")
st.caption(
    f"🟠 {SHELTER}   🟢 {SHADE}   🔴 온열질환 사망(자치구별)"
)

# 자치구 중심점: 전체 시설 좌표의 평균 (온열질환 마커 위치 계산용)
geo = all_df.dropna(subset=["lat", "lon"])
geo = geo[geo["lat"].between(37.0, 38.0) & geo["lon"].between(126.0, 128.0)]
gu_center = geo.groupby("자치구")[["lat", "lon"]].mean()

# 1) 시설 포인트 (필터 적용)
map_df = fdf.dropna(subset=["lat", "lon"]).copy()
map_df = map_df[map_df["lat"].between(37.0, 38.0) & map_df["lon"].between(126.0, 128.0)]
facility_pts = map_df[["lat", "lon"]].copy()
facility_pts["color"] = map_df["데이터종류"].map({SHELTER: "#F4A6A0", SHADE: "#9BD4C7"})
facility_pts["size"] = 30

layers = [facility_pts]

# 2) 온열질환 사망자수 마커: 자치구 중심점, 사망자수에 비례한 크기 (빨강)
death_rows = []
for gu, cnt in SEOUL_GU_DEATHS_2025.items():
    if gu in gu_center.index and (not sel_gu or gu in sel_gu):
        death_rows.append({
            "lat": gu_center.loc[gu, "lat"],
            "lon": gu_center.loc[gu, "lon"],
            "color": "#D7263D",
            "size": 250 * cnt,
        })
if death_rows:
    layers.append(pd.DataFrame(death_rows))

final_map = pd.concat(layers, ignore_index=True)
if len(final_map):
    st.map(final_map, latitude="lat", longitude="lon", color="color", size="size")
    st.caption("🔴 원의 크기 = 자치구별 온열질환 사망자수")
else:
    st.info("표시할 위치 데이터가 없습니다.")

st.divider()

# ── 상세 테이블 ────────────────────────────────────────────
st.subheader("📋 상세 목록")
st.dataframe(
    fdf[["데이터종류", "명칭", "자치구", "세부유형", "도로명주소"]],
    width="stretch", hide_index=True,
)

st.download_button(
    "⬇️ 필터 결과 CSV 다운로드",
    fdf.to_csv(index=False).encode("utf-8-sig"),
    file_name="폭염대응시설_필터결과.csv",
    mime="text/csv",
)
