-- Seoul Mission Trip normalized schema (normalized-v1)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nickname TEXT NOT NULL UNIQUE,
    profile_icon TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    anonymous_key TEXT,
    password_hash TEXT
);

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
    modifiedtime TEXT,
    longitude REAL,
    latitude REAL
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
    view_count INTEGER NOT NULL DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_places_district_type ON places(addr2, content_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_anonymous_key ON users(anonymous_key);
CREATE INDEX IF NOT EXISTS idx_places_coordinates ON places(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_courses_district_theme ON courses(district, theme);
CREATE INDEX IF NOT EXISTS idx_user_courses_user_status ON user_courses(user_id, status);
CREATE INDEX IF NOT EXISTS idx_posts_district_created ON community_posts(district, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_checkins_user_course ON checkins(user_course_id);
