<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import Chart from 'chart.js/auto'
import seoulOnboardingImage from './assets/seoul-onboarding.png'
import {
  MapPinned,
  ChartColumn,
  MessagesSquare,
  BadgeCheck
} from 'lucide-vue-next'

// 페이지네이션 -->
const currentPage = ref(1)
const pageSize = 6

const totalPages = computed(() =>
  Math.ceil(communityPosts.value.length / pageSize)
)

const pagedPosts = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return communityPosts.value.slice(start, start + pageSize)
})

function changePage(page) {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
  }
}

const selectedImage = ref(null)

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const PAGE_STORAGE_KEY = 'seoulMissionPage'
const page = ref('onboarding')
const pageHistory = []
let navigatingBack = false
const nickname = ref('')
const password = ref('')
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const passwordChangeMessage = ref('')
const selectedIcon = ref('mask')
const loading = ref(false)
const errorMessage = ref('')
const courses = ref([])
const chatInput = ref('')
const chatMessages = ref([])
const communityPosts = ref([])
const communityDistrict = ref('')
const communitySort = ref('latest')
const communitySearch = ref('')
const communityBookmarkedOnly = ref(false)
const communityMineOnly = ref(false)
const selectedPost = ref(null)
const galleryImages = ref([])
const communityLoading = ref(false)
const bookmarkingPostIds = ref([])
const communityError = ref('')
const currentUser = ref(null)
const postForm = ref({ title: '', district: '종로구', content: '', image_urls: [], tags: '' })
const selectedTravelCourse = ref(null)
const progressCourses = ref([])
const selectedCompletedCourseIds = ref([])
const activeProgress = ref(null)
const activeMission = ref(null)
const checkInResult = ref(null)
const progressLoading = ref(false)
const chatMessagesElement = ref(null)
const communityStats = ref({
  totals: { post_count: 0, like_count: 0, view_count: 0, bookmark_count: 0 },
  regions: [],
  popular_districts: [],
})
const regionChartElement = ref(null)
const districtChartElement = ref(null)
let regionChart = null
let districtChart = null

const districts = [
  '강남구', '강동구', '강북구', '강서구', '관악구', '광진구', '구로구', '금천구',
  '노원구', '도봉구', '동대문구', '동작구', '마포구', '서대문구', '서초구', '성동구',
  '성북구', '송파구', '양천구', '영등포구', '용산구', '은평구', '종로구', '중구', '중랑구',
]

const categoryTone = {
  관광지: 'cat-attraction', 레포츠: 'cat-leports', 문화시설: 'cat-culture', 쇼핑: 'cat-shopping',
  숙박: 'cat-stay', 여행코스: 'cat-course', 축제공연행사: 'cat-festival',
}

const profileIcons = [
  { id: 'mask', label: '여행자', tone: 'blue' },
  { id: 'place', label: '탐험가', tone: 'green' },
  { id: 'bag', label: '여행가', tone: 'orange' },
  { id: 'hat', label: '도시 여행자', tone: 'purple' },
  { id: 'camera', label: '기록가', tone: 'pink' },
  { id: 'balloon', label: '모험가', tone: 'mint' },
]
const features = [
  {
    icon: MapPinned,
    title: '여행 기록 저장',
    desc: '코스, 방문지, 메모 등\n여행 기록을 남겨요.',
    tone: 'blue'
  },
  {
    icon: ChartColumn,
    title: '서울 여행 커뮤니티 현황',
    desc: '권역별 게시글과 인기 지역 등\n서울 여행 통계를 확인해요.',
    tone: 'green'
  },
  {
    icon: MessagesSquare,
    title: '커뮤니티 참여',
    desc: '익명으로 다른 여행자와\n소통하고 정보를 나눠요.',
    tone: 'purple'
  },
  {
    icon: BadgeCheck,
    title: '개인정보 걱정 없이',
    desc: '개인정보 없이 안심하고\n서비스를 이용해요.',
    tone: 'pink'
  }
]

const canSubmit = computed(() => nickname.value.trim().length > 0 && password.value.length >= 4 && !loading.value)
const displayName = computed(() => nickname.value.trim() || '서울뚜벅이')
const communityUserKey = computed(() => currentUser.value?.id ? `user:${currentUser.value.id}` : `nickname:${displayName.value}`)
const courseUserKey = computed(() => currentUser.value?.id ? `user:${currentUser.value.id}` : displayName.value)
const inProgressCourses = computed(() => progressCourses.value.filter((course) => course.status === 'in_progress'))
const completedCourses = computed(() => progressCourses.value.filter((course) => course.status === 'completed'))
const isEditingPost = computed(() => page.value === 'community-edit')

watch(page, (currentPage, previousPage) => {
  if (!navigatingBack && previousPage && previousPage !== 'onboarding' && previousPage !== currentPage) {
    pageHistory.push(previousPage)
  }
  navigatingBack = false
  if (currentUser.value && currentPage !== 'onboarding') {
    sessionStorage.setItem(PAGE_STORAGE_KEY, currentPage)
  }
})

function goBack(fallback = 'home') {
  const previousPage = pageHistory.pop()
  navigatingBack = true
  if (previousPage) {
    page.value = previousPage
    window.scrollTo({ top: 0, behavior: 'smooth' })
    return
  }
  if (fallback === 'chat') void openChat()
  else if (fallback === 'my-courses') openMyCourses()
  else if (fallback === 'community') void openCommunity()
  else void openHome()
}

onMounted(async () => {
  const saved = localStorage.getItem('seoulMissionUser')
  if (!saved) return
  try {
    const user = JSON.parse(saved)
    if (!user?.id || !user?.nickname) throw new Error('Invalid saved user')
    currentUser.value = user
    nickname.value = user.nickname || ''
    const savedPage = sessionStorage.getItem(PAGE_STORAGE_KEY) || 'home'
    if (savedPage === 'chat' || savedPage === 'course-detail') {
      await openChat()
    } else if (['my-courses', 'course-progress', 'mission-checkin', 'checkin-success', 'course-complete'].includes(savedPage)) {
      openMyCourses()
    } else if (['community', 'community-write', 'community-edit', 'community-detail'].includes(savedPage)) {
      await openCommunity()
    } else if (savedPage === 'my-page') {
      openMyPage()
    } else {
      await openHome()
    }
  } catch {
    localStorage.removeItem('seoulMissionUser')
    sessionStorage.removeItem(PAGE_STORAGE_KEY)
    currentUser.value = null
    page.value = 'onboarding'
  }
})

async function requestRecommendations(message) {
  const response = await fetch(`${API_BASE_URL}/recommendations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, limit: 3 }),
  })
  const result = await response.json()
  if (!response.ok) throw new Error(result.detail || '코스를 불러오지 못했습니다.')
  courses.value = result.courses
  return result
}

async function openHome() {
  page.value = 'home'
  window.scrollTo({ top: 0, behavior: 'smooth' })
  await loadCommunityDashboard()
  if (courses.value.length) return
  try {
    await requestRecommendations('서울의 역사, 야경, 자연 인기 코스를 추천해줘')
  } catch (error) {
    errorMessage.value = error.message
  }
}

async function startTrip() {
  errorMessage.value = ''
  const name = nickname.value.trim()
  if (!name) {
    errorMessage.value = '닉네임을 입력해 주세요.'
    return
  }
  if (password.value.length < 4 || loading.value) {
    errorMessage.value = '비밀번호를 4자 이상 입력해 주세요.'
    return
  }
  loading.value = true
  try {
    const response = await fetch(`${API_BASE_URL}/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nickname: name, profile_icon: selectedIcon.value, password: password.value }),
    })
    const result = await response.json()
    if (!response.ok) {
      const message = result.detail || '프로필 생성에 실패했습니다.'
      if (response.status === 401) window.alert(message)
      throw new Error(message)
    }
    localStorage.setItem('seoulMissionUser', JSON.stringify(result))
    currentUser.value = result
    await openHome()
  } catch (error) {
    errorMessage.value = error.message || '서버 연결을 확인해 주세요.'
  } finally {
    loading.value = false
  }
}

async function openChat() {
  page.value = 'chat'
  window.scrollTo({ top: 0, behavior: 'smooth' })
  const isFirstConversation = !chatMessages.value.length
  if (isFirstConversation) {
    chatMessages.value.push({ type: 'bot', text: '안녕하세요! 여행 코스를 추천해드릴게요. 어떤 여행을 계획하고 계신가요?' })
    loading.value = true
    try {
      const result = courses.value.length
        ? { answer: '서울 관광 데이터베이스에서 인기 코스를 찾아봤어요.', courses: courses.value }
        : await requestRecommendations('서울에서 처음 가기 좋은 인기 코스')
      chatMessages.value.push({ type: 'bot', text: result.answer, courses: result.courses })
    } catch (error) {
      chatMessages.value.push({ type: 'bot', text: error.message || '추천 코스를 불러오지 못했어요.' })
    } finally {
      loading.value = false
    }
  }
  await loadProgressCourses()
  await scrollChatToBottom()
}

async function scrollChatToBottom() {
  await nextTick()
  const element = chatMessagesElement.value
  if (element) element.scrollTop = element.scrollHeight
}

async function sendMessage() {
  const message = chatInput.value.trim()
  if (!message || loading.value) return
  chatMessages.value.push({ type: 'user', text: message })
  chatInput.value = ''
  loading.value = true
  await scrollChatToBottom()
  try {
    const result = await requestRecommendations(message)
    chatMessages.value.push({ type: 'bot', text: result.answer, courses: result.courses })
  } catch (error) {
    chatMessages.value.push({ type: 'bot', text: error.message || '추천 중 문제가 발생했어요. 다시 시도해주세요.' })
  } finally {
    loading.value = false
    await scrollChatToBottom()
  }
}

function openCourseDetail(course) {
  selectedTravelCourse.value = course
  page.value = 'course-detail'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function loadProgressCourses() {
  try {
    const userKeys = [...new Set([courseUserKey.value, displayName.value])]
    const responses = await Promise.all(userKeys.map((userKey) =>
      fetch(`${API_BASE_URL}/course-progress?user_key=${encodeURIComponent(userKey)}`),
    ))
    const courseGroups = await Promise.all(responses.map((response) => response.ok ? response.json() : []))
    progressCourses.value = [...new Map(courseGroups.flat().map((course) => [course.id, course])).values()]
  } catch {
    progressCourses.value = []
  }
}

function openMyCourses() {
  page.value = 'my-courses'
  window.scrollTo({ top: 0, behavior: 'smooth' })
  void loadProgressCourses()
}

async function startTravelCourse() {
  if (!selectedTravelCourse.value || progressLoading.value) return
  progressLoading.value = true
  try {
    const response = await fetch(`${API_BASE_URL}/course-progress`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_key: courseUserKey.value,
        title: selectedTravelCourse.value.title,
        theme: selectedTravelCourse.value.theme,
        summary: selectedTravelCourse.value.summary,
        image_url: selectedTravelCourse.value.image_url,
        total_distance_km: selectedTravelCourse.value.total_distance_km,
        duration_hours: selectedTravelCourse.value.duration_hours,
        places: selectedTravelCourse.value.places,
      }),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || '여행을 시작하지 못했습니다.')
    activeProgress.value = result
    page.value = 'course-progress'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (error) {
    communityError.value = error.message
  } finally {
    progressLoading.value = false
  }
}

async function openProgressCourse(progressId) {
  progressLoading.value = true
  try {
    const listedCourse = progressCourses.value.find((course) => course.id === progressId)
    const userKey = listedCourse?.user_key || activeProgress.value?.user_key || courseUserKey.value
    const response = await fetch(`${API_BASE_URL}/course-progress/${progressId}?user_key=${encodeURIComponent(userKey)}`)
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || '진행 중인 코스를 불러오지 못했습니다.')
    activeProgress.value = result
    page.value = result.status === 'completed' ? 'course-complete' : 'course-progress'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } finally {
    progressLoading.value = false
  }
}

async function abandonProgressCourse(course) {
  if (!window.confirm(`'${course.title}' 코스를 포기하시겠어요?\n현재까지의 미션 기록과 스탬프가 삭제됩니다.`)) return
  progressLoading.value = true
  try {
    const response = await fetch(`${API_BASE_URL}/course-progress/${course.id}?user_key=${encodeURIComponent(course.user_key || courseUserKey.value)}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      const result = await response.json()
      throw new Error(result.detail || '코스를 포기하지 못했습니다.')
    }
    progressCourses.value = progressCourses.value.filter((progress) => progress.id !== course.id)
  } catch (error) {
    window.alert(error.message || '코스를 포기하지 못했습니다.')
  } finally {
    progressLoading.value = false
  }
}

async function deleteSelectedCompletedCourses() {
  const selectedCourses = completedCourses.value.filter((course) => selectedCompletedCourseIds.value.includes(course.id))
  if (!selectedCourses.length || progressLoading.value) return
  if (!window.confirm(`선택한 완료 코스 ${selectedCourses.length}개를 삭제하시겠어요?\n미션 기록과 획득 스탬프도 함께 삭제됩니다.`)) return
  progressLoading.value = true
  try {
    const responses = await Promise.all(selectedCourses.map((course) =>
      fetch(`${API_BASE_URL}/course-progress/${course.id}/completed?user_key=${encodeURIComponent(course.user_key || courseUserKey.value)}`, {
        method: 'DELETE',
      }),
    ))
    if (responses.some((response) => !response.ok)) throw new Error('일부 완료 코스를 삭제하지 못했습니다.')
    const deletedIds = new Set(selectedCourses.map((course) => course.id))
    progressCourses.value = progressCourses.value.filter((course) => !deletedIds.has(course.id))
    selectedCompletedCourseIds.value = []
  } catch (error) {
    window.alert(error.message || '완료 코스를 삭제하지 못했습니다.')
    await loadProgressCourses()
  } finally {
    progressLoading.value = false
  }
}

function openMissionCheckIn(mission) {
  if (mission.status !== 'active') return
  activeMission.value = mission
  page.value = 'mission-checkin'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function checkInMission() {
  if (!activeProgress.value || !activeMission.value || progressLoading.value) return
  progressLoading.value = true
  try {
    const response = await fetch(`${API_BASE_URL}/course-progress/${activeProgress.value.id}/missions/${activeMission.value.id}/check-in`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_key: activeProgress.value.user_key || courseUserKey.value }),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || '체크인하지 못했습니다.')
    checkInResult.value = result
    activeProgress.value = result.progress
    page.value = 'checkin-success'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } finally {
    progressLoading.value = false
  }
}

function continueCourse() {
  page.value = checkInResult.value?.course_completed ? 'course-complete' : 'course-progress'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function logout() {
  localStorage.removeItem('seoulMissionUser')
  sessionStorage.removeItem(PAGE_STORAGE_KEY)
  currentUser.value = null
  nickname.value = ''
  password.value = ''
  page.value = 'onboarding'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function loadCommunityPosts() {
  currentPage.value = 1;
  communityLoading.value = true
  communityError.value = ''
  try {
    const params = new URLSearchParams({ user_key: communityUserKey.value })
    params.set('sort', communitySort.value)
    if (communityDistrict.value) params.set('district', communityDistrict.value)
    if (communitySearch.value.trim()) params.set('q', communitySearch.value.trim())
    if (communityBookmarkedOnly.value) params.set('bookmarked_only', 'true')
    if (communityMineOnly.value) params.set('mine_only', 'true')
    const response = await fetch(`${API_BASE_URL}/community/posts?${params}`)
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || '게시글을 불러오지 못했습니다.')
    communityPosts.value = result
  } catch (error) {
    communityError.value = error.message || '커뮤니티 서버 연결을 확인해 주세요.'
  } finally {
    communityLoading.value = false
  }
}

async function openCommunity() {
  page.value = 'community'
  window.scrollTo({ top: 0, behavior: 'smooth' })
  await loadCommunityPosts()
}

function openMyPage() {
  currentPassword.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
  passwordChangeMessage.value = ''
  page.value = 'my-page'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function changePassword() {
  if (!currentUser.value) return
  if (newPassword.value !== confirmPassword.value) {
    window.alert('새 비밀번호가 일치하지 않습니다.')
    return
  }
  loading.value = true
  passwordChangeMessage.value = ''
  try {
    const response = await fetch(`${API_BASE_URL}/users/password`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUser.value.id,
        current_password: currentPassword.value,
        new_password: newPassword.value,
      }),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || '비밀번호를 변경하지 못했습니다.')
    password.value = newPassword.value
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    passwordChangeMessage.value = result.message
    window.alert(result.message)
  } catch (error) {
    window.alert(error.message || '비밀번호를 변경하지 못했습니다.')
  } finally {
    loading.value = false
  }
}

async function toggleBookmarkedPosts() {
  communityBookmarkedOnly.value = !communityBookmarkedOnly.value
  if (communityBookmarkedOnly.value) communityMineOnly.value = false
  await loadCommunityPosts()
}

async function toggleMyPosts() {
  communityMineOnly.value = !communityMineOnly.value
  if (communityMineOnly.value) communityBookmarkedOnly.value = false
  await loadCommunityPosts()
}

async function loadGalleryImages(preserveSelected = false) {
  const query = postForm.value.district ? `?district=${encodeURIComponent(postForm.value.district)}&limit=15` : '?limit=15'
  const response = await fetch(`${API_BASE_URL}/community/images${query}`)
  const result = await response.json()
  if (!response.ok) throw new Error(result.detail || '사진을 불러오지 못했습니다.')
  if (preserveSelected) {
    const existingImages = postForm.value.image_urls
      .filter((url) => !result.some((image) => image.image_url === url))
      .map((url, index) => ({ id: `existing-${index}`, title: '기존 사진', image_url: url }))
    galleryImages.value = [...existingImages, ...result]
  } else {
    galleryImages.value = result
    postForm.value.image_urls = postForm.value.image_urls.filter((url) => result.some((image) => image.image_url === url))
  }
}

async function openCommunityWrite() {
  page.value = 'community-write'
  communityError.value = ''
  postForm.value = { title: '', district: communityDistrict.value || '종로구', content: '', image_urls: [], tags: '' }
  window.scrollTo({ top: 0, behavior: 'smooth' })
  try {
    await loadGalleryImages()
  } catch (error) {
    communityError.value = error.message
  }
}

async function openCommunityEdit() {
  if (!selectedPost.value?.can_edit) return
  page.value = 'community-edit'
  communityError.value = ''
  postForm.value = {
    title: selectedPost.value.title,
    district: selectedPost.value.district,
    content: selectedPost.value.content,
    image_urls: [...selectedPost.value.image_urls],
    tags: selectedPost.value.tags.join(', '),
  }
  window.scrollTo({ top: 0, behavior: 'smooth' })
  try {
    await loadGalleryImages(true)
  } catch (error) {
    communityError.value = error.message
  }
}

function cancelCommunityForm() {
  if (isEditingPost.value && selectedPost.value) {
    page.value = 'community-detail'
    window.scrollTo({ top: 0, behavior: 'smooth' })
    return
  }
  openCommunity()
}

function togglePostImage(imageUrl) {
  const images = postForm.value.image_urls
  const index = images.indexOf(imageUrl)
  if (index >= 0) images.splice(index, 1)
  else if (images.length < 5) images.push(imageUrl)
}

async function submitCommunityPost() {
  communityError.value = ''
  if (!postForm.value.title.trim() || !postForm.value.content.trim() || !postForm.value.district) {
    communityError.value = '제목, 지역, 내용을 모두 입력해 주세요.'
    return
  }
  communityLoading.value = true
  try {
    const editing = Boolean(isEditingPost.value && selectedPost.value)
    const response = await fetch(
      editing ? `${API_BASE_URL}/community/posts/${selectedPost.value.id}` : `${API_BASE_URL}/community/posts`,
      {
        method: editing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...(editing
            ? { user_key: communityUserKey.value }
            : { nickname: displayName.value, owner_key: communityUserKey.value }),
          title: postForm.value.title,
          content: postForm.value.content,
          region: '서울특별시',
          district: postForm.value.district,
          image_urls: postForm.value.image_urls,
          tags: postForm.value.tags.split(',').map((tag) => tag.trim()).filter(Boolean).slice(0, 5),
        }),
      },
    )
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || (editing ? '게시글을 수정하지 못했습니다.' : '게시글을 등록하지 못했습니다.'))
    selectedPost.value = result
    page.value = 'community-detail'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (error) {
    communityError.value = error.message
  } finally {
    communityLoading.value = false
  }
}

async function openCommunityDetail(postId) {
  communityLoading.value = true
  try {
    const response = await fetch(`${API_BASE_URL}/community/posts/${postId}?user_key=${encodeURIComponent(communityUserKey.value)}`)
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || '게시글을 찾을 수 없습니다.')
    selectedPost.value = result
    page.value = 'community-detail'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (error) {
    communityError.value = error.message
  } finally {
    communityLoading.value = false
  }
}

async function togglePostLike() {
  if (!selectedPost.value || communityLoading.value) return
  communityLoading.value = true
  communityError.value = ''
  try {
    const response = await fetch(`${API_BASE_URL}/community/posts/${selectedPost.value.id}/likes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_key: communityUserKey.value }),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || '좋아요를 처리하지 못했습니다.')
    selectedPost.value.like_count = result.like_count
    selectedPost.value.liked = result.liked
  } catch (error) {
    communityError.value = error.message
  } finally {
    communityLoading.value = false
  }
}

async function loadCommunityDashboard() {
  try {
    const response = await fetch(`${API_BASE_URL}/community/statistics`)
    if (!response.ok) throw new Error('통계를 불러오지 못했습니다.')
    communityStats.value = await response.json()
    await nextTick()
    renderCommunityCharts()
  } catch {}
}

function renderCommunityCharts() {
  if (!communityStats.value || !regionChartElement.value || !districtChartElement.value) return
  regionChart?.destroy()
  districtChart?.destroy()
  const regions = communityStats.value.regions
  regionChart = new Chart(regionChartElement.value, {
    type: 'bar',
    data: {
      labels: regions.map((item) => item.region_group),
      datasets: [{ label: '게시글 수', data: regions.map((item) => item.post_count), backgroundColor: '#3b78ee', borderRadius: 7 }],
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { grid: { display: false } } } },
  })
  const districts = communityStats.value.popular_districts
  districtChart = new Chart(districtChartElement.value, {
    type: 'bar',
    data: {
      labels: districts.map((item) => item.district),
      datasets: [
        { label: '좋아요', data: districts.map((item) => item.like_count), backgroundColor: '#ff5b78', borderRadius: 6 },
        { label: '조회수', data: districts.map((item) => item.view_count), backgroundColor: '#35aa78', borderRadius: 6 },
        { label: '북마크', data: districts.map((item) => item.bookmark_count), backgroundColor: '#f2b43d', borderRadius: 6 },
      ],
    },
    options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, scales: { x: { beginAtZero: true, ticks: { precision: 0 } }, y: { grid: { display: false } } } },
  })
}

async function togglePostBookmark(post) {
  if (!post || bookmarkingPostIds.value.includes(post.id)) return
  bookmarkingPostIds.value = [...bookmarkingPostIds.value, post.id]
  communityError.value = ''
  try {
    const response = await fetch(`${API_BASE_URL}/community/posts/${post.id}/bookmarks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_key: communityUserKey.value }),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || '북마크를 처리하지 못했습니다.')
    post.bookmarked = result.bookmarked
    if (communityBookmarkedOnly.value && !result.bookmarked) {
      communityPosts.value = communityPosts.value.filter((item) => item.id !== post.id)
    }
  } catch (error) {
    communityError.value = error.message
  } finally {
    bookmarkingPostIds.value = bookmarkingPostIds.value.filter((id) => id !== post.id)
  }
}

async function deleteSelectedPost() {
  if (!selectedPost.value?.can_delete) return
  if (!window.confirm('작성한 게시글을 삭제하시겠습니까?')) return
  communityLoading.value = true
  try {
    const response = await fetch(`${API_BASE_URL}/community/posts/${selectedPost.value.id}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_key: communityUserKey.value }),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || '게시글을 삭제하지 못했습니다.')
    selectedPost.value = null
    await openCommunity()
  } catch (error) {
    communityError.value = error.message
  } finally {
    communityLoading.value = false
  }
}

function formatDate(value) {
  if (!value) return ''
  return new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value.replace(' ', 'T') + 'Z'))
}
</script>

<template>
  <main class="page-shell">
    <div class="mobile-page" :class="`view-${page}`">
      <template v-if="page === 'onboarding'">
        <section class="onboarding-hero">
          <div class="hero-copy">
            <p class="eyebrow">SEOUL MISSION TRIP</p>
            <h1>익명 사용자로 설정하고<br><span>나만의 여행</span>을 시작해요!</h1>
            <p>회원가입 없이 여행을 기록하고,<br>소중한 추억을 남겨보세요.</p>
          </div>
          <div class="seoul-art" aria-hidden="true">
            <img :src="seoulOnboardingImage" alt="">
          </div>
        </section>

        <form class="profile-card card" @submit.prevent="startTrip">
          <div class="card-heading"><span class="heading-icon">∞</span><h2>내 여행 프로필 설정</h2></div>
          <div class="field-group">
            <label for="nickname">닉네임 <span class="required-badge">필수</span></label>
            <div class="input-wrap"><span class="mini-mask">∞</span><input id="nickname" v-model="nickname" maxlength="12" placeholder="닉네임을 입력해주세요 (최대 12자)" autocomplete="username"><span class="counter">{{ nickname.length }}/12</span></div>
            <label for="password" class="password-label">비밀번호 <span class="required-badge">필수</span></label>
            <div class="input-wrap"><span class="mini-mask">●</span><input id="password" v-model="password" type="password" minlength="4" maxlength="64" placeholder="비밀번호를 입력해주세요 (4자 이상)" autocomplete="current-password" @keyup.enter="startTrip"></div>
          </div>
          <div v-if="false" class="divider"></div>
          <div v-if="false" class="section-label">프로필 아이콘 선택 <span class="required-badge">필수</span></div>
          <div v-if="false" class="profile-icons" role="radiogroup">
            <button v-for="icon in profileIcons" :key="icon.id" type="button" class="profile-icon-button" :class="[`tone-${icon.tone}`, { selected: selectedIcon === icon.id }]" :aria-label="icon.label" @click="selectedIcon = icon.id">
              <svg v-if="icon.id === 'mask'" class="profile-icon-svg mask-icon" viewBox="0 0 64 64" aria-hidden="true">
                <path d="M10 31c0-8 7-14 16-11 3 1 4 3 6 3s3-2 6-3c9-3 16 3 16 11 0 10-8 16-17 12-3-1-4-3-5-3s-2 2-5 3c-9 4-17-2-17-12Z" />
                <path d="M22 30c5 0 8 3 9 7-7 1-12 0-16-4 1-2 4-3 7-3Zm20 0c-5 0-8 3-9 7 7 1 12 0 16-4-1-2-4-3-7-3Z" class="icon-cutout" />
              </svg>
              <svg v-else-if="icon.id === 'place'" class="profile-icon-svg place-icon" viewBox="0 0 64 64" aria-hidden="true">
                <path d="M11 50c5-8 12-13 21-13s16 5 21 13c-6 3-13 5-21 5s-15-2-21-5Z" class="icon-secondary" />
                <path d="M32 9c-9 0-16 7-16 16 0 12 16 27 16 27s16-15 16-27c0-9-7-16-16-16Zm0 22a6 6 0 1 1 0-12 6 6 0 0 1 0 12Z" />
              </svg>
              <svg v-else-if="icon.id === 'bag'" class="profile-icon-svg bag-icon" viewBox="0 0 64 64" aria-hidden="true">
                <path d="M18 23h28c3 0 5 2 5 5v22c0 3-2 5-5 5H18c-3 0-5-2-5-5V28c0-3 2-5 5-5Z" />
                <path d="M24 23v-6c0-5 3-8 8-8s8 3 8 8v6" class="icon-stroke" />
                <path d="M21 25v28M43 25v28" class="icon-stroke subtle" />
              </svg>
              <svg v-else-if="icon.id === 'hat'" class="profile-icon-svg hat-icon" viewBox="0 0 64 64" aria-hidden="true">
                <path d="M21 20c2-6 6-9 11-9s9 3 11 9l3 14H18l3-14Z" />
                <path d="M11 38c4 5 11 8 21 8s17-3 21-8c2-2 0-5-3-4-6 2-12 3-18 3s-12-1-18-3c-3-1-5 2-3 4Z" class="icon-secondary" />
              </svg>
              <svg v-else-if="icon.id === 'camera'" class="profile-icon-svg camera-icon" viewBox="0 0 64 64" aria-hidden="true">
                <path d="M17 19h9l3-5h8l3 5h7c4 0 7 3 7 7v20c0 4-3 7-7 7H17c-4 0-7-3-7-7V26c0-4 3-7 7-7Z" />
                <path d="M32 45a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z" class="icon-cutout" />
                <path d="M48 27a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" class="icon-cutout" />
              </svg>
              <svg v-else class="profile-icon-svg balloon-icon" viewBox="0 0 64 64" aria-hidden="true">
                <path d="M32 6c-12 0-21 10-21 23 0 12 8 21 17 24h8c9-3 17-12 17-24C53 16 44 6 32 6Z" />
                <path d="M32 6c-5 4-8 12-8 23s3 19 8 24M32 6c5 4 8 12 8 23s-3 19-8 24" class="icon-stroke" />
                <path d="M26 53h12l-3 7h-6l-3-7Z" class="icon-secondary" />
              </svg>
              <b v-if="selectedIcon === icon.id" class="check-mark">✓</b>
            </button>
          </div>
          <p v-if="false" class="helper-text">여행자의 개성을 담은 아이콘을 선택해주세요!</p>
        </form>

        <section class="feature-card card">
          <div class="card-heading"><span class="heading-icon star-icon">★</span><h2>익명으로 이용해도 이런 기능을 이용할 수 있어요</h2></div>
          <div class="features"><article v-for="item in features" :key="item.title">
            <div class="feature-icon" :class="item.tone"><component
            :is="item.icon"
            :size="34"
            :stroke-width="2"/></div><strong>{{ item.title }}</strong><p>{{ item.desc }}</p></article></div>
        </section>
        <section class="action-card"><button class="start-button" :disabled="!canSubmit" @click="startTrip">{{ loading ? '프로필 생성 중...' : '여행 시작하기' }}</button></section>
      </template>

      <template v-else-if="page === 'home'">
        <header class="app-header">
          <div class="header-left"><button class="back-page-button" aria-label="로그아웃" @click="logout">로그아웃</button><div class="brand"><span>◆</span> SEOUL MISSION TRIP</div></div>
          <div class="desktop-menu"><button class="active">홈</button><button @click="openChat">코스 추천</button><button type="button" @click.stop="openMyCourses">여행 로그</button><button @click="openCommunity">커뮤니티</button><button @click="openMyPage">마이페이지</button></div>
        </header>
<section class="mission-section">

  <div class="mission-banner">
  <div class="mission-content">
    <h1>
      서울 여행을<br>
      미션처럼 즐겨보세요!
    </h1>

    <p>
      스탬프를 모으고, 미션을 달성하고,<br>
      여행의 기록을 남겨보세요.
    </p>
  </div>

  </div>
</section>

        <section class="course-section card">
          <div class="section-head"><h2>추천 여행 코스</h2><button @click="openChat">전체 보기 ›</button></div>
          <div v-if="courses.length" class="course-scroll">
            <article v-for="course in courses" :key="course.id" class="home-course-card" role="button" tabindex="0" @click="openCourseDetail(course)" @keydown.enter="openCourseDetail(course)">
              <img :src="course.image_url" :alt="course.title">
              <div class="home-course-copy"><div class="course-badges"><span class="theme-badge">{{ course.district }}</span><span v-for="category in course.categories.slice(0, 2)" :key="category" :class="['category-chip', categoryTone[category]]">{{ category }}</span></div><h3>{{ course.title }}</h3><p>{{ course.summary }}</p><div>◷ 약 {{ course.duration_hours }}시간　⌖ {{ course.total_distance_km }}km　♙ {{ course.stamp_count }}개</div></div>
            </article>
          </div>
          <p v-else class="loading-copy">추천 코스를 불러오는 중이에요...</p>
          <section class="community-dashboard">
            <div class="section-head"><div><span>COMMUNITY DATA</span><h2>서울 여행 커뮤니티 현황</h2></div><small>게시글 활동을 권역과 자치구별로 살펴보세요</small></div>
            <div class="dashboard-summary"><div><small>전체 게시글</small><strong>{{ communityStats.totals.post_count }}</strong></div><div><small>누적 좋아요</small><strong>{{ communityStats.totals.like_count }}</strong></div><div><small>누적 조회수</small><strong>{{ communityStats.totals.view_count }}</strong></div><div><small>누적 북마크</small><strong>{{ communityStats.totals.bookmark_count }}</strong></div></div>
            <div class="dashboard-charts"><article><h3>권역별 게시글 현황</h3><p>서울 5개 권역의 게시글 수</p><div class="chart-wrap"><canvas ref="regionChartElement" aria-label="서울 권역별 커뮤니티 게시글 수 막대 차트"></canvas></div></article><article><h3>인기 지역 TOP 5</h3><p>좋아요·조회수·북마크 합산 상위 자치구</p><div class="chart-wrap"><canvas ref="districtChartElement" aria-label="서울 인기 자치구 상위 5개 좋아요 조회수 북마크 막대 차트"></canvas></div></article></div>
          </section>
          <button class="make-course-button" @click="openChat"><span>➤</span><b>나만의 코스 만들기<small>원하는 테마와 시간을 선택해 나만의 여행 코스를 만들어보세요!</small></b><i>›</i></button>
        </section>
      </template>

      <template v-else-if="page === 'chat'">
        <header class="chat-header"><div class="brand"><span>◆</span> SEOUL MISSION TRIP</div><div class="desktop-menu"><button @click="openHome">홈</button><button class="active">코스 추천</button><button type="button" @click.stop="openMyCourses">여행 로그</button><button @click="openCommunity">커뮤니티</button><button @click="openMyPage">마이페이지</button></div></header>
        <section class="chat-banner"><div><h1>{{ displayName }}님, 오늘은<br>어디로 갈까요?</h1><p>구·시간·테마·관광 유형을 말하면 같은 구 안에서<br>가까운 장소 순서로 코스를 추천해드릴게요!</p></div><span>🤖</span></section>

        <section class="chat-box">
          <div ref="chatMessagesElement" class="messages">
            <div v-for="(message, index) in chatMessages" :key="index" class="message-row" :class="message.type">
              <span v-if="message.type === 'bot'" class="bot-avatar">∞</span>
              <div class="message-content" :class="{ 'with-courses': message.courses?.length }">
                <p>{{ message.text }}</p>
                <div v-if="message.courses?.length" class="chat-course-list">
                  <article v-for="course in message.courses" :key="course.id" class="chat-course-card">
                    <img :src="course.image_url" :alt="course.title">
                    <div class="chat-course-info">
                      <div class="course-badges"><span class="best-badge">{{ course.district }}</span><span v-for="category in course.categories" :key="category" :class="['category-chip', categoryTone[category]]">{{ category }}</span></div>
                      <h3>{{ course.title }}</h3>
                      <p>{{ course.summary }}</p>
                      <div class="course-meta">◷ 약 {{ course.duration_hours }}시간　⌖ 총 {{ course.total_distance_km }}km　♙ {{ course.stamp_count }}개</div>
                      <small>{{ course.reason }}</small>
                    </div>
                    <button type="button" @click="openCourseDetail(course)">상세보기</button>
                  </article>
                </div>
              </div>
            </div>
            <div v-if="loading" class="message-row bot"><span class="bot-avatar">∞</span><p>서울 관광 데이터를 분석하고 있어요<span class="typing">...</span></p></div>
          </div>
          <form class="chat-input" @submit.prevent="sendMessage"><input v-model="chatInput" placeholder="예: 종로에서 3시간 역사 코스 추천해줘"><button :disabled="loading || !chatInput.trim()">➤</button></form>
        </section>

        <section v-if="inProgressCourses.length" class="progress-course-section">
          <div class="section-head"><h2>진행 중인 코스</h2><small>여행을 이어서 진행해보세요</small></div>
          <div class="progress-course-grid"><button v-for="progress in inProgressCourses" :key="progress.id" @click="openProgressCourse(progress.id)"><img v-if="progress.image_url" :src="progress.image_url" :alt="progress.title"><span><b>{{ progress.title }}</b><small>{{ progress.completed_missions }} / {{ progress.total_missions }} 미션 · {{ progress.progress_percent }}% 진행</small><i><em :style="{ width: `${progress.progress_percent}%` }"></em></i></span><strong>›</strong></button></div>
        </section>

      </template>

      <template v-else-if="page === 'my-courses'">
        <header class="course-flow-header"><div class="brand"><span>◆</span> SEOUL MISSION TRIP</div><div class="desktop-menu"><button @click="openHome">홈</button><button @click="openChat">코스 추천</button><button class="active">여행 로그</button><button @click="openCommunity">커뮤니티</button><button @click="openMyPage">마이페이지</button></div></header>
        <section class="my-courses-page">
          <div class="my-courses-title"><div><span>MY TRAVEL COURSES</span><h1>여행 로그</h1><p>시작한 여행 코스의 미션 진행 상황을 확인하고 이어서 진행하세요.</p></div><button @click="openChat">＋ 새로운 코스 찾기</button></div>
          <section class="my-course-group"><div class="section-head"><h2>진행 중인 코스 <span>{{ inProgressCourses.length }}</span></h2><small>마지막 미션부터 이어서 진행할 수 있어요</small></div><div v-if="inProgressCourses.length" class="my-course-grid"><article v-for="course in inProgressCourses" :key="course.id" @click="openProgressCourse(course.id)"><img v-if="course.image_url" :src="course.image_url" :alt="course.title"><div><span>{{ course.theme }}</span><h3>{{ course.title }}</h3><p>{{ course.summary }}</p><div class="my-course-progress"><small>{{ course.completed_missions }} / {{ course.total_missions }} 미션</small><b>{{ course.progress_percent }}%</b><i><em :style="{ width: `${course.progress_percent}%` }"></em></i></div><div class="my-course-actions"><button @click.stop="openProgressCourse(course.id)">이어서 진행하기　›</button><button class="abandon-course-button" :disabled="progressLoading" @click.stop="abandonProgressCourse(course)">포기하기</button></div></div></article></div><div v-else class="empty-course-state"><span>⌖</span><h3>진행 중인 코스가 없어요</h3><p>추천 코스에서 새로운 서울 여행을 시작해보세요.</p><button @click="openChat">코스 추천받기</button></div></section>
          <section v-if="completedCourses.length" class="my-course-group completed"><div class="section-head completed-course-head"><h2>완료한 코스 <span>{{ completedCourses.length }}</span></h2><button class="delete-selected-courses" :disabled="!selectedCompletedCourseIds.length || progressLoading" @click="deleteSelectedCompletedCourses">선택 삭제{{ selectedCompletedCourseIds.length ? ` (${selectedCompletedCourseIds.length})` : '' }}</button></div><div class="my-course-grid"><article v-for="course in completedCourses" :key="course.id" :class="{ selected: selectedCompletedCourseIds.includes(course.id) }" @click="openProgressCourse(course.id)"><label class="completed-course-select" @click.stop><input v-model="selectedCompletedCourseIds" type="checkbox" :value="course.id"><span>선택</span></label><img v-if="course.image_url" :src="course.image_url" :alt="course.title"><div><span>완료</span><h3>{{ course.title }}</h3><p>모든 미션과 스탬프를 획득했습니다.</p><div class="my-course-progress"><small>{{ course.completed_missions }} / {{ course.total_missions }} 미션</small><b>100%</b><i><em style="width: 100%"></em></i></div><button>완료 결과 보기　›</button></div></article></div></section>
        </section>
      </template>

      <template v-else-if="page === 'course-detail' && selectedTravelCourse">
        <header class="course-flow-header"><button class="back-home-button" @click="goBack('chat')"><span>←</span> 이전</button><div class="brand"><span>◆</span> SEOUL MISSION TRIP</div><div class="desktop-menu"><button @click="openHome">홈</button><button class="active" @click="openChat">코스 추천</button><button @click="openMyCourses">여행 로그</button><button @click="openCommunity">커뮤니티</button><button @click="openMyPage">마이페이지</button></div></header>
        <section class="course-detail-page">
          <div class="course-detail-hero"><img :src="selectedTravelCourse.image_url" :alt="selectedTravelCourse.title"><div><div class="course-badges"><span class="theme-badge">{{ selectedTravelCourse.district }}</span><span v-for="category in selectedTravelCourse.categories" :key="category" :class="['category-chip', categoryTone[category]]">{{ category }}</span></div><h1>{{ selectedTravelCourse.title }}</h1><p>{{ selectedTravelCourse.reason }}</p><div>◷ 약 {{ selectedTravelCourse.duration_hours }}시간　⌖ 총 {{ selectedTravelCourse.total_distance_km }}km　♙ {{ selectedTravelCourse.stamp_count }}개</div></div></div>
          <div class="course-mission-overview"><div class="section-head"><h2>코스 미션</h2><small>같은 구 안에서 가까운 순서대로 방문하세요</small></div><div class="overview-mission-list"><article v-for="(place, index) in selectedTravelCourse.places" :key="place.id"><span>{{ index + 1 }}</span><img :src="place.firstimage" :alt="place.title"><div><div class="place-category"><b :class="categoryTone[place.content_type]">{{ place.content_type }}</b><em v-if="index > 0">이전 장소에서 {{ place.distance_from_previous_km }}km</em></div><strong>{{ place.title }}</strong><p>{{ place.addr1 }}</p><small>♙ 스탬프 +1</small></div><i>{{ index === 0 ? '출발' : '다음' }}</i></article></div></div>
          <button class="primary-flow-button" :disabled="progressLoading" @click="startTravelCourse">{{ progressLoading ? '여행 준비 중...' : '여행 시작하기' }}</button>
        </section>
      </template>

      <template v-else-if="page === 'course-progress' && activeProgress">
        <header class="course-flow-header"><button class="back-home-button" @click="goBack('my-courses')"><span>←</span> 이전</button><div class="brand"><span>◆</span> SEOUL MISSION TRIP</div><div class="desktop-menu"><button @click="openHome">홈</button><button @click="openChat">코스 추천</button><button class="active" @click="openMyCourses">여행 로그</button><button @click="openCommunity">커뮤니티</button><button @click="openMyPage">마이페이지</button></div></header>
        <section class="mission-progress-page">
          <div class="flow-title"><span>{{ activeProgress.theme }}</span><h1>{{ activeProgress.title }}</h1><p>{{ activeProgress.completed_missions }} / {{ activeProgress.total_missions }} 미션 완료</p></div>
          <div class="course-progress-bar"><div><b>코스 진행률</b><strong>{{ activeProgress.progress_percent }}%</strong></div><i><em :style="{ width: `${activeProgress.progress_percent}%` }"></em></i></div>
          <div class="mission-timeline"><article v-for="mission in activeProgress.missions" :key="mission.id" :class="mission.status"><span>{{ mission.status === 'completed' ? '✓' : mission.sequence_no }}</span><img v-if="mission.image_url" :src="mission.image_url" :alt="mission.title"><div><small>{{ mission.status === 'active' ? '현재 미션' : mission.status === 'completed' ? '완료' : '잠김' }}</small><h2>{{ mission.title }}</h2><p>{{ mission.address }}</p><b>♙ 스탬프 +{{ mission.stamp_reward }}</b></div><button v-if="mission.status === 'active'" @click="openMissionCheckIn(mission)">체크인하기</button><i v-else>{{ mission.status === 'completed' ? '완료' : '🔒' }}</i></article></div>
        </section>
      </template>

      <template v-else-if="page === 'mission-checkin' && activeMission && activeProgress">
        <header class="course-flow-header"><button class="back-home-button" @click="goBack('my-courses')"><span>←</span> 이전</button><div class="brand"><span>◆</span> SEOUL MISSION TRIP</div><b class="mission-count">{{ activeMission.sequence_no }} / {{ activeProgress.total_missions }}</b></header>
        <section class="checkin-page"><div class="flow-title center"><span>현재 미션</span><h1>{{ activeMission.title }}</h1><p>{{ activeMission.district }}</p></div><img class="checkin-cover" :src="activeMission.image_url" :alt="activeMission.title"><div class="mission-instruction"><span>미션 내용</span><h2>{{ activeMission.title }}에서 체크인하기</h2><p>현장에 도착했다면 아래 체크인 버튼을 눌러주세요.</p><div>⌖ {{ activeMission.address || '서울 관광 명소' }}</div></div><button class="primary-flow-button checkin-button" :disabled="progressLoading" @click="checkInMission">⌖ {{ progressLoading ? '체크인 중...' : '체크인하기' }}</button></section>
      </template>

      <template v-else-if="page === 'checkin-success' && checkInResult">
        <header class="course-flow-header"><button class="back-home-button" @click="page = 'course-progress'"><span>←</span> 코스</button><div class="brand"><span>◆</span> SEOUL MISSION TRIP</div><b class="mission-count">{{ activeProgress.completed_missions }} / {{ activeProgress.total_missions }}</b></header>
        <section class="success-page"><div class="success-check">✓</div><h1>체크인 완료!</h1><p>{{ checkInResult.completed_mission.title }} 방문 인증이 완료되었습니다.</p><div class="stamp-reward"><span>♙</span><small>스탬프 획득!</small><strong>+{{ checkInResult.stamp_earned }}</strong></div><div class="next-mission-info"><span>획득한 스탬프 <b>{{ activeProgress.completed_missions }} / {{ activeProgress.total_missions }}개</b></span><span>다음 목표 <b>{{ checkInResult.course_completed ? '모든 미션 완료' : activeProgress.missions.find((mission) => mission.status === 'active')?.title }}</b></span></div><button class="primary-flow-button" @click="continueCourse">{{ checkInResult.course_completed ? '완료 결과 보기' : '다음 미션으로 이동' }}</button></section>
      </template>

      <template v-else-if="page === 'course-complete' && activeProgress">
        <header class="course-flow-header"><button class="back-home-button" @click="goBack('my-courses')"><span>←</span> 이전</button><div class="brand"><span>◆</span> SEOUL MISSION TRIP</div><div class="desktop-menu"><button @click="openHome">홈</button><button @click="openChat">코스 추천</button><button class="active" @click="openMyCourses">여행 로그</button><button @click="openCommunity">커뮤니티</button><button @click="openMyPage">마이페이지</button></div></header>
        <section class="course-complete-page"><div class="confetti">✦　·　✧　·　✦</div><div class="complete-medal">★</div><span>{{ activeProgress.theme }} 탐험가</span><h1>축하합니다!</h1><p>{{ activeProgress.title }}의<br>모든 미션을 완료했어요!</p><div><span>획득한 스탬프 <b>{{ activeProgress.completed_missions }} / {{ activeProgress.total_missions }}개</b></span><span>완료 시간 <b>{{ formatDate(activeProgress.completed_at) }}</b></span></div><section class="completed-missions"><div class="section-head"><h2>완료한 미션</h2><small>{{ activeProgress.missions.length }}개의 미션을 모두 완료했어요</small></div><div class="mission-timeline"><article v-for="mission in activeProgress.missions" :key="mission.id" class="completed"><span>✓</span><img v-if="mission.image_url" :src="mission.image_url" :alt="mission.title"><div><small>완료</small><h2>{{ mission.title }}</h2><p>{{ mission.address }}</p><b>♙ 스탬프 +{{ mission.stamp_reward }}</b></div><i>완료</i></article></div></section><button class="primary-flow-button" @click="openMyCourses">진행 코스 목록 보기</button></section>
      </template>

      <template v-else-if="page === 'my-page'">
        <header class="community-header"><div class="brand">SEOUL MISSION TRIP</div><div class="desktop-menu"><button @click="openHome">홈</button><button @click="openChat">코스 추천</button><button @click="openMyCourses">여행 로그</button><button @click="openCommunity">커뮤니티</button><button class="active">마이페이지</button></div></header>
        <section class="my-page card">
          <div class="my-page-heading"><span>MY PAGE</span><h1>마이페이지</h1><p><b>{{ displayName }}</b>님의 계정 정보를 관리하세요.</p></div>
          <form class="password-change-form" @submit.prevent="changePassword">
            <h2>비밀번호 변경</h2>
            <label>현재 비밀번호<input v-model="currentPassword" type="password" minlength="4" maxlength="64" autocomplete="current-password" required></label>
            <label>새 비밀번호<input v-model="newPassword" type="password" minlength="4" maxlength="64" autocomplete="new-password" placeholder="4자 이상" required></label>
            <label>새 비밀번호 확인<input v-model="confirmPassword" type="password" minlength="4" maxlength="64" autocomplete="new-password" required></label>
            <p v-if="passwordChangeMessage" class="password-change-success">{{ passwordChangeMessage }}</p>
            <button type="submit" :disabled="loading || currentPassword.length < 4 || newPassword.length < 4 || confirmPassword.length < 4">{{ loading ? '변경 중...' : '비밀번호 변경' }}</button>
          </form>
        </section>
      </template>

      <template v-else-if="page === 'community'">
        <header class="community-header"><div class="brand"><span>◆</span> SEOUL MISSION TRIP</div><div class="desktop-menu"><button @click="openHome">홈</button><button @click="openChat">코스 추천</button><button @click="openMyCourses">여행 로그</button><button class="active">커뮤니티</button><button @click="openMyPage">마이페이지</button></div></header>
        <section class="community-page">
          <div class="community-title-row"><div><p>SEOUL TRAVEL STORIES</p><h1>커뮤니티</h1></div></div>
          <div class="community-toolbar">

  <div class="community-filters">

    <label class="filter-select">

      <MapPinned :size="18" class="filter-icon"/>

      <select disabled>
        <option>서울특별시</option>
      </select>

    </label>

    <label class="filter-select">

      <MapPinned :size="18" class="filter-icon"/>

      <select
        v-model="communityDistrict"
        @change="loadCommunityPosts"
      >
        <option value="">전체 자치구</option>

        <option
          v-for="district in districts"
          :key="district"
        >
          {{ district }}
        </option>

      </select>

    </label>

  </div>

  <button
    class="write-button"
    @click="openCommunityWrite"
  >
    ✏️ 글쓰기
  </button>

</div>
          <div class="community-sort"><label><span class="sr-only">게시글 정렬</span><select v-model="communitySort" @change="loadCommunityPosts"><option value="latest">최신순</option><option value="popular">인기순</option><option value="views">조회순</option><option value="likes">좋아요순</option><option value="bookmarks">북마크순</option></select></label></div>
          <div class="bookmark-list-filter"><button type="button" class="bookmark-list-button" :class="{ active: communityMineOnly }" @click="toggleMyPosts">{{ communityMineOnly ? '전체 게시글 보기' : '내가 쓴 글 모아보기' }}</button><button type="button" class="bookmark-list-button" :class="{ active: communityBookmarkedOnly }" @click="toggleBookmarkedPosts">{{ communityBookmarkedOnly ? '전체 게시글 보기' : '★ 북마크 모아보기' }}</button></div>
          <div v-if="communityLoading" class="community-state">게시글을 불러오는 중입니다...</div>
          <div v-else-if="communityError" class="community-state error">{{ communityError }}</div>
          <div v-else-if="!communityPosts.length" class="community-state">{{ communityMineOnly ? '내가 작성한 게시글이 없습니다.' : communityBookmarkedOnly ? '북마크한 게시글이 없습니다.' : '아직 등록된 게시글이 없습니다.' }}</div>
          <div v-else class="post-list">
            <article v-for="post in pagedPosts" :key="post.id" class="post-list-card" @click="openCommunityDetail(post.id)">
              <img v-if="post.image_url" :src="post.image_url" :alt="post.title"><div v-else class="post-image-empty">서울</div>
              <div class="post-preview"><div><h2>{{ post.title }}</h2></div><div v-if="post.tags.length" class="post-tags"><span v-for="tag in post.tags" :key="tag">#{{ tag }}</span></div><p>{{ post.content }}</p><div class="post-meta"><span>⌖ {{ post.district }}</span><span>조회 {{ post.view_count }}</span><span>{{ formatDate(post.created_at) }}</span></div></div>
              <div class="post-actions"><button type="button" class="post-bookmark" :disabled="bookmarkingPostIds.includes(post.id)" :aria-label="post.bookmarked ? '북마크 해제' : '북마크 추가'" @click.stop.prevent="togglePostBookmark(post)">{{ post.bookmarked ? '★' : '☆' }}</button><div class="post-like">♡ {{ post.like_count }}</div></div>
            </article>
          </div>

          <div
  v-if="totalPages > 1"
  class="pagination"
>
  <button
    @click="changePage(currentPage - 1)"
    :disabled="currentPage === 1"
  >
    ‹
  </button>

  <button
    v-for="page in totalPages"
    :key="page"
    @click="changePage(page)"
    :class="{ active: currentPage === page }"
  >
    {{ page }}
  </button>

  <button
    @click="changePage(currentPage + 1)"
    :disabled="currentPage === totalPages"
  >
    ›
  </button>
</div>
        </section>
      </template>

      <template v-else-if="page === 'community-write' || page === 'community-edit'"> <!-- 커뮤니티 편집 -->
        <header class="community-header"><button class="back-home-button" @click="cancelCommunityForm"><span>←</span> {{ isEditingPost ? '상세' : '목록' }}</button><h1>{{ isEditingPost ? '글 수정' : '글쓰기' }}</h1><div class="community-user">♙ 익명 사용자</div></header>
        <form class="community-form" @submit.prevent="submitCommunityPost">
          <label class="form-field"><span>제목</span><div class="text-counter-wrap"><input v-model="postForm.title" maxlength="50" placeholder="제목을 입력해주세요."><small>{{ postForm.title.length }}/50</small></div></label>
          <div class="form-field"><span>지역 선택</span><div class="region-fields"><label><span>⌖</span><select disabled><option>서울특별시</option></select></label><label><select v-model="postForm.district" @change="loadGalleryImages"><option v-for="district in districts" :key="district">{{ district }}</option></select></label></div></div>
          <label class="form-field"><span>태그 <small>(최대 5개)</small></span><div class="tag-input-wrap"><input v-model="postForm.tags" maxlength="100" placeholder="예: 종로구, 역사여행, 산책" @keydown.enter.prevent><small>{{ postForm.tags.split(',').map((tag) => tag.trim()).filter(Boolean).slice(0, 5).length }}/5</small></div><p>태그는 쉼표(,)로 구분해주세요. # 기호는 자동으로 정리됩니다.</p></label>
          <div class="form-field"><span>대표 사진 <small>(최대 5장)</small></span><div class="photo-picker"><button v-for="image in galleryImages" :key="image.id" type="button" :class="{ selected: postForm.image_urls.includes(image.image_url) }" @click="togglePostImage(image.image_url)"><img :src="image.image_url" :alt="image.title"><b v-if="postForm.image_urls.includes(image.image_url)">{{ postForm.image_urls.indexOf(image.image_url) + 1 }}</b><em>{{ image.title }}</em></button></div><p>사진을 선택한 순서대로 목록에 노출됩니다.</p></div>
          <label class="form-field"><span>내용</span><div class="textarea-counter-wrap"><textarea v-model="postForm.content" maxlength="2000" placeholder="여행 코스, 느낀 점, 꿀팁 등을 자유롭게 공유해주세요!"></textarea><small>{{ postForm.content.length }}/2000</small></div></label>
          <p v-if="communityError" class="form-error">{{ communityError }}</p>
          <div class="form-actions"><button type="button" @click="cancelCommunityForm">취소</button><button type="submit" :disabled="communityLoading">{{ communityLoading ? (isEditingPost ? '수정 중...' : '등록 중...') : (isEditingPost ? '수정 완료' : '등록하기') }}</button></div>
        </form>
      </template>

      <template v-else-if="page === 'community-detail' && selectedPost"> <!-- 커뮤니티 상세 -->
        <header class="community-header"><button class="back-home-button" @click="goBack('community')"><span>←</span> 이전</button><h1>글 상세보기</h1><div class="community-user">♙ 익명 사용자</div></header>
        <article class="post-detail">
          <div class="post-author"><span class="author-avatar">∞</span><div><b>익명 사용자</b><small>{{ formatDate(selectedPost.created_at) }} · 조회 {{ selectedPost.view_count }}</small></div><div class="post-author-actions"><button type="button" class="bookmark-detail-button" :class="{ bookmarked: selectedPost.bookmarked }" :disabled="bookmarkingPostIds.includes(selectedPost.id)" @click.prevent="togglePostBookmark(selectedPost)">{{ selectedPost.bookmarked ? '★ 북마크됨' : '☆ 북마크' }}</button><button v-if="selectedPost.can_edit" class="edit-post-button" :disabled="communityLoading" @click="openCommunityEdit">수정하기</button><button v-if="selectedPost.can_delete" class="delete-post-button" :disabled="communityLoading" @click="deleteSelectedPost">삭제하기</button></div></div>
          <div class="post-detail-title"><h1>{{ selectedPost.title }}</h1><span>⌖ {{ selectedPost.district }}</span></div>
          <div v-if="selectedPost.tags.length" class="post-tags detail-tags"><span v-for="tag in selectedPost.tags" :key="tag">#{{ tag }}</span></div>
          <div
  v-if="selectedPost.image_urls.length"
  class="detail-gallery"
  :class="`count-${Math.min(selectedPost.image_urls.length, 5)}`"
>
  <div
    v-for="(url, index) in selectedPost.image_urls"
    :key="url"
    class="gallery-item"
  >
    <img
      :src="url"
      :alt="`${selectedPost.title} 사진 ${index + 1}`"
      @click="selectedImage = url"
    >
  </div>
</div>
          <div class="post-detail-content">{{ selectedPost.content }}</div>
          <p v-if="communityError" class="form-error">{{ communityError }}</p>
          <div class="post-detail-like"><span>♥　{{ selectedPost.like_count }}명이 좋아합니다</span><button class="post-like-button" :class="{ liked: selectedPost.liked }" :aria-pressed="selectedPost.liked" :disabled="communityLoading" @click="togglePostLike"><b aria-hidden="true">{{ selectedPost.liked ? '♥' : '♡' }}</b> 좋아요</button></div>
          <div class="comment-disabled">ⓘ　이 커뮤니티는 댓글 기능을 제공하지 않습니다.</div>
        </article>

        <Teleport to="body">

<div

    v-if="selectedImage"

    class="image-modal"

    @click="selectedImage=null"

>

    <img

        :src="selectedImage"

        class="modal-image"

        @click.stop

    >

    <button

        class="close-button"

        @click="selectedImage=null"

    >

        ✕

    </button>

</div>

</Teleport>
      </template>
    </div>
  </main>
</template>
