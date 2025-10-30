import streamlit as st
from doc_loader import load_text_from_file
from press_release import draft_press_release_from_doc


def render_press_release_demo():

    uploaded = st.file_uploader(
        "문서 업로드 (PDF / DOCX / TXT)", type=["pdf", "docx", "txt"]
    )
    tone = st.selectbox("매체 톤", ["경제", "IT", "사회"])
    angle = st.text_input(
        "각도/포커스 (선택)",
        placeholder="예: 투자 유치 중심 / 고객 가치 중심 / 기술 혁신 강조",
    )

    if uploaded and st.button("문서로 보도자료 생성"):
        with st.spinner("문서 분석 및 보도자료 작성 중..."):
            try:
                doc_text = load_text_from_file(uploaded, uploaded.name)
                if not doc_text.strip():
                    st.warning(
                        "문서에서 텍스트를 읽지 못했습니다. PDF 스캔본이면 OCR이 필요할 수 있어요."
                    )
                else:
                    result = draft_press_release_from_doc(
                        doc_text, tone=tone, angle=angle
                    )
                    st.success("완료!")
                    st.markdown(result)
            except Exception as e:
                st.error(f"에러: {e}")
