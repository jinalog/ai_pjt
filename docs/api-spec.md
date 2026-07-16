# API 명세

현재 `backend/app/main.py` 기준 명세입니다.

- API 버전: `1.0.0`
- 로컬 기본 주소: `http://127.0.0.1:8000`
- 프론트엔드 개발 프록시: `/api` → `http://127.0.0.1:8000`
- 요청·응답 형식: JSON
- Swagger UI: `/docs`
- OpenAPI JSON: `/openapi.json`

## 사용자 식별 방식

사용자 생성과 로그인에는 `nickname`, `profile_icon`, `password`를 사용합니다. 비밀번호는 PBKDF2-SHA256 해시로 저장됩니다.

로그인 이후 코스와 커뮤니티 소유권 API는 별도 세션이나 JWT 대신 다음 형식의 `user_key`를 사용합니다.

```text
user:{user_id}
```

예: 사용자 ID가 `10`이면 `user:10`입니다. 게시글 응답에는 실제 작성자 닉네임과 ID를 노출하지 않고 `익명 사용자`로 반환합니다.

## 공통 상태 코드

| 상태 코드 | 의미 |
| --- | --- |
| `200` | 조회·수정·토글 성공 |
| `204` | 코스 삭제 성공, 응답 본문 없음 |
| `400` | 필수 입력 누락 또는 허용되지 않는 요청 상태 |
| `401` | 로그인 또는 현재 비밀번호 확인 실패 |
| `403` | 다른 사용자의 게시글 수정·삭제 시도 |
| `404` | 사용자, 코스, 미션 또는 게시글을 찾지 못함 |
| `409` | 현재 활성 미션이 아닌 미션에 체크인 시도 |
| `422` | Pydantic 필드 형식·길이·쿼리 조건 검증 실패 |

## 상태 확인

### `GET /health`

서버 상태를 확인합니다.

응답 예시:

```json
{
  "status": "ok"
}
```

## 사용자

### `POST /users`

닉네임이 없으면 사용자를 생성하고, 이미 존재하면 비밀번호를 확인해 로그인합니다.

### `POST /users/login`

`POST /users`와 동일한 로그인 호환 엔드포인트입니다.

두 API의 요청 본문:

| 필드 | 타입 | 필수 | 제약 |
| --- | --- | --- | --- |
| `nickname` | string | O | 공백만 입력할 수 없음 |
| `profile_icon` | string | O | 현재 프론트엔드 기본값 `mask` |
| `password` | string | O | 4~64자 |

```json
{
  "nickname": "tester",
  "profile_icon": "mask",
  "password": "pass1234"
}
```

응답:

```json
{
  "id": 1,
  "nickname": "tester",
  "profile_icon": "mask",
  "created_at": "2026-07-15 01:09:08"
}
```

기존 비밀번호가 없는 마이그레이션 이전 사용자는 다음 로그인에 입력한 비밀번호가 최초 비밀번호로 등록됩니다. 기존 사용자 비밀번호가 일치하지 않으면 `401`을 반환합니다.

### `PATCH /users/password`

현재 비밀번호를 확인한 후 새 비밀번호로 변경합니다.

| 필드 | 타입 | 필수 | 제약 |
| --- | --- | --- | --- |
| `user_id` | integer | O | 사용자 ID |
| `current_password` | string | O | 4~64자 |
| `new_password` | string | O | 4~64자, 현재 비밀번호와 달라야 함 |

```json
{
  "user_id": 1,
  "current_password": "pass1234",
  "new_password": "new-pass1234"
}
```

성공 응답:

```json
{
  "success": true,
  "message": "비밀번호가 변경되었습니다."
}
```

## 장소·기본 코스

| Method | 경로 | 쿼리·경로 입력 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/places` | `limit=20`(1~100), `offset=0` | 원본 관광 장소 목록 |
| `GET` | `/courses` | `limit=20`(1~100), `offset=0` | 저장된 코스 목록 |
| `GET` | `/courses/{course_id}` | `course_id` | 저장된 코스 상세 |
| `GET` | `/courses/{course_id}/missions` | `course_id`, `limit=20`(1~100), `offset=0` | 코스 미션 목록 |

## 코스 추천

### `POST /recommendations`

메시지에서 자치구, 관광 카테고리, 테마, 요청 시간과 필수 방문지를 분석해 코스를 추천합니다. 장소 좌표를 이용해 가까운 방문 순서를 구성합니다.

요청:

| 필드 | 타입 | 필수 | 기본값 |
| --- | --- | --- | --- |
| `message` | string | O | 없음 |
| `limit` | integer | X | `3`, 서버에서 1~5로 제한 |

```json
{
  "message": "종로에서 역사 장소를 포함한 3시간 코스를 추천해줘",
  "limit": 3
}
```

응답의 `courses` 항목에는 다음 값이 포함됩니다.

- `id`, `title`, `theme`, `district`, `categories`
- `duration_hours`, `stamp_count`, `total_distance_km`
- `image_url`, `summary`, `reason`
- `places`: 장소와 이전 장소로부터의 거리 목록

자치구·카테고리 목록 질문에는 `answer`만 반환하고 `courses`는 빈 배열일 수 있습니다. 여행 의도가 아닌 질문도 안내 답변과 빈 코스 배열을 반환합니다. `OPENAI_API_KEY`가 없거나 호출이 실패하면 데이터 기반 템플릿 답변을 사용합니다.

## 여행 로그·미션

### `POST /course-progress`

추천 코스를 사용자 여행 로그에 저장하고 첫 번째 미션을 활성화합니다.

요청 본문:

| 필드 | 타입 | 필수 | 기본값 |
| --- | --- | --- | --- |
| `user_key` | string | O | 없음 |
| `title` | string | O | 없음 |
| `theme` | string | X | `여행` |
| `summary` | string | X | 빈 문자열 |
| `image_url` | string | X | 빈 문자열 |
| `total_distance_km` | number | X | `0` |
| `duration_hours` | integer | X | `1` |
| `places` | array | O | 한 개 이상 |

장소 필드:

- 선택: `id`, `addr1`, `addr2`, `firstimage`, `content_type`
- 필수: `title`
- 기본값: `distance_from_previous_km=0`

```json
{
  "user_key": "user:1",
  "title": "종로 역사 코스",
  "theme": "역사",
  "summary": "경복궁에서 박물관까지 걷는 코스",
  "image_url": "https://example.com/course.jpg",
  "total_distance_km": 1.4,
  "duration_hours": 3,
  "places": [
    {
      "id": 101,
      "title": "경복궁",
      "addr1": "서울특별시 종로구 사직로 161",
      "addr2": "종로구",
      "content_type": "관광지",
      "distance_from_previous_km": 0
    }
  ]
}
```

### 여행 로그 API

| Method | 경로 | 입력 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/course-progress` | 필수 `user_key`, 선택 `status` | 사용자의 여행 로그 목록 |
| `GET` | `/course-progress/{progress_id}` | 경로 `progress_id`, 쿼리 `user_key` | 진행 상세와 전체 미션 |
| `DELETE` | `/course-progress/{progress_id}` | 경로 `progress_id`, 쿼리 `user_key` | 진행 중인 코스 포기 및 관련 기록 삭제 |
| `DELETE` | `/course-progress/{progress_id}/completed` | 경로 `progress_id`, 쿼리 `user_key` | 완료 코스와 관련 기록 삭제 |
| `POST` | `/course-progress/{progress_id}/missions/{mission_id}/check-in` | 경로 ID, JSON 본문 `user_key` | 활성 미션 체크인 |

`status`는 현재 `in_progress` 또는 `completed` 값을 사용합니다.

체크인 요청:

```json
{
  "user_key": "user:1"
}
```

체크인 응답에는 갱신된 `progress`, 완료된 `completed_mission`, `stamp_earned`, `course_completed`가 포함됩니다. 현재 활성 미션만 체크인할 수 있으며 중복 체크인은 데이터베이스 유일 제약으로 방지됩니다.

`CourseProgressOut`의 주요 상태 값:

- 코스 `status`: `in_progress`, `completed`
- 미션 `status`: `active`, `locked`, `completed`
- 진행 수치: `total_missions`, `completed_missions`, `progress_percent`

## 코스 좋아요·인기 순위

| Method | 경로 | 입력 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/courses/{course_id}/likes` | JSON 본문 `user_key` | 코스 좋아요 설정·취소 |
| `GET` | `/course-rankings/popular` | 선택 `limit=10`(1~100) | 좋아요 수 내림차순 인기 코스 |

좋아요 응답:

```json
{
  "course_id": 1,
  "liked": true,
  "like_count": 3
}
```

## 익명 커뮤니티

### `GET /community/posts`

게시글 목록을 조회합니다.

| 쿼리 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `district` | string | 없음 | 자치구 필터 |
| `q` | string | 없음 | 제목·내용·태그 검색 |
| `user_key` | string | 없음 | 좋아요·북마크·작성자 권한 판별 |
| `bookmarked_only` | boolean | `false` | 현재 사용자가 북마크한 글만 조회 |
| `mine_only` | boolean | `false` | 현재 사용자가 작성한 글만 조회 |
| `sort` | string | `latest` | 정렬 기준 |
| `limit` | integer | `20` | 1~100 |
| `offset` | integer | `0` | 0 이상 |

허용 정렬 값:

| 값 | 기준 |
| --- | --- |
| `latest` | 작성일 최신순, 같은 시간은 ID 역순 |
| `popular` | 좋아요 + 조회수 + 북마크 수 합산 내림차순 |
| `views` | 조회수 내림차순 |
| `likes` | 좋아요 수 내림차순 |
| `bookmarks` | 북마크 수 내림차순 |

`bookmarked_only`와 `mine_only`는 `user_key`가 없으면 빈 배열을 반환합니다. 두 값이 모두 `true`이면 내가 작성하면서 북마크한 글의 교집합을 반환합니다.

### 게시글 작성·수정 요청

작성 `POST /community/posts`:

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `owner_key` | string | O | 작성자 `user_key` |
| `nickname` | string | O | 저장용 값, 외부 응답은 익명 처리 |
| `title` | string | O | 공백만 입력할 수 없음 |
| `content` | string | O | 공백만 입력할 수 없음 |
| `region` | string | X | 기본 `서울특별시` |
| `district` | string | O | 자치구 |
| `image_urls` | string[] | X | 기본 빈 배열 |
| `tags` | string[] | X | 중복 제거 후 최대 5개 |

```json
{
  "owner_key": "user:1",
  "nickname": "tester",
  "title": "종로 산책 후기",
  "content": "경복궁과 서촌을 걸었습니다.",
  "region": "서울특별시",
  "district": "종로구",
  "image_urls": ["https://example.com/image.jpg"],
  "tags": ["종로구", "역사", "산책"]
}
```

수정 `PUT /community/posts/{post_id}`는 `owner_key`, `nickname` 대신 `user_key`를 사용하며 나머지 필드는 동일합니다.

### 커뮤니티 API 목록

| Method | 경로 | 입력 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/community/posts` | 쿼리 필터·정렬 | 게시글 목록 |
| `POST` | `/community/posts` | 게시글 JSON | 익명 게시글 작성 |
| `GET` | `/community/posts/{post_id}` | 선택 쿼리 `user_key` | 상세 조회, 조회수 1 증가 |
| `PUT` | `/community/posts/{post_id}` | 게시글 수정 JSON | 작성자 본인의 글 수정 |
| `DELETE` | `/community/posts/{post_id}` | JSON 본문 `user_key` | 작성자 본인의 글 삭제 |
| `POST` | `/community/posts/{post_id}/likes` | JSON 본문 `user_key` | 좋아요 설정·취소 |
| `POST` | `/community/posts/{post_id}/bookmarks` | JSON 본문 `user_key` | 북마크 설정·취소 |
| `GET` | `/community/statistics` | 없음 | 커뮤니티 대시보드 통계 |
| `GET` | `/community/images` | 선택 `district`, `limit=15`(1~30) | 첨부용 관광 이미지 후보 |

삭제, 좋아요, 북마크 요청 본문:

```json
{
  "user_key": "user:1"
}
```

게시글 응답 `CommunityPostOut`:

- 기본 정보: `id`, `title`, `content`, `region`, `district`, `created_at`
- 통계: `like_count`, `view_count`
- 첨부: 대표 `image_url`, 전체 `image_urls`, `tags`
- 현재 사용자 상태: `liked`, `bookmarked`, `can_edit`, `can_delete`
- `nickname`: 항상 `익명 사용자`

### `GET /community/statistics`

홈 대시보드 데이터를 반환합니다.

```json
{
  "totals": {
    "post_count": 9,
    "like_count": 416,
    "view_count": 6,
    "bookmark_count": 5
  },
  "regions": [],
  "popular_districts": []
}
```

- `regions`: 서울 5개 권역별 게시글·좋아요·조회수·북마크 집계
- `popular_districts`: 좋아요·조회수·북마크 합산 기준 상위 자치구 5개

## 레거시 미션 완료 API

### `POST /courses/{course_id}/missions/{mission_id}/complete`

기본 `missions` 테이블의 완료 여부를 갱신하는 호환 API입니다. 현재 프론트엔드 여행 로그는 이 API 대신 `/course-progress/{progress_id}/missions/{mission_id}/check-in`을 사용합니다.
