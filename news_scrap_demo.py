import streamlit as st
from news_scraper import search_news, NewsError

st.set_page_config(page_title="Pressm AI - 뉴스 스크랩(Agent)", layout="wide")
st.title("📰 Pressm AI — 뉴스 스크랩 (Grounding Agent 버전)")

with st.sidebar:
    st.caption("검색 옵션")
    q = st.text_area("키워드 / 질의", "KT", height=90)
    freshness = st.selectbox("기간(freshness)", ["Day", "Week", "Month"], index=0)
    count = st.slider("개수", 3, 30, 10, step=1)
    market = st.selectbox("시장/언어(market)", ["ko-KR", "en-US", "ja-JP"], index=0)
    st.caption("Tips: 질의 예) 회사명 OR 브랜드명 OR 특정 이슈")

col1, col2 = st.columns([1, 3])
with col1:
    run = st.button("스크랩 실행", use_container_width=True)
with col2:
    st.info(
        "에이전트가 Bing Grounding을 호출해 최신 뉴스를 JSON으로 반환합니다.", icon="ℹ️"
    )

if run:
    try:
        with st.spinner("에이전트 호출 중..."):
            items = search_news(q=q, count=count, freshness=freshness, market=market)
        st.success(f"가져온 기사: {len(items)}건")

        if not items:
            st.warning("결과가 없습니다. 질의를 바꾸거나 기간을 늘려보세요.")
        else:
            for it in items:
                st.markdown("---")
                st.markdown(f"**{it['title'] or '(제목 없음)'}**")
                meta = (
                    f"{it.get('source') or '출처 미상'} · {it.get('published') or ''}"
                )
                st.caption(meta)
                if it.get("snippet"):
                    st.write(it["snippet"])
                if it.get("url"):
                    st.markdown(f"[원문 보기]({it['url']})")

    except NewsError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"예상치 못한 오류: {e}")
