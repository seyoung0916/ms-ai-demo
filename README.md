# Pressm AI

Pressm AI는 언론홍보 업무를 도와주는 **AI 홍보 비서 시스템**

보도자료를 자동으로 써주고,  
조간 스크랩을 요약해주며,  
언론 반응까지 분석해주는 똑똑한 AI입니다.

---

## 📌 프로젝트 소개

- **프로젝트 이름:** Pressm AI (프리즘 AI)
- **목표:**  
  언론홍보의 주요 업무

  - 보도자료 작성 및 메일, MMS 전송
  - 기사 스크랩 정리 및 발송
  - 언론 반응 분석

  세 가지 일에 대한 자동화

---

## 📌 이름과 의미

- **Pressm** = **Press + m**
  - `Press`: 언론, 보도자료
  - `m`: mind / machine / media — AI의 지능과 기술을 상징
- 발음은 **“프리즘”**
  → 언론 데이터를 프리즘 AI에 통과시키면 인사이트(빛)가 나온다는 뜻 ✨

---

## 💡 아이디어 핵심

| 기존 방식                 | Pressm AI 방식                      |
| ------------------------- | ----------------------------------- |
| 기자용 보도자료 직접 작성 | AI가 초안과 제목을 자동으로 생성    |
| 기사 수동 검색·스크랩     | AI가 뉴스 API로 자동 수집           |
| 수작업 요약/보고          | AI가 핵심 문장 3줄 요약과 감성 분석 |

👉 **“홍보 담당자의 시간을 절반으로 줄여주는 AI”**

---

## 📌 주요 기능

### 1. 보도자료 자동 작성 (Auto Write)

- 보도자료로 내보낼 참고 문서를 등록하면 AI가 제목, 서브제목, 본문 초안을 자동 생성
- 매체 톤(경제 / IT / 사회)에 맞춰 문체 조정 가능

### 2. 뉴스 자동 스크랩 (Auto Scrap)

- **Bing News Search API**를 이용해 키워드(회사명·브랜드·이슈)로 매일 뉴스를 자동 수집
- 수집된 기사는 **제목 / 요약(스니펫) / 매체명 / 발행 시각 / 원문 링크** 정보로 정리
- 매일 수집된 내용은 자동으로 날짜별로 구분되어  
  **`news_pdf/2025-10-23.pdf`** 와 같은 형식의 **PDF 파일**로 저장
- PDF에는 기사 **캡처본과 요약문을 포함**
- 필요 시 OpenAI 모델을 이용해 각 기사별로 **3줄 요약** 또는 **감성 분석(긍정 / 부정 / 중립)** 을 추가 가능

  > 💡 예시
  >
  > - `모듈랩스, AI 시스템 공개…업계 관심↑`
  > - `경영진 인터뷰, “데이터 중심 조직으로 간다”`
  > - `AI 관련 정책 변화 기사 12건 감지 (긍정 9 | 부정 1 | 중립 2)`

### 3. 반응 분석 (Media Pulse)

- AI가 수집된 기사들의 긍정/부정/중립을 분석해서  
  “이번 보도자료의 반응이 어땠는지” 자동으로 보여줌

---

## 📌 기대 효과

| 효과           | 설명                                                |
| -------------- | --------------------------------------------------- |
| 업무 시간 단축 | 보도자료 작성·요약·정리에 쓰는 시간을 50% 이상 절약 |
| 실수 줄이기    | AI가 빠뜨린 부분을 자동 체크                        |
| 반응 파악      | 언론 반응을 숫자와 그래프로 한눈에 확인             |
| 전략 강화      | 어떤 톤의 보도자료가 효과적인지 데이터로 알 수 있음 |

---

## 📌 사용 기술

### 1️⃣ Azure OpenAI + Grounding Agent

- Azure OpenAI의 **GPT 모델**을 활용해 자연어 질의 기반으로 뉴스 정보를 요청
- `BingGroundingTool`을 에이전트에 연결하여 AI가 Bing News 데이터를 직접 검색·가공
- 프롬프트 설계 시, JSON 형식으로만 응답하도록 강제하여 결과 파싱 및 후처리 안정성 확보

### 2️⃣ Azure Identity & AI Project SDK

- `DefaultAzureCredential()`을 사용해 **Keyless 인증** 기반으로 Azure Foundry에 접근  
  (로컬 개발 시는 환경 변수 기반)
- `AIProjectClient`를 통해 프로젝트 단위에서 에이전트 및 연결(Connection) 관리

### 3️⃣ Streamlit 인터페이스

- 사용자가 **검색 질의, 기간(freshness), 언어(market)** 등을 직접 지정
- 뉴스 검색, 요약, 스크랩, 저장까지 한 화면에서 처리 가능
- 결과는 즉시 화면에 출력되며 **CSV / JSON 다운로드**, **Azure Blob 업로드** 기능 포함

### 4️⃣ Azure Blob Storage

- 수집된 뉴스 데이터를 **DOCX** 형식으로 변환 후 Blob에 저장  
  (PDF는 한글 폰트 이슈로 DOCX로 전환)
- **SAS URL**을 생성해 다운로드 링크 제공
- 파일 구조 예시:  
  /news/json/2025-10-30/pressm_103001.json  
  /csv/2025-10-30/pressm_103001.csv.  
  /docx/2025-10-30/pressm_KT.docx.  
  (예시는 실제 컨테이너 내부 경로 형태이며, 날짜·검색어에 따라 자동 생성)

---

## 📌 개발 과정 및 문제 해결

### `Bing Grounding 연결 오류 (401 Unauthorized)`

- **문제:**  
  Grounding 연결 시  
  Failed to call Get Bing Grounding Search Results API with status 401  
  오류 발생
- **원인:**  
  Bing 리소스를 _Custom Search_ 로 잘못 생성하거나,  
  Foundry 프로젝트의 Managed Identity가 Bing 리소스에 접근 권한이 없었음
- **해결:**
  - 리소스를 **Bing Search** 로 새로 생성
  - Foundry 프로젝트의 Managed Identity에  
    **Cognitive Services User** 역할(Role) 부여
  - 이후 Connections에서 “Grounding with Bing Search” 재연결로 해결

### `JSON 파싱 실패 (null, None, 코드펜스 등)`

- **문제:**  
  모델 응답이 JSON 대신 텍스트나 null 로 오는 경우 발생
- **해결:**  
   `_extract_json_array()` 로직 개선
  - 코드펜스(````json ... `````) 제거
  - null / None 응답 시 빈 배열 [] 로 대체
  - JSON 디코딩 실패 시 400자 이내 미리보기 출력

### `한글 폰트 깨짐 (PDF 생성)`

- **문제:**  
  ReportLab 기본 폰트에서 한글 미지원 → PDF 내 텍스트 깨짐
- **해결:**  
   PDF 대신 **DOCX 변환 저장**으로 대체
  - python-docx 활용
  - 한글 폰트 호환성 확보
  - Azure Blob Storage에 .docx 파일 업로드
  - 추후 pdf 업로드 기능으로 보완 예정

### `뉴스 결과가 적거나 0건으로 반환`

- **문제:**  
  Bing Grounding이 freshness/market 옵션만으로 결과 제한
- **해결:**
  - **멀티패스 검색(search_news_multi)** 추가
  - site 필터 자동 제거 및 단순화 쿼리 반복 호출
  - `KT` → `(KT) AND (site:zdnet.co.kr OR site:etnews.com ...)` 형태로 보강

---

## 📌 확장성 및 향후 계획

### 자동 보도자료 작성 기능 고도화

- 작성한 보도자료에 대한 톤 보정 및 검토
- 유사도 판단 기능
- 언론사별 톤(경제지 / IT / 사회) 맞춤 문체 모델 추가
- 생성된 보도자료를 바로 이메일 또는 MMS로 전송

### 스크랩 확장 및 고급 요약

- Bing Grounding 기반 뉴스 검색에 더해 언론사 RSS / 포털 API 연동 확장
- 기존에 보내는 언론스크랩과 같이 첫 장 요약 + 캡처본과 함께 기사 요약본 제공

### 미디어 반응 분석 대시보드

- 수집된 기사 데이터를 Azure Cognitive Services의 Text Analytics API로 감성 분석
- 긍정/부정 비율, 주요 단어 클라우드, 기자별 빈도 시각화
- Streamlit 내 그래프 시각화(Plotly 기반)

### 저장 및 관리 자동화

- 뉴스 스크랩 결과를 날짜별 DOCX로 자동 저장
- Azure Blob Storage 내 구조 예시:  
  /news/docx/2025-10-30/pressm_KT.docx
- Azure Table / Cosmos DB로 메타데이터 관리
- 향후 검색 가능한 RAG 인덱스(Azure AI Search) 구축

---
