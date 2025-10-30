# ms-ai-demo/news_scraper.py
import os, json, time
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import BingGroundingTool


# =========================
# Env & Globals
# =========================
ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"  # .env가 같은 폴더에 있을 때
load_dotenv(dotenv_path=ENV_PATH, override=True)

PROJECT_ENDPOINT = (os.getenv("AZURE_AI_PROJECT_ENDPOINT") or "").strip()
MODEL_DEPLOYMENT = (os.getenv("MODEL_DEPLOYMENT") or "").strip()
BING_CONN_NAME = (os.getenv("BING_CONNECTION_NAME") or "").strip()
DEBUG = (os.getenv("DEBUG") or "0").strip() in ("1", "true", "True")


class NewsError(Exception):
    pass


_credential: Optional[DefaultAzureCredential] = None
_project_client: Optional[AIProjectClient] = None
_agent_cache: Optional[dict] = None
_AGENT_NAME = "pressm-bing-agent"


# =========================
# Helpers
# =========================
def _log(msg: str):
    if DEBUG:
        print(f"[news_scraper] {msg}")


def _project() -> AIProjectClient:
    global _credential, _project_client
    if not PROJECT_ENDPOINT:
        raise NewsError("AZURE_AI_PROJECT_ENDPOINT가 비어 있습니다. (.env 확인)")
    if _project_client is None:
        _credential = DefaultAzureCredential()
        _project_client = AIProjectClient(
            endpoint=PROJECT_ENDPOINT, credential=_credential
        )
        _log(f"AIProjectClient initialized: endpoint={PROJECT_ENDPOINT}")
    return _project_client


def _get_bing_tool_definitions():
    """
    프로젝트 Connections에서 Grounding with Bing Search 연결의 connection_id를 찾아
    BingGroundingTool.definitions 반환.
    - BING_CONNECTION_NAME이 있으면 이름으로 조회
    - 없으면 Ground/Bing 계열 연결을 자동 검색해 첫 항목 사용
    """
    client = _project()

    # 1) 이름 지정된 경우
    if BING_CONN_NAME:
        try:
            conn = client.connections.get(BING_CONN_NAME)
            if not conn or not conn.get("id"):
                raise NewsError(f"연결 '{BING_CONN_NAME}'의 id를 찾지 못했습니다.")
            _log(
                f"BING_CONNECTION_NAME={BING_CONN_NAME}, 연결 조회: id={conn.get('id')}"
            )
            return BingGroundingTool(connection_id=conn["id"]).definitions
        except Exception as e:
            raise NewsError(
                f"프로젝트에서 연결 '{BING_CONN_NAME}'을 찾을 수 없습니다. "
                f"Connections 화면의 Name을 확인하세요. 상세: {e}"
            )

    # 2) 자동 검색
    candidates = []
    for c in _project().connections.list():
        ctype = (c.get("connectionType") or "").lower()
        if any(k in ctype for k in ("bing", "ground")):
            candidates.append(c)

    if not candidates:
        raise NewsError(
            "프로젝트에 Grounding/Bing 유형의 연결이 없습니다.\n"
            "- ai.azure.com → Project → Connections/Resources → "
            "Connect a Grounding with Bing Search 로 연결 추가"
        )

    # 첫 후보 사용
    conn = candidates[0]
    _log(
        f"Auto-picked connection: name={conn.get('name')} type={conn.get('connectionType')} id={conn.get('id')}"
    )
    if not conn.get("id"):
        raise NewsError("자동 선택된 연결에서 id를 찾지 못했습니다.")
    return BingGroundingTool(connection_id=conn["id"]).definitions


def _ensure_agent() -> dict:
    """
    같은 이름(_AGENT_NAME)의 에이전트가 있으면 재사용, 없으면 생성/업데이트
    """
    global _agent_cache
    client = _project()

    if _agent_cache is None:
        for ag in client.agents.list_agents():
            if ag.get("name") == _AGENT_NAME:
                _agent_cache = ag
                _log(f"Reusing existing agent: id={ag.get('id')}")
                break

    tools_def = _get_bing_tool_definitions()

    try:
        if _agent_cache is None:
            if not MODEL_DEPLOYMENT:
                raise NewsError("MODEL_DEPLOYMENT가 비어 있습니다. (.env의 배포명)")
            _agent_cache = client.agents.create_agent(
                model=MODEL_DEPLOYMENT,
                name=_AGENT_NAME,
                instructions=(
                    "너는 한국어 뉴스 리서처다. 필요할 때 Grounding with Bing Search 도구를 사용한다. "
                    "사용자 요청에 따라 최신 뉴스를 찾아, 오직 JSON 배열로만 응답하라. "
                    "허위 추정 금지, 불명확하면 빈 문자열로 둔다."
                ),
                tools=tools_def,
            )
            _log(f"Created agent: id={_agent_cache.get('id')}")
        else:
            _agent_cache = client.agents.update_agent(
                agent_id=_agent_cache["id"], tools=tools_def
            )
            _log(f"Updated agent tools: id={_agent_cache.get('id')}")
    except Exception as e:
        raise NewsError(
            "에이전트 생성/업데이트 실패.\n"
            "- Projects > Connections의 Grounding with Bing 연결 'Name'이 .env와 일치하는지\n"
            "- Deployments의 모델 배포명이 MODEL_DEPLOYMENT와 일치하는지\n"
            "- 현재 계정/구독/권한이 프로젝트와 일치하는지\n"
            f"상세: {e}"
        )
    return _agent_cache


def _run_and_wait(agent_id: str, prompt: str, timeout_sec: int = 180) -> str:
    """
    Run 생성 후 상태를 폴링해 최종 응답을 받는다.
    - 완료 상태 문자열이 'completed' 또는 'succeeded'로 올 수 있어 둘 다 허용
    """
    client = _project()
    thread = client.agents.threads.create()
    client.agents.messages.create(thread_id=thread["id"], role="user", content=prompt)

    # create_and_process로 즉시 실행
    run = client.agents.runs.create_and_process(
        thread_id=thread["id"], agent_id=agent_id
    )
    _log(f"Run created: run_id={run['id']}")

    start = time.time()
    TERMINAL_OK = {"completed", "succeeded"}
    TERMINAL_BAD = {"failed", "cancelled", "expired"}

    while True:
        r = client.agents.runs.get(thread_id=thread["id"], run_id=run["id"])
        status = (r.get("status") or "").lower()
        _log(f"Run status: {status}")

        if status in TERMINAL_OK:
            break
        if status in TERMINAL_BAD:
            last_err = r.get("last_error") or ""
            raise NewsError(f"에이전트 실행 실패: {status} {last_err}")

        if time.time() - start > timeout_sec:
            raise NewsError("에이전트 응답 대기 시간 초과")

        time.sleep(0.7)

    # ⬇⬇⬇ 메시지 추출은 while 바깥에서!
    try:
        msg = client.agents.messages.get_last_message_by_role(
            thread_id=thread["id"], role="assistant"
        )
    except Exception:
        msgs = list(client.agents.messages.list(thread_id=thread["id"]))
        msg = next(
            (
                m
                for m in reversed(msgs)
                if (m.get("role") if isinstance(m, dict) else getattr(m, "role", None))
                == "assistant"
            ),
            None,
        )

    if not msg:
        raise NewsError("assistant 메시지를 찾지 못했습니다.")

    parts = (
        msg.get("content", []) if isinstance(msg, dict) else getattr(msg, "content", [])
    ) or []
    texts: List[str] = []
    for p in parts:
        if isinstance(p, dict):
            t = p.get("text")
            if isinstance(t, dict):
                v = t.get("value")
                if isinstance(v, str) and v.strip():
                    texts.append(v.strip())
            v = p.get("value")
            if isinstance(v, str) and v.strip():
                texts.append(v.strip())
            continue

        txt_obj = getattr(p, "text", None)
        if txt_obj is not None:
            v = getattr(txt_obj, "value", None)
            if isinstance(v, str) and v.strip():
                texts.append(v.strip())
                continue
        v = getattr(p, "value", None)
        if isinstance(v, str) and v.strip():
            texts.append(v.strip())

    if not texts:

        def _safe_preview(o, limit=400):
            try:
                if not isinstance(o, (str, int, float, bool, type(None), list, dict)):
                    o = getattr(o, "__dict__", str(o))
                return json.dumps(o, ensure_ascii=False, default=str)[:limit] + "..."
            except Exception:
                return str(o)[:limit] + "..."

        preview = _safe_preview(parts)
        raise NewsError(f"응답 텍스트 없음. content parts 미리보기: {preview}")

    content = " ".join(texts).strip()
    if not content:
        raise NewsError("assistant 응답이 비어 있습니다.")

    return content


def _extract_json_array(text: str) -> Optional[str]:
    t = (text or "").strip()
    # 모델이 null/None 을 내놓는 경우 → 빈 배열 처리
    if t.lower() in ("null", "none"):
        return "[]"

    if t.startswith("```"):
        t = t.strip("`")
        t = t.split("\n", 1)[-1]

    l = t.find("[")
    r = t.rfind("]")
    if l != -1 and r != -1 and r > l:
        return t[l : r + 1]
    # 대괄호가 없어도, 이미 배열일 수 있음 (ex: "[]")
    if t == "[]" or (t.startswith("[") and t.endswith("]")):
        return t
    return None


def search_news(
    q: str, count: int = 10, freshness: str = "Week", market: str = "ko-KR"
) -> List[Dict[str, Any]]:
    """
    Grounding with Bing Search로 최신 뉴스 수집 → JSON 배열 파싱
    """
    if count < 1:
        count = 1
    if count > 50:
        count = 50

    agent = _ensure_agent()

    user_prompt = f"""
아래 조건으로 Grounding with Bing Search를 사용해 최신 뉴스를 찾아라.
- market: {market}
- freshness: {freshness}   # Day | Week | Month
- count: {count}

반드시 아래 '정확한' JSON 배열만 출력하라. 설명/주석/코드펜스/앞뒤 텍스트 모두 금지.
결과가 하나도 없으면 빈 배열 [] 만 출력하라.
[
  {{"title":"...", "snippet":"...", "source":"...", "published":"YYYY-MM-DDTHH:MM:SSZ", "url":"..."}}
]
질의: {q}
"""
    raw = _run_and_wait(agent_id=agent["id"], prompt=user_prompt, timeout_sec=180)

    raw_json = _extract_json_array(raw)
    if raw_json is None:
        retry_prompt = (
            user_prompt
            + "\n주의: 결과가 없으면 반드시 빈 배열 [] 만 출력하라. 다른 텍스트 금지."
        )
        raw2 = _run_and_wait(agent_id=agent["id"], prompt=retry_prompt, timeout_sec=180)
        raw_json = _extract_json_array(raw2)

    if raw_json is None:
        raw_json = "[]"

    try:
        data = json.loads(raw_json)
        if not isinstance(data, list):
            raise ValueError("응답이 리스트(JSON 배열)가 아닙니다.")
    except Exception as e:

        def _safe_preview(o, limit=400):
            try:
                return json.dumps(o, ensure_ascii=False, default=str)[:limit] + "..."
            except Exception:
                s = "" if o is None else str(o)
                return s[:limit] + "..."

        preview = _safe_preview(raw)
        raise NewsError(f"JSON 파싱 실패: {e}\n응답 미리보기: {preview}")

    items: List[Dict[str, Any]] = []
    for v in data:
        items.append(
            {
                "title": (v.get("title") or "").strip(),
                "snippet": (v.get("snippet") or "").strip(),
                "source": (v.get("source") or "").strip(),
                "published": (v.get("published") or "").strip(),
                "url": (v.get("url") or "").strip(),
            }
        )
    return items
