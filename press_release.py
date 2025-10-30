import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)


def _truncate(text: str, max_chars: int = 12000) -> str:
    # 긴 문서에 대한 토큰 초과 가능성 방지
    # 토큰 관리용 잘라내기
    if not text:
        return ""
    return text[:max_chars]


def draft_press_release(keywords: str, tone: str = "사회"):
    system = (
        "너는 한국 KT 회사 홍보실 직원이다. 제목(한 줄), 서브헤드(한 줄), 본문(3~5단락)을 작성하라. "
        "한국 언론 보도자료 포맷을 따르고, 사실/수치/인용은 [플레이스홀더]로 표기."
    )
    user = f"키워드: {keywords}\n매체 톤: {tone}\n출력: 제목/부제/본문"
    resp = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
    )
    return resp.choices[0].message.content


def draft_press_release_from_doc(doc_text: str, tone: str = "경제", angle: str = ""):
    """
    업로드 문서의 '사실'을 근거로 보도자료 초안 작성.
    - 문서에 없는 내용은 추정하지 말고 [확인 필요]로 표기.
    - 문서 인용이 필요한 경우, 근거 문장을 '근거:' 섹션에 모아 요약.
    """
    context = _truncate(doc_text)

    system = (
        "너는 한국 KT 회사 홍보실 직원이다. 제공된 문서 내용만 근거로 보도자료 초안을 작성한다."
        "한국 언론 보도자료 포맷을 따르고, 문서에 없는 수치/날짜/인용은 만들지 말고 [확인 필요]로 남겨라. "
        "출력 형식: 제목(한 줄) → 서브헤드(한 줄) → 본문(3~5단락) → '근거:' 섹션(핵심 사실 요약)."
    )
    angle_line = f"\n원하는 각도/포커스: {angle}" if angle else ""
    user = (
        f"[문서 내용 시작]\n{context}\n[문서 내용 끝]\n"
        f"매체 톤: {tone}{angle_line}\n"
        "요구: 문서 사실만 반영한 보도자료 초안"
    )

    resp = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,  # 문서 사실 준수 위해 낮춤
    )
    return resp.choices[0].message.content
