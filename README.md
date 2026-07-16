# Seoul Mission Trip

서울 관광 데이터를 기반으로 여행 코스를 추천하고, 미션과 스탬프로 여행 진행 상황을 기록하는 웹 서비스입니다. 비밀번호 기반 사용자 계정, 여행 로그, 익명 커뮤니티, 커뮤니티 통계 대시보드를 제공합니다.

## 주요 기능

### 사용자

- 닉네임과 비밀번호로 회원 생성 및 로그인
- PBKDF2-SHA256 기반 비밀번호 해시 저장
- 마이페이지에서 현재 비밀번호 확인 후 비밀번호 변경
- 로그아웃 및 브라우저 로컬 로그인 상태 유지

### 여행 코스와 미션

- 서울 관광 데이터 기반 대화형 코스 추천
- 자치구, 테마, 카테고리와 이동 거리를 고려한 코스 구성
- 추천 코스를 여행 로그에 추가하고 미션 순서대로 체크인
- 미션 완료 시 스탬프 획득 및 다음 미션 활성화
- 진행 중인 코스 이어서 진행하거나 포기
- 완료한 코스의 결과와 전체 미션 확인
- 완료 코스 선택 삭제

### 커뮤니티

- 자치구별 익명 게시글 작성, 조회, 수정, 삭제
- 관광 이미지 첨부 및 태그 등록
- 게시글 검색, 조회수, 좋아요, 북마크
- 북마크한 글과 내가 작성한 글만 모아보기
- 최신순, 인기순, 조회순, 좋아요순, 북마크순 정렬
- 인기순은 좋아요, 조회수, 북마크 수 합산 기준

### 데이터 시각화

- Chart.js 기반 서울 5개 권역별 게시글 현황
- 좋아요, 조회수, 북마크를 합산한 인기 자치구 TOP 5
- 전체 게시글, 좋아요, 조회수, 북마크 누적 통계

## 기술 스택

| 구분 | 기술 |
| --- | --- |
| Frontend | Vue 3, Vite, Chart.js, Lucide Vue Next |
| Backend | FastAPI, Pydantic, Uvicorn |
| Database | SQLite |
| AI | OpenAI API (`gpt-5-mini`, 선택 설정) |
| Data | 한국관광공사 TourAPI 4.0 서울 관광 데이터 |
| External access | ngrok |

OpenAI API 키가 없어도 데이터 기반 추천과 템플릿 응답으로 서비스가 동작합니다. API 키를 설정하면 추천 답변과 코스별 추천 이유가 생성형 응답으로 제공됩니다.

## 프로젝트 구조

```text
ai_team8/
├─ backend/
│  ├─ app/
│  │  ├─ ai.py               # OpenAI 응답 생성
│  │  ├─ database.py         # SQLite 스키마, 조회 및 비즈니스 로직
│  │  └─ main.py             # FastAPI 모델과 엔드포인트
│  ├─ scripts/               # DB 및 로그인 점검 스크립트
│  └─ requirements.txt
├─ data/                     # 서울 관광 원본 JSON 데이터
├─ docs/                     # API 및 DB 설계 문서
├─ frontend/
│  ├─ src/
│  │  ├─ assets/
│  │  ├─ App.vue
│  │  └─ style.css
│  ├─ .env.example
│  ├─ package.json
│  └─ vite.config.js
└─ README.md
```

## 실행 환경

- Python 3.10 이상
- Node.js 20 이상 및 npm
- 선택: OpenAI API 키
- 외부 공개 시 ngrok

## 초기 설치

저장소를 받은 후 프로젝트 루트에서 진행합니다.

### 백엔드

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

PowerShell 실행 정책 때문에 가상환경 활성화가 제한되면 다음처럼 가상환경의 Python을 직접 사용합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS/Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 프론트엔드

```bash
cd frontend
npm install
```

Windows PowerShell에서 `npm.ps1` 실행 정책 오류가 발생하면 `npm.cmd install`을 사용합니다.

## 환경 변수

### OpenAI API

OpenAI 응답을 사용하려면 프로젝트 루트 또는 `backend` 디렉터리에 `.env` 파일을 만들고 다음 값을 설정합니다.

```dotenv
OPENAI_API_KEY=your_openai_api_key
```

`.env` 파일은 Git에서 제외됩니다. API 키를 소스 코드나 README에 직접 작성하지 마세요.

### 프론트엔드 API 주소

로컬과 ngrok 접속을 동일하게 지원하려면 `frontend/.env`를 다음과 같이 설정하는 것을 권장합니다.

```dotenv
VITE_API_BASE_URL=/api
```

Vite 개발 서버가 `/api` 요청을 `http://127.0.0.1:8000`으로 프록시합니다. 환경 변수가 없으면 프론트엔드는 `http://127.0.0.1:8000`을 기본 API 주소로 사용하므로 로컬 접속은 가능하지만 ngrok 외부 접속에서는 API 요청이 실패할 수 있습니다.

## 기동 방법

프로젝트 루트에서 Git Bash 터미널 3개를 열어 다음 순서대로 실행합니다.

### 1. 백엔드

```bash
cd backend
source .venv/Scripts/activate
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 가상환경 활성화 없이 실행:
cd backend
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API: `http://127.0.0.1:8000`
- 상태 확인: `http://127.0.0.1:8000/health`
- Swagger 문서: `http://127.0.0.1:8000/docs`

서버 최초 실행 시 `backend/app.db`가 생성되고 `data`의 서울 관광 JSON 데이터가 자동 적재됩니다. 이후에는 기존 DB를 재사용합니다.

### 2. 프론트엔드

```bash
cd frontend
npm run dev
```

- 화면: `http://localhost:5173`
- Vite는 `0.0.0.0:5173`에서 실행되며 포트가 사용 중이면 종료됩니다(`strictPort`).

### 3. ngrok 외부 공개

ngrok 설치와 authtoken 설정을 완료한 뒤 실행합니다.

```bash
ngrok http --host-header=rewrite 5173
```

ngrok이 출력하는 `https://...ngrok-free.app` 또는 `https://...ngrok-free.dev` 주소로 외부에서 접속할 수 있습니다. 무료 요금제의 브라우저 경고 화면은 최초 한 번 `Visit Site`를 눌러 통과합니다.

```text
백엔드(8000) → 프론트엔드(5173) → ngrok(5173 공개)
```

종료할 때는 각 터미널에서 `Ctrl+C`를 누릅니다. 동일한 포트에 개발 서버를 여러 개 실행하면 이전 코드가 표시될 수 있으므로 서버는 포트별로 하나만 실행합니다.

## 빌드 확인

```bash
cd frontend
npm run build
npm run preview
```

Windows PowerShell에서는 `npm.cmd run build`, `npm.cmd run preview`를 사용할 수 있습니다.

## 주요 API

기본 주소는 `http://127.0.0.1:8000`이며 전체 요청·응답 모델은 실행 중인 서버의 `/docs`에서 확인할 수 있습니다.

### 사용자

| Method | 경로 | 설명 |
| --- | --- | --- |
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/users` | 사용자 생성 또는 비밀번호 로그인 |
| `POST` | `/users/login` | 로그인 호환 엔드포인트 |
| `PATCH` | `/users/password` | 현재 비밀번호 확인 후 비밀번호 변경 |

### 추천 및 여행 로그

| Method | 경로 | 설명 |
| --- | --- | --- |
| `GET` | `/places` | 관광 장소 목록 |
| `POST` | `/recommendations` | 메시지 조건 기반 코스 추천 |
| `GET` | `/courses` | 저장된 코스 목록 |
| `GET` | `/courses/{course_id}` | 코스 상세 조회 |
| `GET` | `/courses/{course_id}/missions` | 코스 미션 목록 |
| `POST` | `/course-progress` | 추천 코스를 여행 로그에 추가 |
| `GET` | `/course-progress` | 사용자의 진행 중·완료 코스 조회 |
| `GET` | `/course-progress/{progress_id}` | 코스 진행 상태와 미션 조회 |
| `DELETE` | `/course-progress/{progress_id}` | 진행 중인 코스 포기 |
| `DELETE` | `/course-progress/{progress_id}/completed` | 완료 코스 내역 삭제 |
| `POST` | `/course-progress/{progress_id}/missions/{mission_id}/check-in` | 현재 미션 체크인 및 스탬프 획득 |
| `POST` | `/courses/{course_id}/likes` | 코스 좋아요 설정·취소 |
| `GET` | `/course-rankings/popular` | 인기 코스 순위 |

### 커뮤니티

| Method | 경로 | 설명 |
| --- | --- | --- |
| `GET` | `/community/posts` | 지역·검색·북마크·내 작성글 필터 및 정렬 |
| `POST` | `/community/posts` | 이미지와 태그를 포함한 게시글 작성 |
| `GET` | `/community/posts/{post_id}` | 게시글 상세 조회 및 조회수 증가 |
| `PUT` | `/community/posts/{post_id}` | 작성자 본인의 게시글 수정 |
| `DELETE` | `/community/posts/{post_id}` | 작성자 본인의 게시글 삭제 |
| `POST` | `/community/posts/{post_id}/likes` | 게시글 좋아요 설정·취소 |
| `POST` | `/community/posts/{post_id}/bookmarks` | 게시글 북마크 설정·취소 |
| `GET` | `/community/statistics` | 권역별 현황과 인기 자치구 통계 |
| `GET` | `/community/images` | 게시글 첨부용 관광 이미지 후보 |

`GET /community/posts`의 `sort` 값은 `latest`, `popular`, `views`, `likes`, `bookmarks`를 지원합니다. 게시글에는 익명 사용자만 노출되며 실제 작성자에게만 수정·삭제 권한이 반환됩니다.

상세 API는 [docs/api-spec.md](docs/api-spec.md), DB 구조는 [docs/db-architecture.md](docs/db-architecture.md)와 [docs/db-schema.sql](docs/db-schema.sql)을 참고하세요.

## 데이터

`data` 디렉터리에는 한국관광공사 TourAPI 4.0에서 수집한 서울 지역 JSON 데이터가 포함되어 있습니다.

- 관광지
- 레포츠
- 문화시설
- 쇼핑
- 숙박
- 여행코스
- 축제·공연·행사

출처와 라이선스 세부 내용은 [data/SOURCE.md](data/SOURCE.md)와 [data/SCHEMA.md](data/SCHEMA.md)를 참고하세요.

## 커밋 전 확인

```bash
git status --short
git diff --check
cd frontend
npm run build
```

`node_modules`, 빌드 결과물, SQLite DB, `.env` 파일은 `.gitignore`에 의해 커밋에서 제외됩니다.
