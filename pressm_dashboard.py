import streamlit as st
from news_scrap_demo import render_news_scrap_demo
from press_release_from_doc_demo import render_press_release_demo

st.set_page_config(page_title="Pressm AI 대시보드", layout="wide")
st.title("Pressm AI — 홍보 비서 대시보드")

# 탭 구성
tab1, tab2 = st.tabs(["보도자료 생성", "뉴스 스크랩"])

# 탭별로 각 파일의 함수 호출
with tab1:
    render_press_release_demo()

with tab2:
    render_news_scrap_demo()
