# Express Entry Dashboard

![Dashboard Preview](static/dashboard-preview.png)

Express Entry Dashboard는 캐나다 IRCC의 Express Entry 드로우 데이터를 수집·요약해, 신청자들이 추세를 빠르게 파악할 수 있도록 시각화한 Flask 기반 웹 애플리케이션입니다. 최근 드로우 내역부터 프로그램별 비중, CRS 컷오프 변화, 누적 선발량까지 한 곳에서 확인할 수 있습니다.

## 주요 기능
- **최근 드로우 현황**: 최신 10건의 드로우 번호, 날짜, 프로그램, 초청 인원, 컷오프 점수를 테이블로 제공합니다.
- **연도/월별 통계**: 연간·월간 선발 건수를 차트로 비교해 계절성과 운영 패턴을 파악할 수 있습니다.
- **프로그램 분포**: 프로그램별 드로우 횟수와 초청 인원 비중을 연도 단위로 분석합니다.
- **컷오프 추세**: 각 드로우의 CRS 컷오프, 5회 이동 평균, 초청 인원 수를 함께 시각화해 정책 변화 영향을 살펴볼 수 있습니다.
- **누적 모멘텀**: 드로우 횟수와 누적 초청 인원 추이를 동시에 보여주어 연간 목표 대비 진척도를 파악합니다.
- **이민 관련 뉴스**: 캐나다 정부 이민부(IRCC) 뉴스룸을 스크랩하여 최신 소식을 제공합니다.

## 기술 스택
- **Backend**: Python, Flask, SQLite
- **Frontend**: HTML, CSS, Chart.js
- **Data**: IRCC Express Entry API, Canada.ca News (HTTP scraping)

## 시작하기

### 사전 준비
- Python 3.10 이상
- 가상환경 권장 (예: `python3 -m venv venv`)

### 설치 및 실행
```bash
git clone <your-repo-url>
cd expressEntryService
python3 -m venv venv
source venv/bin/activate   # Windows는 venv\Scripts\activate
pip install -r requirements.txt

# (선택) 최초 실행 시 DB 스키마 초기화
python -c "from scraper import initialize_db; initialize_db()"

# Flask 앱 실행
export FLASK_APP=app.py    # Windows PowerShell: $env:FLASK_APP = 'app.py'
flask run
```
웹 브라우저에서 `http://127.0.0.1:5000`에 접속하면 대시보드를 확인할 수 있습니다.

### 데이터 갱신
현재 저장소에는 수집 스크립트(`scraper.py`)와 DB 스키마가 포함되어 있으며, 실제 API 호출 로직은 필요에 따라 구현해야 합니다. 새로운 드로우 데이터를 받아 `insert_draw_data()`에 전달하면 SQLite DB(`data/express_entry.db`)가 갱신됩니다.

## 페이지 안내
- `/` – 최근 드로우 리스트
- `/summary` – 연도별/월별/프로그램별 통계, 컷오프 추세, 누적 선발량 차트
- `/score-changes` – 날짜 필터가 가능한 프로그램별 컷오프 라인 차트
- `/news` – IRCC 뉴스룸 최신 기사

## 시각화 개요
- **Yearly Draws Bar Chart**: 연도별 총 드로우 횟수
- **Monthly Draw Distribution**: 연도 대비 월별 드로우 분포
- **Program Distribution**: 프로그램별 드로우 건수 스택 차트
- **Program Mix Share**: 연도별 초청 인원 비중 (스택 영역 차트)
- **Cut-off & Invitations Trend**: CRS 컷오프, 이동 평균, 초청 인원을 한 그래프에 표시
- **Cumulative Draw Momentum**: 누적 드로우 수와 누적 초청 인원 추이
- **Score Changes**: 개별 프로그램의 세부 컷오프 라인 차트 (날짜 필터)

## 프로젝트 구조
```
expressEntryService/
├── app.py                 # Flask 앱 및 라우트, 데이터 집계 로직
├── scraper.py             # DB 초기화 및 드로우 데이터 적재 헬퍼
├── requirements.txt       # Python 의존성 목록
├── data/
│   └── express_entry.db   # SQLite 데이터베이스 (생성 후)
├── static/
│   ├── charts.js          # Chart.js 헬퍼 함수 및 시각화 로직
│   └── style.css          # 공용 스타일시트
├── templates/
│   ├── index.html         # 최근 드로우 페이지
│   ├── summary.html       # 통계/시각화 대시보드
│   ├── score_changes.html # 프로그램별 컷오프 추세
│   └── news.html          # 뉴스 리스트
├── read_before_use.rtf
└── venv/                  # (옵션) 로컬 가상환경
```

> **참고**: `static/dashboard-preview.png`는 README에 사용할 스크린샷 자리입니다. 대시보드를 실행한 뒤 캡처를 저장하면 README가 더욱 보기 좋아집니다.

## 라이선스
별도의 라이선스가 명시되지 않았으므로, 배포 전 사용 정책을 확인하고 필요 시 LICENSE 파일을 추가하세요.
