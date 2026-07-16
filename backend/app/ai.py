import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_MODEL = "gpt-5-mini"
_client: OpenAI | None = None


def _get_client() -> OpenAI | None:
    global _client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    if _client is None:
        _client = OpenAI(api_key=api_key)
    return _client


def generate_off_topic_reply(message: str, fallback: str) -> str:
    """Short, friendly reply for messages that don't look like a travel request.

    Falls back to a template message if no API key is configured or the call fails.
    """
    client = _get_client()
    if client is None:
        return fallback

    try:
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 '서울 미션 트립' 서비스의 여행 코스 추천 챗봇이야. "
                        "사용자 메시지가 서울 여행 코스 추천 요청처럼 보이지 않을 때 쓰는 응답이야. "
                        "1~2문장으로 짧고 친근하게 반응한 다음, 원하는 테마·지역·소요시간을 알려주면 "
                        "코스를 추천해줄 수 있다고 자연스럽게 안내해. 실제 장소나 코스를 지어내지 마."
                    ),
                },
                {"role": "user", "content": message},
            ],
            max_completion_tokens=300,
            reasoning_effort="minimal",
        )
        answer = response.choices[0].message.content
        return answer.strip() if answer else fallback
    except Exception:
        return fallback


def generate_chat_response(message: str, courses: list[dict], fallback_answer: str) -> dict:
    """Generate a conversational answer and a per-course recommendation reason via OpenAI.

    Falls back to template text if no API key is configured or the call fails,
    so the chat feature keeps working before a key is set.
    """
    fallback_reasons = [
        f"{course['district']} 안에서 mapx(경도)·mapy(위도)를 기준으로 가까운 장소 순서로 구성했어요."
        for course in courses
    ]
    client = _get_client()
    if client is None:
        return {"answer": fallback_answer, "reasons": fallback_reasons}

    course_lines = "\n".join(
        f"{index + 1}. [{course['id']}] {course['title']} - {course['duration_hours']}시간, "
        f"{course['stamp_count']}곳, 총 {course['total_distance_km']}km: {course['summary']}"
        for index, course in enumerate(courses)
    ) or "조건에 맞는 코스를 찾지 못했습니다."

    try:
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 '서울 미션 트립' 서비스의 여행 코스 추천 챗봇이야. "
                        "실제 서울 관광 데이터로 이미 구성된 코스 목록이 주어지면 "
                        '다음 JSON 형식으로만 답해: {"answer": "사용자에게 보여줄 2~3문장 안내", '
                        '"reasons": ["코스별 추천 이유 1문장", ...]}\n'
                        "reasons 배열은 코스 목록과 순서·개수가 같아야 해. "
                        "각 이유는 사용자 요청과 그 코스의 테마·구·거리·장소 구성을 근거로 자연스럽게 설명해. "
                        "목록에 없는 장소나 정보를 지어내지 마."
                    ),
                },
                {
                    "role": "user",
                    "content": f"사용자 요청: {message}\n\n코스 목록:\n{course_lines}",
                },
            ],
            max_completion_tokens=600,
            reasoning_effort="minimal",
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content or "{}")
        answer = (data.get("answer") or "").strip() or fallback_answer
        reasons = data.get("reasons")
        if not isinstance(reasons, list) or len(reasons) != len(courses):
            reasons = fallback_reasons
        else:
            reasons = [
                reason.strip() if isinstance(reason, str) and reason.strip() else fallback_reasons[index]
                for index, reason in enumerate(reasons)
            ]
        return {"answer": answer, "reasons": reasons}
    except Exception:
        return {"answer": fallback_answer, "reasons": fallback_reasons}
