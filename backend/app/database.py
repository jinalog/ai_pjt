import json
import hashlib
import hmac
import math
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "app.db"
DATA_DIR = BASE_DIR.parent / "data"

SEOUL_DISTRICTS = (
    "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구",
    "금천구", "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구",
    "서초구", "성동구", "성북구", "송파구", "양천구", "영등포구", "용산구",
    "은평구", "종로구", "중구", "중랑구",
)

CONTENT_TYPES = ("관광지", "레포츠", "문화시설", "쇼핑", "숙박", "여행코스", "축제공연행사")
_CATEGORY_KEYWORDS = {
    "관광지": ["관광지", "명소", "볼거리"],
    "레포츠": ["레포츠", "스포츠", "액티비티", "운동"],
    "문화시설": ["문화시설", "박물관", "미술관", "전시", "공연"],
    "쇼핑": ["쇼핑", "시장", "백화점", "기념품"],
    "숙박": ["숙박", "호텔", "숙소", "게스트하우스"],
    "여행코스": ["여행코스", "투어 코스", "관광 코스"],
    "축제공연행사": ["축제", "공연", "행사", "페스티벌"],
}
_THEMES = {
    "역사": ["역사", "궁", "궁궐", "종묘", "한옥", "전통", "사찰", "문화재"],
    "자연": ["자연", "공원", "숲", "산", "한강", "호수", "생태", "산책"],
    "야경": ["야경", "밤", "전망", "타워", "한강", "청계천", "데이트"],
    "미식": ["맛집", "음식", "먹거리", "시장", "카페", "미식"],
    "문화": ["문화", "미술", "박물관", "공연", "전시", "예술"],
    "가족": ["가족", "아이", "어린이", "체험", "놀이", "키즈"],
}
_GENERIC_TRAVEL_KEYWORDS = ("여행", "코스", "추천", "관광", "놀거리", "볼거리", "구경", "나들이", "다녀오", "돌아보")


def extract_district(addr1: str | None) -> str | None:
    """Extract one of Seoul's 25 districts from a primary address."""
    if not addr1:
        return None
    return next((district for district in SEOUL_DISTRICTS if district in addr1), None)


def _district_short_name(district: str) -> str:
    """Drop the trailing '구' so '종로구' also matches a bare '종로'.

    Skipped for 2-character names like '중구' since stripping would leave a
    single character ('중') that collides with unrelated words.
    """
    return district[:-1] if district.endswith("구") and len(district) > 2 else district


def has_travel_intent(query: str) -> bool:
    """Whether the message plausibly asks for a Seoul travel course.

    Used to avoid recommending courses for unrelated small talk or gibberish.
    """
    normalized = query.strip().lower()
    theme_match = any(any(word in normalized for word in words) for words in _THEMES.values())
    category_match = any(category in normalized for category in CONTENT_TYPES) or any(
        any(word in normalized for word in words) for words in _CATEGORY_KEYWORDS.values()
    )
    district_match = any(
        district in normalized or _district_short_name(district) in normalized
        for district in SEOUL_DISTRICTS
    )
    time_match = re.search(r"\d+(?:\.\d+)?\s*시간", normalized) is not None
    generic_match = any(word in normalized for word in _GENERIC_TRAVEL_KEYWORDS)
    return theme_match or category_match or district_match or time_match or generic_match


_LIST_TRIGGER_WORDS = ("리스트", "목록")
_DISTRICT_LIST_WORDS = ("지역구", "지역")
_CATEGORY_LIST_WORDS = ("카테고리", "종류", "분류")


def detect_list_query(query: str) -> dict | None:
    """Detect a plain 'list the X' request, distinct from a course recommendation.

    Returns None if the message isn't asking for a list at all.
    """
    normalized = query.strip().lower()
    if not any(word in normalized for word in _LIST_TRIGGER_WORDS):
        return None

    district = next(
        (
            d for d in SEOUL_DISTRICTS
            if d in normalized or _district_short_name(d) in normalized
        ),
        None,
    )
    category = next((c for c in CONTENT_TYPES if c in normalized), None)

    if district:
        return {"type": "district_places", "district": district, "category": category}
    if any(word in normalized for word in _DISTRICT_LIST_WORDS):
        return {"type": "districts"}
    if any(word in normalized for word in _CATEGORY_LIST_WORDS):
        return {"type": "categories"}
    return None


_MUST_INCLUDE_TRIGGER_WORDS = ("추가", "포함", "넣어")
_MUST_INCLUDE_WINDOW_CHARS = 40


def find_must_include_place(query: str, district: str | None = None) -> dict | None:
    """Find a place the user explicitly demanded be included in the course.

    Looks for a "꼭 추가해줘" / "포함해줘" / "넣어줘" style request, then matches
    the text right before the trigger word against real place titles in the
    database (rather than guessing where a "name" starts with NLP heuristics).
    Prefers the longest matching title so a more specific name wins.
    """
    trigger_index = min(
        (query.index(word) for word in _MUST_INCLUDE_TRIGGER_WORDS if word in query),
        default=None,
    )
    if trigger_index is None:
        return None
    window = query[max(0, trigger_index - _MUST_INCLUDE_WINDOW_CHARS):trigger_index]
    if len(window.strip()) < 2:
        return None

    with get_connection() as conn:
        base_query = (
            "SELECT id, title, addr1, addr2, content_type, firstimage, mapx, mapy FROM places "
            "WHERE LENGTH(title) >= 2 AND firstimage != '' AND CAST(mapx AS REAL) BETWEEN 126 AND 128 "
            "AND CAST(mapy AS REAL) BETWEEN 37 AND 38"
        )
        params: list = []
        if district:
            base_query += " AND addr2 = ?"
            params.append(district)
        candidates = conn.execute(base_query, params).fetchall()

    best = None
    for row in candidates:
        title = row["title"]
        if title and title in window and (best is None or len(title) > len(best["title"])):
            best = dict(row)
    return best


def list_places_by_district(district: str, category: str | None = None, limit: int = 30) -> list[dict]:
    with get_connection() as conn:
        if category:
            rows = conn.execute(
                """SELECT id, title, content_type FROM places
                   WHERE addr2 = ? AND content_type = ? AND title != ''
                   ORDER BY id LIMIT ?""",
                (district, category, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, title, content_type FROM places
                   WHERE addr2 = ? AND title != ''
                   ORDER BY CASE content_type WHEN '관광지' THEN 0 WHEN '문화시설' THEN 1 ELSE 2 END, id
                   LIMIT ?""",
                (district, limit),
            ).fetchall()
        return [dict(row) for row in rows]


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _lookup_user_id(conn: sqlite3.Connection, user_key: str | None) -> int | None:
    if not user_key:
        return None
    if user_key.startswith("user:") and user_key[5:].isdigit():
        row = conn.execute("SELECT id FROM users WHERE id = ?", (int(user_key[5:]),)).fetchone()
    else:
        row = conn.execute("SELECT id FROM users WHERE anonymous_key = ?", (user_key,)).fetchone()
    return int(row["id"]) if row else None


def _resolve_user_id(conn: sqlite3.Connection, user_key: str, nickname: str | None = None) -> int:
    existing = _lookup_user_id(conn, user_key)
    if existing:
        return existing
    internal_name = f"anonymous-{abs(hash(user_key))}"
    cursor = conn.execute(
        "INSERT INTO users (nickname, profile_icon, anonymous_key) VALUES (?, 'mask', ?)",
        (internal_name, user_key),
    )
    return int(cursor.lastrowid)


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                region TEXT,
                content_type TEXT,
                content_type_id TEXT,
                contentid TEXT UNIQUE,
                contenttypeid TEXT,
                title TEXT,
                addr1 TEXT,
                addr2 TEXT,
                zipcode TEXT,
                tel TEXT,
                mapx TEXT,
                mapy TEXT,
                mlevel TEXT,
                areacode TEXT,
                sigungucode TEXT,
                lDongRegnCd TEXT,
                lDongSignguCd TEXT,
                cat1 TEXT,
                cat2 TEXT,
                cat3 TEXT,
                lclsSystm1 TEXT,
                lclsSystm2 TEXT,
                lclsSystm3 TEXT,
                firstimage TEXT,
                firstimage2 TEXT,
                cpyrhtDivCd TEXT,
                createdtime TEXT,
                modifiedtime TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nickname TEXT NOT NULL UNIQUE,
                profile_icon TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "anonymous_key" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN anonymous_key TEXT")
        if "password_hash" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        conn.execute("UPDATE users SET anonymous_key = 'user:' || id WHERE anonymous_key IS NULL OR anonymous_key = ''")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_anonymous_key ON users(anonymous_key)")

        place_columns = {row[1] for row in conn.execute("PRAGMA table_info(places)")}
        if "longitude" not in place_columns:
            conn.execute("ALTER TABLE places ADD COLUMN longitude REAL")
        if "latitude" not in place_columns:
            conn.execute("ALTER TABLE places ADD COLUMN latitude REAL")
        conn.execute("UPDATE places SET longitude = CAST(mapx AS REAL), latitude = CAST(mapy AS REAL)")

        existing_post_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'community_posts'"
        ).fetchone()
        if existing_post_table:
            post_columns = {row[1] for row in conn.execute("PRAGMA table_info(community_posts)")}
            if "author_id" not in post_columns and not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'legacy_community_posts'"
            ).fetchone():
                conn.execute("ALTER TABLE community_posts RENAME TO legacy_community_posts")

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_by INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                district TEXT NOT NULL,
                theme TEXT NOT NULL,
                source TEXT NOT NULL CHECK(source IN ('ai', 'user', 'system')),
                image_url TEXT,
                total_distance_km REAL NOT NULL DEFAULT 0,
                estimated_hours INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS course_places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                place_id INTEGER NOT NULL,
                sequence_no INTEGER NOT NULL,
                distance_from_previous_km REAL NOT NULL DEFAULT 0,
                FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,
                FOREIGN KEY(place_id) REFERENCES places(id) ON DELETE RESTRICT,
                UNIQUE(course_id, sequence_no)
            );

            CREATE TABLE IF NOT EXISTS course_missions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_place_id INTEGER NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT,
                mission_type TEXT NOT NULL DEFAULT 'checkin' CHECK(mission_type = 'checkin'),
                stamp_reward INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(course_place_id) REFERENCES course_places(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS user_courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'in_progress' CHECK(status IN ('in_progress', 'completed')),
                current_sequence INTEGER NOT NULL DEFAULT 1,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,
                UNIQUE(user_id, course_id)
            );

            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_course_id INTEGER NOT NULL,
                mission_id INTEGER NOT NULL,
                checked_in_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_course_id) REFERENCES user_courses(id) ON DELETE CASCADE,
                FOREIGN KEY(mission_id) REFERENCES course_missions(id) ON DELETE RESTRICT,
                UNIQUE(user_course_id, mission_id)
            );

            CREATE TABLE IF NOT EXISTS stamps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                checkin_id INTEGER NOT NULL UNIQUE,
                place_id INTEGER NOT NULL,
                earned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(checkin_id) REFERENCES checkins(id) ON DELETE CASCADE,
                FOREIGN KEY(place_id) REFERENCES places(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS course_likes (
                course_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(course_id, user_id),
                FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS community_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author_id INTEGER NOT NULL,
                course_id INTEGER,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                region TEXT NOT NULL DEFAULT '서울특별시',
                district TEXT NOT NULL,
                like_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS post_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                image_url TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(post_id) REFERENCES community_posts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS post_likes (
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(post_id, user_id),
                FOREIGN KEY(post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS post_bookmarks (
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(post_id, user_id),
                FOREIGN KEY(post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS post_tags (
                post_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY(post_id, tag),
                FOREIGN KEY(post_id) REFERENCES community_posts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_places_district_type ON places(addr2, content_type);
            CREATE INDEX IF NOT EXISTS idx_places_coordinates ON places(latitude, longitude);
            CREATE INDEX IF NOT EXISTS idx_courses_district_theme ON courses(district, theme);
            CREATE INDEX IF NOT EXISTS idx_user_courses_user_status ON user_courses(user_id, status);
            CREATE INDEX IF NOT EXISTS idx_posts_district_created ON community_posts(district, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_checkins_user_course ON checkins(user_course_id);
            """
        )
        post_columns = {row[1] for row in conn.execute("PRAGMA table_info(community_posts)")}
        if "view_count" not in post_columns:
            conn.execute("ALTER TABLE community_posts ADD COLUMN view_count INTEGER NOT NULL DEFAULT 0")

        def resolve_user_id(key: str | None, nickname: str | None = None) -> int:
            normalized_key = key or f"legacy:{nickname or 'anonymous'}"
            if normalized_key.startswith("user:") and normalized_key[5:].isdigit():
                row = conn.execute("SELECT id FROM users WHERE id = ?", (int(normalized_key[5:]),)).fetchone()
                if row:
                    return int(row["id"])
            row = conn.execute("SELECT id FROM users WHERE anonymous_key = ?", (normalized_key,)).fetchone()
            if row:
                return int(row["id"])
            internal_name = f"anonymous-{abs(hash(normalized_key))}"
            cursor = conn.execute(
                "INSERT INTO users (nickname, profile_icon, anonymous_key) VALUES (?, 'mask', ?)",
                (internal_name, normalized_key),
            )
            return int(cursor.lastrowid)

        migration_done = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = 'normalized-v1'"
        ).fetchone()
        if not migration_done:
            legacy_posts = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'legacy_community_posts'"
            ).fetchone()
            if legacy_posts:
                for post in conn.execute("SELECT * FROM legacy_community_posts ORDER BY id").fetchall():
                    author_id = resolve_user_id(post["owner_key"] if "owner_key" in post.keys() else None, post["nickname"])
                    conn.execute(
                        """INSERT OR IGNORE INTO community_posts
                           (id, author_id, title, content, region, district, like_count, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (post["id"], author_id, post["title"], post["content"], post["region"], post["district"], post["like_count"], post["created_at"]),
                    )
                if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='community_post_images'").fetchone():
                    conn.execute(
                        """INSERT OR IGNORE INTO post_images(id, post_id, image_url, sort_order)
                           SELECT id, post_id, image_url, sort_order FROM community_post_images"""
                    )

            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_course_progress'").fetchone():
                for progress in conn.execute("SELECT * FROM user_course_progress ORDER BY id").fetchall():
                    user_id = resolve_user_id(progress["user_key"])
                    course_cursor = conn.execute(
                        """INSERT INTO courses
                           (title, description, district, theme, source, image_url)
                           VALUES (?, ?, '서울특별시', ?, 'ai', ?)""",
                        (progress["title"], progress["summary"], progress["theme"], progress["image_url"]),
                    )
                    course_id = int(course_cursor.lastrowid)
                    old_missions = conn.execute(
                        "SELECT * FROM user_course_missions WHERE progress_id = ? ORDER BY sequence_no",
                        (progress["id"],),
                    ).fetchall()
                    for old in old_missions:
                        if not old["place_id"]:
                            continue
                        place_cursor = conn.execute(
                            """INSERT INTO course_places(course_id, place_id, sequence_no)
                               VALUES (?, ?, ?)""",
                            (course_id, old["place_id"], old["sequence_no"]),
                        )
                        mission_cursor = conn.execute(
                            """INSERT INTO course_missions(course_place_id, title, description, stamp_reward)
                               VALUES (?, ?, ?, ?)""",
                            (place_cursor.lastrowid, old["title"], f"{old['title']}에서 체크인하기", old["stamp_reward"]),
                        )
                    user_course_cursor = conn.execute(
                        """INSERT INTO user_courses(user_id, course_id, status, current_sequence, started_at, completed_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (user_id, course_id, progress["status"], min(progress["completed_missions"] + 1, max(progress["total_missions"], 1)), progress["started_at"], progress["completed_at"]),
                    )
                    user_course_id = int(user_course_cursor.lastrowid)
                    for old in old_missions:
                        if old["status"] != "completed" or not old["place_id"]:
                            continue
                        mission = conn.execute(
                            """SELECT cm.id FROM course_missions cm
                               JOIN course_places cp ON cp.id = cm.course_place_id
                               WHERE cp.course_id = ? AND cp.sequence_no = ?""",
                            (course_id, old["sequence_no"]),
                        ).fetchone()
                        if mission:
                            checkin_cursor = conn.execute(
                                "INSERT INTO checkins(user_course_id, mission_id, checked_in_at) VALUES (?, ?, COALESCE(?, CURRENT_TIMESTAMP))",
                                (user_course_id, mission["id"], old["checked_in_at"]),
                            )
                            conn.execute(
                                "INSERT INTO stamps(user_id, checkin_id, place_id, earned_at) VALUES (?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))",
                                (user_id, checkin_cursor.lastrowid, old["place_id"], old["checked_in_at"]),
                            )

            conn.execute("INSERT INTO schema_migrations(version) VALUES ('normalized-v1')")

        for legacy_table in (
            "community_likes", "community_post_images", "legacy_community_posts",
            "user_course_missions", "user_course_progress", "missions", "travel_courses",
        ):
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (legacy_table,)).fetchone():
                conn.execute(f"DROP TABLE {legacy_table}")
        conn.commit()


def get_user_by_nickname(nickname: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, nickname, profile_icon, created_at FROM users WHERE nickname = ?",
            (nickname,),
        ).fetchone()
        return dict(row) if row else None


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 210_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def create_user(nickname: str, profile_icon: str, password: str) -> dict:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO users (nickname, profile_icon, password_hash) VALUES (?, ?, ?)",
            (nickname, profile_icon, _hash_password(password)),
        )
        if cursor.lastrowid:
            conn.execute(
                "UPDATE users SET anonymous_key = 'user:' || id WHERE id = ? AND anonymous_key IS NULL",
                (cursor.lastrowid,),
            )
            row = conn.execute(
                "SELECT id, nickname, profile_icon, created_at FROM users WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, nickname, profile_icon, created_at FROM users WHERE nickname = ?",
                (nickname,),
            ).fetchone()
        conn.commit()
        return dict(row)


def login_user(nickname: str, profile_icon: str, password: str) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, nickname, profile_icon, created_at, password_hash FROM users WHERE nickname = ?",
            (nickname,),
        ).fetchone()
        if not row:
            return create_user(nickname, profile_icon, password)
        if not row["password_hash"]:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (_hash_password(password), row["id"]),
            )
            conn.commit()
        elif not _verify_password(password, row["password_hash"]):
            raise ValueError("비밀번호가 올바르지 않습니다.")
        return {key: row[key] for key in ("id", "nickname", "profile_icon", "created_at")}


def change_user_password(user_id: int, current_password: str, new_password: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise LookupError("사용자를 찾을 수 없습니다.")
        if not row["password_hash"] or not _verify_password(current_password, row["password_hash"]):
            raise ValueError("현재 비밀번호가 올바르지 않습니다.")
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (_hash_password(new_password), user_id))
        conn.commit()
        return True


def seed_test_data() -> int:
    # AI recommendations are normalized into courses when a user starts one.
    return 0


def load_json_data(data_dir: Path | None = None) -> int:
    data_dir = data_dir or DATA_DIR
    json_files = sorted(data_dir.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No JSON files found in {data_dir}")

    inserted = 0
    with get_connection() as conn:
        for json_path in json_files:
            with json_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            region = payload.get("region", "")
            content_type = payload.get("contentType", "")
            content_type_id = str(payload.get("contentTypeId", ""))

            for item in payload.get("items", []):
                values = {
                    "source_file": json_path.name,
                    "region": region,
                    "content_type": content_type,
                    "content_type_id": content_type_id,
                    "contentid": item.get("contentid", ""),
                    "contenttypeid": item.get("contenttypeid", ""),
                    "title": item.get("title", ""),
                    "addr1": item.get("addr1", ""),
                    "addr2": extract_district(item.get("addr1")) or item.get("addr2", ""),
                    "zipcode": item.get("zipcode", ""),
                    "tel": item.get("tel", ""),
                    "mapx": item.get("mapx", ""),
                    "mapy": item.get("mapy", ""),
                    "mlevel": item.get("mlevel", ""),
                    "areacode": item.get("areacode", ""),
                    "sigungucode": item.get("sigungucode", ""),
                    "lDongRegnCd": item.get("lDongRegnCd", ""),
                    "lDongSignguCd": item.get("lDongSignguCd", ""),
                    "cat1": item.get("cat1", ""),
                    "cat2": item.get("cat2", ""),
                    "cat3": item.get("cat3", ""),
                    "lclsSystm1": item.get("lclsSystm1", ""),
                    "lclsSystm2": item.get("lclsSystm2", ""),
                    "lclsSystm3": item.get("lclsSystm3", ""),
                    "firstimage": item.get("firstimage", ""),
                    "firstimage2": item.get("firstimage2", ""),
                    "cpyrhtDivCd": item.get("cpyrhtDivCd", ""),
                    "createdtime": item.get("createdtime", ""),
                    "modifiedtime": item.get("modifiedtime", ""),
                }

                columns = ", ".join(values.keys())
                placeholders = ", ".join(["?" for _ in values])
                try:
                    conn.execute(
                        f"INSERT OR IGNORE INTO places ({columns}) VALUES ({placeholders})",
                        tuple(values.values()),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    continue

        conn.commit()

    return inserted


def backfill_place_districts() -> int:
    """Fill addr2 from addr1, or from the nearest district centroid when address is empty."""
    with get_connection() as conn:
        rows = conn.execute("SELECT id, addr1, addr2, mapx, mapy FROM places").fetchall()
        updates = []
        for row in rows:
            district = extract_district(row["addr1"])
            if district and row["addr2"] != district:
                updates.append((district, row["id"]))
        conn.executemany("UPDATE places SET addr2 = ? WHERE id = ?", updates)

        # Some source types, especially 여행코스, have coordinates but no address.
        coordinate_groups: dict[str, list[tuple[float, float]]] = {}
        for row in rows:
            district = extract_district(row["addr1"]) or (row["addr2"] if row["addr2"] in SEOUL_DISTRICTS else None)
            try:
                lon, lat = float(row["mapx"]), float(row["mapy"])
            except (TypeError, ValueError):
                continue
            if district and 126 <= lon <= 128 and 37 <= lat <= 38:
                coordinate_groups.setdefault(district, []).append((lon, lat))
        centroids = {
            district: (
                sum(point[0] for point in points) / len(points),
                sum(point[1] for point in points) / len(points),
            )
            for district, points in coordinate_groups.items()
            if points
        }
        coordinate_updates = []
        for row in rows:
            if extract_district(row["addr1"]) or row["addr2"] in SEOUL_DISTRICTS:
                continue
            try:
                lon, lat = float(row["mapx"]), float(row["mapy"])
            except (TypeError, ValueError):
                continue
            if not (126 <= lon <= 128 and 37 <= lat <= 38) or not centroids:
                continue
            nearest = min(
                centroids,
                key=lambda district: (lon - centroids[district][0]) ** 2 + (lat - centroids[district][1]) ** 2,
            )
            coordinate_updates.append((nearest, row["id"]))
        conn.executemany("UPDATE places SET addr2 = ? WHERE id = ?", coordinate_updates)
        conn.commit()
        return len(updates) + len(coordinate_updates)


def list_places(limit: int = 20, offset: int = 0) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, addr1, addr2, region, content_type, content_type_id, contentid FROM places ORDER BY id LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]


def count_places() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM places").fetchone()
        return int(row["count"])


def _haversine_km(first: dict, second: dict) -> float:
    """Return distance in kilometres. mapx is longitude and mapy is latitude."""
    lon1, lat1 = math.radians(float(first["mapx"])), math.radians(float(first["mapy"]))
    lon2, lat2 = math.radians(float(second["mapx"])), math.radians(float(second["mapy"]))
    dlon, dlat = lon2 - lon1, lat2 - lat1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(value))


def _insert_at_cheapest_position(route: list[dict], place: dict) -> list[dict]:
    """Splice `place` into `route` wherever it adds the least extra walking distance.

    Building the route first (ignoring `place`) and inserting it afterward keeps
    each course's own character intact instead of forcing `place` to be the
    fixed starting point of every course.
    """
    best_index = len(route)
    best_extra_cost = _haversine_km(route[-1], place)
    for index in range(len(route) - 1):
        before, after = route[index], route[index + 1]
        extra_cost = (
            _haversine_km(before, place) + _haversine_km(place, after) - _haversine_km(before, after)
        )
        if extra_cost < best_extra_cost:
            best_extra_cost = extra_cost
            best_index = index + 1
    return route[:best_index] + [place] + route[best_index:]


_WALK_SPEED_KMH = 4.0
_DWELL_HOURS_BY_CATEGORY = {
    "관광지": 1.5,
    "문화시설": 1.0,
    "축제공연행사": 1.0,
    "레포츠": 1.5,
    "쇼핑": 0.5,
    "숙박": 0.5,
    "여행코스": 1.0,
}
_DEFAULT_DWELL_HOURS = 1.0
_TIME_TOLERANCE_HOURS = 20 / 60
_MAX_TIME_TARGETED_STOPS = 8
_DEFAULT_TARGET_HOURS = 6.0


def _estimate_duration_hours(route: list[dict], total_distance_km: float) -> int:
    """Walking time from total_distance_km plus a per-stop dwell time estimate."""
    travel_hours = total_distance_km / _WALK_SPEED_KMH
    dwell_hours = sum(
        _DWELL_HOURS_BY_CATEGORY.get(place["content_type"], _DEFAULT_DWELL_HOURS) for place in route
    )
    return max(1, round(travel_hours + dwell_hours))


def recommend_courses(query: str, limit: int = 3) -> list[dict]:
    """Recommend district-local routes ordered by geographic proximity.

    Returns an empty list when the message shows no sign of being a Seoul
    travel request, instead of falling back to a generic "인기" course.
    """
    normalized = query.strip().lower()
    if not has_travel_intent(query):
        return []

    selected_theme = next(
        (theme for theme, words in _THEMES.items() if any(word in normalized for word in words)),
        "인기",
    )
    theme_words = _THEMES.get(selected_theme, ["서울", "명소", "여행"])
    explicit_categories = [category for category in CONTENT_TYPES if category in normalized]
    selected_categories = explicit_categories or [
        category for category, words in _CATEGORY_KEYWORDS.items()
        if any(word in normalized for word in words)
    ] or list(CONTENT_TYPES)
    selected_district = next(
        (
            district for district in SEOUL_DISTRICTS
            if district in normalized or _district_short_name(district) in normalized
        ),
        None,
    )
    target_hours_match = re.search(r"(\d+(?:\.\d+)?)\s*시간", normalized)
    target_hours = float(target_hours_match.group(1)) if target_hours_match else _DEFAULT_TARGET_HOURS

    must_include_place = find_must_include_place(query, district=selected_district)
    if must_include_place is None and selected_district:
        must_include_place = find_must_include_place(query)
    if must_include_place and not selected_district:
        selected_district = must_include_place["addr2"] or selected_district

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, addr1, addr2, content_type, firstimage, mapx, mapy
            FROM places
            WHERE title != '' AND addr2 != '' AND firstimage != ''
              AND content_type IN ('관광지', '레포츠', '문화시설', '쇼핑', '숙박', '여행코스', '축제공연행사')
              AND CAST(mapx AS REAL) BETWEEN 126 AND 128
              AND CAST(mapy AS REAL) BETWEEN 37 AND 38
            ORDER BY id
            """
        ).fetchall()

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        place = dict(row)
        if selected_district and place["addr2"] != selected_district:
            continue
        if place["content_type"] not in selected_categories:
            continue
        haystack = f"{place['title']} {place['addr1']} {place['content_type']}".lower()
        score = sum(6 for word in theme_words if word in haystack)
        score += sum(3 for word in normalized.split() if len(word) >= 2 and word in haystack)
        score += 3 if place["content_type"] in selected_categories else 0
        score += 2 if place["content_type"] in ("관광지", "여행코스") else 0
        place["recommendation_score"] = score
        grouped.setdefault(place["addr2"], []).append(place)

    if must_include_place and must_include_place["addr2"] not in grouped:
        grouped[must_include_place["addr2"]] = []

    for district_places in grouped.values():
        district_places.sort(key=lambda place: (-place["recommendation_score"], place["id"]))
    district_order = sorted(
        grouped,
        key=lambda district: (
            -sum(place["recommendation_score"] for place in grouped[district][:10]),
            -len({place["content_type"] for place in grouped[district]}),
            district,
        ),
    )
    if selected_district:
        district_order = [selected_district] * limit if selected_district in grouped else []
    else:
        district_order = district_order[:limit]

    courses: list[dict] = []
    used_by_district: dict[str, set[int]] = {}
    labels = ["베스트", "여유", "발견", "취향", "로컬"]
    for index, district in enumerate(district_order):
        used_ids = used_by_district.setdefault(district, set())
        ranked = [place for place in grouped[district] if place["id"] not in used_ids]
        if not ranked:
            ranked = grouped[district]

        # Limit each category so the 4,368 shopping rows cannot hide other source types.
        category_counts: dict[str, int] = {}
        balanced_pool = []
        for place in ranked:
            category = place["content_type"]
            if category_counts.get(category, 0) >= 8:
                continue
            category_counts[category] = category_counts.get(category, 0) + 1
            balanced_pool.append(place)
        balanced_pool.sort(key=lambda place: (-place["recommendation_score"], place["id"]))

        forced_here = must_include_place is not None and must_include_place["addr2"] == district
        if not balanced_pool and not forced_here:
            continue

        route = [balanced_pool.pop(0)] if balanced_pool else [dict(must_include_place)]
        # Keep adding the nearest next stop while it stays within ~20 minutes of the requested duration.
        hours_used = _DWELL_HOURS_BY_CATEGORY.get(route[0]["content_type"], _DEFAULT_DWELL_HOURS)
        while balanced_pool and len(route) < _MAX_TIME_TARGETED_STOPS:
            current = route[-1]
            next_place = min(
                balanced_pool,
                key=lambda place: (_haversine_km(current, place), -place["recommendation_score"]),
            )
            added_hours = _haversine_km(current, next_place) / _WALK_SPEED_KMH + _DWELL_HOURS_BY_CATEGORY.get(
                next_place["content_type"], _DEFAULT_DWELL_HOURS
            )
            if hours_used + added_hours > target_hours + _TIME_TOLERANCE_HOURS:
                break
            balanced_pool.remove(next_place)
            route.append(next_place)
            hours_used += added_hours

        # Build each course normally first, then splice the requested place in wherever it
        # costs the least extra walking distance -- keeps every course's own character
        # instead of forcing the same fixed starting point on all of them.
        if forced_here and not any(place["id"] == must_include_place["id"] for place in route):
            route = _insert_at_cheapest_position(route, dict(must_include_place))

        total_distance = 0.0
        for route_index, place in enumerate(route):
            distance = 0.0 if route_index == 0 else _haversine_km(route[route_index - 1], place)
            total_distance += distance
            place["distance_from_previous_km"] = round(distance, 2)
            place.pop("recommendation_score", None)
            used_ids.add(place["id"])
        categories = list(dict.fromkeys(place["content_type"] for place in route))
        label = labels[index % len(labels)]
        courses.append(
            {
                "id": f"recommended-{district}-{index + 1}",
                "title": f"{district} {selected_theme} {label} 코스",
                "theme": selected_theme,
                "district": district,
                "categories": categories,
                "duration_hours": _estimate_duration_hours(route, total_distance),
                "stamp_count": len(route),
                "total_distance_km": round(total_distance, 2),
                "image_url": route[0]["firstimage"],
                "summary": " → ".join(place["title"] for place in route),
                "places": route,
                "reason": (
                    f"요청하신 '{must_include_place['title']}'을(를) 동선상 가장 자연스러운 위치에 포함해서, "
                    f"{district} 안에서 가까운 장소 순서로 구성했어요."
                    if forced_here
                    else f"{district} 안에서 mapx(경도)·mapy(위도)를 기준으로 가까운 장소 순서로 구성했어요."
                ),
            }
        )
    return courses


def _attach_post_images(conn: sqlite3.Connection, post: dict, user_key: str | None = None) -> dict:
    images = conn.execute(
        "SELECT image_url FROM post_images WHERE post_id = ? ORDER BY sort_order, id",
        (post["id"],),
    ).fetchall()
    post["image_urls"] = [row["image_url"] for row in images]
    post["image_url"] = post["image_urls"][0] if post["image_urls"] else None
    tag_rows = conn.execute(
        "SELECT tag FROM post_tags WHERE post_id = ? ORDER BY tag",
        (post["id"],),
    ).fetchall()
    post["tags"] = [row["tag"] for row in tag_rows]
    post["nickname"] = "익명 사용자"
    viewer_id = _lookup_user_id(conn, user_key)
    author_id = post.get("author_id")
    can_manage = bool(viewer_id and author_id == viewer_id)
    post["can_edit"] = can_manage
    post["can_delete"] = can_manage
    post["liked"] = bool(
        viewer_id
        and conn.execute(
            "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?",
            (post["id"], viewer_id),
        ).fetchone()
    )
    post["bookmarked"] = bool(
        viewer_id
        and conn.execute(
            "SELECT 1 FROM post_bookmarks WHERE post_id = ? AND user_id = ?",
            (post["id"], viewer_id),
        ).fetchone()
    )
    post.pop("author_id", None)
    return post


def list_community_posts(
    district: str | None = None,
    query: str | None = None,
    user_key: str | None = None,
    bookmarked_only: bool = False,
    mine_only: bool = False,
    sort_by: str = "latest",
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    with get_connection() as conn:
        viewer_id = _lookup_user_id(conn, user_key)
        conditions: list[str] = []
        params: list[object] = []
        if district:
            conditions.append("cp.district = ?")
            params.append(district)
        if query:
            conditions.append("(cp.title LIKE ? OR cp.content LIKE ? OR EXISTS (SELECT 1 FROM post_tags pt WHERE pt.post_id = cp.id AND pt.tag LIKE ?))")
            keyword = f"%{query}%"
            params.extend([keyword, keyword, keyword])
        if bookmarked_only:
            if not viewer_id:
                return []
            conditions.append("EXISTS (SELECT 1 FROM post_bookmarks pb WHERE pb.post_id = cp.id AND pb.user_id = ?)")
            params.append(viewer_id)
        if mine_only:
            if not viewer_id:
                return []
            conditions.append("cp.author_id = ?")
            params.append(viewer_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order_by = {
            "latest": "cp.created_at DESC, cp.id DESC",
            "popular": "(cp.like_count + cp.view_count + (SELECT COUNT(*) FROM post_bookmarks pb WHERE pb.post_id = cp.id)) DESC, cp.id DESC",
            "views": "cp.view_count DESC, cp.id DESC",
            "likes": "cp.like_count DESC, cp.id DESC",
            "bookmarks": "(SELECT COUNT(*) FROM post_bookmarks pb WHERE pb.post_id = cp.id) DESC, cp.id DESC",
        }.get(sort_by, "cp.created_at DESC, cp.id DESC")
        rows = conn.execute(
            f"""SELECT cp.id, cp.author_id, cp.title, cp.content, cp.region, cp.district,
                       cp.like_count, cp.view_count, cp.created_at
                FROM community_posts cp {where}
                ORDER BY {order_by} LIMIT ? OFFSET ?""",
            (*params, limit, offset),
        ).fetchall()
        return [_attach_post_images(conn, dict(row), user_key=user_key) for row in rows]


def get_community_post(post_id: int, user_key: str | None = None, increment_view: bool = False) -> dict | None:
    with get_connection() as conn:
        if increment_view:
            conn.execute("UPDATE community_posts SET view_count = view_count + 1 WHERE id = ?", (post_id,))
            conn.commit()
        row = conn.execute(
            """SELECT id, author_id, title, content, region, district, like_count, view_count, created_at
               FROM community_posts WHERE id = ?""",
            (post_id,),
        ).fetchone()
        return _attach_post_images(conn, dict(row), user_key=user_key) if row else None


def create_community_post(
    owner_key: str,
    nickname: str,
    title: str,
    content: str,
    region: str,
    district: str,
    image_urls: list[str],
    tags: list[str],
) -> dict:
    with get_connection() as conn:
        author_id = _resolve_user_id(conn, owner_key, nickname)
        cursor = conn.execute(
            """INSERT INTO community_posts (author_id, title, content, region, district)
               VALUES (?, ?, ?, ?, ?)""",
            (author_id, title, content, region, district),
        )
        post_id = int(cursor.lastrowid)
        conn.executemany(
            "INSERT INTO post_images (post_id, image_url, sort_order) VALUES (?, ?, ?)",
            [(post_id, url, index) for index, url in enumerate(image_urls[:5])],
        )
        conn.executemany(
            "INSERT INTO post_tags (post_id, tag) VALUES (?, ?)",
            [(post_id, tag) for tag in tags[:5]],
        )
        conn.commit()
    return get_community_post(post_id, user_key=owner_key)


def update_community_post(
    post_id: int,
    user_key: str,
    title: str,
    content: str,
    region: str,
    district: str,
    image_urls: list[str],
    tags: list[str],
) -> dict | bool | None:
    with get_connection() as conn:
        user_id = _lookup_user_id(conn, user_key)
        row = conn.execute(
            "SELECT author_id FROM community_posts WHERE id = ?", (post_id,)
        ).fetchone()
        if not row:
            return None
        if not user_id or row["author_id"] != user_id:
            return False
        conn.execute(
            """UPDATE community_posts
               SET title = ?, content = ?, region = ?, district = ?
               WHERE id = ?""",
            (title, content, region, district, post_id),
        )
        conn.execute("DELETE FROM post_images WHERE post_id = ?", (post_id,))
        conn.executemany(
            "INSERT INTO post_images (post_id, image_url, sort_order) VALUES (?, ?, ?)",
            [(post_id, url, index) for index, url in enumerate(image_urls[:5])],
        )
        conn.execute("DELETE FROM post_tags WHERE post_id = ?", (post_id,))
        conn.executemany(
            "INSERT INTO post_tags (post_id, tag) VALUES (?, ?)",
            [(post_id, tag) for tag in tags[:5]],
        )
        conn.commit()
    return get_community_post(post_id, user_key=user_key)


def delete_community_post(post_id: int, user_key: str) -> bool | None:
    with get_connection() as conn:
        user_id = _lookup_user_id(conn, user_key)
        row = conn.execute(
            "SELECT author_id FROM community_posts WHERE id = ?", (post_id,)
        ).fetchone()
        if not row:
            return None
        if not user_id or row["author_id"] != user_id:
            return False
        conn.execute("DELETE FROM community_posts WHERE id = ?", (post_id,))
        conn.commit()
        return True


def toggle_community_like(post_id: int, user_key: str) -> dict | None:
    with get_connection() as conn:
        post = conn.execute("SELECT id FROM community_posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            return None
        user_id = _resolve_user_id(conn, user_key)
        liked = conn.execute(
            "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?",
            (post_id, user_id),
        ).fetchone()
        if liked:
            conn.execute("DELETE FROM post_likes WHERE post_id = ? AND user_id = ?", (post_id, user_id))
            conn.execute("UPDATE community_posts SET like_count = MAX(0, like_count - 1) WHERE id = ?", (post_id,))
            is_liked = False
        else:
            conn.execute("INSERT INTO post_likes (post_id, user_id) VALUES (?, ?)", (post_id, user_id))
            conn.execute("UPDATE community_posts SET like_count = like_count + 1 WHERE id = ?", (post_id,))
            is_liked = True
        conn.commit()
        count = conn.execute("SELECT like_count FROM community_posts WHERE id = ?", (post_id,)).fetchone()[0]
        return {"post_id": post_id, "liked": is_liked, "like_count": count}


def toggle_community_bookmark(post_id: int, user_key: str) -> dict | None:
    with get_connection() as conn:
        if not conn.execute("SELECT 1 FROM community_posts WHERE id = ?", (post_id,)).fetchone():
            return None
        user_id = _resolve_user_id(conn, user_key)
        bookmarked = conn.execute(
            "SELECT 1 FROM post_bookmarks WHERE post_id = ? AND user_id = ?",
            (post_id, user_id),
        ).fetchone()
        if bookmarked:
            conn.execute("DELETE FROM post_bookmarks WHERE post_id = ? AND user_id = ?", (post_id, user_id))
            is_bookmarked = False
        else:
            conn.execute("INSERT INTO post_bookmarks(post_id, user_id) VALUES (?, ?)", (post_id, user_id))
            is_bookmarked = True
        conn.commit()
        return {"post_id": post_id, "bookmarked": is_bookmarked}


def list_community_images(district: str | None = None, limit: int = 15) -> list[dict]:
    with get_connection() as conn:
        if district:
            rows = conn.execute(
                """SELECT id, title, addr2 AS district, firstimage AS image_url
                   FROM places WHERE addr2 = ? AND firstimage != ''
                   ORDER BY CASE content_type WHEN '관광지' THEN 0 WHEN '문화시설' THEN 1 ELSE 2 END, id
                   LIMIT ?""",
                (district, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, title, addr2 AS district, firstimage AS image_url
                   FROM places WHERE firstimage != '' AND addr2 != ''
                   ORDER BY CASE content_type WHEN '관광지' THEN 0 WHEN '문화시설' THEN 1 ELSE 2 END, id
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]


def get_community_statistics() -> dict:
    region_case = """CASE
        WHEN district IN ('종로구', '중구', '용산구') THEN '도심권'
        WHEN district IN ('성동구', '광진구', '동대문구', '중랑구', '성북구', '강북구', '도봉구', '노원구') THEN '동북권'
        WHEN district IN ('은평구', '서대문구', '마포구') THEN '서북권'
        WHEN district IN ('양천구', '강서구', '구로구', '금천구', '영등포구', '동작구', '관악구') THEN '서남권'
        ELSE '동남권' END"""
    with get_connection() as conn:
        region_rows = conn.execute(
            f"""SELECT {region_case} AS region_group, COUNT(*) AS post_count,
                       COALESCE(SUM(like_count), 0) AS like_count,
                       COALESCE(SUM(view_count), 0) AS view_count,
                       COALESCE(SUM((SELECT COUNT(*) FROM post_bookmarks pb WHERE pb.post_id = community_posts.id)), 0) AS bookmark_count
                FROM community_posts GROUP BY region_group ORDER BY post_count DESC"""
        ).fetchall()
        district_rows = conn.execute(
            """SELECT district, COUNT(*) AS post_count,
                      COALESCE(SUM(like_count), 0) AS like_count,
                      COALESCE(SUM(view_count), 0) AS view_count,
                      COALESCE(SUM((SELECT COUNT(*) FROM post_bookmarks pb WHERE pb.post_id = community_posts.id)), 0) AS bookmark_count
               FROM community_posts GROUP BY district
               ORDER BY (like_count + view_count + bookmark_count) DESC, post_count DESC LIMIT 5"""
        ).fetchall()
        totals = conn.execute(
            """SELECT COUNT(*) AS post_count, COALESCE(SUM(like_count), 0) AS like_count,
                      COALESCE(SUM(view_count), 0) AS view_count,
                      (SELECT COUNT(*) FROM post_bookmarks) AS bookmark_count FROM community_posts"""
        ).fetchone()
        region_values = {row["region_group"]: dict(row) for row in region_rows}
        all_regions = [
            region_values.get(name, {"region_group": name, "post_count": 0, "like_count": 0, "view_count": 0, "bookmark_count": 0})
            for name in ("도심권", "동북권", "서북권", "서남권", "동남권")
        ]
        return {
            "totals": dict(totals),
            "regions": all_regions,
            "popular_districts": [dict(row) for row in district_rows],
        }


def seed_community_posts() -> int:
    samples = [
        ("종로구에서 보낸 가장 힐링되는 하루", "광화문부터 북촌한옥마을, 창덕궁까지 천천히 다녀왔어요. 전통과 역사가 어우러진 종로의 하루를 추천합니다.", "종로구", 128),
        ("봄날의 경복궁 산책", "햇살이 따뜻한 경복궁을 걸으며 여유로운 시간을 보냈어요. 사진 찍기 좋은 장소도 많아요.", "종로구", 96),
        ("낙산공원에서 바라본 서울 야경", "낮에는 한양도성길을 걷고, 저녁에는 낙산공원에서 야경까지 완벽한 코스였어요.", "종로구", 87),
        ("서울 골목 골목, 감성 가득한 하루", "조용한 분위기의 카페와 오래된 골목을 발견하는 재미가 있었어요.", "마포구", 55),
        ("창덕궁 후원, 꼭 가보세요", "창덕궁 후원은 사전 예약을 추천해요. 자연과 어우러진 풍경이 정말 인상적이었습니다.", "종로구", 43),
    ]
    with get_connection() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM community_posts").fetchone()[0]
        if existing:
            return 0
        author_id = _resolve_user_id(conn, "seed:community", "익명 사용자")
        inserted = 0
        for sample_index, (title, content, district, like_count) in enumerate(samples):
            image_rows = conn.execute(
                "SELECT firstimage FROM places WHERE addr2 = ? AND firstimage != '' ORDER BY id LIMIT 3 OFFSET ?",
                (district, sample_index * 3),
            ).fetchall()
            cursor = conn.execute(
                """INSERT INTO community_posts (author_id, title, content, district, like_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (author_id, title, content, district, like_count),
            )
            post_id = int(cursor.lastrowid)
            conn.executemany(
                "INSERT INTO post_images (post_id, image_url, sort_order) VALUES (?, ?, ?)",
                [(post_id, row["firstimage"], index) for index, row in enumerate(image_rows)],
            )
            inserted += 1
        conn.commit()
        return inserted


def _get_course_progress(conn: sqlite3.Connection, progress_id: int) -> dict | None:
    row = conn.execute(
        """SELECT uc.id, u.anonymous_key AS user_key, c.title, c.theme,
                  COALESCE(c.description, '') AS summary,
                  COALESCE(c.image_url, '') AS image_url,
                  (SELECT COUNT(*) FROM course_places cp WHERE cp.course_id = c.id) AS total_missions,
                  (SELECT COUNT(*) FROM checkins ci WHERE ci.user_course_id = uc.id) AS completed_missions,
                  uc.status, uc.started_at, uc.completed_at
           FROM user_courses uc
           JOIN users u ON u.id = uc.user_id
           JOIN courses c ON c.id = uc.course_id
           WHERE uc.id = ?""",
        (progress_id,),
    ).fetchone()
    if not row:
        return None
    progress = dict(row)
    missions = conn.execute(
        """SELECT cm.id, uc.id AS progress_id, cp.sequence_no, p.id AS place_id,
                  cm.title, COALESCE(p.addr1, '') AS address,
                  COALESCE(p.addr2, '') AS district,
                  COALESCE(p.firstimage, '') AS image_url,
                  COALESCE(p.content_type, '관광지') AS content_type,
                  CASE
                    WHEN ci.id IS NOT NULL THEN 'completed'
                    WHEN uc.status = 'in_progress' AND cp.sequence_no = uc.current_sequence THEN 'active'
                    ELSE 'locked'
                  END AS status,
                  cm.stamp_reward, ci.checked_in_at
           FROM user_courses uc
           JOIN course_places cp ON cp.course_id = uc.course_id
           JOIN course_missions cm ON cm.course_place_id = cp.id
           JOIN places p ON p.id = cp.place_id
           LEFT JOIN checkins ci ON ci.user_course_id = uc.id AND ci.mission_id = cm.id
           WHERE uc.id = ? ORDER BY cp.sequence_no""",
        (progress_id,),
    ).fetchall()
    progress["missions"] = [dict(mission) for mission in missions]
    progress["progress_percent"] = round(
        progress["completed_missions"] / max(progress["total_missions"], 1) * 100
    )
    return progress


def start_course_progress(user_key: str, course: dict) -> dict:
    places = course.get("places", [])
    if not places:
        raise ValueError("Course must contain at least one place")
    with get_connection() as conn:
        user_id = _resolve_user_id(conn, user_key)
        existing = conn.execute(
            """SELECT uc.id FROM user_courses uc
               JOIN courses c ON c.id = uc.course_id
               WHERE uc.user_id = ? AND c.title = ? AND uc.status = 'in_progress'
               ORDER BY uc.id DESC LIMIT 1""",
            (user_id, course["title"]),
        ).fetchone()
        if existing:
            return _get_course_progress(conn, existing["id"])

        course_cursor = conn.execute(
            """INSERT INTO courses
               (created_by, title, description, district, theme, source, image_url,
                total_distance_km, estimated_hours)
               VALUES (?, ?, ?, ?, ?, 'ai', ?, ?, ?)""",
            (
                user_id,
                course["title"],
                course.get("summary", ""),
                places[0].get("addr2") or "서울특별시",
                course.get("theme", "여행"),
                course.get("image_url", ""),
                float(course.get("total_distance_km") or 0),
                max(1, int(round(float(course.get("duration_hours") or len(places))))),
            ),
        )
        course_id = int(course_cursor.lastrowid)
        for index, place in enumerate(places, start=1):
            place_id = place.get("id")
            if not place_id:
                raise ValueError("Every course place must reference a stored place")
            cp_cursor = conn.execute(
                """INSERT INTO course_places
                   (course_id, place_id, sequence_no, distance_from_previous_km)
                   VALUES (?, ?, ?, ?)""",
                (course_id, place_id, index, float(place.get("distance_from_previous_km") or 0)),
            )
            title = place.get("title") or f"미션 {index}"
            conn.execute(
                """INSERT INTO course_missions
                   (course_place_id, title, description, mission_type, stamp_reward)
                   VALUES (?, ?, ?, 'checkin', 1)""",
                (cp_cursor.lastrowid, title, f"{title}에서 체크인하기"),
            )
        progress_cursor = conn.execute(
            "INSERT INTO user_courses(user_id, course_id) VALUES (?, ?)",
            (user_id, course_id),
        )
        progress_id = int(progress_cursor.lastrowid)
        conn.commit()
        return _get_course_progress(conn, progress_id)


def list_user_course_progress(user_key: str, status: str | None = None) -> list[dict]:
    with get_connection() as conn:
        user_id = _lookup_user_id(conn, user_key)
        if not user_id:
            return []
        if status:
            rows = conn.execute(
                "SELECT id FROM user_courses WHERE user_id = ? AND status = ? ORDER BY id DESC",
                (user_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id FROM user_courses WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        return [_get_course_progress(conn, row["id"]) for row in rows]


def get_user_course_progress(progress_id: int, user_key: str) -> dict | None:
    with get_connection() as conn:
        user_id = _lookup_user_id(conn, user_key)
        if not user_id:
            return None
        owner = conn.execute(
            "SELECT id FROM user_courses WHERE id = ? AND user_id = ?",
            (progress_id, user_id),
        ).fetchone()
        return _get_course_progress(conn, progress_id) if owner else None


def abandon_user_course_progress(progress_id: int, user_key: str) -> bool:
    with get_connection() as conn:
        user_id = _lookup_user_id(conn, user_key)
        if not user_id:
            return False
        cursor = conn.execute(
            "DELETE FROM user_courses WHERE id = ? AND user_id = ? AND status = 'in_progress'",
            (progress_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_completed_user_course_progress(progress_id: int, user_key: str) -> bool:
    with get_connection() as conn:
        user_id = _lookup_user_id(conn, user_key)
        if not user_id:
            return False
        cursor = conn.execute(
            "DELETE FROM user_courses WHERE id = ? AND user_id = ? AND status = 'completed'",
            (progress_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def check_in_course_mission(progress_id: int, mission_id: int, user_key: str) -> dict | None:
    with get_connection() as conn:
        user_id = _lookup_user_id(conn, user_key)
        if not user_id:
            return None
        progress = conn.execute(
            "SELECT * FROM user_courses WHERE id = ? AND user_id = ?",
            (progress_id, user_id),
        ).fetchone()
        if not progress:
            return None
        mission = conn.execute(
            """SELECT cm.*, cp.sequence_no, cp.place_id
               FROM course_missions cm
               JOIN course_places cp ON cp.id = cm.course_place_id
               WHERE cm.id = ? AND cp.course_id = ?""",
            (mission_id, progress["course_id"]),
        ).fetchone()
        if not mission:
            return None
        existing_checkin = conn.execute(
            "SELECT 1 FROM checkins WHERE user_course_id = ? AND mission_id = ?",
            (progress_id, mission_id),
        ).fetchone()
        if existing_checkin:
            current = _get_course_progress(conn, progress_id)
            return {
                "progress": current,
                "completed_mission": next(item for item in current["missions"] if item["id"] == mission_id),
                "stamp_earned": mission["stamp_reward"],
                "course_completed": progress["status"] == "completed",
            }
        if progress["status"] != "in_progress" or mission["sequence_no"] != progress["current_sequence"]:
            raise ValueError("Only the active mission can be checked in")

        checkin_cursor = conn.execute(
            "INSERT INTO checkins(user_course_id, mission_id) VALUES (?, ?)",
            (progress_id, mission_id),
        )
        conn.execute(
            "INSERT INTO stamps(user_id, checkin_id, place_id) VALUES (?, ?, ?)",
            (user_id, checkin_cursor.lastrowid, mission["place_id"]),
        )
        completed_count = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE user_course_id = ?",
            (progress_id,),
        ).fetchone()[0]
        total_missions = conn.execute(
            "SELECT COUNT(*) FROM course_places WHERE course_id = ?", (progress["course_id"],)
        ).fetchone()[0]
        course_completed = completed_count >= total_missions
        if course_completed:
            conn.execute(
                "UPDATE user_courses SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (progress_id,),
            )
        else:
            conn.execute(
                "UPDATE user_courses SET current_sequence = ? WHERE id = ?",
                (mission["sequence_no"] + 1, progress_id),
            )
        conn.commit()
        refreshed = _get_course_progress(conn, progress_id)
        return {
            "progress": refreshed,
            "completed_mission": next(item for item in refreshed["missions"] if item["id"] == mission_id),
            "stamp_earned": mission["stamp_reward"],
            "course_completed": course_completed,
        }


def list_courses(limit: int = 20, offset: int = 0) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, title, COALESCE(description, '') AS description,
                      district AS region, 'normal' AS difficulty
               FROM courses ORDER BY id DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]


def get_course(course_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT id, title, COALESCE(description, '') AS description,
                      district AS region, 'normal' AS difficulty
               FROM courses WHERE id = ?""",
            (course_id,),
        ).fetchone()
        return dict(row) if row else None


def list_missions(course_id: int, limit: int = 20, offset: int = 0) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT cm.id, cp.course_id, cm.title,
                      COALESCE(cm.description, '') AS description,
                      cm.stamp_reward AS reward_points, 0 AS completed
               FROM course_missions cm
               JOIN course_places cp ON cp.id = cm.course_place_id
               WHERE cp.course_id = ? ORDER BY cp.sequence_no LIMIT ? OFFSET ?""",
            (course_id, limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]


def complete_mission(course_id: int, mission_id: int) -> dict | None:
    """Compatibility lookup; completion is user-scoped through the check-in API."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT cm.id, cp.course_id, cm.title,
                      COALESCE(cm.description, '') AS description,
                      cm.stamp_reward AS reward_points, 0 AS completed
               FROM course_missions cm
               JOIN course_places cp ON cp.id = cm.course_place_id
               WHERE cm.id = ? AND cp.course_id = ?""",
            (mission_id, course_id),
        ).fetchone()
        return dict(row) if row else None


def toggle_course_like(course_id: int, user_key: str) -> dict | None:
    with get_connection() as conn:
        if not conn.execute("SELECT 1 FROM courses WHERE id = ?", (course_id,)).fetchone():
            return None
        user_id = _resolve_user_id(conn, user_key)
        existing = conn.execute(
            "SELECT 1 FROM course_likes WHERE course_id = ? AND user_id = ?",
            (course_id, user_id),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM course_likes WHERE course_id = ? AND user_id = ?",
                (course_id, user_id),
            )
            liked = False
        else:
            conn.execute(
                "INSERT INTO course_likes(course_id, user_id) VALUES (?, ?)",
                (course_id, user_id),
            )
            liked = True
        like_count = conn.execute(
            "SELECT COUNT(*) FROM course_likes WHERE course_id = ?", (course_id,)
        ).fetchone()[0]
        conn.commit()
        return {"course_id": course_id, "liked": liked, "like_count": like_count}


def list_popular_courses(limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.id, c.title, COALESCE(c.description, '') AS description,
                      c.district, c.theme, c.source,
                      COALESCE(c.image_url, '') AS image_url,
                      COUNT(cl.user_id) AS like_count
               FROM courses c
               LEFT JOIN course_likes cl ON cl.course_id = c.id
               GROUP BY c.id
               ORDER BY like_count DESC, c.created_at DESC, c.id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


if __name__ == "__main__":
    init_db()
    count = load_json_data()
    seed_count = seed_test_data()
    print(f"Imported {count} items into {DB_PATH}")
    print(f"Seeded {seed_count} test course/mission records")
