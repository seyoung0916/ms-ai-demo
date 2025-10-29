import streamlit as st
from press_release import draft_press_release

st.set_page_config(page_title="Pressm AI - 보도자료 생성", layout="centered")
st.title("📰 Pressm AI — 보도자료 자동 생성")

# 입력 폼
keywords = st.text_area("핵심 키워드", "신제품 출시, 11월 론칭, 가격 29만원")
tone = st.selectbox("매체 톤 선택", ["경제", "IT", "사회"])

if st.button("보도자료 생성하기"):
    with st.spinner("AI가 작성 중입니다..."):
        result = draft_press_release(keywords, tone)
    st.success("완료!")
    st.markdown(result)
