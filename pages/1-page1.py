# 표준 라이브러리
import os
import datetime
from io import BytesIO

# 서드파티 라이브러리
import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import matplotlib.pyplot as plt
import koreanize_matplotlib

# -----------------------------
# KRX 상장사 목록 / 종목코드 변환
# -----------------------------
@st.cache_data(show_spinner=False, ttl=60 * 60 * 12)  # 12시간 캐시
def get_krx_company_list() -> pd.DataFrame:
    url = "http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
    df_listing = pd.read_html(url, header=0, flavor="bs4", encoding="EUC-KR")[0]
    df_listing = df_listing[["회사명", "종목코드"]].copy()
    df_listing["종목코드"] = df_listing["종목코드"].apply(lambda x: f"{x:06}")
    return df_listing

def get_stock_code_by_company(company_or_code: str) -> str:
    s = (company_or_code or "").strip()
    if s.isdigit() and len(s) == 6:
        return s

    company_df = get_krx_company_list()
    codes = company_df[company_df["회사명"] == s]["종목코드"].values
    if len(codes) > 0:
        return codes[0]
    raise ValueError(f"'{s}'을(를) 찾을 수 없습니다. 회사명(정확히) 또는 6자리 종목코드를 입력하세요.")

# -----------------------------
# 데이터 로딩(캐시)
# -----------------------------
@st.cache_data(show_spinner=False, ttl=60 * 10)  # 10분 캐시
def load_price_df(code: str, start_yyyymmdd: str, end_yyyymmdd: str) -> pd.DataFrame:
    df = fdr.DataReader(code, start_yyyymmdd, end_yyyymmdd)
    return df

def normalize_to_100(close: pd.Series) -> pd.Series:
    close = close.dropna()
    if close.empty:
        return close
    base = close.iloc[0]
    return (close / base) * 100

# -----------------------------
# UI
# -----------------------------
st.title("📈 주가 비교 서비스 (최대 3종목)")

st.sidebar.subheader("비교할 종목 입력 (최대 3개)")
st.sidebar.caption("회사명(예: 삼성전자) 또는 6자리 종목코드(예: 005930)")

c1 = st.sidebar.text_input("종목 1", value="")
c2 = st.sidebar.text_input("종목 2", value="")
c3 = st.sidebar.text_input("종목 3 (선택)", value="")

today_dt = datetime.datetime.now()
jan_1 = datetime.date(today_dt.year, 1, 1)

selected_dates = st.sidebar.date_input(
    "조회 기간",
    (jan_1, today_dt.date()),
    format="MM.DD.YYYY",
)

compare_mode = st.sidebar.selectbox(
    "비교 방식",
    ["정규화 비교", "종가 비교"],
)

confirm_btn = st.sidebar.button("비교하기")

# -----------------------------
# 메인 로직
# -----------------------------
if confirm_btn:
    # 입력 정리
    raw_list = [c1, c2, c3]
    raw_list = [x.strip() for x in raw_list if x and x.strip()]
    raw_list = list(dict.fromkeys(raw_list))  # 중복 제거(입력 순서 유지)

    if len(raw_list) < 2:
        st.warning("최소 2개 종목을 입력해야 비교할 수 있어요.")
        st.stop()
    if len(raw_list) > 3:
        st.warning("최대 3개 종목까지만 비교할 수 있어요.")
        st.stop()

    # 날짜
    start_date = selected_dates[0].strftime("%Y%m%d")
    end_date = selected_dates[1].strftime("%Y%m%d")

    with st.spinner("데이터 수집/정리 중..."):
        # 각 종목의 (표시명, 코드, 가격DF) 수집
        items = []
        for x in raw_list:
            code = get_stock_code_by_company(x)
            df = load_price_df(code, start_date, end_date)
            if df.empty:
                st.warning(f"[{x}] 데이터가 없어서 제외했어요.")
                continue

            # label: 회사명 입력이면 회사명, 코드 입력이면 코드로 표시
            label = x
            items.append((label, code, df))

    if len(items) < 2:
        st.error("비교 가능한 종목이 2개 미만입니다. 기간/입력을 다시 확인해 주세요.")
        st.stop()

    # 비교용 데이터프레임 생성(날짜 인덱스 기준 outer join)
    compare_df = pd.DataFrame()
    summary_rows = []

    for label, code, df in items:
        # Close 기준
        close = df["Close"].copy()
        close.name = label

        # 정규화/절대값 선택
        if compare_mode.startswith("정규화"):
            series = normalize_to_100(close)
        else:
            series = close

        compare_df = compare_df.join(series, how="outer") if not compare_df.empty else series.to_frame()

        # 요약 지표
        close_clean = close.dropna()
        if not close_clean.empty:
            start_close = float(close_clean.iloc[0])
            end_close = float(close_clean.iloc[-1])
            period_return = (end_close / start_close - 1) * 100

            # 일간 수익률 변동성(표준편차)
            daily_ret = close_clean.pct_change().dropna()
            vol = float(daily_ret.std() * 100) if not daily_ret.empty else 0.0

            summary_rows.append({
                "종목": label,
                "코드": code,
                "시작 종가": round(start_close, 2),
                "종료 종가": round(end_close, 2),
                "기간 수익률(%)": round(period_return, 2),
                "일간 변동성(%)": round(vol, 2),
            })

    # 정렬/결측 처리
    compare_df = compare_df.sort_index()

    # -----------------------------
    # 출력: 요약 테이블
    # -----------------------------
    st.subheader("🧾 요약")
    summary_df = pd.DataFrame(summary_rows).sort_values("기간 수익률(%)", ascending=False)
    st.dataframe(summary_df, width="stretch")

    # -----------------------------
    # 출력: 비교 차트
    # -----------------------------
    st.subheader("📊 비교 차트")
    fig, ax = plt.subplots(figsize=(12, 6))
    for col in compare_df.columns:
        ax.plot(compare_df.index, compare_df[col], linewidth=2, label=col)

    ax.set_title("종목 비교" + (" (첫날=100 정규화)" if compare_mode.startswith("정규화") else " (종가 절대값)"))
    ax.set_ylabel("Index" if compare_mode.startswith("정규화") else "Close")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
    ax.legend(loc="upper left", ncols=2, frameon=True)
    fig.tight_layout()
    st.pyplot(fig)

    # -----------------------------
    # 다운로드: 비교 테이블 엑셀
    # -----------------------------
    st.subheader("📥 비교 데이터 다운로드")
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        compare_df.to_excel(writer, index=True, sheet_name="compare")
        summary_df.to_excel(writer, index=False, sheet_name="summary")

    st.download_button(
        label="엑셀 다운로드 (compare + summary)",
        data=output.getvalue(),
        file_name="stock_compare.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
