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


def get_krx_company_list() -> pd.DataFrame:
    try:
        # 파이썬 및 인터넷의 기본 문자열 인코딩 방식- UTF-8
        url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
        # MS 프로그램들은 cp949 / 구 몇몇 파일들의 인코딩 방식: EUC-KR
        df_listing = pd.read_html(url, header=0, flavor='bs4', encoding='EUC-KR')[0]
        
        # 필요한 컬럼만 추출 및 종목코드 6자리 포맷 맞추기
        df_listing = df_listing[['회사명', '종목코드']].copy()
        df_listing['종목코드'] = df_listing['종목코드'].apply(lambda x: f'{x:06}')
        return df_listing
    except Exception as e:
        st.error(f"상장사 명단을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame(columns=['회사명', '종목코드'])

def get_stock_code_by_company(company_name: str) -> str:
    # 만약 입력값이 숫자 6자리라면 그대로 반환
    if company_name.isdigit() and len(company_name) == 6:
        return company_name
    
    company_df = get_krx_company_list()
    codes = company_df[company_df['회사명'] == company_name]['종목코드'].values
    if len(codes) > 0:
        return codes[0]
    else:
        raise ValueError(f"'{company_name}'을 찾을 수 없습니다. 종목코드 6자리를 직접 입력해보세요.")

company_name = st.sidebar.text_input('조회할 회사를 입력하세요')
# https://docs.streamlit.io/develop/api-reference/widgets/st.date_input

today = datetime.datetime.now()
jan_1 = datetime.date(today.year, 1, 1)

selected_dates = st.sidebar.date_input(
    '조회할 날짜를 입력하세요',
    (jan_1, today),
    format="MM.DD.YYYY",
)

# st.write(selected_dates)

confirm_btn = st.sidebar.button('조회하기') # 클릭하면 True

# --- 메인 로직 ---
if confirm_btn:
    if not company_name: # '' 
        st.warning("조회할 회사 이름을 입력하세요.")
    else:
        try:
            with st.spinner('데이터를 수집하는 중...'):
                stock_code = get_stock_code_by_company(company_name)
                start_date = selected_dates[0].strftime("%Y%m%d")
                end_date = selected_dates[1].strftime("%Y%m%d")
                
                price_df = fdr.DataReader(stock_code, start_date, end_date)
                
            if price_df.empty:
                st.info("해당 기간의 주가 데이터가 없습니다.")
            else:
                st.subheader(f"[{company_name}] 주가 데이터")
                st.dataframe(price_df.tail(10), width="stretch")

                import matplotlib.dates as mdates
                from matplotlib.ticker import FuncFormatter

                # Matplotlib 시각화 (개선 버전)
                plot_df = price_df.copy()
                plot_df = plot_df.reset_index()  # Date가 인덱스일 가능성 대비

                # 날짜 컬럼 이름이 보통 Date/날짜/Datetime 등으로 올 수 있어서 안전 처리
                date_col = plot_df.columns[0]
                plot_df[date_col] = pd.to_datetime(plot_df[date_col])

                plot_df["MA5"] = plot_df["Close"].rolling(5).mean()
                plot_df["MA20"] = plot_df["Close"].rolling(20).mean()
                plot_df["MA60"] = plot_df["Close"].rolling(60).mean()

                has_volume = "Volume" in plot_df.columns and plot_df["Volume"].notna().any()

                if has_volume:
                    fig, (ax1, ax2) = plt.subplots(
                        2, 1, figsize=(12, 7),
                        gridspec_kw={"height_ratios": [3, 1]},
                        sharex=True
                    )
                else:
                    fig, ax1 = plt.subplots(figsize=(12, 5))
                    ax2 = None

                # ---- 가격 라인 + 이동평균 ----
                ax1.plot(plot_df[date_col], plot_df["Close"], linewidth=1.8, label="Close")
                ax1.plot(plot_df[date_col], plot_df["MA5"], linewidth=1.2, label="MA5")
                ax1.plot(plot_df[date_col], plot_df["MA20"], linewidth=1.2, label="MA20")
                ax1.plot(plot_df[date_col], plot_df["MA60"], linewidth=1.2, label="MA60")

                # 최고/최저/마지막 값 마커
                high_idx = plot_df["Close"].idxmax()
                low_idx = plot_df["Close"].idxmin()
                last_idx = plot_df.index[-1]

                ax1.scatter(plot_df.loc[high_idx, date_col], plot_df.loc[high_idx, "Close"], s=50, label="High")
                ax1.scatter(plot_df.loc[low_idx, date_col], plot_df.loc[low_idx, "Close"], s=50, label="Low")
                ax1.scatter(plot_df.loc[last_idx, date_col], plot_df.loc[last_idx, "Close"], s=50, label="Last")

                # 값 라벨(너무 겹치면 주석만 빼도 됨)
                ax1.annotate(f"{plot_df.loc[high_idx, 'Close']:.0f}",
                            (plot_df.loc[high_idx, date_col], plot_df.loc[high_idx, "Close"]),
                            textcoords="offset points", xytext=(6, 6), fontsize=9)
                ax1.annotate(f"{plot_df.loc[low_idx, 'Close']:.0f}",
                            (plot_df.loc[low_idx, date_col], plot_df.loc[low_idx, "Close"]),
                            textcoords="offset points", xytext=(6, -14), fontsize=9)
                ax1.annotate(f"{plot_df.loc[last_idx, 'Close']:.0f}",
                            (plot_df.loc[last_idx, date_col], plot_df.loc[last_idx, "Close"]),
                            textcoords="offset points", xytext=(6, 6), fontsize=9)

                # ---- 축/그리드/포맷 ----
                ax1.set_title(f"{company_name} 종가 추이", fontsize=15)
                ax1.set_ylabel("Price")

                ax1.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)

                # y축 천 단위 콤마
                ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:,.0f}"))

                # x축 날짜 포맷 (너무 촘촘하면 자동으로 간격 조절됨)
                ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
                ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))

                ax1.legend(loc="upper left", ncols=3, frameon=True)

                # ---- 거래량 ----
                if has_volume and ax2 is not None:
                    ax2.bar(plot_df[date_col], plot_df["Volume"])
                    ax2.set_ylabel("Volume")
                    ax2.grid(True, linestyle="--", linewidth=0.5, alpha=0.4)
                    ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:,.0f}"))

                fig.autofmt_xdate(rotation=30, ha="right")
                fig.tight_layout()
                st.pyplot(fig)


                # 엑셀 다운로드 기능
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    price_df.to_excel(writer, index=True, sheet_name='Sheet1')
                st.download_button(
                    label="📥 엑셀 파일 다운로드",
                    data=output.getvalue(),
                    file_name=f"{company_name}_주가.xlsx",
                    mime="application/vnd.ms-excel"
                )
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")


