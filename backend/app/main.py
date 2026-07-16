import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.ai import generate_chat_response, generate_off_topic_reply
from app.database import (
    CONTENT_TYPES,
    SEOUL_DISTRICTS,
    abandon_user_course_progress,
    complete_mission,
    create_community_post,
    delete_community_post,
    detect_list_query,
    delete_completed_user_course_progress,
    get_course,
    get_community_post,
    get_community_statistics,
    get_user_course_progress,
    has_travel_intent,
    initialize_database,
    list_courses,
    list_community_images,
    list_community_posts,
    list_places_by_district,
    list_popular_courses,
    list_user_course_progress,
    list_missions,
    list_places,
    login_user,
    recommend_courses,
    start_course_progress,
    check_in_course_mission,
    change_user_password,
    toggle_community_like,
    toggle_community_bookmark,
    toggle_course_like,
    update_community_post,
)


class PlaceOut(BaseModel):
    id: int
    title: str
    addr1: str | None = None
    addr2: str | None = None
    region: str | None = None
    content_type: str | None = None
    content_type_id: str | None = None
    contentid: str | None = None


class CourseOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    region: str | None = None
    difficulty: str | None = None


class MissionOut(BaseModel):
    id: int
    course_id: int
    title: str
    description: str | None = None
    reward_points: int
    completed: int


class UserLoginIn(BaseModel):
    nickname: str
    profile_icon: str
    password: str = Field(min_length=4, max_length=64)


class UserOut(BaseModel):
    id: int
    nickname: str
    profile_icon: str
    created_at: str


class UserPasswordChangeIn(BaseModel):
    user_id: int
    current_password: str = Field(min_length=4, max_length=64)
    new_password: str = Field(min_length=4, max_length=64)


class RecommendationIn(BaseModel):
    message: str
    limit: int = 3


class RecommendedPlaceOut(BaseModel):
    id: int
    title: str
    addr1: str | None = None
    addr2: str | None = None
    content_type: str | None = None
    firstimage: str | None = None
    mapx: str | None = None
    mapy: str | None = None
    distance_from_previous_km: float = 0


class RecommendedCourseOut(BaseModel):
    id: str
    title: str
    theme: str
    district: str
    categories: list[str]
    duration_hours: int
    stamp_count: int
    image_url: str
    total_distance_km: float
    summary: str
    reason: str
    places: list[RecommendedPlaceOut]


class RecommendationOut(BaseModel):
    answer: str
    courses: list[RecommendedCourseOut]


class CommunityPostIn(BaseModel):
    owner_key: str
    nickname: str
    title: str
    content: str
    region: str = "서울특별시"
    district: str
    image_urls: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CommunityPostOut(BaseModel):
    id: int
    nickname: str
    title: str
    content: str
    region: str
    district: str
    like_count: int
    view_count: int = 0
    created_at: str
    image_url: str | None = None
    image_urls: list[str]
    tags: list[str] = Field(default_factory=list)
    liked: bool = False
    bookmarked: bool = False
    can_edit: bool = False
    can_delete: bool = False


class CommunityPostUpdateIn(BaseModel):
    user_key: str
    title: str
    content: str
    region: str = "서울특별시"
    district: str
    image_urls: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CommunityLikeIn(BaseModel):
    user_key: str


class CommunityLikeOut(BaseModel):
    post_id: int
    liked: bool
    like_count: int


class CommunityBookmarkOut(BaseModel):
    post_id: int
    bookmarked: bool


class CommunityImageOut(BaseModel):
    id: int
    title: str
    district: str | None = None
    image_url: str


class CommunityStatItem(BaseModel):
    post_count: int
    like_count: int
    view_count: int
    bookmark_count: int = 0
    region_group: str | None = None
    district: str | None = None


class CommunityStatsOut(BaseModel):
    totals: dict[str, int]
    regions: list[CommunityStatItem]
    popular_districts: list[CommunityStatItem]


class CourseStartPlaceIn(BaseModel):
    id: int | None = None
    title: str
    addr1: str | None = None
    addr2: str | None = None
    firstimage: str | None = None
    content_type: str | None = None
    distance_from_previous_km: float = 0


class CourseStartIn(BaseModel):
    user_key: str
    title: str
    theme: str = "여행"
    summary: str = ""
    image_url: str = ""
    total_distance_km: float = 0
    duration_hours: int = 1
    places: list[CourseStartPlaceIn]


class CourseLikeIn(BaseModel):
    user_key: str


class CourseLikeOut(BaseModel):
    course_id: int
    liked: bool
    like_count: int


class PopularCourseOut(BaseModel):
    id: int
    title: str
    description: str
    district: str
    theme: str
    source: str
    image_url: str
    like_count: int


class ProgressMissionOut(BaseModel):
    id: int
    progress_id: int
    sequence_no: int
    place_id: int | None = None
    title: str
    address: str | None = None
    district: str | None = None
    image_url: str | None = None
    content_type: str | None = None
    status: str
    stamp_reward: int
    checked_in_at: str | None = None


class CourseProgressOut(BaseModel):
    id: int
    user_key: str
    title: str
    theme: str
    summary: str | None = None
    image_url: str | None = None
    total_missions: int
    completed_missions: int
    progress_percent: int
    status: str
    started_at: str
    completed_at: str | None = None
    missions: list[ProgressMissionOut]


class CheckInIn(BaseModel):
    user_key: str


class CheckInOut(BaseModel):
    progress: CourseProgressOut
    completed_mission: ProgressMissionOut
    stamp_earned: int
    course_completed: bool


def get_allowed_origins() -> list[str]:
    """Return local origins plus origins configured in Render.

    Render backend environment variable example:
    CORS_ORIGINS=https://your-frontend.onrender.com
    Multiple origins can be separated with commas.
    """
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    configured_origins = os.getenv("CORS_ORIGINS", "")
    for origin in configured_origins.split(","):
        normalized = origin.strip().rstrip("/")
        if normalized:
            origins.append(normalized)

    return list(dict.fromkeys(origins))


@asynccontextmanager
async def lifespan(app: FastAPI):
    result = initialize_database()

    print(f"[DB] path={result['database_path']}")
    print(f"[DB] existed={result['database_existed']}")
    print(f"[DB] imported_places={result['imported_places']}")
    print(f"[DB] updated_districts={result['updated_districts']}")
    print(f"[DB] total_places={result['total_places']}")

    yield


app = FastAPI(
    title="AI Team8 Travel API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/places", response_model=list[PlaceOut])
def get_places(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> list[dict]:
    return list_places(limit=limit, offset=offset)


@app.get("/courses", response_model=list[CourseOut])
def get_courses(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> list[dict]:
    return list_courses(limit=limit, offset=offset)


@app.get("/courses/{course_id}", response_model=CourseOut)
def get_course_detail(course_id: int) -> dict:
    course = get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@app.get("/courses/{course_id}/missions", response_model=list[MissionOut])
def get_course_missions(course_id: int, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> list[dict]:
    course = get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return list_missions(course_id=course_id, limit=limit, offset=offset)


@app.post("/users/login", response_model=UserOut)
def login_user_endpoint(payload: UserLoginIn) -> dict:
    if not payload.nickname.strip():
        raise HTTPException(status_code=400, detail="Nickname is required")
    try:
        return login_user(payload.nickname.strip(), payload.profile_icon, payload.password)
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@app.post("/users", response_model=UserOut)
def create_or_login_user(payload: UserLoginIn) -> dict:
    if not payload.nickname.strip():
        raise HTTPException(status_code=400, detail="Nickname is required")
    try:
        return login_user(payload.nickname.strip(), payload.profile_icon, payload.password)
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@app.patch("/users/password")
def update_user_password(payload: UserPasswordChangeIn) -> dict:
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="새 비밀번호는 현재 비밀번호와 달라야 합니다.")
    try:
        change_user_password(payload.user_id, payload.current_password, payload.new_password)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return {"success": True, "message": "비밀번호가 변경되었습니다."}


def _build_list_answer(list_query: dict) -> str:
    if list_query["type"] == "districts":
        return f"서울시 자치구는 총 {len(SEOUL_DISTRICTS)}개예요: " + ", ".join(SEOUL_DISTRICTS)

    if list_query["type"] == "categories":
        return f"코스에서 다루는 카테고리는 총 {len(CONTENT_TYPES)}가지예요: " + ", ".join(CONTENT_TYPES)

    district = list_query["district"]
    category = list_query["category"]
    label = f"{district} {category}" if category else district
    places = list_places_by_district(district, category=category)
    if not places:
        return f"{label} 관련 장소를 찾지 못했어요."
    names = ", ".join(place["title"] for place in places)
    return f"{label} 목록 ({len(places)}곳): {names}"


@app.post("/recommendations", response_model=RecommendationOut)
def get_recommendations(payload: RecommendationIn) -> dict:
    message = payload.message.strip() or "서울 인기 여행 코스를 추천해줘"

    list_query = detect_list_query(message)
    if list_query is not None:
        return {"answer": _build_list_answer(list_query), "courses": []}

    if not has_travel_intent(message):
        fallback_answer = "서울 여행 코스 추천 요청인지 잘 모르겠어요. 원하시는 테마(예: 역사, 야경), 지역(예: 종로), 소요시간을 알려주시면 코스를 추천해드릴게요!"
        return {
            "answer": generate_off_topic_reply(message, fallback_answer),
            "courses": [],
        }
    courses = recommend_courses(message, limit=max(1, min(payload.limit, 5)))
    fallback_answer = f"요청하신 조건을 서울 관광 데이터베이스와 비교해 {len(courses)}개의 코스를 찾았어요."
    result = generate_chat_response(message, courses, fallback_answer)
    for course, reason in zip(courses, result["reasons"]):
        course["reason"] = reason
    return {
        "answer": result["answer"],
        "courses": courses,
    }


@app.post("/course-progress", response_model=CourseProgressOut)
def start_course(payload: CourseStartIn) -> dict:
    if not payload.user_key.strip() or not payload.title.strip() or not payload.places:
        raise HTTPException(status_code=400, detail="User, title and places are required")
    try:
        return start_course_progress(
            payload.user_key.strip(),
            {
                "title": payload.title.strip(),
                "theme": payload.theme,
                "summary": payload.summary,
                "image_url": payload.image_url,
                "total_distance_km": payload.total_distance_km,
                "duration_hours": payload.duration_hours,
                "places": [place.model_dump() for place in payload.places],
            },
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/course-progress", response_model=list[CourseProgressOut])
def get_course_progress_list(user_key: str, status: str | None = None) -> list[dict]:
    return list_user_course_progress(user_key=user_key, status=status)


@app.get("/course-progress/{progress_id}", response_model=CourseProgressOut)
def get_course_progress_detail(progress_id: int, user_key: str) -> dict:
    progress = get_user_course_progress(progress_id, user_key)
    if not progress:
        raise HTTPException(status_code=404, detail="Course progress not found")
    return progress


@app.delete("/course-progress/{progress_id}", status_code=204)
def abandon_course_progress(progress_id: int, user_key: str) -> None:
    if not abandon_user_course_progress(progress_id, user_key.strip()):
        raise HTTPException(status_code=404, detail="In-progress course not found")


@app.delete("/course-progress/{progress_id}/completed", status_code=204)
def delete_completed_course_progress(progress_id: int, user_key: str) -> None:
    if not delete_completed_user_course_progress(progress_id, user_key.strip()):
        raise HTTPException(status_code=404, detail="Completed course not found")


@app.post("/course-progress/{progress_id}/missions/{mission_id}/check-in", response_model=CheckInOut)
def check_in_mission(progress_id: int, mission_id: int, payload: CheckInIn) -> dict:
    try:
        result = check_in_course_mission(progress_id, mission_id, payload.user_key.strip())
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if not result:
        raise HTTPException(status_code=404, detail="Course or mission not found")
    return result


@app.get("/course-rankings/popular", response_model=list[PopularCourseOut])
def get_popular_course_ranking(limit: int = Query(10, ge=1, le=100)) -> list[dict]:
    return list_popular_courses(limit=limit)


@app.post("/courses/{course_id}/likes", response_model=CourseLikeOut)
def like_course(course_id: int, payload: CourseLikeIn) -> dict:
    if not payload.user_key.strip():
        raise HTTPException(status_code=400, detail="User is required")
    result = toggle_course_like(course_id, payload.user_key.strip())
    if not result:
        raise HTTPException(status_code=404, detail="Course not found")
    return result


@app.get("/community/posts", response_model=list[CommunityPostOut])
def get_community_posts(
    district: str | None = None,
    q: str | None = None,
    user_key: str | None = None,
    bookmarked_only: bool = False,
    mine_only: bool = False,
    sort: str = Query("latest", pattern="^(latest|popular|views|likes|bookmarks)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    return list_community_posts(
        district=district,
        query=q.strip() if q else None,
        user_key=user_key,
        bookmarked_only=bookmarked_only,
        mine_only=mine_only,
        sort_by=sort,
        limit=limit,
        offset=offset,
    )


@app.get("/community/statistics", response_model=CommunityStatsOut)
def get_community_dashboard_statistics() -> dict:
    return get_community_statistics()


@app.get("/community/posts/{post_id}", response_model=CommunityPostOut)
def get_community_post_detail(post_id: int, user_key: str | None = None) -> dict:
    post = get_community_post(post_id, user_key=user_key, increment_view=True)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.post("/community/posts", response_model=CommunityPostOut)
def add_community_post(payload: CommunityPostIn) -> dict:
    if not payload.owner_key.strip() or not payload.title.strip() or not payload.content.strip() or not payload.district.strip():
        raise HTTPException(status_code=400, detail="Title, content and district are required")
    return create_community_post(
        owner_key=payload.owner_key.strip(),
        nickname=payload.nickname.strip() or "익명 사용자",
        title=payload.title.strip(),
        content=payload.content.strip(),
        region=payload.region.strip() or "서울특별시",
        district=payload.district.strip(),
        image_urls=payload.image_urls,
        tags=list(dict.fromkeys(tag.strip().lstrip("#") for tag in payload.tags if tag.strip()))[:5],
    )


@app.delete("/community/posts/{post_id}")
def remove_community_post(post_id: int, payload: CommunityLikeIn) -> dict:
    result = delete_community_post(post_id, payload.user_key.strip())
    if result is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if result is False:
        raise HTTPException(status_code=403, detail="Only the author can delete this post")
    return {"deleted": True, "post_id": post_id}


@app.put("/community/posts/{post_id}", response_model=CommunityPostOut)
def edit_community_post(post_id: int, payload: CommunityPostUpdateIn) -> dict:
    if not payload.user_key.strip() or not payload.title.strip() or not payload.content.strip() or not payload.district.strip():
        raise HTTPException(status_code=400, detail="Title, content and district are required")
    result = update_community_post(
        post_id=post_id,
        user_key=payload.user_key.strip(),
        title=payload.title.strip(),
        content=payload.content.strip(),
        region=payload.region.strip() or "서울특별시",
        district=payload.district.strip(),
        image_urls=payload.image_urls,
        tags=list(dict.fromkeys(tag.strip().lstrip("#") for tag in payload.tags if tag.strip()))[:5],
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if result is False:
        raise HTTPException(status_code=403, detail="Only the author can edit this post")
    return result


@app.post("/community/posts/{post_id}/likes", response_model=CommunityLikeOut)
def like_community_post(post_id: int, payload: CommunityLikeIn) -> dict:
    result = toggle_community_like(post_id, payload.user_key.strip() or "anonymous")
    if not result:
        raise HTTPException(status_code=404, detail="Post not found")
    return result


@app.post("/community/posts/{post_id}/bookmarks", response_model=CommunityBookmarkOut)
def bookmark_community_post(post_id: int, payload: CommunityLikeIn) -> dict:
    result = toggle_community_bookmark(post_id, payload.user_key.strip() or "anonymous")
    if not result:
        raise HTTPException(status_code=404, detail="Post not found")
    return result


@app.get("/community/images", response_model=list[CommunityImageOut])
def get_community_images(
    district: str | None = None,
    limit: int = Query(15, ge=1, le=30),
) -> list[dict]:
    return list_community_images(district=district, limit=limit)


@app.post("/courses/{course_id}/missions/{mission_id}/complete", response_model=MissionOut)
def complete_course_mission(course_id: int, mission_id: int) -> dict:
    mission = complete_mission(course_id=course_id, mission_id=mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission
