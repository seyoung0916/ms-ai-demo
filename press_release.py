import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)


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


if __name__ == "__main__":
    print(draft_press_release("KT 해킹"))
