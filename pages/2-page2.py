import os
import datetime
from io import BytesIO

# 서드파티 라이브러리
import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import matplotlib.pyplot as plt
import koreanize_matplotlib

st.title("주가 비교 서비스")
st.caption("Streamlit + FinanceDataReader로 만드는 간단한 종목 비교 대시보드")

st.markdown(
    """
### 서비스 소개
이 서비스는 **여러 종목의 주가 흐름을 같은 기간 기준으로 비교**할 수 있도록 도와주는 도구입니다.  
회사명 또는 종목코드를 입력하면 데이터를 자동으로 수집하고, **비교 차트와 핵심 지표**를 한눈에 보여줍니다.

### 제공 기능
- **최대 3개 종목 비교** (정규화 / 절대값)
- **기간 수익률, 변동성** 등 요약 지표 제공
- 비교 데이터 **엑셀 다운로드** 지원

### 사용 방법
1) 사이드바에 종목을 2~3개 입력  
2) 조회 기간 선택  
3) **비교하기** 버튼 클릭
"""
)

st.info("💡 팁: 회사명은 '삼성전자'처럼 정확히 입력하거나, 6자리 종목코드(예: 005930)를 입력해도 됩니다.")

