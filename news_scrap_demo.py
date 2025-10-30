# ms-ai-demo/news_scrap_demo.py
import json
import collections
from urllib.parse import urlparse
import streamlit as st

from news_scraper import search_news, search_news_multi, NewsError
from storage_utils import (
    upload_json,  # (현재 화면에서는 사용하지 않지만 import 유지해도 무방)
    sas_url,
    download_bytes,
    to_csv_bytes,
    public_blob_url,
    generate_docx_bytes,
    make_docx_filename_from_query,
    upload_docx,
)


def render_news_scrap_demo():

    # ── 유틸 ────────────────────────────────────────────────────────
    def _attach_site_filters(q: str, sites_text: str) -> str:
        """줄바꿈 입력된 사이트 목록을 site: 필터로 묶어 쿼리에 합성"""
        sites = [s.strip() for s in (sites_text or "").splitlines() if s.strip()]
        if not sites:
            return q
        site_expr = " OR ".join([f"site:{s}" for s in sites])
        return f"({q}) AND ({site_expr})"

    def _domain(u: str) -> str:
        try:
            netloc = urlparse(u or "").netloc.lower()
            return netloc.replace("www.", "")
        except Exception:
            return ""

    # ── 기본 UI ─────────────────────────────────────────────────────

    # 세션 상태 키 보장
    if "items" not in st.session_state:
        st.session_state["items"] = []
    if "blob_info" not in st.session_state:
        st.session_state["blob_info"] = None
    if "docx_blob_info" not in st.session_state:
        st.session_state["docx_blob_info"] = None

    # ── 검색 폼 (리런에도 상태 유지) ───────────────────────────────
    with st.form("search_form", clear_on_submit=False):
        st.caption("검색 옵션")
        q = st.text_area("키워드 / 질의", "KT", height=90)
        freshness = st.selectbox("기간(freshness)", ["Day", "Week", "Month"], index=2)
        count = st.slider("개수", 3, 30, 10, step=1)
        market = st.selectbox("시장/언어(market)", ["ko-KR", "en-US", "ja-JP"], index=0)
        st.caption("Tips: 질의 예) 회사명 OR 브랜드명 OR 특정 이슈")

        multi = st.checkbox("확장 검색(멀티패스)", value=True)
        target_results = st.slider("목표 결과 수", 10, 50, 20, step=5)

        preset = st.toggle("🇰🇷 한국 주요 IT/경제 매체 프리셋 사용", value=True)
        if preset:
            preset_sites = """
    news.naver.com
    zdnet.co.kr
    it.chosun.com
    etnews.com
    hankyung.com
    mk.co.kr
    yonhapnews.co.kr
    newsis.com
    news1.kr
    bloter.net
    seoul.co.kr
    hankookilbo.com
    inews24.com
    chosun.com
    joongang.co.kr
    donga.com
    hani.co.kr
    kyunghyang.com
    mt.co.kr
    edaily.co.kr
    moneys.co.kr
    heraldcorp.com
    ohmynews.com
    pressian.com
    segye.com
    munhwa.com
    asiatoday.co.kr
    ytn.co.kr
    jtbc.co.kr
    sbs.co.kr
    kbs.co.kr
    imbc.co.kr
    tvchosun.com
    hankooki.com
    kookje.co.kr
    busan.com
    """.strip()
            sites_text = st.text_area(
                "사이트 필터 (수정 가능)", preset_sites, height=150
            )
        else:
            sites_text = st.text_area("사이트 필터 (선택, 줄바꿈)", "", height=80)

        submit = st.form_submit_button("🔎 스크랩 실행", use_container_width=True)

    st.info(
        "에이전트가 Grounding with Bing Search를 호출해 최신 뉴스를 JSON으로 반환합니다.",
        icon="ℹ️",
    )

    # ── 액션: 검색 실행 ─────────────────────────────────────────────
    if submit:
        try:
            with st.spinner("에이전트 호출 중..."):
                compound_q = _attach_site_filters(q, sites_text)
                if multi:
                    items = search_news_multi(
                        q=compound_q,
                        count=count,
                        freshness=freshness,
                        market=market,
                        target_results=target_results,
                        max_rounds=3,
                    )
                else:
                    items = search_news(
                        q=compound_q, count=count, freshness=freshness, market=market
                    )
            st.session_state["items"] = items
            st.success(f"가져온 기사: {len(items)}건")
        except NewsError as e:
            st.error(str(e))
            st.session_state["items"] = []
        except Exception as e:
            st.error(f"예상치 못한 오류: {e}")
            st.session_state["items"] = []

    # ── 렌더: 항상 세션 상태 기반으로 표시 ─────────────────────────
    items = st.session_state.get("items", []) or []
    if not items:
        st.warning("결과가 없습니다. 질의를 바꾸거나 기간을 늘려보세요.")
    else:
        # 리스트 표시
        for it in items:
            st.markdown("---")
            st.markdown(f"**{it.get('title') or '(제목 없음)'}**")
            meta = f"{it.get('source') or '출처 미상'} · {it.get('published') or ''}"
            st.caption(meta)
            if it.get("snippet"):
                st.write(it["snippet"])
            if it.get("url"):
                st.markdown(f"[원문 보기]({it['url']})")

        # 출처 요약
        st.markdown("### 📚 수집 출처 요약")
        counter = collections.Counter(
            _domain(it.get("url", "")) for it in items if it.get("url")
        )
        cols = st.columns(3)
        for i, (dom, cnt) in enumerate(counter.most_common(9)):
            with cols[i % 3]:
                st.write(f"- **{dom}** × {cnt}")

        # ── 내보내기 / 저장 (CSV/JSON 다운로드 + DOCX Blob 업로드만) ─────────────
        st.markdown("### ⬇️ 내보내기 / ☁️ 저장")

        # CSV / JSON 다운로드
        c1, c2 = st.columns([1, 1])
        with c1:
            st.download_button(
                "CSV 다운로드",
                data=to_csv_bytes(items),
                file_name="pressm_news.csv",
                mime="text/csv",
                use_container_width=True,
                key="dl_csv",
            )
        with c2:
            st.download_button(
                "JSON 다운로드",
                data=json.dumps(items, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name="pressm_news.json",
                mime="application/json",
                use_container_width=True,
                key="dl_json",
            )

        # ── DOCX 업로드 전용 UI ──────────────────────────────────────────
        st.markdown("### 🧾 DOCX를 Blob에 업로드")

        # 파일명 제안 (쿼리 기준 + 날짜)
        suggest_name = make_docx_filename_from_query(q, include_date=True)

        # 사용자가 경로 수정 가능(컨테이너 내 경로)
        docx_blob_path = st.text_input(
            "DOCX 파일 경로 (컨테이너 내, 기본: docx/…):",
            value=suggest_name,
            help="예: docx/KT_20251030.docx — 반드시 'docx/' 아래에 저장됩니다.",
        )

        # DOCX 생성
        generated_at = __import__("datetime").datetime.now().__str__()
        docx_bytes = generate_docx_bytes(
            items,
            title="Pressm AI — 뉴스 스크랩 리포트",
            query=q,
            freshness=freshness,
            market=market,
            generated_at=generated_at,
        )

        # 업로드 버튼 (업로드만 남김)
        if st.button(
            "☁️ DOCX를 Blob에 업로드", use_container_width=True, key="upload_docx_btn"
        ):
            try:
                with st.spinner("DOCX 업로드 중..."):
                    path = (docx_blob_path or "").strip()
                    if not path or not path.lower().startswith("docx/"):
                        path = "docx/" + (path or "pressm_report.docx")
                    if not path.lower().endswith(".docx"):
                        path += ".docx"

                    container, blob = upload_docx(docx_bytes, path)
                    link = sas_url(container, blob, minutes=120) or public_blob_url(
                        container, blob
                    )

                    st.session_state["docx_blob_info"] = {
                        "container": container,
                        "blob": blob,
                        "link": link,
                    }
                st.success("DOCX 업로드 완료! 아래 링크로 열거나 다운로드할 수 있어요.")
                st.rerun()  # 업로드 후 즉시 재렌더링하여 링크/버튼 노출
            except Exception as e:
                import traceback

                st.error(f"DOCX 업로드 실패: {e}")
                st.exception(traceback.format_exc())

        # 업로드 결과 표시 (세션 유지)
        docx_blob_info = st.session_state.get("docx_blob_info")
        if docx_blob_info:
            st.info(
                f"DOCX Blob 경로: `{docx_blob_info['container']}/{docx_blob_info['blob']}`"
            )
            # 새 탭으로 열기(권장: SAS 있으면 바로 열림)
            st.markdown(
                f'<a href="{docx_blob_info["link"]}" target="_blank" rel="noopener noreferrer">🔗 DOCX 링크 새 탭으로 열기</a>',
                unsafe_allow_html=True,
            )

            # Blob에서 직접 내려받기(앱 내 버튼) — SAS/퍼블릭 여부 관계없이 시도
            data_docx = None
            try:
                data_docx = download_bytes(
                    docx_blob_info["container"], docx_blob_info["blob"]
                )
            except Exception as e:
                st.warning(f"Blob DOCX 직접 다운로드 준비 실패: {e}")
            if data_docx:
                st.download_button(
                    label="📥 Blob에서 DOCX 직접 다운로드",
                    data=data_docx,
                    file_name=docx_blob_info["blob"].split("/")[-1],
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="dl_docx_blob_direct",
                )
