from __future__ import annotations


import os, json, io, datetime, traceback
from typing import Optional, Tuple, List
from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions,
    ContentSettings,
)
from azure.core.exceptions import (
    ResourceNotFoundError,
    HttpResponseError,
    ClientAuthenticationError,
)

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    from docx import Document
    from docx.shared import Pt
    from docx.oxml.ns import qn
except Exception:
    # python-docx may not be installed; functions that use it should handle ImportError at runtime
    Document = None
    Pt = None
    qn = None
import re

# ── ENV ─────────────────────────────────────────────────────────
CONN_STR = (os.getenv("AZURE_STORAGE_CONNECTION_STRING") or "").strip()
ACCOUNT_NAME = (os.getenv("AZURE_STORAGE_ACCOUNT") or "").strip()
ACCOUNT_KEY = (os.getenv("AZURE_STORAGE_KEY") or "").strip()
CONTAINER = (os.getenv("AZURE_STORAGE_CONTAINER") or "news").strip()

_client: Optional[BlobServiceClient] = None


# ── Core Client ─────────────────────────────────────────────────
def _svc() -> BlobServiceClient:
    """
    우선순위:
      1) Connection String
      2) AccountName + AccountKey
    """
    global _client
    if _client:
        return _client

    if CONN_STR:
        _client = BlobServiceClient.from_connection_string(CONN_STR)
        return _client

    if not ACCOUNT_NAME or not ACCOUNT_KEY:
        raise RuntimeError(
            "스토리지 인증 정보가 없습니다. "
            "AZURE_STORAGE_CONNECTION_STRING 또는 (AZURE_STORAGE_ACCOUNT + AZURE_STORAGE_KEY) 를 설정하세요."
        )

    account_url = f"https://{ACCOUNT_NAME}.blob.core.windows.net"
    _client = BlobServiceClient(account_url=account_url, credential=ACCOUNT_KEY)
    return _client


def _download_noto_font(font_dir: str = "./fonts") -> Optional[str]:
    """
    NotoSansKR-Regular.otf 폰트를 자동 다운로드하여 경로 반환
    """
    # Use the googlefonts 'noto-cjk' raw file URL (raw content) to download the OTF file
    font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/KR/NotoSansKR-Regular.otf"
    os.makedirs(font_dir, exist_ok=True)
    font_path = os.path.join(font_dir, "NotoSansKR-Regular.otf")
    if not os.path.exists(font_path):
        try:
            import requests

            r = requests.get(font_url)
            r.raise_for_status()
            with open(font_path, "wb") as f:
                f.write(r.content)
        except Exception as e:
            print(f"폰트 다운로드 실패: {e}")
            return None
    return font_path


def _find_korean_font_path() -> Optional[str]:
    """
    한글 폰트 경로 탐색:
      1) .env: KOREAN_FONT_PATH 지정 시 우선
      2) macOS/Windows/리눅스에서 흔한 경로 추정
      3) 없으면 None (Helvetica 사용) → 일부 한글이 깨질 수 있음
    """
    env_path = (os.getenv("KOREAN_FONT_PATH") or "").strip()
    if env_path and os.path.exists(env_path):
        return env_path

    # 자동 다운로드 시도
    noto_font = _download_noto_font()
    if noto_font and os.path.exists(noto_font):
        return noto_font

    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/Apple SD Gothic Neo.ttf",
        "/Library/Fonts/NotoSansCJKkr-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
        "C:\\Windows\\Fonts\\malgun.ttf",
        "C:\\Windows\\Fonts\\malgunbd.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansKR-Regular.otf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _register_korean_font(font_name: str = "KFONT") -> Optional[str]:
    """
    ReportLab에 한글 폰트 등록. 성공 시 font_name 반환, 실패 시 None.
    """
    try:
        fp = _find_korean_font_path()
        if not fp:
            return None
        pdfmetrics.registerFont(TTFont(font_name, fp))
        return font_name
    except Exception:
        return None


def generate_pdf_bytes(
    items: List[dict],
    *,
    title: str,
    query: str,
    freshness: str,
    market: str,
    generated_at: Optional[str] = None,
) -> bytes:
    """
    뉴스 항목을 간단한 표/문단으로 PDF 렌더링하여 바이트 반환.
    - 한글 폰트가 없으면 Helvetica로 진행(일부 글자 깨질 수 있음)
    - 폰트 파일이 있으면 .env KOREAN_FONT_PATH에 지정 권장
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36
    )

    font_name = _register_korean_font() or "Helvetica"
    styles = getSampleStyleSheet()

    base = {
        "fontName": font_name,
        "fontSize": 11,
        "leading": 16,
    }
    # base에서 중복 키 제거 후 전달
    base_title = {
        k: v for k, v in base.items() if k not in ("fontSize", "leading", "spaceAfter")
    }
    style_title = ParagraphStyle(
        "title", **base_title, fontSize=16, leading=22, spaceAfter=12
    )
    style_sub = ParagraphStyle(
        "sub", **base, textColor=colors.HexColor("#555555"), spaceAfter=8
    )
    style_cell = ParagraphStyle("cell", **base)

    story: List = []
    story.append(Paragraph(title, style_title))
    subtitle = f"Query: {query}  |  Freshness: {freshness}  |  Market: {market}"
    if generated_at:
        subtitle += f"  |  Generated: {generated_at}"
    story.append(Paragraph(subtitle, style_sub))
    story.append(Spacer(1, 6))

    # 표 데이터: 헤더 + 행들
    data = [["제목", "매체/시간", "링크"]]
    for it in items:
        title_p = Paragraph((it.get("title") or "").replace("\n", " "), style_cell)
        meta = f"{it.get('source') or '-'} / {it.get('published') or '-'}"
        meta_p = Paragraph(meta, style_cell)
        url = it.get("url") or "-"
        # 링크는 그냥 텍스트로 (PDF 클릭링크까지 구현하려면 <link> 태그 사용 가능)
        url_p = Paragraph(url.replace(" ", ""), style_cell)
        data.append([title_p, meta_p, url_p])

    table = Table(data, colWidths=[250, 120, 150])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f3f6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#222222")),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#fbfcfe")],
                ),
            ]
        )
    )
    story.append(table)

    # 폰트 경고 (옵션)
    if font_name == "Helvetica":
        story.append(Spacer(1, 6))
        warn = "⚠️ 시스템에 한글 폰트가 없어 일부 문자가 깨질 수 있습니다. .env의 KOREAN_FONT_PATH에 한글 폰트 경로를 지정하세요."
        story.append(Paragraph(warn, style_sub))

    doc.build(story)
    return buf.getvalue()


# ── DOCX 변환 ──────────────────────────────────────────────────
def generate_docx_bytes(
    items: List[dict],
    *,
    title: str,
    query: str,
    freshness: str,
    market: str,
    generated_at: Optional[str] = None,
) -> bytes:
    """
    뉴스 항목을 docx(워드) 파일로 변환하여 바이트 반환. 한글 깨짐 없음.
    """
    if Document is None:
        raise RuntimeError(
            "python-docx가 설치되어 있지 않습니다. 'python-docx' 패키지를 설치하세요."
        )

    doc = Document()
    # 한글 스타일 지정 (맑은 고딕을 기본으로 시도)
    try:
        style = doc.styles["Normal"]
        font = style.font
        font.name = "맑은 고딕"
        font.size = Pt(11)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "맑은 고딕")
    except Exception:
        # 일부 환경에서는 스타일 변경이 실패할 수 있으나 파일 자체는 생성됨
        pass

    doc.add_heading(title, level=0)
    subtitle = f"Query: {query}  |  Freshness: {freshness}  |  Market: {market}"
    if generated_at:
        subtitle += f"  |  Generated: {generated_at}"
    doc.add_paragraph(subtitle)

    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "제목"
    hdr_cells[1].text = "매체/시간"
    hdr_cells[2].text = "링크"

    for it in items:
        row_cells = table.add_row().cells
        row_cells[0].text = (it.get("title") or "").replace("\n", " ")
        meta = f"{it.get('source') or '-'} / {it.get('published') or '-'}"
        row_cells[1].text = meta
        row_cells[2].text = it.get("url") or "-"

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pdf_filename_from_query(query: str, include_date: bool = True) -> str:
    """
    검색조건(쿼리)로부터 파일명 생성.
    - 'pdf/' 폴더 아래
    - 하위 폴더 추가 생성 없음
    - 한글/영문/숫자만 남기고 나머지는 '_' 치환
    - 덮어쓰기 방지를 위해 기본은 날짜 접미사 붙임(원치 않으면 include_date=False)
    """
    q = (query or "").strip()
    if not q:
        q = "pressm"
    slug = re.sub(r"[^0-9A-Za-z가-힣]+", "_", q).strip("_")
    if include_date:
        today = datetime.datetime.now().strftime("%Y%m%d")
        return f"pdf/{slug}_{today}.pdf"
    return f"pdf/{slug}.pdf"


# ── Container ───────────────────────────────────────────────────
def ensure_container():
    svc = _svc()
    if not CONTAINER.islower():
        raise RuntimeError(
            "AZURE_STORAGE_CONTAINER는 반드시 소문자여야 합니다. (예: news)"
        )
    try:
        svc.create_container(CONTAINER)
    except Exception as e:
        s = str(e)
        if "ContainerAlreadyExists" in s or "Conflict" in s:
            return
        raise


# ── Upload / Download ───────────────────────────────────────────
def upload_json(obj, *, prefix: str = "news/json") -> Tuple[str, str]:
    """
    obj(JSON 직렬화)를 업로드. return (container, blob_path)
    """
    ensure_container()
    now = datetime.datetime.now().strftime("%Y-%m-%d")
    ts = datetime.datetime.now().strftime("%H%M%S")
    blob_path = f"{prefix}/{now}/pressm_{ts}.json"

    data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    content = ContentSettings(content_type="application/json; charset=utf-8")

    bc = _svc().get_blob_client(CONTAINER, blob_path)
    try:
        bc.upload_blob(data, overwrite=True, content_settings=content)
        return CONTAINER, blob_path
    except ClientAuthenticationError as e:
        raise RuntimeError(f"[auth] 인증 실패: {e}")
    except HttpResponseError as e:
        raise RuntimeError(f"[http] 업로드 실패: {e}")
    except Exception as e:
        raise RuntimeError(f"[blob] 업로드 실패: {e}\n{traceback.format_exc()}")


def download_bytes(container: str, blob: str) -> bytes:
    bc = _svc().get_blob_client(container=container, blob=blob)
    try:
        stream = bc.download_blob()
        return stream.readall()
    except ResourceNotFoundError as e:
        raise RuntimeError(f"Blob을 찾을 수 없습니다: {container}/{blob} — {e}")
    except Exception as e:
        raise RuntimeError(f"Blob 다운로드 실패: {e}")


# ── URL / SAS ───────────────────────────────────────────────────
def public_blob_url(container: str, blob: str) -> str:
    acct = ACCOUNT_NAME or (
        _svc().account_name if hasattr(_svc(), "account_name") else ""
    )
    return f"https://{acct}.blob.core.windows.net/{container}/{blob}"


def sas_url(container: str, blob: str, minutes: int = 120) -> Optional[str]:
    """
    키 방식에서 SAS 생성:
      - Connection String 있으면 그 계정키로
      - 아니면 Account Key로
    """
    from datetime import datetime, timedelta

    acct = ACCOUNT_NAME or (
        _svc().account_name if hasattr(_svc(), "account_name") else ""
    )
    if not acct:
        return None

    # 계정 키 확보
    ak = ACCOUNT_KEY
    if not ak and CONN_STR:
        # 연결문자열만 있고 ACCOUNT_KEY 환경변수는 비어있을 수 있음 → SAS 생성을 생략
        return None

    if not ak:
        return None

    token = generate_blob_sas(
        account_name=acct,
        account_key=ak,
        container_name=container,
        blob_name=blob,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(minutes=minutes),
    )
    return f"https://{acct}.blob.core.windows.net/{container}/{blob}?{token}"


def upload_pdf(pdf_bytes: bytes, blob_path: str) -> Tuple[str, str]:
    """
    이미 생성된 PDF 바이트를 지정한 blob_path에 업로드.
    blob_path 예: 'pdf/KT_20251030.pdf'
    """
    ensure_container()
    content = ContentSettings(content_type="application/pdf")
    bc = _svc().get_blob_client(CONTAINER, blob_path)
    try:
        bc.upload_blob(pdf_bytes, overwrite=True, content_settings=content)
        return CONTAINER, blob_path
    except ClientAuthenticationError as e:
        raise RuntimeError(f"[auth] 인증 실패: {e}")
    except HttpResponseError as e:
        raise RuntimeError(f"[http] 업로드 실패: {e}")
    except Exception as e:
        raise RuntimeError(f"[blob] 업로드 실패: {e}\n{traceback.format_exc()}")


def upload_docx(docx_bytes: bytes, blob_path: str) -> Tuple[str, str]:
    """
    이미 생성된 DOCX 바이트를 지정한 blob_path에 업로드.
    blob_path 예: 'docx/KT_20251030.docx'
    """
    ensure_container()
    content = ContentSettings(
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    bc = _svc().get_blob_client(CONTAINER, blob_path)
    try:
        bc.upload_blob(docx_bytes, overwrite=True, content_settings=content)
        return CONTAINER, blob_path
    except ClientAuthenticationError as e:
        raise RuntimeError(f"[auth] 인증 실패: {e}")
    except HttpResponseError as e:
        raise RuntimeError(f"[http] 업로드 실패: {e}")
    except Exception as e:
        raise RuntimeError(f"[blob] 업로드 실패: {e}\n{traceback.format_exc()}")


def make_docx_filename_from_query(query: str, include_date: bool = True) -> str:
    """
    검색조건(쿼리)로부터 DOCX 파일명 생성. 'docx/' 아래에 저장.
    """
    q = (query or "").strip()
    if not q:
        q = "pressm"
    slug = re.sub(r"[^0-9A-Za-z가-힣]+", "_", q).strip("_")
    if include_date:
        today = datetime.datetime.now().strftime("%Y%m%d")
        return f"docx/{slug}_{today}.docx"
    return f"docx/{slug}.docx"


# ── CSV 변환 ─────────────────────────────────────────────────────
def to_csv_bytes(items: List[dict]) -> bytes:
    import csv

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["title", "source", "published", "url", "snippet"])
    for it in items:
        w.writerow(
            [
                it.get("title", ""),
                it.get("source", ""),
                it.get("published", ""),
                it.get("url", ""),
                it.get("snippet", ""),
            ]
        )
    return buf.getvalue().encode("utf-8")
