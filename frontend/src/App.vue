<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { api, API_BASE, patchJson, postJson } from './api/client'
import { useAppStore } from './stores/app'

type DimensionKey = 'moral' | 'academic' | 'arts_sports'
type OpportunitySource = 'activity' | 'competition' | 'evergreen'  // evergreen=星轨探索目录项

interface Opportunity {
  id: number | string
  source_type: OpportunitySource
  source_label: string
  title: string
  category: string
  dimension: DimensionKey
  dimension_label: string
  organizer: string
  location: string
  start_time: string
  deadline: string
  season_months: string
  credit_hint: string
  rule_ref: string
  official_url: string
  registration_url: string
  contact_email: string
  article_url: string
  group_qr_url: string
  description: string
  requirements: string[]
  tags: string[]
  attachments: Array<{ name: string; url: string }>
  images?: string[]
  roi_score: number
  in_basket: boolean
  activity_id?: string | number
}

interface BasketItem {
  id: number | string
  stage: string
  note: string
  opportunity: Opportunity
}

interface ApplicationItem {
  id: number
  title: string
  dimension: DimensionKey
  award_level: string
  material_manifest: Record<string, boolean>
  ai_review: Record<string, any>
  ai_confidence: number
  risk_tags: string[]
  suggested_score: number
  status: string
  admin_comment: string
  student_name?: string
  opportunity_title?: string
}

interface HonorItem {
  id: number
  title: string
  category: string
  image_url: string
  sort_order: number
  visibility: string
}

interface RuleDocument {
  id: number
  name: string
  version: string
  file_url: string
  notes: string
  is_active: number
  uploaded_at: string
}

interface DashboardSummary {
  user: { name: string; college: string; major: string }
  score: {
    rule_version: string
    total: number
    details: Array<{
      key: DimensionKey
      label: string
      base: number
      raw_add: number
      normalized_add: number
      deduction: number
      score: number
      weight: number
      weighted: number
      cap: number
    }>
  }
  pending_score: number
  goal_gap: number
  ledgers: Array<{ title: string; dimension: DimensionKey; score: number; rule_ref: string }>
  pending_applications: ApplicationItem[]
  gpa_info?: {
    score: number | null
    bonus: number
    tier: string
    weighted_average?: number | null
    academic_base?: number | null
    from_courses?: boolean
    course_count?: number
  }
  scoring_rules?: {
    formula: string
    dimensions: Array<{ key: string; label: string; base: number; cap: number; weight: number }>
    note: string
  }
}

interface TemplateData {
  rule_version: string
  active_rule_document: RuleDocument | null
  strict_materials: string[]
  dimensions: Array<{ key: DimensionKey; label: string; base: number; cap: number; weight: number }>
  notes: string[]
}

type UploadedFile = { id?: number; name: string; url: string; type?: string; proofType?: string }

interface AnalyzeMatch {
  id: string
  title: string
  category: string
  category_name?: string
  description?: string
  icon?: string
  level: string
  score: number
  confidence: number
  decision: string
  reason: string
  risk_level?: string
  confidence_detail?: string
  section?: string
  note?: string
  audit?: AuditPayload
}

interface AnalyzeResult {
  file_id: number
  filename: string
  extracted_text: string
  has_text_content: boolean
  matches: AnalyzeMatch[]
}

interface AuditPayload {
  status?: string
  confidence_score?: number
  matched_regulation?: {
    section?: string
    clause_id?: string
    clause_text?: string
    score_calculated?: number
  }
  extracted_features?: Record<string, any>
  risk_assessment?: {
    risk_tags?: string[]
    risk_description?: string
  }
  missing_fields?: Array<{
    field_key: string
    field_name: string
    guidance_tips: string
  }>
  audit_chain?: string[]
}

interface AdminUser {
  id: number
  student_id: string
  name: string
  department: string
  class_name: string
  item_count: number
  submission_count: number
  created_at: string
}

interface AdminUserItem {
  id: number
  catalog_item_id: string
  title: string
  score: number
  source: string
  submission_id?: number
  completion_date: string
  created_at: string
  category?: string
  category_name?: string
  level?: string
  section?: string
}

interface CatalogExplorerItem {
  id: string
  category: string
  category_name: string
  subcategory: string
  subcategory_name: string
  title: string
  description: string
  level: string
  score: number
  icon: string
  section: string
  note: string
  required_proofs?: Array<{ type: string; name: string; description: string }>
}

interface CatalogFilters {
  categories: Array<{ key: string; name: string }>
  levels: string[]
  subcategories: Array<{ key: string; name: string }>
  sections: string[]
}

// ---- 学业成绩录入 ----
interface GradeCourse {
  key: string
  id?: number
  course_name: string
  grade: number | null
  credits: number | null
  course_type: string
  ocr_source: boolean
}

interface GradeOcrCourse {
  course_name: string
  grade: number
  credits: number
  course_type: string
  confidence: number
  selected: boolean
}

interface GradeComputation {
  weighted_average: number
  academic_base_score: number
  gpa_bonus: number
  gpa_tier: string
  required_courses_avg: number | null
  required_min_grade: number | null
  all_required_pass: boolean
}

const store = useAppStore()
const route = useRoute()
const router = useRouter()

const studentTabs = ['星盘总览', '机会大厅', '备赛清单', '星轨探索', '智审中心']
const adminTabs = ['数据看板', '用户管理', '活动发布管理', '综测审核中心', '规则与材料模板']
const activeStudentTab = ref('星盘总览')
const activeAdminTab = ref('数据看板')
const opportunityMode = ref<OpportunitySource>('activity')
const auditQueue = ref('')

const loading = ref(false)
const gpaEditValue = ref('')
const gpaSaving = ref(false)
const summary = ref<DashboardSummary | null>(null)
const opportunities = ref<Opportunity[]>([])
const basket = ref<BasketItem[]>([])
const applications = ref<ApplicationItem[]>([])
const adminApplications = ref<ApplicationItem[]>([])
const honors = ref<HonorItem[]>([])
const templates = ref<TemplateData | null>(null)
const ruleDocs = ref<RuleDocument[]>([])
const adminStats = ref<any>(null)
const adminUsers = ref<AdminUser[]>([])
const adminUsersLoading = ref(false)
const adminUserKeyword = ref('')
const adminDashboardKeyword = ref('')
const adminDashboardStatusFilter = ref('')
const catalogItems = ref<CatalogExplorerItem[]>([])
const catalogFilters = ref<CatalogFilters>({ categories: [], levels: [], subcategories: [], sections: [] })
const submittedCatalogIds = ref<Set<string>>(new Set())
const basketCatalogIds = ref<Set<string>>(new Set())
const catalogQuery = reactive({ category: '', level: '', section: '', subcategory: '', keyword: '' })

// ---- 学年选择 ----
const currentAcademicYear = ref('2025-2026')
const availableAcademicYears = ref<string[]>(['2025-2026', '2024-2025', '2023-2024'])

// ---- 学业成绩录入弹窗 ----
const showGradeModal = ref(false)
const gradeModalYear = ref('')
const gradeModalCourses = ref<GradeCourse[]>([])
const gradeModalUploadFiles = ref<File[]>([])
const gradeModalServerFiles = ref<UploadedFile[]>([])
const gradeModalOcrLoading = ref(false)
const gradeModalOcrResults = ref<GradeOcrCourse[]>([])
const gradeModalOcrDone = ref(false)
const gradeModalSaving = ref(false)
const gradeModalSaved = ref(false)
const gradeModalError = ref('')
const gradeComputation = ref<GradeComputation | null>(null)

const selectedOpportunity = ref<Opportunity | null>(null)
const selectedDashboardApplication = ref<ApplicationItem | null>(null)
const selectedAdminUser = ref<AdminUser | null>(null)
const selectedAdminUserItems = ref<AdminUserItem[]>([])
const userEditorVisible = ref(false)
const resetPasswordVisible = ref(false)
const userItemsVisible = ref(false)
const draggedHonorId = ref<number | null>(null)
const brokenOpportunityImages = ref<Set<number | string>>(new Set())

const filters = reactive({
  dimension: '',
  category: '',
  keyword: '',
})

const materialParsing = ref(false)
const materialSubmitMode = ref<'match' | 'targeted'>('match')
const materialSelectedFiles = ref<File[]>([])
const materialServerFiles = ref<UploadedFile[]>([])
const materialAnalysisResults = ref<AnalyzeResult[]>([])
const materialAddedItems = ref<Array<{ id: string; fileId: number; filename: string; title: string; category: string; category_name?: string; level: string; score: number; confidence: number; status: string }>>([])
const materialSupplementFiles = ref<Record<string, UploadedFile | null>>({})
const materialExtraKeyword = ref('')
const targetCatalogQuery = reactive({ category: '', level: '', keyword: '' })
const selectedTargetItem = ref<CatalogExplorerItem | null>(null)
const targetRequiredProofs = ref<Array<{ type: string; name: string; description: string }>>([])
const targetProofFiles = ref<Record<string, UploadedFile | null>>({})
const targetCompletionDate = ref('')
const targetAiVerifyResult = ref('')
const targetManualForm = reactive({
  title: '',
  category: 'academic',
  level: '',
  score: '',
  description: '',
  completion_date: '',
})
const targetManualFiles = ref<UploadedFile[]>([])

// ---- 星轨探索提交认证弹窗 ----
const showSubmitModal = ref(false)
const submitModalItem = ref<CatalogExplorerItem | null>(null)
const submitForm = reactive({ title: '', dimension: '', award_level: '', completion_date: '', score_estimate: 0 })
const submitModalFiles = ref<File[]>([])
const submitModalServerFiles = ref<UploadedFile[]>([])
const submitModalAnalyzing = ref(false)
const submitModalAnalyzed = ref(false)
const submitModalAnalysisResult = ref<AnalyzeResult | null>(null)
const submitModalConfidence = ref(0)
const submitModalSubmitting = ref(false)
const submitModalSubmitted = ref(false)
const honorForm = reactive({ title: '', category: '证书', image_url: '' })
const honorDropOver = ref(false)
const honorSelectedFiles = ref<File[]>([])
const honorEditorVisible = ref(false)
const honorEditForm = reactive({ id: 0, title: '', category: '证书', image_url: '', visibility: 'private' })
const publishForm = reactive({
  source_type: 'activity' as OpportunitySource,
  title: '',
  category: '活动通知',
  dimension: 'moral' as DimensionKey,
  organizer: '电子与信息学院',
  location: '',
  start_time: '',
  deadline: '',
  season_months: '',
  credit_hint: '',
  rule_ref: '',
  official_url: '',
  registration_url: '',
  contact_email: '',
  article_url: '',
  group_qr_url: '',
  description: '',
  requirementsText: '活动或比赛通知\n参赛或参与证明\n结果证明',
  tagsText: '学院通知\n可加分',
})
const aiNoticeText = ref('')
const aiGroupMessage = ref('')
const aiParsed = ref<Record<string, any> | null>(null)
const publishScanFiles = ref<File[]>([])
const publishScanUploading = ref(false)
const publishScanStatus = ref('')
const aiExpanded = ref(true)
const aiParsing = ref(false)
const publishImages = ref<Array<{ name: string; url: string; localUrl: string }>>([])
const publishQr = ref<{ name: string; url: string; localUrl: string } | null>(null)
const publishDragOver = ref(false)
const ruleUpload = reactive({ version: '2024-07-12-electronic-info-v1', notes: '' })
const userEditForm = reactive({
  id: 0,
  student_id: '',
  name: '',
  password: '000000',
  department: '电子与信息学院',
  class_name: '',
})
const resetPasswordForm = reactive({ userId: 0, name: '', password: '000000' })

const radarRef = ref<HTMLDivElement | null>(null)
const barRef = ref<HTMLDivElement | null>(null)

const modeLabel = computed(() => (store.roleMode === 'student' ? '学生端' : '管理端'))
const currentTabs = computed(() => (store.roleMode === 'student' ? studentTabs : adminTabs))
const currentActiveTab = computed(() => (store.roleMode === 'student' ? activeStudentTab.value : activeAdminTab.value))
const activeRuleDoc = computed(() => ruleDocs.value.find(doc => doc.is_active) || templates.value?.active_rule_document || null)
const canViewAdmin = computed(() => store.currentUser?.role === 'admin')
const filteredOpportunities = computed(() => {
  return opportunities.value.filter(item => {
    if (item.source_type !== opportunityMode.value) return false
    if (filters.dimension && item.dimension !== filters.dimension) return false
    if (filters.category && item.category !== filters.category) return false
    if (filters.keyword && !item.title.includes(filters.keyword.trim())) return false
    return true
  })
})

const currentOpportunityCategories = computed(() => {
  const categories = opportunities.value
    .filter(item => item.source_type === opportunityMode.value)
    .map(item => item.category)
    .filter(Boolean)
  return Array.from(new Set(categories)).slice(0, 5)
})

const opportunityCounts = computed(() => ({
  activity: opportunities.value.filter(item => item.source_type === 'activity').length,
  competition: opportunities.value.filter(item => item.source_type === 'competition').length,
}))

const completedScoreItems = computed(() => {
  return (summary.value?.ledgers || [])
    .filter(item => (item as any).kind !== 'base')  // 排除基础分（学业基本分等），只展示加分项
    .map(item => ({
      title: item.title,
      dimension: dimensionDisplayName(item.dimension),
      child: inferLedgerChild(item.title, item.rule_ref),
      level: inferLedgerLevel(item.title, item.rule_ref),
      score: item.score,
    }))
})

const categoryScoreDistribution = computed(() => {
  const totals = new Map<string, number>()
  for (const item of completedScoreItems.value) {
    totals.set(item.child, (totals.get(item.child) || 0) + item.score)
  }
  return Array.from(totals, ([name, value]) => ({ name, value }))
})

const aiAnalysisStamp = ref('刚刚更新')
const aiScoreInsights = computed(() => {
  const details = summary.value?.score.details || []
  const lowest = [...details].sort((a, b) => a.score - b.score)[0]
  const pending = applications.value.filter(item => ['pending_human', 'needs_more'].includes(item.status))
  const highPending = pending.filter(item => item.ai_confidence >= 0.85).length
  const ledgerScore = completedScoreItems.value.reduce((sum, item) => sum + item.score, 0)
  return [
    {
      tone: 'warning',
      title: `${lowest?.label || '文体'}仍是短板`,
      text: `当前${lowest?.label || '文体'}分为 ${lowest?.score ?? 60}，建议优先参加学院文体活动、主持/诗歌节观众、志愿服务等低门槛项目。`,
    },
    {
      tone: 'success',
      title: '综合成绩稳定',
      text: `当前已入账 ${completedScoreItems.value.length} 项、原始加分合计 ${ledgerScore} 分，总评 ${summary.value?.score.total ?? '--'}。继续保持材料完整度可减少人工往返。`,
    },
    {
      tone: 'info',
      title: '近期可冲刺',
      text: `还有 ${pending.length} 条认证在审核链路中，其中 ${highPending} 条 AI 高置信。建议补齐通知来源、名单和结果证明后提交。`,
    },
  ]
})

const auditStats = computed(() => {
  const all = adminApplications.value
  return {
    pending: all.filter(item => ['pending_ai', 'pending_human', 'needs_more'].includes(item.status)).length,
    high: all.filter(item => item.ai_confidence >= 0.85 && item.status === 'pending_human').length,
    risk: all.filter(item => item.status === 'needs_more' || item.ai_confidence < 0.7).length,
    approved: all.filter(item => item.status === 'approved').length,
  }
})

const adminDashboardRows = computed(() => {
  const keyword = adminDashboardKeyword.value.trim().toLowerCase()
  return adminApplications.value.filter(item => {
    if (adminDashboardStatusFilter.value && item.status !== adminDashboardStatusFilter.value) return false
    if (keyword && !`${item.student_name || ''}${item.title}${item.award_level}`.toLowerCase().includes(keyword)) return false
    return true
  }).slice(0, 5)
})
const adminDashboardFocus = computed(() => {
  if (selectedDashboardApplication.value) {
    const fresh = adminApplications.value.find(item => item.id === selectedDashboardApplication.value?.id)
    if (fresh) return fresh
  }
  return adminDashboardRows.value.find(item => item.status === 'pending_human') || adminDashboardRows.value[0] || null
})
const adminDashboardKpis = computed(() => ({
  opportunity_count: Number(adminStats.value?.opportunity_count ?? 0),
  application_count: Number(adminStats.value?.application_count ?? adminApplications.value.length),
  pending_count: adminApplications.value.filter(item => ['pending_ai', 'pending_human', 'needs_more'].includes(item.status)).length,
  approved_score: Number(adminStats.value?.approved_score ?? 0),
}))
const adminUserItemTotalScore = computed(() => selectedAdminUserItems.value.reduce((sum, item) => sum + (item.score || 0), 0))
const catalogExplorerStats = computed(() => ({
  moral: catalogItems.value.filter(item => item.category === 'moral').length,
  academic: catalogItems.value.filter(item => item.category === 'academic').length,
  sports: catalogItems.value.filter(item => item.category === 'sports').length,
  total: catalogItems.value.length,
}))
const filteredCatalogItems = computed(() => {
  const keyword = catalogQuery.keyword.trim().toLowerCase()
  return catalogItems.value.filter(item => {
    if (catalogQuery.category && item.category !== catalogQuery.category) return false
    if (catalogQuery.level && item.level !== catalogQuery.level) return false
    if (catalogQuery.section && item.section !== catalogQuery.section) return false
    if (catalogQuery.subcategory && item.subcategory !== catalogQuery.subcategory) return false
    if (keyword && !`${item.title}${item.description}${item.section}`.toLowerCase().includes(keyword)) return false
    return true
  })
})
const filteredTargetCatalogItems = computed(() => {
  const keyword = targetCatalogQuery.keyword.trim().toLowerCase()
  return catalogItems.value.filter(item => {
    if (targetCatalogQuery.category && item.category !== targetCatalogQuery.category) return false
    if (targetCatalogQuery.level && item.level !== targetCatalogQuery.level) return false
    if (keyword && !`${item.title}${item.description}${item.section}`.toLowerCase().includes(keyword)) return false
    return true
  }).slice(0, 30)
})
void filteredTargetCatalogItems

function switchTab(tab: string) {
  if (store.roleMode === 'student') activeStudentTab.value = tab
  else {
    activeAdminTab.value = tab
    if (tab === '用户管理' && canViewAdmin.value) loadAdminUsers()
  }
}

function switchRole(role: 'student' | 'admin') {
  if (role === 'admin') {
    if (!canViewAdmin.value) return
    window.location.assign('/back-to-admin')
    return
  }
  if (canViewAdmin.value) {
    window.location.assign('/view-as-student')
    return
  }
  store.switchRole('student')
  router.push('/student')
  nextTick(renderCharts)
}

async function logout() {
  await fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  await router.push('/login')
}

watch(
  () => route.path,
  path => {
    if (path.startsWith('/admin') && canViewAdmin.value) store.switchRole('admin')
    else store.switchRole('student')
    nextTick(renderCharts)
  },
  { immediate: true },
)

watch(opportunityMode, () => {
  filters.category = ''
})

function dimensionDisplayName(dimension: DimensionKey) {
  const map: Record<DimensionKey, string> = {
    moral: '德育表现',
    academic: '学业表现',
    arts_sports: '文体表现',
  }
  return map[dimension]
}

function inferLedgerChild(title: string, ruleRef: string) {
  const text = `${title}${ruleRef}`
  if (text.includes('学生干部') || text.includes('团总支') || text.includes('学生会') || text.includes('班长') || text.includes('团支书') || text.includes('宿舍长') || text.includes('社团') || text.includes('助理')) return '学生干部'
  if (text.includes('志愿') || text.includes('义务劳动') || text.includes('三下乡')) return '志愿活动'
  if (text.includes('军训')) return '荣誉称号'
  if (text.includes('文明宿舍')) return '文明宿舍'
  if (text.includes('献血') || text.includes('见义勇为')) return '好人好事'
  if (text.includes('办公室值班') || text.includes('承办')) return '活动组织'
  if (text.includes('代表大会')) return '代表参会'
  if (text.includes('班集体') || text.includes('团员')) return '集体荣誉'
  if (text.includes('处分') || text.includes('缺勤') || text.includes('旷课')) return '扣分'
  if (text.includes('电子设计') || text.includes('蓝桥杯') || text.includes('竞赛') || text.includes('互联网') || text.includes('大挑') || text.includes('小挑') || text.includes('挑战杯')) return '学科竞赛'
  if (text.includes('论文') || text.includes('SCI') || text.includes('期刊')) return '学术论文'
  if (text.includes('专利') || text.includes('软著') || text.includes('著作权')) return '专利软著'
  if (text.includes('证书') || text.includes('四级') || text.includes('六级') || text.includes('英语') || text.includes('普通话') || text.includes('计算机等级')) return '专业证书'
  if (text.includes('大创') || text.includes('立项') || text.includes('攀登计划')) return '科研立项'
  if (text.includes('考研') || text.includes('研究生')) return '考研升学'
  if (text.includes('均分') || text.includes('单科') || text.includes('学业成绩加分') || text.includes('GPA')) return 'GPA成绩加分'
  if (text.includes('主持') || text.includes('文艺') || text.includes('运动会') || text.includes('体育') || text.includes('啦啦队') || text.includes('训练') || text.includes('演出')) return '文体活动'
  if (text.includes('讲座') || text.includes('团学代')) return '参加活动'
  if (text.includes('刊物') || text.includes('发表')) return '文章发表'
  if (text.includes('荣誉称号') || text.includes('先进个人') || text.includes('优秀') || text.includes('标兵')) return '荣誉称号'
  return '其他加分'
}

function inferLedgerLevel(title: string, ruleRef: string) {
  const text = `${title}${ruleRef}`
  if (text.includes('国家级')) return '国家级'
  if (text.includes('省级')) return '省级'
  if (text.includes('校级')) return '校级'
  if (text.includes('院级') || text.includes('学院')) return '院级'
  return '认定'
}

function refreshAiScoreAnalysis() {
  aiAnalysisStamp.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  ElMessage.success('AI 已根据当前入账和待审核材料刷新建议')
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '待人工审核',
    auto_approved: 'AI自动通过',
    pending_ai: '待 AI 初审',
    pending_human: '待人工审核',
    needs_more: '需补材料',
    approved: '已入账',
    rejected: '已驳回',
  }
  return map[status] || status
}

function statusText(app: ApplicationItem) {
  if (app.status === 'needs_more') return '信息存疑需复核'
  if (app.status === 'rejected') return '材料不符合要求'
  if (app.ai_confidence >= 0.85 && app.status !== 'rejected') return 'AI 建议通过'
  if (app.ai_confidence < 0.6) return '材料需人工复核'
  return '材料需人工复核'
}

function isHighConfidenceAudit(app: ApplicationItem) {
  return app.ai_confidence >= 0.85 && app.status === 'pending_human'
}

function isReviewAudit(app: ApplicationItem) {
  return app.status === 'needs_more' || app.ai_confidence < 0.7
}

function orderAuditRows(rows: ApplicationItem[]) {
  const high = rows.filter(isHighConfidenceAudit)
  const review = rows.filter(item => !isHighConfidenceAudit(item) && isReviewAudit(item))
  const rest = rows.filter(item => !isHighConfidenceAudit(item) && !isReviewAudit(item))
  const ordered: ApplicationItem[] = []
  while (high.length || review.length) {
    if (high.length) ordered.push(high.shift()!)
    if (high.length) ordered.push(high.shift()!)
    if (review.length) ordered.push(review.shift()!)
  }
  return [...ordered, ...rest]
}

function confidenceClass(value: number) {
  if (value >= 0.85) return 'confidence-high'
  if (value >= 0.6) return 'confidence-mid'
  return 'confidence-low'
}

function sourceConfidence(value: number) {
  return value > 1 ? value / 100 : value
}

function sourceStatus(status: string) {
  if (status === 'pending') return 'pending_human'
  if (status === 'auto_approved') return 'approved'
  return status || 'pending_human'
}

function mapSubmissionToApplication(row: any): ApplicationItem {
  const confidence = sourceConfidence(Number(row.ai_confidence || 0))
  const missing = row.missing_proofs || row.ai_review?.missing_materials || []
  return {
    id: row.id,
    title: row.title,
    dimension: row.category === 'sports' ? 'arts_sports' : (row.category || row.dimension || 'academic'),
    award_level: row.level || row.award_level || row.proof_filename || '证明材料',
    material_manifest: {},
    ai_review: {
      recognized_text: row.ai_reason || '',
      missing_materials: missing,
      rule_ref: row.matched_regulation?.section || row.section || '',
      recommendation: row.review_remarks || row.ai_reason || (confidence >= 0.85 ? 'AI 建议通过，等待人工复核。' : '建议人工复核材料。'),
      matched_regulation: row.matched_regulation || {},
      extracted_features: row.extracted_features || {},
      risk_assessment: row.risk_assessment || {},
      missing_fields: row.missing_fields || [],
      audit_chain: row.audit_chain || [],
    },
    ai_confidence: confidence,
    risk_tags: [
      confidence >= 0.85 ? 'AI高置信' : confidence < 0.7 ? '需人工复核' : '待人工确认',
      ...(missing.length ? ['材料缺失'] : []),
      ...((row.risk_assessment?.risk_tags || []) as string[]),
    ],
    suggested_score: Number(row.score || 0),
    status: sourceStatus(row.status),
    admin_comment: row.review_remarks || '',
    student_name: row.student_name || '',
    opportunity_title: row.title,
  }
}

function imgUrl(url: string) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  if (url.startsWith('/competition-covers') || url.startsWith('/uploads/opportunity-demo')) return url
  if (import.meta.env.PROD && url.startsWith('/uploads')) return url
  return API_BASE.replace('/api', '') + url
}

function isRealExternalUrl(url?: string) {
  if (!url) return false
  if (url.startsWith('/uploads')) return true
  if (!/^https?:\/\//.test(url)) return false
  if (url.includes('example.edu')) return false
  if (url === 'https://mp.weixin.qq.com/') return false
  return true
}

function visibleContactEmail(email?: string) {
  if (!email || email.includes('example.')) return ''
  return email
}

const honorPresets = [
  { variant: 'honor-gold', brand: 'NCIETCC', type: 'CERTIFICATE', award: '一等奖', subject: '英语翻译挑战赛', date: '2026.01', seal: '荣誉证书' },
  { variant: 'honor-blue', brand: 'Bebras', type: 'PARTICIPATION', award: '优秀', subject: '信息思维挑战', date: '2023', seal: '思维挑战' },
  { variant: 'honor-red', brand: 'HUAWEI', type: 'CERTIFICATION', award: 'HCIA-AI', subject: '人工智能认证', date: '2028.11', seal: 'AI' },
  { variant: 'honor-green', brand: '929 Challenge', type: 'CERTIFICATE', award: 'Top 50', subject: '创业挑战赛', date: '2025.11', seal: '创业' },
  { variant: 'honor-photo', brand: 'Challenge Cup', type: 'SHOWCASE', award: '院赛展示', subject: '创新创业项目', date: '2025.10', seal: '科创' },
]

function opportunityImage(item: Opportunity) {
  if (brokenOpportunityImages.value.has(item.id)) return ''
  const image = item.images?.find(Boolean)
  return image ? imgUrl(image) : ''
}

function opportunityFallbackClass(item: Opportunity) {
  if (item.source_type === 'competition') {
    return item.category === '国家级' ? 'fallback-national' : 'fallback-provincial'
  }
  if (item.source_type === 'activity') return 'fallback-activity'
  if (item.title.includes('嵌入式') || item.title.includes('芯片')) return 'fallback-chip'
  if (item.title.includes('挑战杯')) return 'fallback-challenge'
  if (item.title.includes('智能汽车')) return 'fallback-smartcar'
  if (item.title.includes('数学建模')) return 'fallback-math'
  if (item.title.includes('电子')) return 'fallback-electronic'
  return 'fallback-default'
}

function opportunityFallbackTitle(item: Opportunity) {
  if (item.source_type === 'competition') {
    const title = item.title
    // 折行策略：在"大赛""竞赛""挑战赛""赛"等处折行
    return title
      .replace('全国大学生', '全国大学生\n')
      .replace('中国大学生', '中国大学生\n')
      .replace('全国高校', '全国高校\n')
      .replace('广东省大学生', '广东省大学生\n')
      .replace('广东省本科', '广东省本科\n')
  }
  return item.title.replace('全国大学生', '全国大学生\n').replace('中国大学生', '中国大学生\n')
}

function opportunityFallbackKeyword(item: Opportunity) {
  if (item.source_type === 'competition') {
    return item.category || '学科竞赛'
  }
  if (item.source_type === 'activity') {
    return item.category || '近期活动'
  }
  const title = item.title
  const keywordRules = [
    '物联网', '数学建模', '电子设计', '计算机设计',
    '蓝桥杯', '挑战杯', '智能汽车', '信息安全', '创新创业',
    '学风建设', '社会实践', '助理招新',
  ]
  return keywordRules.find(key => title.includes(key)) || item.category || item.dimension_label
}

function markOpportunityImageBroken(item: Opportunity) {
  brokenOpportunityImages.value = new Set([...brokenOpportunityImages.value, item.id])
}

function applyOpportunityFilters() {
  filters.keyword = filters.keyword.trim()
}

function resetOpportunityFilters() {
  filters.dimension = ''
  filters.category = ''
  filters.keyword = ''
}

function honorImage(item: HonorItem) {
  return item.image_url ? imgUrl(item.image_url) : ''
}

function honorPreset(item: HonorItem, index: number) {
  if (item.title.includes('华为') || item.title.includes('HCIA')) return honorPresets[2]
  if (item.title.includes('Bebras')) return honorPresets[1]
  if (item.title.includes('中葡') || item.title.includes('929')) return honorPresets[3]
  if (item.title.includes('挑战杯') || item.title.includes('院赛')) return honorPresets[4]
  if (item.title.includes('英语') || item.title.includes('翻译')) return honorPresets[0]
  return honorPresets[index % honorPresets.length]
}

function opportunityLinks(item: Opportunity) {
  return [
    { label: '官网/来源', url: item.official_url },
    { label: '报名链接', url: item.registration_url },
    { label: '公众号文章', url: item.article_url },
  ].filter(link => isRealExternalUrl(link.url))
}

function opportunityAttachments(item: Opportunity) {
  return (item.attachments || []).filter(file => Boolean(file.url))
}

async function loadCatalogExplorer() {
  const year = currentAcademicYear.value
  const [catalogData, userItems, submissions, basketItems] = await Promise.all([
    api<{ items: CatalogExplorerItem[]; filters: CatalogFilters }>('/catalog'),
    api<{ items: Array<{ catalog_item_id?: string }> }>(`/user-items?academic_year=${year}`),
    api<{ submissions: Array<{ catalog_item_id?: string; status: string }> }>(`/submissions?academic_year=${year}`),
    api<BasketItem[]>('/plan-basket'),
  ])
  catalogItems.value = catalogData.items || []
  catalogFilters.value = catalogData.filters || { categories: [], levels: [], subcategories: [], sections: [] }
  const ids = new Set<string>()
  for (const item of userItems.items || []) {
    if (item.catalog_item_id) ids.add(item.catalog_item_id)
  }
  for (const item of submissions.submissions || []) {
    if (item.catalog_item_id && ['pending', 'needs_more', 'auto_approved', 'approved'].includes(item.status)) {
      ids.add(item.catalog_item_id)
    }
  }
  const basketIds = new Set<string>()
  for (const item of mergeBasketRows(basketItems || [])) {
    const activityId = item.opportunity?.activity_id
    if (typeof activityId === 'string' && activityId.startsWith('CAT-')) {
      basketIds.add(activityId.slice(4))
    }
  }
  submittedCatalogIds.value = ids
  basketCatalogIds.value = basketIds
}

function catalogCategoryClass(category: string) {
  if (category === 'academic') return 'academic'
  if (category === 'sports') return 'sports'
  return 'moral'
}

function catalogLevelClass(level: string) {
  if (level.includes('国家')) return 'national'
  if (level.includes('省')) return 'provincial'
  if (level.includes('校')) return 'school'
  return 'college'
}

function catalogBasketStorageKey() {
  return `zongce-catalog-basket-${store.studentId}`
}

function basketIdentity(item: BasketItem) {
  return String(item.opportunity?.activity_id || item.opportunity?.id || item.id)
}

function loadLocalCatalogBasket() {
  try {
    const raw = localStorage.getItem(catalogBasketStorageKey())
    return raw ? JSON.parse(raw) as BasketItem[] : []
  } catch {
    return []
  }
}

function saveLocalCatalogBasket(items: BasketItem[]) {
  localStorage.setItem(catalogBasketStorageKey(), JSON.stringify(items))
}

function mergeBasketRows(remoteRows: BasketItem[], localRows = loadLocalCatalogBasket()) {
  const rows = new Map<string, BasketItem>()
  for (const item of remoteRows) rows.set(basketIdentity(item), item)
  for (const item of localRows) {
    const key = basketIdentity(item)
    if (!rows.has(key)) rows.set(key, item)
  }
  return Array.from(rows.values())
}

function markOpportunitiesInBasket(items: Opportunity[], basketRows: BasketItem[]) {
  const ids = new Set(basketRows.map(item => String(item.opportunity?.id)))
  return items.map(item => ({
    ...item,
    in_basket: item.in_basket || ids.has(String(item.id)),
  }))
}

function catalogItemToOpportunity(item: CatalogExplorerItem): Opportunity {
  const dimension = item.category === 'sports' ? 'arts_sports' : item.category === 'moral' || item.category === 'academic' ? item.category : 'academic'
  return {
    id: `CAT-${item.id}`,
    source_type: 'evergreen',
    source_label: '星轨探索',
    title: item.title,
    category: item.section || item.category_name,
    dimension,
    dimension_label: item.category_name || dimensionDisplayName(dimension),
    organizer: '综测细则目录',
    location: '',
    start_time: '',
    deadline: '',
    season_months: '',
    credit_hint: item.description || `${item.level}项目，预计可加 ${item.score} 分`,
    rule_ref: item.section || item.note || '',
    official_url: '',
    registration_url: '',
    contact_email: '',
    article_url: '',
    group_qr_url: '',
    description: item.description || item.title,
    requirements: item.required_proofs?.map(proof => proof.name || proof.type).filter(Boolean) || [],
    tags: [item.level, item.section].filter(Boolean),
    attachments: [],
    images: [],
    roi_score: item.score,
    in_basket: true,
    activity_id: `CAT-${item.id}`,
  }
}

async function addCatalogItem(item: CatalogExplorerItem) {
  try {
    const identity = `CAT-${item.id}`
    const fallbackRow: BasketItem = {
      id: `local-${identity}`,
      stage: '想参加',
      note: '',
      opportunity: catalogItemToOpportunity(item),
    }
    const created = await postJson<BasketItem>('/plan-basket', {
      user_id: store.studentId,
      catalog_item_id: item.id,
      title: item.title,
      category: item.category,
      category_name: item.category_name,
      description: item.description,
      level: item.level,
      score: item.score,
      section: item.section,
      stage: '想参加',
    })
    const row = created?.opportunity ? created : fallbackRow
    const localRows = loadLocalCatalogBasket().filter(existing => basketIdentity(existing) !== identity)
    saveLocalCatalogBasket([fallbackRow, ...localRows])
    basketCatalogIds.value = new Set([...basketCatalogIds.value, item.id])
    basket.value = mergeBasketRows([row, ...basket.value.filter(existing => basketIdentity(existing) !== identity)])
    ElMessage.success(`已添加「${item.title}」到备赛清单`)
    await loadAll()
    if (!basket.value.some(existing => basketIdentity(existing) === identity)) {
      basket.value = mergeBasketRows([row, ...basket.value])
    }
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

function userItemSourceLabel(source: string) {
  if (source === 'upload') return '上传审核'
  if (source === 'manual') return '手动添加'
  return '管理员添加'
}

async function loadAdminUsers() {
  if (!canViewAdmin.value) return
  adminUsersLoading.value = true
  try {
    const keyword = adminUserKeyword.value.trim()
    const data = await api<{ users: AdminUser[] }>(`/admin/users${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''}`)
    adminUsers.value = data.users || []
  } catch (error) {
    ElMessage.error(`用户加载失败：${(error as Error).message}`)
  } finally {
    adminUsersLoading.value = false
  }
}

let adminUserSearchTimer: number | undefined
function debounceAdminUserSearch() {
  window.clearTimeout(adminUserSearchTimer)
  adminUserSearchTimer = window.setTimeout(loadAdminUsers, 300)
}

function openAddAdminUser() {
  Object.assign(userEditForm, { id: 0, student_id: '', name: '', password: '000000', department: '电子与信息学院', class_name: '' })
  userEditorVisible.value = true
}

function openEditAdminUser(user: AdminUser) {
  Object.assign(userEditForm, { id: user.id, student_id: user.student_id, name: user.name, password: '', department: user.department, class_name: user.class_name })
  userEditorVisible.value = true
}

async function saveAdminUser() {
  try {
    if (userEditForm.id) {
      await api(`/admin/users/${userEditForm.id}`, {
        method: 'PUT',
        body: JSON.stringify({ name: userEditForm.name.trim(), department: userEditForm.department.trim(), class_name: userEditForm.class_name.trim() }),
      })
      ElMessage.success('用户已更新')
    } else {
      await api('/admin/users', {
        method: 'POST',
        body: JSON.stringify({
          student_id: userEditForm.student_id.trim(),
          name: userEditForm.name.trim(),
          password: userEditForm.password.trim(),
          department: userEditForm.department.trim(),
          class_name: userEditForm.class_name.trim(),
        }),
      })
      ElMessage.success('用户已创建')
    }
    userEditorVisible.value = false
    await loadAdminUsers()
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

async function disableAdminUser(user: AdminUser) {
  if (!window.confirm(`确定禁用用户「${user.name}」吗？`)) return
  try {
    await api(`/admin/users/${user.id}`, { method: 'DELETE' })
    ElMessage.success(`已禁用用户「${user.name}」`)
    await loadAdminUsers()
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

function openResetAdminPassword(user: AdminUser) {
  Object.assign(resetPasswordForm, { userId: user.id, name: user.name, password: '000000' })
  resetPasswordVisible.value = true
}

async function resetAdminPassword() {
  try {
    await api(`/admin/users/${resetPasswordForm.userId}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ password: resetPasswordForm.password.trim() }),
    })
    resetPasswordVisible.value = false
    ElMessage.success('密码已重置')
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

async function viewAdminUserItems(user: AdminUser) {
  selectedAdminUser.value = user
  selectedAdminUserItems.value = []
  userItemsVisible.value = true
  try {
    const data = await api<{ items: AdminUserItem[] }>(`/admin/users/${user.id}/items`)
    selectedAdminUserItems.value = data.items || []
  } catch (error) {
    ElMessage.error(`综测项目加载失败：${(error as Error).message}`)
  }
}

async function deleteAdminUserItem(item: AdminUserItem) {
  if (!selectedAdminUser.value) return
  if (!window.confirm(`确定删除「${item.title}」吗？此操作会同步影响学生端。`)) return
  try {
    await api(`/admin/users/${selectedAdminUser.value.id}/items/${item.id}`, { method: 'DELETE' })
    ElMessage.success('项目已删除')
    await viewAdminUserItems(selectedAdminUser.value)
    await loadAdminUsers()
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

async function loadAll() {
  loading.value = true
  const year = currentAcademicYear.value
  try {
    const [summaryData, opps, basketData, appData, honorData, templateData, docsData, yearData] = await Promise.all([
      api<DashboardSummary>(`/dashboard/summary?user_id=${store.studentId}&academic_year=${year}`),
      api<Opportunity[]>(`/opportunities?user_id=${store.studentId}`),
      api<BasketItem[]>(`/plan-basket?user_id=${store.studentId}`),
      api<{ submissions: any[] }>(`/submissions?academic_year=${year}`),
      api<HonorItem[]>(`/honor-wall?user_id=${store.studentId}`),
      api<TemplateData>('/material-templates'),
      api<RuleDocument[]>('/rule-documents'),
      api<{ years: string[]; current: string }>('/academic-years'),
    ])
    summary.value = summaryData
    basket.value = mergeBasketRows(basketData)
    opportunities.value = markOpportunitiesInBasket(opps, basket.value)
    applications.value = (appData.submissions || []).map(mapSubmissionToApplication)
    honors.value = honorData
    templates.value = templateData
    ruleDocs.value = docsData
    if (yearData?.years?.length) availableAcademicYears.value = yearData.years
    // 首次加载才用服务端学年覆盖默认值，后续保持用户选择
    if (!summary.value && yearData?.current) {
      currentAcademicYear.value = yearData.current
    }
    if (canViewAdmin.value) {
      adminApplications.value = []
      const [statsData, adminAppData] = await Promise.all([
        api<any>('/admin/stats'),
        api<{ submissions: any[] }>('/admin/submissions?per_page=200'),
      ])
      adminStats.value = {
        opportunity_count: statsData.opportunity_count ?? 0,
        application_count: statsData.application_count ?? statsData.total_submissions ?? 0,
        pending_count: statsData.pending_count ?? statsData.pending_reviews ?? 0,
        approved_score: statsData.approved_score ?? 0,
      }
      adminApplications.value = orderAuditRows((adminAppData.submissions || []).map(mapSubmissionToApplication))
      await loadAdminUsers()
    } else {
      adminStats.value = null
      adminApplications.value = []
      adminUsers.value = []
    }
    await loadCatalogExplorer()
    await nextTick()
    renderCharts()
  } catch (error) {
    ElMessage.error(`数据加载失败：${(error as Error).message}`)
  } finally {
    loading.value = false
  }
}

async function clearExistingBasketOnce() {
  const clearKey = `zongce-basket-cleared-after-catalog-fix-v2-${store.studentId}`
  if (localStorage.getItem(clearKey) === '1') return
  try {
    const existing = await api<BasketItem[]>(`/plan-basket?user_id=${store.studentId}`)
    await Promise.all(existing.map(item => api(`/plan-basket/${item.id}`, { method: 'DELETE' })))
    saveLocalCatalogBasket([])
    localStorage.setItem(clearKey, '1')
  } catch (error) {
    saveLocalCatalogBasket([])
    localStorage.setItem(clearKey, '1')
    ElMessage.error(`清空旧备赛清单失败：${(error as Error).message}`)
  }
}

function renderCharts() {
  if (!summary.value || !radarRef.value || !barRef.value) return
  const details = summary.value.score.details
  const donut = echarts.getInstanceByDom(radarRef.value) || echarts.init(radarRef.value)
  donut.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 分 ({d}%)' },
    legend: { bottom: 12, icon: 'circle', textStyle: { color: '#64748b' } },
    series: [{
      name: '加权贡献',
      type: 'pie',
      radius: ['46%', '68%'],
      center: ['50%', '48%'],
      minAngle: 18,
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#fff', borderWidth: 4 },
      label: {
        formatter: '{b}\n{c} 分',
        color: '#475569',
        fontSize: 13,
        fontWeight: 600,
      },
      labelLine: { length: 20, length2: 14 },
      data: details.map((item, index) => ({
        name: item.label,
        value: Number(item.weighted.toFixed(2)),
        itemStyle: { color: ['#6366f1', '#4ea2df', '#f2ad36'][index] },
      })),
    }],
  })
  const distribution = categoryScoreDistribution.value
  const maxDistribution = Math.max(...distribution.map(item => item.value), 0)
  const yAxisMax = Math.max(10, Math.ceil((maxDistribution + 2) / 5) * 5)
  const bar = echarts.getInstanceByDom(barRef.value) || echarts.init(barRef.value)
  bar.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 54, right: 28, top: 44, bottom: 72 },
    xAxis: {
      type: 'category',
      data: distribution.map(item => item.name),
      axisLabel: { color: '#6b7280', interval: 0, rotate: 18, fontSize: 12 },
      axisLine: { lineStyle: { color: '#9ca3af' } },
    },
    yAxis: {
      type: 'value',
      name: '分数',
      max: yAxisMax,
      nameTextStyle: { color: '#6b7280', align: 'left' },
      axisLabel: { color: '#6b7280' },
      splitLine: { lineStyle: { color: '#e5e7eb' } },
    },
    series: [{
      name: '加分',
      type: 'bar',
      barWidth: 54,
      data: distribution.map(item => item.value),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#6658f0' },
          { offset: 1, color: '#aeb7ff' },
        ]),
        borderRadius: [7, 7, 0, 0],
      },
    }],
  })
}

watch(() => summary.value, () => nextTick(renderCharts))
watch(activeStudentTab, tab => { if (tab === '星盘总览') { nextTick(renderCharts) } })

async function saveGpa() {
  const raw = gpaEditValue.value
  const val = (typeof raw === 'string' ? raw : String(raw ?? '')).trim()
  if (!val || isNaN(Number(val)) || Number(val) < 0 || Number(val) > 100) {
    ElMessage.warning('请输入 0-100 的有效分数')
    return
  }
  gpaSaving.value = true
  try {
    await api('/profile', { method: 'PUT', body: JSON.stringify({ gpa_score: Number(val) }) })
    ElMessage.success('均分已保存')
    await loadAll()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    gpaSaving.value = false
  }
}

// ---- 学年切换（watch v-model 驱动） ----
watch(currentAcademicYear, (newYear, oldYear) => {
  if (newYear !== oldYear && oldYear !== undefined) loadAll()
})

function generateAcademicYears(): string[] {
  const now = new Date()
  const cy = now.getFullYear()
  const cm = now.getMonth() + 1
  const startYear = cm >= 9 ? cy : cy - 1
  const years: string[] = []
  for (let i = 0; i < 4; i++) {
    const y = startYear - i
    years.push(`${y}-${y + 1}`)
  }
  return years
}

// ---- 学业成绩录入弹窗 ----
async function openGradeModal() {
  gradeModalYear.value = currentAcademicYear.value
  gradeModalUploadFiles.value = []
  gradeModalServerFiles.value = []
  gradeModalOcrLoading.value = false
  gradeModalOcrResults.value = []
  gradeModalOcrDone.value = false
  gradeModalSaving.value = false
  gradeModalSaved.value = false
  gradeModalError.value = ''
  gradeComputation.value = null

  try {
    const data = await api<{
      courses: Array<{ id: number; course_name: string; grade: number; credits: number; course_type: string; ocr_source: boolean }>
      weighted_average: number | null; academic_base_score: number | null
      gpa_bonus: number; gpa_tier: string
      required_courses_avg: number | null; required_min_grade: number | null
      all_required_pass: boolean
    }>(`/course-grades?academic_year=${currentAcademicYear.value}`)
    gradeModalCourses.value = (data.courses || []).map(c => ({
      key: crypto.randomUUID(),
      id: c.id,
      course_name: c.course_name,
      grade: c.grade,
      credits: c.credits,
      course_type: c.course_type,
      ocr_source: c.ocr_source || false,
    }))
    if (data.weighted_average !== null) {
      gradeComputation.value = {
        weighted_average: data.weighted_average,
        academic_base_score: data.academic_base_score!,
        gpa_bonus: data.gpa_bonus,
        gpa_tier: data.gpa_tier,
        required_courses_avg: data.required_courses_avg,
        required_min_grade: data.required_min_grade,
        all_required_pass: data.all_required_pass,
      }
    }
  } catch {
    gradeModalCourses.value = []
  }
  showGradeModal.value = true
}

function addGradeCourse() {
  gradeModalCourses.value.push({
    key: crypto.randomUUID(),
    course_name: '',
    grade: null,
    credits: null,
    course_type: '必修',
    ocr_source: false,
  })
}

function removeGradeCourse(key: string) {
  gradeModalCourses.value = gradeModalCourses.value.filter(c => c.key !== key)
  updateGradeComputation()
}

function updateGradeComputation() {
  const courses = gradeModalCourses.value
  const valid = courses.filter(c => c.grade !== null && c.credits !== null && c.grade > 0 && c.credits > 0)
  if (valid.length === 0 || courses.some(c => c.grade === null || c.credits === null || !c.course_name)) {
    gradeComputation.value = null
    return
  }

  const totalWeighted = valid.reduce((sum, c) => sum + c.grade! * c.credits!, 0)
  const totalCredits = valid.reduce((sum, c) => sum + c.credits!, 0)
  const weightedAvg = Math.round((totalWeighted / totalCredits) * 100) / 100
  const academicBase = Math.min(80, Math.round(weightedAvg * 0.8 * 100) / 100)

  const required = valid.filter(c => c.course_type === '必修' || c.course_type === '限选')
  let reqAvg: number | null = null, reqMin: number | null = null, allPass = false
  if (required.length) {
    const rw = required.reduce((sum, c) => sum + c.grade! * c.credits!, 0)
    const rc = required.reduce((sum, c) => sum + c.credits!, 0)
    reqAvg = Math.round((rw / rc) * 100) / 100
    reqMin = Math.round(Math.min(...required.map(c => c.grade!)) * 10) / 10
    allPass = required.every(c => c.grade! >= 70)
  }

  let bonus = 0, tier = ''
  if (required.length && reqAvg !== null) {
    if (reqAvg >= 85 && required.every(c => c.grade! >= 75)) { bonus = 5; tier = '均分≥85且单科≥75' }
    else if (reqAvg >= 80 && required.every(c => c.grade! >= 70)) { bonus = 3; tier = '均分≥80且单科≥70' }
    else if (reqAvg >= 75 && required.every(c => c.grade! >= 70)) { bonus = 2; tier = '均分≥75且单科≥70' }
  }

  gradeComputation.value = {
    weighted_average: weightedAvg,
    academic_base_score: academicBase,
    gpa_bonus: bonus,
    gpa_tier: tier,
    required_courses_avg: reqAvg,
    required_min_grade: reqMin,
    all_required_pass: allPass,
  }
}

function handleGradeModalFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  const files = Array.from(input.files).filter(f => {
    const ext = f.name.split('.').pop()?.toLowerCase() || ''
    return ['jpg', 'jpeg', 'png', 'bmp', 'webp'].includes(ext)
  })
  if (!files.length) { ElMessage.warning('仅支持 JPG、PNG 等图片格式'); return }
  gradeModalUploadFiles.value = [...gradeModalUploadFiles.value, ...files]
  input.value = ''
}

function removeGradeModalFile(idx: number) {
  gradeModalUploadFiles.value.splice(idx, 1)
}

async function gradeModalOcrAnalyze() {
  if (!gradeModalUploadFiles.value.length) { ElMessage.warning('请先上传成绩单图片'); return }
  gradeModalOcrLoading.value = true
  gradeModalError.value = ''
  try {
    const serverFiles: any[] = []
    for (const file of gradeModalUploadFiles.value) {
      const uploaded = await uploadSingleFile(file, 'grade_report')
      if (uploaded.id) serverFiles.push(uploaded)
    }
    gradeModalServerFiles.value = serverFiles

    const result = await postJson<{
      results: Array<{ file_name: string; courses: Array<{
        course_name: string; grade: number; credits: number
        course_type: string; confidence: number
      }> }>
    }>('/course-grades/ocr', { uploaded_file_ids: serverFiles.map(f => f.id!) })

    const allCourses: GradeOcrCourse[] = []
    for (const r of result.results || []) {
      for (const c of r.courses || []) {
        allCourses.push({ ...c, selected: true })
      }
    }
    gradeModalOcrResults.value = allCourses
    gradeModalOcrDone.value = true
    if (allCourses.length) {
      ElMessage.success(`OCR识别到 ${allCourses.length} 门课程，请勾选确认后加入列表`)
    } else {
      ElMessage.warning('未能从图片中识别出课程信息，请尝试手动添加')
    }
  } catch (error) {
    ElMessage.error(`OCR失败：${(error as Error).message}`)
  } finally {
    gradeModalOcrLoading.value = false
  }
}

function addOcrCoursesToList() {
  const selected = gradeModalOcrResults.value.filter(c => c.selected)
  if (!selected.length) { ElMessage.warning('请先勾选要添加的课程'); return }
  for (const course of selected) {
    gradeModalCourses.value.push({
      key: crypto.randomUUID(),
      course_name: course.course_name,
      grade: course.grade,
      credits: course.credits,
      course_type: course.course_type,
      ocr_source: true,
    })
  }
  gradeModalOcrResults.value = []
  gradeModalOcrDone.value = false
  updateGradeComputation()
  ElMessage.success(`已添加 ${selected.length} 门课程`)
}

async function saveGradeCourses() {
  const courses = gradeModalCourses.value
  if (!courses.length) { gradeModalError.value = '请至少添加一门课程'; return }
  const hasEmpty = courses.some(c => !c.course_name.trim() || c.grade === null || c.credits === null)
  if (hasEmpty) { gradeModalError.value = '请填写完整的课程信息（名称、成绩、学分）'; return }
  const badGrade = courses.some(c => c.grade! < 0 || c.grade! > 100)
  if (badGrade) { gradeModalError.value = '成绩必须在 0-100 之间'; return }
  const badCredit = courses.some(c => c.credits! <= 0 || c.credits! > 15)
  if (badCredit) { gradeModalError.value = '学分必须在 0.5-15 之间'; return }

  gradeModalSaving.value = true
  gradeModalError.value = ''
  try {
    const result = await postJson<{ success: boolean; course_count: number; weighted_average: number | null; gpa_bonus: number }>(
      '/course-grades',
      {
        academic_year: gradeModalYear.value,
        courses: courses.map(c => ({
          course_name: c.course_name.trim(),
          grade: c.grade,
          credits: c.credits,
          course_type: c.course_type,
          ocr_source: c.ocr_source,
        })),
      }
    )
    gradeModalSaved.value = true
    ElMessage.success(`已保存 ${result.course_count} 门课程成绩，GPA加分 ${result.gpa_bonus > 0 ? '+' + result.gpa_bonus : '0'}`)
    // 立即刷新仪表盘
    await loadAll()
  } catch (error) {
    gradeModalError.value = (error as Error).message || '保存失败'
    ElMessage.error(`保存失败：${(error as Error).message}`)
  } finally {
    gradeModalSaving.value = false
  }
}

function closeGradeModal() {
  showGradeModal.value = false
  setTimeout(() => {
    gradeModalCourses.value = []
    gradeModalUploadFiles.value = []
    gradeModalServerFiles.value = []
    gradeModalOcrResults.value = []
    gradeModalOcrDone.value = false
    gradeModalSaved.value = false
    gradeModalError.value = ''
    gradeComputation.value = null
  }, 300)
}

async function addToBasket(opportunity: Opportunity) {
  const row = await postJson<BasketItem>('/plan-basket', {
    user_id: store.studentId,
    opportunity_id: opportunity.id,
    stage: '想参加',
  })
  opportunity.in_basket = true
  basket.value = mergeBasketRows([row, ...basket.value])
  ElMessage.success('已加入备赛清单')
  await loadAll()
}

async function updateBasket(item: BasketItem) {
  if (String(item.id).startsWith('local-')) {
    const localRows = loadLocalCatalogBasket().map(row => basketIdentity(row) === basketIdentity(item) ? item : row)
    saveLocalCatalogBasket(localRows)
    ElMessage.success('备赛状态已更新')
    return
  }
  await patchJson(`/plan-basket/${item.id}`, { stage: item.stage, note: item.note })
  ElMessage.success('备赛状态已更新')
  await loadAll()
}

async function removeBasket(item: BasketItem) {
  saveLocalCatalogBasket(loadLocalCatalogBasket().filter(row => basketIdentity(row) !== basketIdentity(item)))
  if (!String(item.id).startsWith('local-')) {
    await api(`/plan-basket/${item.id}`, { method: 'DELETE' })
  }
  ElMessage.success('已移出备赛清单')
  await loadAll()
}

function chooseForCert(opportunity: Opportunity) {
  materialSubmitMode.value = 'targeted'
  targetCatalogQuery.keyword = opportunity.title
  activeStudentTab.value = '智审中心'
}

function cleanFileTitle(name: string) {
  return name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim().slice(0, 48)
}

// ===== 星轨探索提交认证弹窗 =====

function openSubmitModal(item: CatalogExplorerItem) {
  submitModalItem.value = item
  submitForm.title = item.title
  submitForm.dimension = item.category === 'sports' ? 'arts_sports' : (item.category === 'moral' || item.category === 'academic' ? item.category : 'academic')
  submitForm.award_level = item.level || ''
  submitForm.completion_date = ''
  submitForm.score_estimate = item.score || 0
  submitModalFiles.value = []
  submitModalServerFiles.value = []
  submitModalAnalyzing.value = false
  submitModalAnalyzed.value = false
  submitModalAnalysisResult.value = null
  submitModalConfidence.value = 0
  submitModalSubmitting.value = false
  submitModalSubmitted.value = false

  showSubmitModal.value = true
}

function handleSubmitModalFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || []).filter(f => {
    const ext = f.name.split('.').pop()?.toLowerCase() || ''
    return ['jpg','jpeg','png','bmp','webp','gif','pdf','doc','docx'].includes(ext)
  })
  if (!files.length) { input.value = ''; return }
  const existing = submitModalFiles.value
  const newFiles = files.filter(f => !existing.some(e => e.name === f.name && e.size === f.size))
  if (newFiles.length) submitModalFiles.value = [...existing, ...newFiles]
  input.value = ''
}

function removeSubmitModalFile(index: number) {
  submitModalFiles.value.splice(index, 1)
}

async function submitModalAnalyze() {
  if (!submitModalFiles.value.length) { ElMessage.warning('请先选择证明材料'); return }
  submitModalAnalyzing.value = true
  try {
    // Upload files
    const serverFiles: UploadedFile[] = []
    for (const file of submitModalFiles.value) {
      const uploaded = await uploadSingleFile(file, 'general')
      serverFiles.push(uploaded)
    }
    submitModalServerFiles.value = serverFiles

    // AI analyze
    const item = submitModalItem.value!
    const keyword = `${item.title} ${item.category} ${item.level}`.trim()
    const analysis = await api<{ results: AnalyzeResult[] }>('/analyze', {
      method: 'POST',
      body: JSON.stringify({
        uploaded_file_ids: serverFiles.map(f => f.id).filter(Boolean),
        keyword,
      }),
    })
    const rawResults = (analysis as any).results || []
    rawResults.forEach((r: AnalyzeResult) => { r.matches.forEach((m: any) => fallbackAuditFromText(r, m)) })
    const merged = mergePackageAnalysisResults(rawResults)
    const best = merged[0] || null
    submitModalAnalysisResult.value = best
    submitModalAnalyzed.value = true

    const bestMatch = best?.matches?.[0]
    submitModalConfidence.value = bestMatch?.confidence || 0
    ElMessage.success(`AI分析完成，置信率 ${Math.round(submitModalConfidence.value)}%`)
  } catch (error) {
    ElMessage.error(`AI分析失败：${(error as Error).message}`)
  } finally {
    submitModalAnalyzing.value = false
  }
}

async function submitModalSubmit() {
  const uploadedIds = submitModalServerFiles.value.map(f => f.id).filter(Boolean) as number[]
  if (!uploadedIds.length) { ElMessage.warning('请先上传证明材料'); return }
  submitModalSubmitting.value = true
  try {
    const bestMatch = submitModalAnalysisResult.value?.matches?.[0]
    const item = submitModalItem.value!
    const response = await postJson<{ status: string; submission_id?: number; proofs_complete?: boolean }>('/submissions', {
      catalog_item_id: bestMatch?.id || item.id,
      uploaded_file_ids: uploadedIds,
      completion_date: submitForm.completion_date || undefined,
      ai_confidence: submitModalConfidence.value,
      ai_decision: submitModalConfidence.value >= 80 ? 'high' : (submitModalConfidence.value >= 60 ? 'medium' : 'low'),
      ai_reason: bestMatch?.reason || '',
      ai_audit: bestMatch?.audit || {},
    })
    submitModalSubmitted.value = true
    ElMessage.success('已提交审核，等待管理端终审')
    await loadAll()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    submitModalSubmitting.value = false
  }
}

function closeSubmitModal() {
  showSubmitModal.value = false
  setTimeout(() => {
    submitModalItem.value = null
    submitModalFiles.value = []
    submitModalServerFiles.value = []
    submitModalAnalyzed.value = false
    submitModalAnalysisResult.value = null
    submitModalConfidence.value = 0
    submitModalSubmitted.value = false
  
  }, 300)
}

async function uploadSingleFile(file: File, proofType = 'general') {
  const form = new FormData()
  form.append('files', file)
  form.append('proof_type', proofType)
  const result = await api<{
    files?: Array<{ id: number; original_filename?: string; filename?: string; view_url?: string; file_path?: string; file_type?: string }>
    filename?: string
    url?: string
  }>('/upload', { method: 'POST', body: form })
  const uploaded = result.files?.[0]
  if (uploaded) {
    return {
      id: uploaded.id,
      filename: uploaded.original_filename || uploaded.filename || file.name,
      url: uploaded.view_url || (uploaded.file_path ? `/api/uploads/${uploaded.file_path}` : ''),
      type: uploaded.file_type || file.type || file.name.split('.').pop(),
      proofType,
    }
  }
  return { filename: result.filename || file.name, url: result.url || '', type: file.type, proofType }
}

async function uploadPublishImageFile(file: File, target: 'cover' | 'qr') {
  const form = new FormData()
  form.append('files', file)
  const result = await api<{ files?: Array<{ original_filename?: string; view_url?: string; file_path?: string }>; filename?: string; url?: string }>('/upload', { method: 'POST', body: form })
  const uploaded = result.files?.[0]
  const item = {
    name: uploaded?.original_filename || result.filename || file.name,
    url: uploaded?.view_url || (uploaded?.file_path ? `/api/uploads/${uploaded.file_path}` : result.url || ''),
    localUrl: URL.createObjectURL(file),
  }
  if (target === 'cover') {
    publishImages.value.push(item)
  } else {
    if (publishQr.value?.localUrl) URL.revokeObjectURL(publishQr.value.localUrl)
    publishQr.value = item
    publishForm.group_qr_url = item.url
  }
}

async function handlePublishImageSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  for (const file of files) {
    if (!file.type.startsWith('image/')) {
      ElMessage.warning('活动图片只支持图片文件')
      continue
    }
    await uploadPublishImageFile(file, 'cover')
  }
  input.value = ''
}

async function handlePublishQrSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    if (!file.type.startsWith('image/')) {
      ElMessage.warning('群二维码只支持图片文件')
    } else {
      await uploadPublishImageFile(file, 'qr')
    }
  }
  input.value = ''
}

function removePublishImage(index: number) {
  const item = publishImages.value[index]
  if (item?.localUrl) URL.revokeObjectURL(item.localUrl)
  publishImages.value.splice(index, 1)
}

function removePublishQr() {
  if (publishQr.value?.localUrl) URL.revokeObjectURL(publishQr.value.localUrl)
  publishQr.value = null
  publishForm.group_qr_url = ''
}

function onPublishDragOver(event: DragEvent) {
  event.preventDefault()
  publishDragOver.value = true
}

function onPublishDragLeave() {
  publishDragOver.value = false
}

async function onPublishDrop(event: DragEvent) {
  event.preventDefault()
  publishDragOver.value = false
  const files = Array.from(event.dataTransfer?.files || []).filter(file => file.type.startsWith('image/'))
  for (const file of files) {
    await uploadPublishImageFile(file, 'cover')
  }
}

async function uploadRuleDocument(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const form = new FormData()
  form.append('file', file)
  form.append('version', ruleUpload.version)
  form.append('notes', ruleUpload.notes)
  await api('/rule-documents/upload', { method: 'POST', body: form })
  input.value = ''
  ruleUpload.notes = ''
  ElMessage.success('已上传并设为当前综测细则')
  await loadAll()
}

async function activateRuleDocument(doc: RuleDocument) {
  await postJson(`/rule-documents/${doc.id}/activate`, {})
  ElMessage.success('已切换当前综测细则')
  await loadAll()
}

async function createHonor() {
  if (!honorForm.title.trim()) {
    ElMessage.warning('请填写荣誉标题')
    return
  }
  if (honorSelectedFiles.value.length) {
    await addHonorFiles(honorSelectedFiles.value)
    return
  }
  await postJson('/honor-wall', { user_id: store.studentId, ...honorForm })
  honorForm.title = ''
  honorForm.image_url = ''
  await loadAll()
}

async function addHonorFiles(files: File[]) {
  const images = files.filter(file => file.type.startsWith('image/'))
  if (!images.length) return
  for (const [index, file] of images.entries()) {
    const result = await uploadSingleFile(file)
    await postJson('/honor-wall', {
      user_id: store.studentId,
      title: images.length === 1 ? honorForm.title.trim() || cleanFileTitle(file.name) : `${honorForm.title.trim() || cleanFileTitle(file.name)} ${index + 1}`,
      category: honorForm.category,
      image_url: result.url,
      visibility: 'private',
    })
  }
  honorForm.title = ''
  honorForm.image_url = ''
  ElMessage.success(`已加入 ${images.length} 张荣誉图片`)
  await loadAll()
}

async function handleHonorFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || []).filter(file => file.type.startsWith('image/'))
  if (!files.length) {
    ElMessage.warning('荣誉星墙只支持图片文件')
  } else {
    honorSelectedFiles.value = files
  }
  input.value = ''
}

async function onHonorPageDrop(event: DragEvent) {
  event.preventDefault()
  honorDropOver.value = false
  const files = Array.from(event.dataTransfer?.files || []).filter(file => file.type.startsWith('image/'))
  if (!files.length) return
  honorSelectedFiles.value = files
}

function removeSelectedHonorFile(index: number) {
  honorSelectedFiles.value.splice(index, 1)
}

function openHonorEditor(item: HonorItem) {
  Object.assign(honorEditForm, {
    id: item.id,
    title: item.title,
    category: item.category,
    image_url: item.image_url,
    visibility: item.visibility,
  })
  honorEditorVisible.value = true
}

async function saveHonorEdit() {
  if (!honorEditForm.id) return
  await patchJson(`/honor-wall/${honorEditForm.id}`, {
    user_id: store.studentId,
    title: honorEditForm.title,
    category: honorEditForm.category,
    image_url: honorEditForm.image_url,
    visibility: honorEditForm.visibility,
  })
  honorEditorVisible.value = false
  ElMessage.success('荣誉信息已更新')
  await loadAll()
}

async function deleteHonor() {
  if (!honorEditForm.id) return
  await api(`/honor-wall/${honorEditForm.id}`, {
    method: 'DELETE',
    body: JSON.stringify({ user_id: store.studentId }),
  })
  honorEditorVisible.value = false
  ElMessage.success('已移除荣誉展示')
  await loadAll()
}

async function replaceHonorImage(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const result = await uploadSingleFile(file)
  honorEditForm.image_url = result.url
  input.value = ''
}

async function dropHonor(target: HonorItem) {
  if (!draggedHonorId.value || draggedHonorId.value === target.id) return
  const from = honors.value.find(item => item.id === draggedHonorId.value)
  if (!from) return
  const fromOrder = from.sort_order
  await Promise.all([
    patchJson(`/honor-wall/${from.id}`, { user_id: store.studentId, sort_order: target.sort_order }),
    patchJson(`/honor-wall/${target.id}`, { user_id: store.studentId, sort_order: fromOrder }),
  ])
  draggedHonorId.value = null
  await loadAll()
}

function selectDashboardApplication(item: ApplicationItem) {
  selectedDashboardApplication.value = item
}

function handlePublishScanFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || []).filter(f => {
    const ext = f.name.split('.').pop()?.toLowerCase() || ''
    return ['jpg','jpeg','png','bmp','webp','gif','pdf','doc','docx'].includes(ext)
  })
  if (!files.length) { input.value = ''; return }
  const existing = publishScanFiles.value
  const added = files.filter(f => !existing.some(e => e.name === f.name && e.size === f.size))
  if (added.length) publishScanFiles.value = [...existing, ...added]
  input.value = ''
}

function removePublishScanFile(index: number) {
  publishScanFiles.value.splice(index, 1)
}

async function publishAiScan() {
  if (!publishScanFiles.value.length) { ElMessage.warning('请先选择需要扫描的文件'); return }
  publishScanUploading.value = true
  publishScanStatus.value = '⏳ 上传文件中...'
  try {
    // Upload
    const form = new FormData()
    publishScanFiles.value.forEach(f => form.append('files', f))
    const uploadResult = await api<{ files: Array<{ id: number; original_filename: string }> }>('/upload', { method: 'POST', body: form })
    const fileIds = ((uploadResult as any).files || []).map((f: any) => f.id).filter(Boolean)
    if (!fileIds.length) { ElMessage.error('文件上传失败'); return }

    // AI analyze
    publishScanStatus.value = '🔍 AI正在扫描识别文字...'
    const analysis = await api<{ results: Array<{ extracted_text: string; extracted_text_full?: string; filename: string }> }>('/analyze', {
      method: 'POST',
      body: JSON.stringify({ uploaded_file_ids: fileIds, keyword: '' }),
    })
    const results = (analysis as any).results || []
    const allText = results.map((r: any) => r.extracted_text_full || r.extracted_text || '').filter(Boolean).join('\n\n')
    if (!allText.trim()) { ElMessage.warning('未能从文件中提取到有效文字'); return }

    // Fill form
    const titleGuess = allText.split(/[\n\r]+/).find((l: string) => l.length > 6 && l.length < 100) || publishScanFiles.value[0]?.name?.replace(/\.[^.]+$/, '') || ''
    publishForm.title = titleGuess.slice(0, 160)
    publishForm.description = allText.slice(0, 2000)

    // Date detection
    const dm = allText.match(/(20\d{2}[年\-\/\.]\d{1,2}[月\-\/\.]\d{1,2}[日号])/)
    if (dm) publishForm.deadline = dm[1]

    // Location detection
    const lm = allText.match(/(?:地点|地址|教室|报告厅|线上)[：:]\s*([^\n]{3,40})/)
    if (lm) publishForm.location = lm[1]

    aiParsed.value = { title: publishForm.title, description: publishForm.description, autoFilled: true }
    publishScanStatus.value = `✅ 已扫描 ${results.length} 个文件并填充，请核对 `
    publishScanFiles.value = []
    ElMessage.success('AI扫描完成，请核对表单信息')
  } catch (error) {
    ElMessage.error(`AI扫描失败：${(error as Error).message}`)
  } finally {
    publishScanUploading.value = false
  }
}

async function runAiParse() {
  const rawText = [aiNoticeText.value, aiGroupMessage.value].map(item => item.trim()).filter(Boolean).join('\n\n')
  if (!rawText) {
    ElMessage.warning('请粘贴通知内容')
    return
  }
  aiParsing.value = true
  try {
    const parsed = await postJson<Record<string, any>>('/ai/parse-opportunity', { raw_text: rawText })
    aiParsed.value = parsed
    Object.assign(publishForm, {
      title: parsed.title || publishForm.title,
      category: parsed.category || publishForm.category,
      dimension: parsed.dimension || publishForm.dimension,
      location: parsed.location || publishForm.location,
      deadline: parsed.deadline || publishForm.deadline,
      description: parsed.description || aiNoticeText.value,
    })
    aiExpanded.value = false
    ElMessage.success('解析完成，请核对信息')
  } finally {
    aiParsing.value = false
  }
}

function savePublishDraft() {
  localStorage.setItem('zongce-publish-draft', JSON.stringify({
    form: publishForm,
    aiNoticeText: aiNoticeText.value,
    aiGroupMessage: aiGroupMessage.value,
  }))
  ElMessage.success('已存为草稿')
}

async function publishOpportunity() {
  if (!publishForm.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  await postJson('/opportunities', {
    ...publishForm,
    requirements: publishForm.requirementsText.split('\n').map(item => item.trim()).filter(Boolean),
    tags: publishForm.tagsText.split('\n').map(item => item.trim()).filter(Boolean),
    attachments: [],
    images: publishImages.value.map(item => item.url),
    group_qr_url: publishQr.value?.url || publishForm.group_qr_url,
    roi_score: 3.8,
  })
  ElMessage.success('已发布到机会大厅')
  Object.assign(publishForm, {
    title: '',
    location: '',
    start_time: '',
    deadline: '',
    season_months: '',
    credit_hint: '',
    rule_ref: '',
    official_url: '',
    registration_url: '',
    contact_email: '',
    article_url: '',
    group_qr_url: '',
    description: '',
  })
  aiNoticeText.value = ''
  aiGroupMessage.value = ''
  aiParsed.value = null
  publishImages.value.forEach(item => URL.revokeObjectURL(item.localUrl))
  publishImages.value = []
  removePublishQr()
  await loadAll()
}

function materialFileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() || ''
  if (ext === 'pdf') return 'PDF'
  if (['doc', 'docx'].includes(ext)) return 'Word'
  return 'Image'
}

function addMaterialSelectedFiles(files: File[]) {
  const validFiles = files.filter(file => {
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    return ['jpg', 'jpeg', 'png', 'bmp', 'webp', 'gif', 'pdf', 'doc', 'docx'].includes(ext)
  })
  const existingKeys = new Set(materialSelectedFiles.value.map(file => `${file.name}-${file.size}-${file.lastModified}`))
  const appendFiles = validFiles.filter(file => !existingKeys.has(`${file.name}-${file.size}-${file.lastModified}`))
  if (!appendFiles.length) {
    if (files.length) ElMessage.info('选择的文件已在当前申报包中')
    return
  }
  materialSelectedFiles.value = [...materialSelectedFiles.value, ...appendFiles]
  materialAnalysisResults.value = []
  materialServerFiles.value = []
  materialSupplementFiles.value = {}
}

function handleMaterialSubmitFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  addMaterialSelectedFiles(Array.from(input.files || []))
  input.value = ''
}

function onMaterialSubmitDrop(event: DragEvent) {
  event.preventDefault()
  addMaterialSelectedFiles(Array.from(event.dataTransfer?.files || []))
}

function removeMaterialSelectedFile(index: number) {
  materialSelectedFiles.value.splice(index, 1)
}

function matchConfidenceClass(value: number) {
  if (value >= 95) return 'conf-high'
  if (value >= 60) return 'conf-medium'
  return 'conf-low'
}

function auditLightLabel(match: AnalyzeMatch) {
  const missingCount = match.audit?.missing_fields?.length || 0
  if (match.confidence >= 95 && missingCount === 0) return '绿灯高置信'
  if (match.confidence >= 60) return missingCount ? '需补充佐证' : '黄灯待复核'
  return '红灯高风险'
}

function auditLightClass(match: AnalyzeMatch) {
  if (match.confidence >= 95 && !(match.audit?.missing_fields?.length)) return 'audit-light-green'
  if (match.confidence >= 60) return 'audit-light-amber'
  return 'audit-light-red'
}

function auditFeatureValue(match: AnalyzeMatch, key: string, fallback = '未识别') {
  const value = match.audit?.extracted_features?.[key]
  if (typeof value === 'boolean') return value ? '是' : '否'
  return value || fallback
}

function ensureAudit(match: AnalyzeMatch) {
  if (!match.audit) match.audit = {}
  if (!match.audit.extracted_features) match.audit.extracted_features = {}
  if (!match.audit.missing_fields) match.audit.missing_fields = []
  if (!match.audit.risk_assessment) match.audit.risk_assessment = { risk_tags: [] }
  if (!match.audit.audit_chain) match.audit.audit_chain = []
  return match.audit
}

const manualAuditRepairs: Record<string, { missing: string[], risks: string[] }> = {
  detected_name: { missing: ['identity_match_proof'], risks: ['IDENTITY_UNCLEAR', 'NAME_MISMATCH'] },
  event_name: { missing: ['event_name', 'event_name_proof'], risks: ['EVENT_UNCLEAR'] },
  award_level: { missing: ['award_level_proof'], risks: ['AWARD_LEVEL_UNCLEAR'] },
  date: { missing: ['date_proof'], risks: ['DATE_UNCLEAR'] },
}

function recalculateManualAuditConfidence(match: AnalyzeMatch) {
  const audit = ensureAudit(match)
  const meta = audit as typeof audit & { manual_baseline_confidence?: number, manual_edited?: boolean }
  if (!Number.isFinite(meta.manual_baseline_confidence)) {
    meta.manual_baseline_confidence = Number.isFinite(match.confidence) ? match.confidence : (audit.confidence_score || 0)
  }

  const features = audit.extracted_features || {}
  let missingFields = audit.missing_fields || []
  let riskTags = audit.risk_assessment?.risk_tags || []
  const coreKeys = ['detected_name', 'event_name', 'award_level', 'date']
  const completedCore = coreKeys.filter(key => String(features[key] || '').trim()).length

  for (const key of coreKeys) {
    if (!String(features[key] || '').trim()) continue
    const repair = manualAuditRepairs[key]
    if (!repair) continue
    missingFields = missingFields.filter(field => !repair.missing.includes(field.field_key))
    riskTags = riskTags.filter(tag => !repair.risks.includes(tag))
  }

  audit.missing_fields = missingFields
  audit.risk_assessment!.risk_tags = Array.from(new Set(riskTags))

  const unresolvedCount = audit.missing_fields.length + audit.risk_assessment!.risk_tags.length
  const baseline = Math.max(0, Math.min(meta.manual_baseline_confidence || 0, 88))
  const evidenceCap = meta.manual_edited ? 90 : 95
  const completenessCap = completedCore >= 4
    ? evidenceCap
    : completedCore === 3
      ? 86
      : completedCore === 2
        ? 80
        : 72
  const nextConfidence = Math.max(
    5,
    Math.min(completenessCap, baseline + completedCore * 4 - unresolvedCount * 3),
  )

  match.confidence = Number(nextConfidence.toFixed(1))
  audit.confidence_score = match.confidence
  match.decision = match.confidence >= 95 && unresolvedCount === 0 ? 'high' : (match.confidence >= 60 ? 'medium' : 'low')
  audit.status = match.decision === 'high'
    ? 'HIGH_CONFIDENCE'
    : (match.confidence >= 60 ? (audit.missing_fields.length ? 'NEED_SUPPLEMENT' : 'PENDING_HUMAN') : 'HIGH_RISK')
  audit.audit_chain = [
    ...(audit.audit_chain || []).filter(step => !step.startsWith('学生补全字段后重算置信度')),
    `学生补全字段后重算置信度为 ${match.confidence.toFixed(1)}%。`,
  ]
}

function setAuditFeature(match: AnalyzeMatch, key: string, event: Event) {
  const input = event.target as HTMLInputElement
  const audit = ensureAudit(match)
  audit.extracted_features![key] = input.value.trim()
  ;(audit as typeof audit & { manual_edited?: boolean }).manual_edited = true
  recalculateManualAuditConfidence(match)
}

function fallbackAuditFromText(result: AnalyzeResult, match: AnalyzeMatch) {
  const audit = ensureAudit(match)
  const text = `${result.filename}\n${result.extracted_text || ''}`
  if (!audit.extracted_features!.detected_name) {
    const foundName = text.match(/姓名\s*([\u4e00-\u9fa5]{2,4})(?=\d|身份证|证件|Name|参加|$)/)
      || text.match(/姓\s*名\s*([\u4e00-\u9fa5]{2,4})(?=\d|身份证|证件|Name|参加|$)/)
    if (foundName?.[1]) audit.extracted_features!.detected_name = foundName[1]
  }
  if (!audit.extracted_features!.date) {
    const foundDate = text.match(/(202\d\s*(?:年|[-./]|\s)\s*(?:0?[1-9]|1[0-2])\s*月?)/)
    if (foundDate?.[1]) audit.extracted_features!.date = foundDate[1].replace(/\s+/g, ' ').trim()
  }
}

function auditRiskTags(match: AnalyzeMatch) {
  return match.audit?.risk_assessment?.risk_tags || []
}

function supplementKey(result: AnalyzeResult, match: AnalyzeMatch, fieldKey: string) {
  return `${result.file_id}-${match.id}-${fieldKey}`
}

async function handleSupplementSelect(event: Event, result: AnalyzeResult, match: AnalyzeMatch, fieldKey: string) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const key = supplementKey(result, match, fieldKey)
  try {
    const uploaded = await uploadSingleFile(file, fieldKey)
    materialSupplementFiles.value = {
      ...materialSupplementFiles.value,
      [key]: { id: uploaded.id, name: uploaded.filename, url: uploaded.url, type: uploaded.type, proofType: fieldKey },
    }
    const audit = ensureAudit(match)
    audit.missing_fields = (audit.missing_fields || []).filter(field => field.field_key !== fieldKey)
    if (fieldKey === 'identity_match_proof') {
      audit.risk_assessment!.risk_tags = (audit.risk_assessment!.risk_tags || []).filter(tag => tag !== 'IDENTITY_UNCLEAR')
    }
    audit.audit_chain!.push(`补充材料已加入申报包：${uploaded.filename}`)
    recalculateManualAuditConfidence(match)
    ElMessage.success('补充材料已加入本次申报包')
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    input.value = ''
  }
}

async function reanalyzeWithSupplements(result: AnalyzeResult, match: AnalyzeMatch) {
  const baseIds = materialServerFiles.value.map(file => file.id).filter(Boolean) as number[]
  const supplementIds = matchSupplementFiles(result, match).map(file => file.id).filter(Boolean) as number[]
  const uploadedFileIds = Array.from(new Set([...baseIds, ...supplementIds]))
  if (!uploadedFileIds.length) {
    ElMessage.warning('暂无可重新分析的材料')
    return
  }
  materialParsing.value = true
  try {
    const analysis = await api<{ results: AnalyzeResult[] }>('/analyze', {
      method: 'POST',
      body: JSON.stringify({
        uploaded_file_ids: uploadedFileIds,
        keyword: `${materialExtraKeyword.value} ${match.title}`.trim(),
      }),
    })
    const refreshed = (analysis.results || [])
      .flatMap(item => item.matches || [])
      .find(item => item.id === match.id)
    if (!refreshed) {
      ElMessage.warning('重新分析完成，但未找到同一综测项目匹配')
      return
    }
    match.confidence = refreshed.confidence
    match.decision = refreshed.decision
    match.reason = refreshed.reason
    match.audit = refreshed.audit || match.audit
    fallbackAuditFromText(result, match)
    ElMessage.success('已用补充材料刷新 AI 结构化结果')
  } catch (error) {
    ElMessage.error(`重新分析失败：${(error as Error).message}`)
  } finally {
    materialParsing.value = false
  }
}

function matchSupplementFiles(result: AnalyzeResult, match: AnalyzeMatch) {
  return (match.audit?.missing_fields || [])
    .map(field => materialSupplementFiles.value[supplementKey(result, match, field.field_key)])
    .filter(Boolean) as UploadedFile[]
}

function mergeAuditPayload(base: AuditPayload = {}, incoming: AuditPayload = {}) {
  const merged: AuditPayload = {
    ...base,
    extracted_features: { ...(base.extracted_features || {}) },
    risk_assessment: {
      ...(base.risk_assessment || {}),
      risk_tags: [...(base.risk_assessment?.risk_tags || [])],
    },
    missing_fields: [...(base.missing_fields || [])],
    audit_chain: [...(base.audit_chain || [])],
  }
  Object.entries(incoming.extracted_features || {}).forEach(([key, value]) => {
    if (value && !merged.extracted_features?.[key]) merged.extracted_features![key] = value
  })
  const tags = new Set([...(merged.risk_assessment?.risk_tags || []), ...(incoming.risk_assessment?.risk_tags || [])])
  merged.risk_assessment!.risk_tags = [...tags]
  const missingMap = new Map((merged.missing_fields || []).map(field => [field.field_key, field]))
  ;(incoming.missing_fields || []).forEach(field => {
    if (!missingMap.has(field.field_key)) missingMap.set(field.field_key, field)
  })
  const features = merged.extracted_features || {}
  if (features.detected_name) missingMap.delete('identity_match_proof')
  if (features.date) missingMap.delete('date')
  if (features.event_name) missingMap.delete('event_name')
  merged.missing_fields = [...missingMap.values()]
  merged.audit_chain = [...new Set([...(merged.audit_chain || []), ...(incoming.audit_chain || [])])]
  return merged
}

function mergePackageAnalysisResults(results: AnalyzeResult[]) {
  if (results.length <= 1) return results
  const matchMap = new Map<string, AnalyzeMatch>()
  results.forEach(result => {
    result.matches.forEach(match => {
      fallbackAuditFromText(result, match)
      const existing = matchMap.get(match.id)
      const audit = mergeAuditPayload(match.audit || {}, {
        audit_chain: [`材料包包含文件：${result.filename}`],
      })
      if (!existing) {
        matchMap.set(match.id, { ...match, audit })
        return
      }
      const current = { ...match, audit }
      const stronger = current.confidence > existing.confidence ? current : existing
      const weaker = current.confidence > existing.confidence ? existing : current
      matchMap.set(match.id, {
        ...stronger,
        confidence: Math.max(existing.confidence, match.confidence),
        reason: [stronger.reason, weaker.reason].filter(Boolean).join('；'),
        audit: mergeAuditPayload(stronger.audit || {}, weaker.audit || {}),
      })
    })
  })
  return [{
    file_id: materialServerFiles.value[0]?.id || 0,
    filename: `申报材料包（${results.length}份）：${results.map(item => item.filename).join('、')}`,
    extracted_text: results.map(item => item.extracted_text || '').filter(Boolean).join('\n\n'),
    has_text_content: results.some(item => item.has_text_content),
    matches: [...matchMap.values()].sort((a, b) => b.confidence - a.confidence),
  }]
}

async function uploadAndAnalyzeMaterials() {
  if (!materialSelectedFiles.value.length) {
    ElMessage.warning('请先选择证明材料')
    return
  }
  materialParsing.value = true
  try {
    const form = new FormData()
    materialSelectedFiles.value.forEach(file => form.append('files', file))
    const uploadResult = await api<{ files: Array<{ id: number; original_filename: string; view_url?: string; file_path?: string; file_type?: string }> }>('/upload', {
      method: 'POST',
      body: form,
    })
    materialServerFiles.value = uploadResult.files.map(file => ({
      id: file.id,
      name: file.original_filename,
      url: file.view_url || (file.file_path ? `/api/uploads/${file.file_path}` : ''),
      type: file.file_type,
    }))
    const analysis = await api<{ results: AnalyzeResult[] }>('/analyze', {
      method: 'POST',
      body: JSON.stringify({
        uploaded_file_ids: materialServerFiles.value.map(file => file.id).filter(Boolean),
        keyword: materialExtraKeyword.value.trim(),
      }),
    })
    const rawResults = analysis.results || []
    rawResults.forEach(result => {
      result.matches.forEach(match => fallbackAuditFromText(result, match))
    })
    materialAnalysisResults.value = mergePackageAnalysisResults(rawResults)
    materialSupplementFiles.value = {}
    ElMessage.success(`AI分析完成，共匹配 ${materialAnalysisResults.value.reduce((sum, item) => sum + item.matches.length, 0)} 个综测项目`)
  } catch (error) {
    ElMessage.error(`AI分析失败：${(error as Error).message}`)
  } finally {
    materialParsing.value = false
  }
}

async function submitMatchedMaterial(result: AnalyzeResult, match: AnalyzeMatch) {
  try {
    const packageFileIds = materialServerFiles.value.map(file => file.id).filter(Boolean) as number[]
    const supplementIds = matchSupplementFiles(result, match).map(file => file.id).filter(Boolean) as number[]
    const uploadedFileIds = Array.from(new Set([...(packageFileIds.length ? packageFileIds : [result.file_id]), ...supplementIds]))
    const response = await postJson<{ status: string; proofs_complete?: boolean; submission_id?: number }>('/submissions', {
      catalog_item_id: match.id,
      uploaded_file_ids: uploadedFileIds,
      ai_confidence: match.confidence,
      ai_decision: match.decision || (match.confidence >= 80 ? 'high' : 'medium'),
      ai_reason: match.reason || '',
      ai_audit: match.audit || {},
    })
    materialAddedItems.value.push({
      id: match.id,
      fileId: result.file_id || 0,
      filename: packageFileIds.length > 1 ? `${packageFileIds.length} 份材料组合包` : result.filename,
      title: match.title,
      category: match.category,
      category_name: match.category_name,
      level: match.level,
      score: match.score,
      confidence: match.confidence,
      status: response.status,
    })
    ElMessage.success(response.status === 'needs_more' ? '已提交审核，系统已标记需补充佐证' : '已提交审核，等待管理端终审')
    await loadAll()
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

function isMaterialAdded(result: AnalyzeResult, match: AnalyzeMatch) {
  return materialAddedItems.value.some(item => item.id === match.id && item.fileId === result.file_id)
}

async function selectTargetCatalogItem(item: CatalogExplorerItem) {
  selectedTargetItem.value = item
  targetCompletionDate.value = ''
  targetAiVerifyResult.value = ''
  const proofs = item.required_proofs?.length
    ? item.required_proofs
    : [{ type: 'general', name: '相关证明材料', description: '请上传能证明该项成果的材料文件' }]
  targetRequiredProofs.value = proofs
  targetProofFiles.value = Object.fromEntries(proofs.map(proof => [proof.type, null]))
}

async function handleTargetProofSelect(event: Event, proofType: string) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const uploaded = await uploadSingleFile(file, proofType)
    targetProofFiles.value = {
      ...targetProofFiles.value,
      [proofType]: { id: uploaded.id, name: uploaded.filename, url: uploaded.url, type: uploaded.type, proofType },
    }
    ElMessage.success('材料已上传')
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    input.value = ''
  }
}
void selectTargetCatalogItem
void handleTargetProofSelect

async function handleTargetManualFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || []).filter(file => {
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    return ['jpg', 'jpeg', 'png', 'bmp', 'webp', 'gif', 'pdf', 'doc', 'docx'].includes(ext)
  })
  if (!files.length) return
  materialParsing.value = true
  try {
    for (const file of files) {
      const uploaded = await uploadSingleFile(file, 'manual_proof')
      targetManualFiles.value.push({
        id: uploaded.id,
        name: uploaded.filename,
        url: uploaded.url,
        type: uploaded.type,
        proofType: 'manual_proof',
      })
    }
    ElMessage.success('材料已上传')
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    materialParsing.value = false
    input.value = ''
  }
}

function removeTargetManualFile(index: number) {
  targetManualFiles.value.splice(index, 1)
}

async function submitTargetedMaterial() {
  if (!targetManualForm.title.trim()) {
    ElMessage.warning('请填写加分项目名称')
    return
  }
  if (!targetManualForm.level) {
    ElMessage.warning('请选择加分级别')
    return
  }
  const uploadedIds = targetManualFiles.value.map(file => file.id).filter(Boolean) as number[]
  if (!uploadedIds.length) {
    ElMessage.warning('请至少上传一份加分材料证明')
    return
  }
  materialParsing.value = true
  try {
    const aiConfidence = 55
    const aiDecision = 'medium'
    const aiReason = '学生定向手动填写申报信息，需管理员按材料原件复核。'
    const scoreValue = Number(targetManualForm.score || 0)
    const aiAudit: AuditPayload = {
      status: 'MANUAL_REVIEW',
      confidence_score: aiConfidence,
      matched_regulation: {
        section: '手动定向提交',
        clause_text: targetManualForm.description.trim() || '学生手动填写加分项目，等待人工核验。',
        score_calculated: scoreValue,
      },
      extracted_features: {
        event_name: targetManualForm.title.trim(),
        award_level: targetManualForm.level,
        date: targetManualForm.completion_date,
        material_count: targetManualFiles.value.length,
      },
      risk_assessment: {
        risk_tags: ['MANUAL_TARGETED_SUBMISSION'],
        risk_description: '该材料未绑定既有综测目录，需管理员核验项目名称、级别、分值和证明材料。',
      },
      missing_fields: [],
      audit_chain: [
        `学生手动填写加分项目：${targetManualForm.title.trim()}`,
        `选择加分级别：${targetManualForm.level}`,
        `上传证明材料 ${targetManualFiles.value.length} 份`,
        '进入管理端审核队列，管理员通过后才写入综测得分',
      ],
    }
    const verify = await api<{ results: AnalyzeResult[] }>('/analyze', {
      method: 'POST',
      body: JSON.stringify({
        uploaded_file_ids: uploadedIds,
        keyword: `${targetManualForm.title} ${targetManualForm.level}`.trim(),
      }),
    })
    const bestMatch = (verify.results || [])
      .flatMap(result => result.matches || [])
      .sort((a, b) => b.confidence - a.confidence)[0]
    if (bestMatch?.audit?.extracted_features) {
      aiAudit.extracted_features = {
        ...aiAudit.extracted_features,
        ...bestMatch.audit.extracted_features,
        event_name: targetManualForm.title.trim(),
        award_level: targetManualForm.level,
      }
    }
    if (bestMatch?.audit?.risk_assessment?.risk_tags?.length) {
      aiAudit.risk_assessment!.risk_tags = [
        ...new Set([...(aiAudit.risk_assessment!.risk_tags || []), ...bestMatch.audit.risk_assessment.risk_tags]),
      ]
    }
    if (bestMatch?.confidence) {
      aiAudit.audit_chain!.push(`AI 参考匹配：${bestMatch.title}，置信度 ${bestMatch.confidence.toFixed(1)}%`)
    }
    const response = await postJson<{ status: string; proofs_complete?: boolean; submission_id?: number }>('/submissions', {
      uploaded_file_ids: uploadedIds,
      completion_date: targetManualForm.completion_date,
      manual_title: targetManualForm.title.trim(),
      manual_category: targetManualForm.category,
      manual_level: targetManualForm.level,
      manual_score: scoreValue,
      manual_description: targetManualForm.description.trim(),
      ai_confidence: aiConfidence,
      ai_decision: aiDecision,
      ai_reason: aiReason,
      ai_audit: aiAudit,
    })
    targetAiVerifyResult.value = response.status === 'needs_more' ? '已提交，当前标记为需补材料' : '已提交到管理端审核队列'
    materialAddedItems.value.push({
      id: `manual-${response.submission_id || Date.now()}`,
      fileId: uploadedIds[0] || 0,
      filename: targetManualFiles.value.map(file => file.name).join('、'),
      title: targetManualForm.title.trim(),
      category: targetManualForm.category,
      category_name: targetManualForm.category === 'moral' ? '品德行为' : targetManualForm.category === 'sports' ? '文体表现' : '学业表现',
      level: targetManualForm.level,
      score: scoreValue,
      confidence: aiConfidence,
      status: response.status,
    })
    ElMessage.success('已提交审核，等待管理端终审')
    Object.assign(targetManualForm, {
      title: '',
      category: 'academic',
      level: '',
      score: '',
      description: '',
      completion_date: '',
    })
    targetManualFiles.value = []
    await loadAll()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    materialParsing.value = false
  }
}

async function loadAdminQueue() {
  const data = await api<{ submissions: any[] }>(`/admin/submissions?per_page=200${auditQueue.value ? `&queue=${auditQueue.value}` : ''}`)
  let rows = (data.submissions || []).map(mapSubmissionToApplication)
  if (auditQueue.value === 'high_confidence') rows = rows.filter(item => item.ai_confidence >= 0.85 && item.status === 'pending_human')
  if (auditQueue.value === 'risk') rows = rows.filter(item => item.ai_confidence < 0.7 || item.status === 'needs_more')
  adminApplications.value = orderAuditRows(rows)
}

async function decide(app: ApplicationItem, decision: 'approved' | 'rejected' | 'needs_more' | 'return') {
  const score = decision === 'approved' ? Number(app.suggested_score || 0) : undefined
  const action = decision === 'approved' ? 'approve' : decision
  const comment = decision === 'approved'
    ? '人工复核通过，写入综测流水。'
    : decision === 'needs_more'
      ? '请补齐学校/学院通知、参赛名单或官方结果证明。'
      : decision === 'return'
        ? '重新打回，需补充材料后复核；如已入账则撤销该提交对应加分。'
        : '材料与细则不匹配，驳回。'
  await api(`/admin/submissions/${app.id}`, {
    method: 'PUT',
    body: JSON.stringify({
      action,
      score,
      comment,
      remarks: comment,
      rule_ref: app.ai_review?.rule_ref || '',
    }),
  })
  ElMessage.success(decision === 'return' ? '已重新打回，等待学生补充材料' : '审核结果已保存')
  await loadAll()
}

onMounted(async () => {
  await clearExistingBasketOnce()
  await loadAll()
})
</script>

<template>
  <main class="app-shell" v-loading="loading">
    <aside class="app-sidebar">
      <div class="brand">
        <span class="brand-mark">Z</span>
        <div>
          <strong>综测星轨</strong>
          <small>Zongce Agent</small>
        </div>
      </div>

      <div v-if="canViewAdmin" class="role-switch">
        <button :class="{ active: store.roleMode === 'admin' }" @click="switchRole('admin')">管理端</button>
        <button :class="{ active: store.roleMode === 'student' }" @click="switchRole('student')">学生端</button>
      </div>

      <nav class="nav-list">
        <button
          v-for="tab in currentTabs"
          :key="tab"
          :class="{ active: currentActiveTab === tab }"
          @click="switchTab(tab)"
        >
          <span class="nav-dot" />
          {{ tab }}
        </button>
      </nav>

      <div class="sidebar-footer">
        <span>当前细则</span>
        <strong>{{ activeRuleDoc?.name || '2025年7月电信学院综测细则（公示版）' }}</strong>
      </div>
    </aside>

    <section class="main-frame">
      <header class="app-topbar">
        <h1>{{ store.roleMode === 'student' ? activeStudentTab : activeAdminTab }}</h1>
        <div class="topbar-actions">
          <div v-if="store.roleMode === 'student'" class="academic-year-selector">
            <span class="year-label">学年</span>
            <el-select v-model="currentAcademicYear" size="default">
              <el-option v-for="y in availableAcademicYears" :key="y" :label="y" :value="y" />
            </el-select>
          </div>
          <button class="bell-btn" aria-label="消息">
            <span class="bell-dot">1</span>
            ●
          </button>
          <button class="login-card">
            <span class="avatar-circle">{{ store.roleMode === 'student' ? '张' : '王' }}</span>
            <span>
              <strong>{{ store.currentUser?.name || (store.roleMode === 'student' ? summary?.user.name || '张三' : '王五') }}</strong>
              <small>{{ store.roleMode === 'student' ? '学生账号' : '管理员' }}</small>
            </span>
          </button>
          <button class="logout-btn" @click="logout">退出</button>
        </div>
      </header>

      <section class="workspace">
      <header class="page-banner">
        <div>
          <span class="eyebrow">{{ modeLabel }}</span>
          <h1>{{ store.roleMode === 'student' ? activeStudentTab : activeAdminTab }}</h1>
          <p v-if="store.roleMode === 'student'">围绕综测目标发现机会、规划备赛、提交材料并追踪审核。</p>
          <p v-else>结合 AI 初审结果，完成活动发布、规则维护与材料复核。</p>
        </div>
        <div class="identity">
          <span>{{ store.currentUser?.name || (store.roleMode === 'student' ? summary?.user.name || '张三' : '王五') }}</span>
          <small>{{ store.roleMode === 'student' ? store.currentUser?.department || '电子信息工程' : '管理端审核员' }}</small>
        </div>
      </header>

      <template v-if="store.roleMode === 'student'">
        <section v-show="activeStudentTab === '星轨探索'" class="catalog-explorer-page">
          <div class="explorer-header">
            <div>
              <h2><span class="explorer-star">★</span> 星轨探索</h2>
              <p>浏览电信学院全部206项综测加分项目 · AI审核通过后计入你的星轨得分</p>
            </div>
          </div>

          <div class="explorer-stats">
            <article class="explorer-stat moral">
              <span>♥</span>
              <div><small>品德项目</small><strong>{{ catalogExplorerStats.moral }}</strong><em>加分上限30分</em></div>
            </article>
            <article class="explorer-stat academic">
              <span>▮</span>
              <div><small>学业项目</small><strong>{{ catalogExplorerStats.academic }}</strong><em>加分上限20分</em></div>
            </article>
            <article class="explorer-stat sports">
              <span>♜</span>
              <div><small>文体项目</small><strong>{{ catalogExplorerStats.sports }}</strong><em>加分上限40分</em></div>
            </article>
            <article class="explorer-stat total">
              <span>☷</span>
              <div><small>总计项目</small><strong>{{ catalogExplorerStats.total }}</strong><em>206项加分项</em></div>
            </article>
          </div>

          <div class="explorer-filters">
            <select v-model="catalogQuery.category">
              <option value="">全部板块</option>
              <option v-for="item in catalogFilters.categories" :key="item.key" :value="item.key">{{ item.name }}</option>
            </select>
            <select v-model="catalogQuery.level">
              <option value="">全部级别</option>
              <option v-for="level in catalogFilters.levels" :key="level" :value="level">{{ level }}</option>
            </select>
            <select v-model="catalogQuery.section">
              <option value="">全部分类</option>
              <option v-for="section in catalogFilters.sections" :key="section" :value="section">{{ section }}</option>
            </select>
            <select v-model="catalogQuery.subcategory">
              <option value="">全部子类</option>
              <option v-for="item in catalogFilters.subcategories" :key="item.key" :value="item.key">{{ item.name }}</option>
            </select>
            <input v-model="catalogQuery.keyword" placeholder="搜索项目名称..." />
            <span>共 {{ filteredCatalogItems.length }} 项</span>
          </div>

          <div class="catalog-grid">
            <article
              v-for="item in filteredCatalogItems"
              :key="item.id"
              class="catalog-explorer-card"
              :class="{ selected: submittedCatalogIds.has(item.id) || basketCatalogIds.has(item.id) }"
            >
              <div class="catalog-card-top">
                <span class="catalog-icon-box">{{ item.icon?.includes('trophy') ? '♜' : item.icon?.includes('heart') ? '♥' : item.icon?.includes('book') ? '▮' : '♟' }}</span>
                <div class="catalog-card-badges">
                  <span :class="['catalog-badge', catalogCategoryClass(item.category)]">{{ item.category_name }}</span>
                  <span :class="['catalog-badge', catalogLevelClass(item.level)]">{{ item.level }}</span>
                </div>
              </div>
              <h3>{{ item.title }}</h3>
              <p>{{ item.description }}</p>
              <div class="catalog-card-footer">
                <strong>+{{ item.score }}分</strong>
                <span>{{ item.section }}</span>
              </div>
              <div v-if="item.note" class="catalog-note-line">ⓘ {{ item.note }}</div>
              <div class="catalog-card-actions">
                <span v-if="submittedCatalogIds.has(item.id)" class="catalog-submitted">已提交/已通过</span>
                <button v-else class="btn-primary-sm" @click="openSubmitModal(item)">提交认证</button>
              </div>
            </article>
          </div>
        </section>

        <section v-show="activeStudentTab === '星盘总览'" class="overview-page">
          <div class="score-hero-card">
            <div class="score-copy">
              <span class="eyebrow">综合测评总分</span>
              <div class="score-number">{{ summary?.score.total ?? '--' }}</div>
              <p>待审核潜在加分 {{ summary?.pending_score ?? 0 }}，距离 90 分目标还差 {{ summary?.goal_gap ?? 0 }}。</p>
              <div class="hero-actions">
                <button class="btn-primary-sm" @click="activeStudentTab = '机会大厅'">去找加分机会</button>
                <button class="btn-ghost" @click="activeStudentTab = '智审中心'">提交材料认证</button>
                <button class="btn-ghost" @click="openGradeModal">编辑学业成绩</button>
              </div>
            </div>
            <div class="score-orbit">
              <div class="orbit-core">{{ summary?.score.total ?? '--' }}</div>
              <span v-for="item in summary?.score.details" :key="item.key" :class="['orbit-dot', item.key]">
                {{ item.label }} {{ item.score }}
              </span>
            </div>
          </div>

          <div class="stats-bar">
            <div v-for="item in summary?.score.details" :key="item.key" class="stat-item">
              <span>{{ item.label }}</span>
              <strong>{{ item.score }}</strong>
              <small>权重 {{ Math.round(item.weight * 100) }}%</small>
            </div>
            <div class="stat-divider" />
            <div class="stat-item accent-stat">
              <span>待审核</span>
              <strong>{{ summary?.pending_score ?? 0 }}</strong>
              <small>AI 初审后人工确认</small>
            </div>
          </div>

          <div class="score-chart-grid">
            <div class="score-card-panel">
              <h2>三大板块得分构成</h2>
              <div ref="radarRef" class="chart" />
            </div>
            <div class="score-card-panel">
              <h2>各分类加分分布</h2>
              <div ref="barRef" class="chart" />
            </div>
          </div>

          <div class="ai-score-panel">
            <div class="score-panel-head">
              <h2><span>AI</span> 智能分析与建议</h2>
              <button class="btn-ghost" @click="refreshAiScoreAnalysis">重新分析</button>
            </div>
            <div class="ai-score-meta">基于当前入账流水、待审核材料和综测细则生成，{{ aiAnalysisStamp }}</div>
            <div class="ai-insight-list">
              <article v-for="item in aiScoreInsights" :key="item.title" :class="['ai-insight', item.tone]">
                <strong>{{ item.title }}</strong>
                <p>{{ item.text }}</p>
              </article>
            </div>
          </div>

          <div class="completed-score-panel">
            <div class="score-panel-head">
              <h2>我已完成的加分项目（{{ completedScoreItems.length }}）</h2>
              <button class="btn-ghost" @click="activeStudentTab = '机会大厅'">去大厅添加更多</button>
            </div>
            <div class="score-project-table">
              <div class="score-project-head">
                <span>项目名称</span>
                <span>大类</span>
                <span>子类</span>
                <span>级别</span>
                <span>得分</span>
              </div>
              <div v-for="item in completedScoreItems" :key="item.title" class="score-project-row">
                <strong>{{ item.title }}</strong>
                <span :class="['score-chip', item.dimension.includes('学业') ? 'academic' : item.dimension.includes('文体') ? 'arts' : 'moral']">{{ item.dimension }}</span>
                <span>{{ item.child }}</span>
                <span :class="['level-pill', item.level === '国家级' ? 'national' : item.level === '校级' ? 'school' : item.level === '省级' ? 'province' : 'college']">{{ item.level }}</span>
                <em>+{{ item.score }}</em>
              </div>
            </div>
          </div>
        </section>

        <section v-show="activeStudentTab === '机会大厅'" class="page-stack">
          <div class="hall-tabs">
            <button :class="{ active: opportunityMode === 'activity' }" @click="opportunityMode = 'activity'">
              近期活动 <span>{{ opportunityCounts.activity }}</span>
            </button>
            <button :class="{ active: opportunityMode === 'competition' }" @click="opportunityMode = 'competition'">
              学科竞赛 <span>{{ opportunityCounts.competition }}</span>
            </button>
          </div>

          <div class="hall-filter-panel">
            <div class="filter-row">
              <span class="filter-label">综测归属:</span>
              <div class="filter-options">
                <button :class="{ active: !filters.dimension }" @click="filters.dimension = ''">全部</button>
                <button :class="{ active: filters.dimension === 'moral' }" @click="filters.dimension = 'moral'">德育</button>
                <button :class="{ active: filters.dimension === 'academic' }" @click="filters.dimension = 'academic'">学业</button>
                <button :class="{ active: filters.dimension === 'arts_sports' }" @click="filters.dimension = 'arts_sports'">文体</button>
              </div>
            </div>
            <div class="filter-row">
              <span class="filter-label">{{ opportunityMode === 'activity' ? '活动类型:' : '竞赛级别:' }}</span>
              <div class="filter-options">
                <button :class="{ active: !filters.category }" @click="filters.category = ''">全部</button>
                <button
                  v-for="category in currentOpportunityCategories"
                  :key="category"
                  :class="{ active: filters.category === category }"
                  @click="filters.category = category"
                >
                  {{ category }}
                </button>
              </div>
            </div>
            <div class="filter-row filter-search-row">
              <span class="filter-label">其他条件:</span>
              <el-input
                v-model="filters.keyword"
                class="hall-search-input"
                placeholder="请输入比赛/活动/证书"
                clearable
                @keyup.enter="applyOpportunityFilters"
              />
              <button class="filter-action primary" @click="applyOpportunityFilters">查询</button>
              <button class="filter-action" @click="resetOpportunityFilters">重置</button>
            </div>
          </div>

          <div class="section-header">
            <h2>{{ opportunityMode === 'activity' ? '近期活动' : '学科竞赛目录' }}</h2>
            <p>{{ opportunityMode === 'activity' ? '展示由管理员发布的近期校园活动通知。' : '共收录65项官方认证学科竞赛，含国家级A类和省级A类赛事。' }}</p>
          </div>

          <div class="activity-grid">
            <article v-for="item in filteredOpportunities" :key="item.id" class="activity-card-rich">
              <div class="card-image-wrapper">
                <img
                  v-if="opportunityImage(item)"
                  :src="opportunityImage(item)"
                  :alt="item.title"
                  class="card-image"
                  loading="lazy"
                  @error="markOpportunityImageBroken(item)"
                />
                <div v-else :class="['opportunity-image-fallback', opportunityFallbackClass(item)]">
                  <span>{{ opportunityFallbackKeyword(item) }}</span>
                  <strong>{{ opportunityFallbackTitle(item) }}</strong>
                </div>
                <span class="image-tag">{{ opportunityImage(item) ? item.category : opportunityFallbackKeyword(item) }}</span>
              </div>
              <div class="card-body">
                <div class="card-meta">
                  <span class="type-tag">{{ item.dimension_label }}</span>
                  <span>{{ item.deadline || item.season_months || '时间待通知' }}</span>
                </div>
                <h3>{{ item.title }}</h3>
                <p>{{ item.description }}</p>
                <div class="card-footer">
                  <span>ROI {{ item.roi_score }}</span>
                  <div>
                    <button class="btn-text" @click="selectedOpportunity = item">详情</button>
                    <button class="btn-primary-sm" :disabled="item.in_basket" @click="addToBasket(item)">
                      {{ item.in_basket ? '已添加' : '添加备赛清单' }}
                    </button>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section v-show="activeStudentTab === '备赛清单'" class="page-stack">
          <article v-for="item in basket" :key="basketIdentity(item)" class="basket-row">
            <img v-if="opportunityImage(item.opportunity)" :src="opportunityImage(item.opportunity)" alt="" />
            <div v-else :class="['basket-image-fallback', opportunityFallbackClass(item.opportunity)]">
              <span>{{ opportunityFallbackKeyword(item.opportunity) }}</span>
            </div>
            <div>
              <span class="source">{{ item.opportunity.category }}</span>
              <h3>{{ item.opportunity.title }}</h3>
              <p>{{ item.opportunity.credit_hint }}</p>
            </div>
            <el-select v-model="item.stage" @change="updateBasket(item)">
              <el-option v-for="stage in ['想参加', '已报名', '备赛中', '材料待提交', '已结算']" :key="stage" :label="stage" :value="stage" />
            </el-select>
            <el-input v-model="item.note" placeholder="备赛备注" @change="updateBasket(item)" />
            <div class="basket-actions">
              <button class="btn-text" @click="selectedOpportunity = item.opportunity">详情</button>
              <el-button text type="danger" @click="removeBasket(item)">移出</el-button>
            </div>
          </article>
          <el-empty v-if="!basket.length" description="还没有加入备赛清单" />
        </section>

        <section v-show="activeStudentTab === '智审中心'" class="page-stack material-submit-page">
          <div class="source-page-header">
            <h2>材料提交</h2>
            <p>上传证明材料 · AI自动识别匹配项目 · 定向提交确保材料齐全</p>
          </div>

          <div class="source-tabs">
            <button :class="{ active: materialSubmitMode === 'match' }" @click="materialSubmitMode = 'match'">AI智能匹配</button>
            <button :class="{ active: materialSubmitMode === 'targeted' }" @click="materialSubmitMode = 'targeted'">定向提交</button>
          </div>

          <div v-if="materialSubmitMode === 'match'" class="upload-layout">
            <div class="source-card">
              <header>上传证明材料</header>
              <label class="source-upload-zone" @dragover.prevent @drop.prevent="onMaterialSubmitDrop">
                <input type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.webp,.pdf,.doc,.docx" @change="handleMaterialSubmitFileSelect" />
                <strong>点击或拖拽文件到此处</strong>
                <span>支持 JPG、PNG、PDF、DOCX 格式</span>
              </label>
              <div v-if="materialSelectedFiles.length" class="source-file-list">
                <div v-for="(file, index) in materialSelectedFiles" :key="`${file.name}-${index}`" class="source-file-item">
                  <b>{{ materialFileIcon(file.name) }}</b>
                  <span>{{ file.name }}</span>
                  <small>{{ (file.size / 1024).toFixed(1) }} KB</small>
                  <button @click="removeMaterialSelectedFile(index)">×</button>
                </div>
              </div>
              <input v-model="materialExtraKeyword" class="source-keyword" placeholder="补充关键词可提高匹配准确率（可选）" />
              <button class="source-primary-btn" :disabled="!materialSelectedFiles.length || materialParsing" @click="uploadAndAnalyzeMaterials">
                {{ materialParsing ? 'AI分析中...' : 'AI分析' }}
              </button>
              <p class="source-note">文件将上传至服务器，AI 自动提取文字内容并匹配最合适的综测加分项目</p>
              <div class="source-badges">
                <span>PDF解析</span>
                <span>Word解析</span>
                <span>AI增强</span>
                <span>关键词匹配</span>
              </div>
            </div>

            <div class="source-card analysis-card">
              <header>AI分析结果</header>
              <div v-if="!materialAnalysisResults.length" class="analysis-empty">
                <strong>🤖</strong>
                <p>选择文件后点击「AI分析」</p>
                <span>AI将自动识别证明材料内容，匹配综测项目</span>
              </div>
              <div v-else class="analysis-results">
                <article v-for="result in materialAnalysisResults" :key="result.file_id" class="analysis-file-group">
                  <h3>{{ result.filename }}</h3>
                  <p class="source-extracted-text">
                    {{ result.has_text_content ? result.extracted_text.slice(0, 150) : '未能从文件中提取文字，基于文件名和关键词匹配。' }}
                  </p>
                  <div v-for="match in result.matches" :key="`${result.file_id}-${match.id}`" class="source-match-card">
                    <div class="source-match-main">
                      <div class="audit-card-title">
                        <strong>{{ match.title }}</strong>
                        <span :class="['audit-light-pill', auditLightClass(match)]">{{ auditLightLabel(match) }}</span>
                      </div>
                      <p>{{ match.description }}</p>
                      <div class="source-match-badges">
                        <span>{{ match.category_name || match.category }}</span>
                        <span>{{ match.level }}</span>
                        <span>+{{ match.score }}分</span>
                        <span v-if="match.audit?.matched_regulation?.section">{{ match.audit.matched_regulation.section }}</span>
                      </div>
                      <div class="audit-structured-grid">
                        <label>
                          <span>姓名</span>
                          <input :value="auditFeatureValue(match, 'detected_name', '')" placeholder="手动填写姓名" @input="event => setAuditFeature(match, 'detected_name', event)" />
                        </label>
                        <label>
                          <span>活动/证书</span>
                          <input :value="auditFeatureValue(match, 'event_name', match.title)" placeholder="手动填写活动或证书名称" @input="event => setAuditFeature(match, 'event_name', event)" />
                        </label>
                        <label>
                          <span>等级</span>
                          <input :value="auditFeatureValue(match, 'award_level', match.level || '')" placeholder="手动填写等级" @input="event => setAuditFeature(match, 'award_level', event)" />
                        </label>
                        <label>
                          <span>日期</span>
                          <input :value="auditFeatureValue(match, 'date', '')" placeholder="手动填写日期" @input="event => setAuditFeature(match, 'date', event)" />
                        </label>
                      </div>
                      <div v-if="auditRiskTags(match).length" class="audit-risk-tags">
                        <span v-for="tag in auditRiskTags(match)" :key="tag">{{ tag }}</span>
                      </div>
                      <div v-if="match.audit?.missing_fields?.length" class="audit-missing-box">
                        <b>需补充佐证</b>
                        <div v-for="field in match.audit.missing_fields" :key="field.field_key">
                          <strong>{{ field.field_name }}</strong>
                          <small>{{ field.guidance_tips }}</small>
                          <label class="audit-supplement-upload">
                            <input type="file" accept=".jpg,.jpeg,.png,.bmp,.webp,.pdf,.doc,.docx" @change="event => handleSupplementSelect(event, result, match, field.field_key)" />
                            <span>{{ materialSupplementFiles[supplementKey(result, match, field.field_key)]?.name || '上传补充材料' }}</span>
                          </label>
                        </div>
                        <button class="audit-reanalyze-btn" :disabled="materialParsing" @click="reanalyzeWithSupplements(result, match)">
                          {{ materialParsing ? '重新分析中...' : '用补充材料重新分析' }}
                        </button>
                      </div>
                      <div v-if="matchSupplementFiles(result, match).length" class="audit-supplement-summary">
                        <strong>已补充 {{ matchSupplementFiles(result, match).length }} 份材料</strong>
                        <button class="audit-reanalyze-btn" :disabled="materialParsing" @click="reanalyzeWithSupplements(result, match)">
                          {{ materialParsing ? '重新分析中...' : '刷新上方识别结果' }}
                        </button>
                      </div>
                      <ol v-if="match.audit?.audit_chain?.length" class="audit-chain-list">
                        <li v-for="step in match.audit.audit_chain" :key="step">{{ step }}</li>
                      </ol>
                    </div>
                    <div class="source-confidence">
                      <span :class="matchConfidenceClass(match.confidence)">{{ match.confidence.toFixed(1) }}%</span>
                      <button class="source-primary-small" :disabled="isMaterialAdded(result, match)" @click="submitMatchedMaterial(result, match)">
                        {{ isMaterialAdded(result, match) ? '已提交' : '提交整组审核' }}
                      </button>
                    </div>
                  </div>
                </article>
              </div>
            </div>
          </div>

          <div v-else class="targeted-submit-grid">
            <div class="source-card targeted-manual-card">
              <header>填写加分资料</header>
              <div class="manual-target-form">
                <label class="manual-field wide">
                  <span>加分项目名称</span>
                  <input v-model="targetManualForm.title" placeholder="如：全国大学生物联网设计竞赛省级一等奖" />
                </label>
                <label class="manual-field">
                  <span>综测板块</span>
                  <select v-model="targetManualForm.category">
                    <option value="moral">品德行为</option>
                    <option value="academic">学业表现</option>
                    <option value="sports">文体表现</option>
                  </select>
                </label>
                <label class="manual-field">
                  <span>加分级别</span>
                  <select v-model="targetManualForm.level">
                    <option value="">请选择</option>
                    <option value="院级">院级</option>
                    <option value="校级">校级</option>
                    <option value="省级">省级</option>
                    <option value="国家级">国家级</option>
                    <option value="国际级">国际级</option>
                    <option value="其他">其他</option>
                  </select>
                </label>
                <label class="manual-field">
                  <span>建议加分</span>
                  <input v-model="targetManualForm.score" inputmode="decimal" placeholder="由管理员终审确认" />
                </label>
                <label class="manual-field">
                  <span>完成日期</span>
                  <input v-model="targetManualForm.completion_date" type="date" />
                </label>
                <label class="manual-field wide">
                  <span>补充说明</span>
                  <textarea v-model="targetManualForm.description" rows="5" placeholder="填写奖项等级、团队身份、排名、主办方、证书编号等关键信息" />
                </label>
              </div>
            </div>

            <div class="source-card targeted-proof-card">
              <header>上传加分材料证明</header>
              <label class="source-upload-zone compact-zone">
                <input type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.webp,.pdf,.doc,.docx" @change="handleTargetManualFileSelect" />
                <strong>点击上传图片 / PDF / Word</strong>
                <span>可一次选择多份材料，作为同一个定向申报包提交</span>
              </label>
              <div v-if="targetManualFiles.length" class="source-file-list">
                <div v-for="(file, index) in targetManualFiles" :key="`${file.name}-${index}`" class="source-file-item">
                  <b>{{ materialFileIcon(file.name) }}</b>
                  <span>{{ file.name }}</span>
                  <small>{{ file.proofType || '证明材料' }}</small>
                  <button @click="removeTargetManualFile(index)">×</button>
                </div>
              </div>
              <p v-if="targetAiVerifyResult" class="target-ai-result">{{ targetAiVerifyResult }}</p>
              <button class="source-primary-btn" :disabled="materialParsing" @click="submitTargetedMaterial">
                {{ materialParsing ? '提交中...' : '提交审核' }}
              </button>
              <p class="source-note">定向提交不会自动入账，管理员会在审核队列中核验项目名称、级别、分值和材料原件。</p>
            </div>
          </div>

          <div v-if="materialAddedItems.length" class="source-card added-materials">
            <header>已提交/加入</header>
            <table>
              <thead><tr><th>来源文件</th><th>匹配项目</th><th>大类</th><th>级别</th><th>得分</th><th>置信度</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="item in materialAddedItems" :key="`${item.fileId}-${item.id}`">
                  <td>{{ item.filename }}</td>
                  <td>{{ item.title }}</td>
                  <td>{{ item.category_name || item.category }}</td>
                  <td>{{ item.level }}</td>
                  <td>+{{ item.score }}</td>
                  <td>{{ item.confidence.toFixed(1) }}%</td>
                  <td>{{ statusLabel(sourceStatus(item.status)) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section
          v-show="activeStudentTab === '荣誉星墙'"
          :class="['page-stack', 'honor-page', { 'is-dragging': honorDropOver }]"
          @dragover.prevent="honorDropOver = true"
          @dragleave.prevent="honorDropOver = false"
          @drop="onHonorPageDrop"
        >
          <div class="honor-hero">
            <div>
              <span class="eyebrow">Honor Gallery</span>
              <h2>把证书、活动照片和比赛瞬间排成自己的成长展墙</h2>
              <p>拖动卡片可以调整顺序；这里不等于综测入账，只用于展示成长记录。</p>
            </div>
            <div class="panel inline-form honor-add-panel">
              <el-input v-model="honorForm.title" placeholder="荣誉标题" />
              <el-select v-model="honorForm.category">
                <el-option label="证书" value="证书" />
                <el-option label="竞赛" value="竞赛" />
                <el-option label="活动" value="活动" />
                <el-option label="照片" value="照片" />
              </el-select>
              <label class="honor-upload-zone" @dragover.prevent @drop.prevent="onHonorPageDrop">
                <input type="file" multiple accept=".jpg,.jpeg,.png,.webp" @change="handleHonorFileSelect" />
                <strong>点击或拖拽选择图片</strong>
                <span>填写标题和分类后一起添加到荣誉墙</span>
              </label>
              <div v-if="honorSelectedFiles.length" class="honor-file-list">
                <span v-for="(file, index) in honorSelectedFiles" :key="`${file.name}-${index}`">
                  {{ file.name }}
                  <button type="button" @click.stop="removeSelectedHonorFile(index)">×</button>
                </span>
              </div>
              <el-button type="primary" @click="createHonor">
                {{ honorSelectedFiles.length ? '添加图文荣誉' : '添加文字荣誉' }}
              </el-button>
            </div>
          </div>
          <div class="honor-wall">
            <article
              v-for="(item, index) in honors"
              :key="item.id"
              draggable="true"
              :class="['honor-card', `honor-card-${index % 3}`]"
              @dragstart="draggedHonorId = item.id"
              @dragover.prevent
              @drop.stop="dropHonor(item)"
            >
              <img v-if="item.image_url" :src="honorImage(item)" :alt="item.title" />
              <div v-else :class="['honor-visual', honorPreset(item, index).variant]">
                <div class="cert-border" />
                <div class="cert-top">
                  <span>{{ honorPreset(item, index).brand }}</span>
                  <em>{{ honorPreset(item, index).type }}</em>
                </div>
                <div class="cert-main">
                  <small>授予</small>
                  <strong>张三</strong>
                  <p>{{ honorPreset(item, index).subject }}</p>
                  <h3>{{ honorPreset(item, index).award }}</h3>
                </div>
                <div class="cert-bottom">
                  <span>{{ honorPreset(item, index).date }}</span>
                  <i>{{ honorPreset(item, index).seal }}</i>
                </div>
              </div>
              <div class="honor-caption" role="button" title="点击编辑标题和分类" @click.stop="openHonorEditor(item)">
                <span>{{ item.category }}</span>
                <strong>{{ item.title }}</strong>
              </div>
            </article>
          </div>
        </section>
      </template>

      <template v-else>
        <section v-show="activeAdminTab === '数据看板'" class="admin-dashboard-page">
          <div class="dashboard-kpi-row">
            <article class="dashboard-kpi kpi-blue">
              <span>♟ 活动/赛事总数</span>
              <strong>{{ adminDashboardKpis.opportunity_count }}</strong>
              <em>项</em>
            </article>
            <article class="dashboard-kpi kpi-green">
              <span>◎ 认证申请总数</span>
              <strong>{{ adminDashboardKpis.application_count }}</strong>
              <em>条</em>
            </article>
            <article class="dashboard-kpi kpi-red">
              <span>ⓘ 当前待处理</span>
              <strong>{{ adminDashboardKpis.pending_count }}</strong>
              <em>条</em>
            </article>
            <article class="dashboard-kpi kpi-gray">
              <span>◴ 已入账原始分</span>
              <strong>{{ adminDashboardKpis.approved_score }}</strong>
              <em>分</em>
            </article>
          </div>

          <div class="dashboard-main-grid">
            <section class="dashboard-panel review-list-panel">
              <div class="panel-title-row">
                <h2>实时综测审核列表</h2>
                <button class="panel-action" @click="activeAdminTab = '综测审核中心'">进入审核中心</button>
              </div>
              <div class="dashboard-filters">
                <input v-model="adminDashboardKeyword" class="dashboard-input" placeholder="搜索学生姓名或材料..." />
                <select v-model="adminDashboardStatusFilter" class="dashboard-input">
                  <option value="">审核状态</option>
                  <option value="pending_human">待人工审核</option>
                  <option value="needs_more">需补材料</option>
                  <option value="approved">已入账</option>
                  <option value="rejected">已驳回</option>
                </select>
              </div>
              <div class="dashboard-table">
                <div class="dashboard-table-head">
                  <span>学生姓名</span>
                  <span>材料类型</span>
                  <span>活动名称</span>
                  <span>AI 置信度</span>
                  <span>健康状态</span>
                  <span>操作</span>
                </div>
                <div v-for="item in adminDashboardRows" :key="item.id" class="dashboard-table-row">
                  <span>{{ item.student_name || '-' }}</span>
                  <span>{{ item.award_level || item.dimension }}</span>
                  <span>{{ item.title }}</span>
                  <strong :class="confidenceClass(item.ai_confidence)">{{ Math.round(item.ai_confidence * 100) }}%</strong>
                  <span :class="['dashboard-status', confidenceClass(item.ai_confidence)]">{{ statusLabel(item.status) }}</span>
                  <button class="dashboard-link" @click="selectDashboardApplication(item)">查看详情</button>
                </div>
                <div v-if="!adminDashboardRows.length" class="dashboard-table-empty">暂无真实审核申请</div>
              </div>
            </section>

            <aside class="dashboard-panel student-detail-panel">
              <h2>学生综测详情</h2>
              <div v-if="adminDashboardFocus" class="student-detail-card">
                <h3>{{ adminDashboardFocus.student_name || '-' }} <span>{{ adminDashboardFocus.award_level || '综测材料' }}</span></h3>
                <div class="detail-matrix">
                  <span>材料名称</span><strong>{{ adminDashboardFocus.title }}</strong>
                  <span>当前建议</span><strong>{{ adminDashboardFocus.suggested_score }} 分</strong>
                  <span>审核状态</span><strong>{{ statusLabel(adminDashboardFocus.status) }}</strong>
                </div>
              </div>
              <div v-else class="student-detail-empty">暂无可查看的真实审核记录</div>
              <h3 class="trend-title">近期审核趋势</h3>
              <div class="trend-chart">
                <svg viewBox="0 0 420 220" aria-label="近期审核趋势图">
                  <line x1="38" y1="24" x2="390" y2="24" />
                  <line x1="38" y1="72" x2="390" y2="72" />
                  <line x1="38" y1="120" x2="390" y2="120" />
                  <line x1="38" y1="168" x2="390" y2="168" />
                  <path d="M54 146 C92 152 112 158 138 140 S168 74 210 82 S260 96 286 134 S330 152 364 118 S388 104 404 126" />
                  <circle cx="54" cy="146" r="5" />
                  <circle cx="138" cy="140" r="5" />
                  <circle cx="210" cy="82" r="5" />
                  <circle cx="286" cy="134" r="5" />
                  <circle cx="364" cy="118" r="5" />
                  <text x="6" y="28">100</text>
                  <text x="14" y="76">80</text>
                  <text x="14" y="124">60</text>
                  <text x="14" y="172">40</text>
                  <text x="46" y="202">周一</text>
                  <text x="128" y="202">周二</text>
                  <text x="202" y="202">周三</text>
                  <text x="278" y="202">周四</text>
                  <text x="356" y="202">周五</text>
                </svg>
              </div>
            </aside>
          </div>
        </section>

        <section v-show="activeAdminTab === '活动发布管理'" class="publish-page">
          <!-- AI 文件上传扫描区（可折叠） -->
          <div class="ai-section" :class="{ expanded: aiExpanded }">
            <button class="ai-header" @click="aiExpanded = !aiExpanded">
              <div class="ai-header-left">
                <span class="ai-icon">AI</span>
                <div>
                  <span class="ai-title">AI 智能解析</span>
                  <span class="ai-optional">（选填）</span>
                </div>
              </div>
              <div class="ai-header-right">
                <span class="ai-subtitle" v-if="!aiExpanded">{{ aiParsed ? '已解析，可继续核对表单' : '上传文件，AI自动扫描填充' }}</span>
                <span class="chevron">{{ aiExpanded ? '⌃' : '⌄' }}</span>
              </div>
            </button>
            <Transition name="slide">
              <div v-if="aiExpanded" class="ai-body">
                <p class="ai-hint">上传通知截图/PDF/Word文件，AI自动扫描文字并填充下方表单，发布前须人工核对。</p>
                <div class="form-row">
                  <label class="form-label">📎 上传文件扫描（截图/PDF/Word）</label>
                  <label class="publish-scan-zone" @dragover.prevent @drop.prevent="(e) => { e.preventDefault(); const dt = (e as DragEvent).dataTransfer; if (dt) { const dropped = Array.from(dt.files).filter((f: any) => { const ext = (f.name as string).split('.').pop()?.toLowerCase() || ''; return ['jpg','jpeg','png','bmp','webp','gif','pdf','doc','docx'].includes(ext) }); const ex = publishScanFiles; const nf = dropped.filter((f: any) => !ex.some((ef: any) => ef.name === f.name && ef.size === f.size)); if (nf.length) publishScanFiles = [...ex, ...nf] } }">
                    <input type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.webp,.gif,.pdf,.doc,.docx" @change="handlePublishScanFileSelect" />
                    <strong>点击或拖拽文件到此处</strong>
                    <span>支持 JPG、PNG、PDF、DOCX 格式</span>
                  </label>
                  <div v-if="publishScanFiles.length" class="cert-file-list">
                    <div v-for="(f, i) in publishScanFiles" :key="`ps-${f.name}-${i}`" class="cert-file-item">
                      <b>{{ materialFileIcon(f.name) }}</b>
                      <span>{{ f.name }}</span>
                      <small>{{ (f.size / 1024).toFixed(1) }} KB</small>
                      <button @click="removePublishScanFile(i)">x</button>
                    </div>
                  </div>
                  <div style="display:flex;gap:8px;align-items:center;margin-top:8px">
                    <button class="btn-primary ai-parse-btn" :disabled="!publishScanFiles.length || publishScanUploading" @click="publishAiScan">
                      <span v-if="publishScanUploading">⏳ AI 正在扫描识别...</span>
                      <span v-else>🤖 AI 扫描文件并填充表单</span>
                    </button>
                    <span v-if="publishScanStatus" style="font-size:11px;color:#64748b;">{{ publishScanStatus }}</span>
                  </div>
                </div>
              </div>
            </Transition>
          </div>

          <div class="publish-layout">
            <div class="publish-left">
              <h2 class="section-title"><span class="section-icon">▣</span> 活动信息</h2>
              <div class="form-card">
                <div class="form-row">
                  <label class="form-label">活动标题 <span class="text-danger">*</span></label>
                  <input v-model="publishForm.title" class="form-input" placeholder="输入活动标题" maxlength="200" />
                </div>

                <div class="publish-form-grid">
                  <div class="form-row">
                    <label class="form-label">活动类型 <span class="text-danger">*</span></label>
                    <div class="select-wrap">
                      <select v-model="publishForm.category" class="form-input">
                        <option value="活动通知">活动通知</option>
                        <option value="学科竞赛">学科竞赛</option>
                        <option value="创新创业">创新创业</option>
                        <option value="志愿服务">志愿服务</option>
                        <option value="证书考试">证书考试</option>
                      </select>
                      <span class="select-arrow">⌄</span>
                    </div>
                  </div>
                  <div class="form-row">
                    <label class="form-label">展示区 <span class="text-danger">*</span></label>
                    <div class="select-wrap">
                      <select v-model="publishForm.source_type" class="form-input">
                        <option value="activity">近期活动</option>
                      </select>
                      <span class="select-arrow">⌄</span>
                    </div>
                  </div>
                </div>

                <div class="publish-form-grid">
                  <div class="form-row">
                    <label class="form-label">综测归属 <span class="text-danger">*</span></label>
                    <div class="select-wrap">
                      <select v-model="publishForm.dimension" class="form-input">
                        <option value="moral">德育</option>
                        <option value="academic">学业</option>
                        <option value="arts_sports">文体</option>
                      </select>
                      <span class="select-arrow">⌄</span>
                    </div>
                  </div>
                  <div class="form-row">
                    <label class="form-label">组织单位</label>
                    <input v-model="publishForm.organizer" class="form-input" placeholder="电子与信息学院" />
                  </div>
                </div>

                <div class="publish-form-grid">
                  <div class="form-row">
                    <label class="form-label">开始时间</label>
                    <input v-model="publishForm.start_time" class="form-input" placeholder="2026-05-23 19:00" />
                  </div>
                  <div class="form-row">
                    <label class="form-label">报名截止/赛季</label>
                    <input v-model="publishForm.deadline" class="form-input" placeholder="2026-05-20 18:00 / 通常 7-8 月" />
                  </div>
                </div>

                <div class="form-row">
                  <label class="form-label">地点</label>
                  <input v-model="publishForm.location" class="form-input" placeholder="教室、报告厅、线上链接等" />
                </div>

                <div class="publish-form-grid">
                  <div class="form-row">
                    <label class="form-label">官网/来源链接</label>
                    <input v-model="publishForm.official_url" class="form-input" placeholder="通知来源、官网或公众号链接" />
                  </div>
                  <div class="form-row">
                    <label class="form-label">报名链接</label>
                    <input v-model="publishForm.registration_url" class="form-input" placeholder="报名表、问卷星或系统链接" />
                  </div>
                </div>

                <div class="publish-form-grid">
                  <div class="form-row">
                    <label class="form-label">联系邮箱</label>
                    <input v-model="publishForm.contact_email" class="form-input" placeholder="只填写公开通知中的邮箱" />
                  </div>
                  <div class="form-row">
                    <label class="form-label">公众号文章</label>
                    <input v-model="publishForm.article_url" class="form-input" placeholder="公众号推文链接" />
                  </div>
                </div>

                <div class="form-row">
                  <label class="form-label">活动描述 <span class="text-danger">*</span></label>
                  <textarea v-model="publishForm.description" class="form-input form-textarea" rows="5" placeholder="输入活动详情描述..." />
                </div>

                <div class="publish-form-grid">
                  <div class="form-row">
                    <label class="form-label">综测提示</label>
                    <textarea v-model="publishForm.credit_hint" class="form-input form-textarea" rows="3" placeholder="说明可能对应的综测加分方向" />
                  </div>
                  <div class="form-row">
                    <label class="form-label">规则引用</label>
                    <textarea v-model="publishForm.rule_ref" class="form-input form-textarea" rows="3" placeholder="引用综测细则条款或学院通知依据" />
                  </div>
                </div>

                <div class="publish-form-grid">
                  <div class="form-row">
                    <label class="form-label">材料要求 <span class="optional">每行一项</span></label>
                    <textarea v-model="publishForm.requirementsText" class="form-input form-textarea" rows="4" />
                  </div>
                  <div class="form-row">
                    <label class="form-label">标签 <span class="optional">每行一项</span></label>
                    <textarea v-model="publishForm.tagsText" class="form-input form-textarea" rows="4" />
                  </div>
                </div>
              </div>
            </div>

            <div class="publish-right">
              <h2 class="section-title"><span class="section-icon">▧</span> 图片上传</h2>
              <div class="form-card">
                <div class="form-row">
                  <label class="form-label">活动图片（第一张为封面）<span class="text-danger">*</span></label>
                  <div
                    class="image-grid"
                    :class="{ 'drag-over': publishDragOver }"
                    @dragover="onPublishDragOver"
                    @dragleave="onPublishDragLeave"
                    @drop="onPublishDrop"
                  >
                    <div v-for="(img, i) in publishImages" :key="img.url" class="image-item">
                      <img :src="img.localUrl" alt="" class="image-thumb" />
                      <span v-if="i === 0" class="cover-badge">封面</span>
                      <button class="image-remove" @click="removePublishImage(i)">×</button>
                    </div>
                    <label class="image-add">
                      <input type="file" accept="image/*" multiple class="hidden-input" @change="handlePublishImageSelect" />
                      <span class="add-plus">＋</span>
                      <span>添加</span>
                    </label>
                  </div>
                  <p class="image-hint">支持拖拽上传，发布到机会大厅后作为活动卡片和详情页图片。</p>
                </div>

                <div class="form-row">
                  <label class="form-label">群二维码 <span class="optional">（选填）</span></label>
                  <div class="qrcode-upload">
                    <div v-if="publishQr" class="qrcode-preview">
                      <img :src="publishQr.localUrl" alt="" class="qrcode-img" />
                      <button class="image-remove" @click="removePublishQr">×</button>
                    </div>
                    <label v-else class="qrcode-add">
                      <input type="file" accept="image/*" class="hidden-input" @change="handlePublishQrSelect" />
                      <span class="qr-mark">▦</span>
                      <span>上传二维码</span>
                    </label>
                  </div>
                  <p class="image-hint">用于活动详情中展示加群资料，不作为审核依据。</p>
                </div>

                <div class="submit-buttons">
                  <button class="btn-outline" @click="savePublishDraft">存为草稿</button>
                  <button class="btn-primary" @click="publishOpportunity">直接发布</button>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section v-show="activeAdminTab === '综测审核中心'" class="audit-dashboard">
          <div class="audit-hero">
            <div>
              <h2>审核中心 <span>辅导员视图</span></h2>
              <p>结合 AI 初审结果，快速完成全院加分材料复核。</p>
            </div>
          </div>
          <div class="audit-stat-grid">
            <div><span>待审核材料</span><strong>{{ auditStats.pending }}</strong></div>
            <div><span>AI 高置信材料（可一键通过）</span><strong>{{ auditStats.high }}</strong></div>
            <div><span>存疑需人工复核</span><strong>{{ auditStats.risk }}</strong></div>
            <div><span>今日已通过</span><strong>{{ auditStats.approved }}</strong></div>
          </div>
          <div class="audit-filter-row">
            <el-select v-model="auditQueue" placeholder="队列" clearable @change="loadAdminQueue">
              <el-option label="高置信" value="high_confidence" />
              <el-option label="需补材料" value="needs_more" />
              <el-option label="存疑/低置信" value="risk" />
              <el-option label="已通过" value="approved" />
              <el-option label="已驳回" value="rejected" />
            </el-select>
          </div>
          <div class="audit-table">
            <div class="audit-table-head">
              <span>学生姓名</span>
              <span>材料类型</span>
              <span>活动名称</span>
              <span>建议加分</span>
              <span>AI 置信度</span>
              <span>当前状态</span>
              <span>操作</span>
            </div>
            <div v-for="item in adminApplications" :key="item.id" class="audit-table-row">
              <span>{{ item.student_name || '张三' }}</span>
              <span>{{ item.award_level || item.dimension }}</span>
              <span>{{ item.title }}</span>
              <strong>+{{ item.suggested_score }}</strong>
              <span :class="['confidence-pill', confidenceClass(item.ai_confidence)]">{{ Math.round(item.ai_confidence * 100) }}%</span>
              <span class="audit-state"><i :class="confidenceClass(item.ai_confidence)" />{{ statusText(item) }}</span>
              <span class="audit-actions">
                <button class="approve" :disabled="item.status === 'approved'" @click="decide(item, 'approved')">通过</button>
                <button class="detail" @click="decide(item, 'needs_more')">补材料</button>
                <button class="reject" @click="decide(item, 'rejected')">驳回</button>
                <button class="detail" @click="decide(item, 'return')">重新打回</button>
              </span>
            </div>
          </div>
        </section>

        <section v-show="activeAdminTab === '用户管理'" class="admin-users-page" v-loading="adminUsersLoading">
          <div class="admin-users-head">
            <div>
              <h2>星轨用户管理</h2>
              <p>管理学生账号 · 添加/编辑/禁用用户</p>
            </div>
            <button class="btn-primary-sm" @click="openAddAdminUser">+ 添加用户</button>
          </div>

          <div class="admin-users-toolbar">
            <input v-model="adminUserKeyword" placeholder="搜索学号、姓名或院系..." @input="debounceAdminUserSearch" />
            <span>共 {{ adminUsers.length }} 人</span>
          </div>

          <div class="admin-users-table">
            <div class="admin-users-row admin-users-row-head">
              <span>ID</span>
              <span>学号</span>
              <span>姓名</span>
              <span>院系</span>
              <span>班级</span>
              <span>综测项目数</span>
              <span>提交数</span>
              <span>注册时间</span>
              <span>操作</span>
            </div>
            <div v-for="user in adminUsers" :key="user.id" class="admin-users-row">
              <span>#{{ user.id }}</span>
              <strong>{{ user.student_id }}</strong>
              <span>{{ user.name }}</span>
              <span>{{ user.department }}</span>
              <span>{{ user.class_name || '-' }}</span>
              <span>{{ user.item_count }}</span>
              <span>{{ user.submission_count }}</span>
              <span>{{ user.created_at }}</span>
              <span class="admin-user-actions">
                <button title="查看综测" @click="viewAdminUserItems(user)">★</button>
                <button title="编辑" @click="openEditAdminUser(user)">✎</button>
                <button title="重置密码" @click="openResetAdminPassword(user)">●</button>
                <button class="danger" title="禁用" @click="disableAdminUser(user)">⊘</button>
              </span>
            </div>
            <div v-if="!adminUsers.length" class="admin-users-empty">暂无用户</div>
          </div>
        </section>

        <section v-show="activeAdminTab === '规则与材料模板'" class="rules-page">
          <div class="rule-document-card">
            <div>
              <span class="eyebrow">当前参考细则</span>
              <h2>{{ activeRuleDoc?.name || '未设置综测细则' }}</h2>
              <p>{{ activeRuleDoc?.version || templates?.rule_version }}</p>
              <p class="muted">{{ activeRuleDoc?.notes || '上传 Word/PDF 后，系统会记录当前参考版本。' }}</p>
            </div>
            <div class="doc-actions">
              <a v-if="activeRuleDoc" class="btn-primary-sm" :href="imgUrl(activeRuleDoc.file_url)" target="_blank">点开查看</a>
              <label class="upload-rule-btn">
                上传新细则
                <input type="file" accept=".pdf,.doc,.docx" @change="uploadRuleDocument" />
              </label>
            </div>
          </div>

          <div class="grid form-grid">
            <div class="panel">
              <h2>综测计算口径</h2>
              <div v-for="item in templates?.dimensions" :key="item.key" class="rule-row">
                <strong>{{ item.label }}</strong>
                <span>基本分 {{ item.base }} ｜ 附加分上限 {{ item.cap }} ｜ 权重 {{ Math.round(item.weight * 100) }}%</span>
              </div>
            </div>
            <div class="panel">
              <h2>材料模板</h2>
              <ol class="material-list">
                <li v-for="item in templates?.strict_materials" :key="item">{{ item }}</li>
              </ol>
              <p v-for="note in templates?.notes" :key="note" class="muted">{{ note }}</p>
            </div>
          </div>

          <div class="panel doc-list-panel">
            <h2>细则文档版本</h2>
            <div v-for="doc in ruleDocs" :key="doc.id" class="doc-row">
              <div>
                <strong>{{ doc.name }}</strong>
                <span>{{ doc.version }} ｜ {{ doc.is_active ? '当前使用' : '可切换' }}</span>
              </div>
              <div>
                <a :href="imgUrl(doc.file_url)" target="_blank">查看</a>
                <button v-if="!doc.is_active" class="btn-text" @click="activateRuleDocument(doc)">设为当前</button>
              </div>
            </div>
          </div>
        </section>
      </template>
      </section>
    </section>

    <el-dialog v-model="userEditorVisible" width="520px" class="user-edit-dialog">
      <template #header>
        <strong>{{ userEditForm.id ? '编辑用户' : '添加用户' }}</strong>
      </template>
      <div class="user-edit-body">
        <label>学号</label>
        <input v-model="userEditForm.student_id" :disabled="!!userEditForm.id" placeholder="请输入学号" />
        <label>姓名</label>
        <input v-model="userEditForm.name" placeholder="请输入姓名" />
        <template v-if="!userEditForm.id">
          <label>密码</label>
          <input v-model="userEditForm.password" placeholder="默认密码 000000" />
        </template>
        <label>院系</label>
        <input v-model="userEditForm.department" />
        <label>班级</label>
        <input v-model="userEditForm.class_name" placeholder="如：通信2101班" />
      </div>
      <template #footer>
        <el-button @click="userEditorVisible = false">取消</el-button>
        <el-button type="primary" @click="saveAdminUser">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetPasswordVisible" width="420px">
      <template #header>
        <strong>重置密码</strong>
      </template>
      <div class="user-edit-body">
        <p class="muted">为用户「{{ resetPasswordForm.name }}」重置密码</p>
        <label>新密码</label>
        <input v-model="resetPasswordForm.password" />
      </div>
      <template #footer>
        <el-button @click="resetPasswordVisible = false">取消</el-button>
        <el-button type="primary" @click="resetAdminPassword">确认重置</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="userItemsVisible" width="760px">
      <template #header>
        <strong>综测项目 - {{ selectedAdminUser?.name }}（{{ selectedAdminUser?.student_id }}）</strong>
      </template>
      <div class="admin-user-items">
        <p class="muted">共 {{ selectedAdminUserItems.length }} 项 · 总分 {{ adminUserItemTotalScore }}</p>
        <div v-if="!selectedAdminUserItems.length" class="admin-users-empty">该用户暂无综测项目</div>
        <div v-for="item in selectedAdminUserItems" :key="item.id" class="admin-user-item-row">
          <strong>{{ item.title }}</strong>
          <span>{{ item.category_name || '-' }}</span>
          <span>{{ item.level || '-' }}</span>
          <em>+{{ item.score }}</em>
          <span>{{ userItemSourceLabel(item.source) }}</span>
          <button class="danger" @click="deleteAdminUserItem(item)">删除</button>
        </div>
      </div>
    </el-dialog>

    <el-dialog :model-value="!!selectedOpportunity" width="760px" class="detail-dialog" @close="selectedOpportunity = null">
      <template #header>
        <strong>{{ selectedOpportunity?.title }}</strong>
      </template>
      <div v-if="selectedOpportunity" class="detail-body">
        <img
          v-if="opportunityImage(selectedOpportunity)"
          :src="opportunityImage(selectedOpportunity)"
          :alt="selectedOpportunity.title"
          class="detail-cover"
          @error="markOpportunityImageBroken(selectedOpportunity)"
        />
        <div v-else :class="['detail-cover-fallback', opportunityFallbackClass(selectedOpportunity)]">
          <span>{{ opportunityFallbackKeyword(selectedOpportunity) }}</span>
          <strong>{{ opportunityFallbackTitle(selectedOpportunity) }}</strong>
        </div>
        <p>{{ selectedOpportunity.description }}</p>
        <div class="detail-grid">
          <span>组织单位：{{ selectedOpportunity.organizer || '待通知' }}</span>
          <span>时间：{{ selectedOpportunity.start_time || selectedOpportunity.season_months || '待通知' }}</span>
          <span>截止：{{ selectedOpportunity.deadline || '待通知' }}</span>
          <span>地点：{{ selectedOpportunity.location || '待通知' }}</span>
        </div>
        <h3>报名与资料</h3>
        <div
          v-if="opportunityLinks(selectedOpportunity).length || opportunityAttachments(selectedOpportunity).length || selectedOpportunity.group_qr_url || visibleContactEmail(selectedOpportunity.contact_email)"
          class="link-list"
        >
          <a v-for="link in opportunityLinks(selectedOpportunity)" :key="link.label" :href="imgUrl(link.url)" target="_blank">{{ link.label }}</a>
          <a v-for="file in opportunityAttachments(selectedOpportunity)" :key="file.url" :href="imgUrl(file.url)" target="_blank">{{ file.name }}</a>
          <a v-if="selectedOpportunity.group_qr_url" :href="imgUrl(selectedOpportunity.group_qr_url)" target="_blank">群二维码/图片资料</a>
          <span v-if="visibleContactEmail(selectedOpportunity.contact_email)">邮箱：{{ visibleContactEmail(selectedOpportunity.contact_email) }}</span>
        </div>
        <p v-else class="muted">暂无可直接打开的官网、报名链接或附件。</p>
        <h3>材料要求</h3>
        <ul>
          <li v-for="req in selectedOpportunity.requirements" :key="req">{{ req }}</li>
        </ul>
        <h3>综测规则提示</h3>
        <p>{{ selectedOpportunity.credit_hint }}</p>
        <p class="muted">{{ selectedOpportunity.rule_ref }}</p>
        <el-button type="primary" @click="chooseForCert(selectedOpportunity); selectedOpportunity = null">用这个活动提交认证</el-button>
      </div>
    </el-dialog>

    <!-- ====== 星轨探索：提交认证弹窗 ====== -->
    <el-dialog v-model="showSubmitModal" width="620px" class="submit-cert-dialog" @close="closeSubmitModal">
      <template #header>
        <strong>提交认证</strong>
        <span class="dialog-subtitle">{{ submitModalItem?.title }}</span>
      </template>

      <!-- 未提交状态 -->
      <div v-if="!submitModalSubmitted" class="submit-cert-body">

        <!-- 认证项信息（只读，来自catalog） -->
        <div class="submit-cert-section">
          <h4>认证项目</h4>
          <div class="cert-info-cards">
            <div class="cert-info-item">
              <span>项目名称</span>
              <strong>{{ submitModalItem?.title }}</strong>
            </div>
            <div class="cert-info-item">
              <span>评价维度</span>
              <strong>{{ submitForm.dimension === 'moral' ? '思想品德' : submitForm.dimension === 'academic' ? '学业表现' : submitForm.dimension === 'arts_sports' ? '文体表现' : submitForm.dimension }}</strong>
            </div>
            <div class="cert-info-item">
              <span>获奖/认证等级</span>
              <strong>{{ submitForm.award_level || submitModalItem?.level }}</strong>
            </div>
            <div class="cert-info-item">
              <span>预估加分</span>
              <strong class="cert-score">+{{ submitForm.score_estimate || submitModalItem?.score }} 分</strong>
            </div>
            <div class="cert-info-item">
              <span>当前适用细则</span>
              <strong class="cert-rule-ref">{{ activeRuleDoc?.name || '2025年7月电信学院综测细则（公示版）' }}</strong>
            </div>
            <label class="cert-info-item cert-date-pick">
              <span>完成/获证日期（选填）</span>
              <el-date-picker v-model="submitForm.completion_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" size="small" style="width:100%" />
            </label>
          </div>
        </div>

        <!-- 上传证明材料 -->
        <div class="submit-cert-section">
          <h4>上传证明材料</h4>
          <label class="cert-upload-zone" @dragover.prevent @drop.prevent="(e) => { e.preventDefault(); const dt = (e as DragEvent).dataTransfer; if (dt) { const dropped = Array.from(dt.files).filter((f: any) => { const ext = (f.name as string).split('.').pop()?.toLowerCase() || ''; return ['jpg','jpeg','png','bmp','webp','gif','pdf','doc','docx'].includes(ext) }); const ex = submitModalFiles; const nf = dropped.filter((f: any) => !ex.some((ef: any) => ef.name === f.name && ef.size === f.size)); if (nf.length) submitModalFiles = [...ex, ...nf] } }">
            <input type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.webp,.pdf,.doc,.docx" @change="handleSubmitModalFileSelect" />
            <strong>点击或拖拽文件到此处</strong>
            <span>支持 JPG、PNG、PDF、DOCX 格式</span>
          </label>
          <div v-if="submitModalFiles.length" class="cert-file-list">
            <div v-for="(f, i) in submitModalFiles" :key="`${f.name}-${i}`" class="cert-file-item">
              <b>{{ materialFileIcon(f.name) }}</b>
              <span>{{ f.name }}</span>
              <small>{{ (f.size / 1024).toFixed(1) }} KB</small>
              <button @click="removeSubmitModalFile(i)">x</button>
            </div>
          </div>
        </div>

        <!-- 底部操作栏：AI分析（左下角）+ 提交（右下角） -->
        <div class="submit-cert-actions">
          <div class="cert-actions-left">
            <button
              class="cert-ai-sm-btn"
              :disabled="!submitModalFiles.length || submitModalAnalyzing"
              @click="submitModalAnalyze"
            >
              <span v-if="submitModalAnalyzing">⏳ 分析中...</span>
              <span v-else-if="submitModalAnalyzed">🔄 重新分析</span>
              <span v-else>🤖 AI 审核</span>
            </button>
            <!-- AI 置信率小环（分析完成后显示在按钮旁） -->
            <div v-if="submitModalAnalyzed" :class="['cert-conf-inline', submitModalConfidence >= 85 ? 'conf-high' : submitModalConfidence >= 60 ? 'conf-medium' : 'conf-low']">
              <span class="cert-inline-value">{{ Math.round(submitModalConfidence) }}%</span>
              <span class="cert-inline-label">AI置信率</span>
            </div>
          </div>
          <div class="cert-actions-right">
            <el-button @click="closeSubmitModal">取消</el-button>
            <button
              class="cert-submit-btn"
              :disabled="submitModalSubmitting || !submitModalServerFiles.length"
              @click="submitModalSubmit"
            >
              {{ submitModalSubmitting ? '提交中...' : '提交审核' }}
            </button>
          </div>
        </div>

        <!-- AI 匹配详情（折叠，分析完成后显示） -->
        <details v-if="submitModalAnalyzed && submitModalAnalysisResult?.matches?.length" class="cert-match-details">
          <summary>AI 审核详情 — 匹配到 {{ submitModalAnalysisResult.matches.length }} 个综测项目</summary>
          <div class="cert-match-list">
            <div v-for="match in submitModalAnalysisResult.matches.slice(0, 5)" :key="match.id" class="cert-match-item">
              <div class="cert-match-head">
                <strong>{{ match.title }}</strong>
                <span :class="['cert-conf-pill', matchConfidenceClass(match.confidence)]">{{ Math.round(match.confidence) }}%</span>
              </div>
              <p class="cert-match-reason">{{ match.reason }}</p>
              <div class="cert-match-meta">
                <span>{{ match.category_name || match.category }}</span>
                <span>{{ match.level }}</span>
                <em>+{{ match.score }}分</em>
              </div>
            </div>
          </div>
          <details v-if="submitModalAnalysisResult.extracted_text" class="cert-extracted-text" style="margin-top:8px">
            <summary>AI 提取的文本内容</summary>
            <pre>{{ submitModalAnalysisResult.extracted_text.slice(0, 500) }}</pre>
          </details>
        </details>
      </div>

      <!-- 提交成功状态 -->
      <div v-else class="submit-cert-success">
        <div class="cert-success-icon">&#10003;</div>
        <h3>提交成功</h3>
        <p>您的认证材料已提交，AI 审核置信率 {{ Math.round(submitModalConfidence) }}%，管理员将进行最终审核并入账。</p>
        <el-button type="primary" @click="closeSubmitModal">完成</el-button>
      </div>
    </el-dialog>

    <el-dialog v-model="honorEditorVisible" width="520px" class="honor-edit-dialog">
      <template #header>
        <strong>编辑荣誉展示</strong>
      </template>
      <div class="honor-edit-body">
        <img v-if="honorEditForm.image_url" :src="imgUrl(honorEditForm.image_url)" alt="" />
        <el-input v-model="honorEditForm.title" placeholder="荣誉标题" />
        <el-select v-model="honorEditForm.category">
          <el-option label="证书" value="证书" />
          <el-option label="竞赛" value="竞赛" />
          <el-option label="活动" value="活动" />
          <el-option label="照片" value="照片" />
        </el-select>
        <label class="proof-upload-box compact">
          <input type="file" accept=".jpg,.jpeg,.png,.webp" @change="replaceHonorImage" />
          <strong>替换图片</strong>
          <span>选择新图片后再保存</span>
        </label>
      </div>
      <template #footer>
        <el-button type="danger" plain @click="deleteHonor">移除</el-button>
        <el-button @click="honorEditorVisible = false">取消</el-button>
        <el-button type="primary" @click="saveHonorEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- ====== 学业成绩录入弹窗 ====== -->
    <el-dialog v-model="showGradeModal" width="780px" class="grade-input-dialog" :close-on-click-modal="false" @close="closeGradeModal">
      <template #header>
        <strong>学业成绩录入</strong>
        <span class="grade-year-badge">📅 {{ gradeModalYear }} 学年</span>
      </template>

      <div v-if="!gradeModalSaved" class="grade-modal-body">

        <!-- 成绩单上传识别区 -->
        <div class="grade-ocr-section">
          <h4>上传成绩单自动识别（可选）</h4>
          <label class="cert-upload-zone" style="margin-bottom:6px;"
            @dragover.prevent @drop.prevent="(e) => { e.preventDefault(); const dt = e.dataTransfer; if (dt?.files) handleGradeModalFileSelect({ target: { files: dt.files, value: '' } } as any) }">
            <input type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.webp" style="display:none;" @change="handleGradeModalFileSelect" />
            <strong>📎 点击或拖拽成绩单截图</strong>
            <span>支持 JPG、PNG 格式，将自动 OCR 识别课程和成绩</span>
          </label>
          <div v-if="gradeModalUploadFiles.length" class="cert-file-list">
            <div v-for="(f, i) in gradeModalUploadFiles" :key="i" class="cert-file-item">
              <b>IMG</b>
              <span>{{ f.name }}</span>
              <small>{{ (f.size / 1024).toFixed(1) }} KB</small>
              <button @click="removeGradeModalFile(i)">x</button>
            </div>
          </div>
          <button v-if="gradeModalUploadFiles.length && !gradeModalOcrDone"
            class="cert-ai-sm-btn" :disabled="gradeModalOcrLoading"
            @click="gradeModalOcrAnalyze" style="margin-top:8px;">
            <span v-if="gradeModalOcrLoading">⏳ OCR识别中...</span>
            <span v-else>🤖 OCR识别</span>
          </button>
        </div>

        <!-- OCR识别结果 -->
        <div v-if="gradeModalOcrDone && gradeModalOcrResults.length" class="grade-ocr-results">
          <h4>OCR识别结果 <span class="grade-course-count">({{ gradeModalOcrResults.length }} 门)</span></h4>
          <div v-for="(ocr, i) in gradeModalOcrResults" :key="i" class="grade-ocr-row">
            <el-checkbox v-model="ocr.selected" />
            <span class="gor-name">{{ ocr.course_name }}</span>
            <span class="gor-grade">{{ ocr.grade }}分</span>
            <span class="gor-credit">{{ ocr.credits }}学分</span>
            <span class="gor-type">{{ ocr.course_type }}</span>
            <span :class="['gor-conf', ocr.confidence >= 0.8 ? 'text-green' : ocr.confidence >= 0.6 ? 'text-amber' : 'text-red']">置信度 {{ Math.round(ocr.confidence * 100) }}%</span>
          </div>
          <button class="btn-ghost" @click="addOcrCoursesToList" style="margin-top:8px;">将选中课程加入列表</button>
        </div>

        <!-- 课程列表 -->
        <div class="grade-courses-section">
          <h4>课程成绩 <span class="grade-course-count">({{ gradeModalCourses.length }} 门)</span></h4>
          <div class="grade-course-header">
            <span class="gch-name">课程名称</span>
            <span class="gch-grade">成绩</span>
            <span class="gch-credit">学分</span>
            <span class="gch-type">课程类型</span>
            <span class="gch-action"></span>
          </div>
          <div v-if="!gradeModalCourses.length" class="grade-empty-hint">暂无课程，请手动添加或上传成绩单自动识别</div>
          <div v-for="course in gradeModalCourses" :key="course.key" class="grade-course-row">
            <input v-model="course.course_name" class="grade-input name" placeholder="如：高等数学" @input="updateGradeComputation" />
            <input v-model.number="course.grade" type="number" min="0" max="100" class="grade-input num" placeholder="0-100" @input="updateGradeComputation" />
            <input v-model.number="course.credits" type="number" min="0.5" max="15" step="0.5" class="grade-input num" placeholder="学分" @input="updateGradeComputation" />
            <select v-model="course.course_type" class="grade-select" @change="updateGradeComputation">
              <option value="必修">必修</option>
              <option value="限选">限选</option>
              <option value="任选">任选</option>
              <option value="公选">公选</option>
            </select>
            <button class="grade-remove-btn" @click="removeGradeCourse(course.key)" title="删除">✕</button>
          </div>
          <button class="grade-add-btn" @click="addGradeCourse">+ 添加科目</button>
        </div>

        <!-- 实时计算面板 -->
        <div v-if="gradeComputation" class="grade-computation-panel">
          <h4>实时计算</h4>
          <div class="grade-comp-grid">
            <div class="grade-comp-item">
              <span>加权平均分</span>
              <strong>{{ gradeComputation.weighted_average }}</strong>
            </div>
            <div class="grade-comp-item">
              <span>学业基本分（满分80）</span>
              <strong>{{ gradeComputation.academic_base_score }}</strong>
            </div>
            <div class="grade-comp-item">
              <span>GPA加分</span>
              <strong :class="gradeComputation.gpa_bonus > 0 ? 'text-green' : ''">
                {{ gradeComputation.gpa_bonus > 0 ? '+' + gradeComputation.gpa_bonus : '0' }}
              </strong>
            </div>
            <div class="grade-comp-item">
              <span>必修限选均分</span>
              <strong>{{ gradeComputation.required_courses_avg ?? '—' }}</strong>
            </div>
            <div class="grade-comp-item">
              <span>必修限选最低分</span>
              <strong :class="!gradeComputation.all_required_pass ? 'text-red' : ''">
                {{ gradeComputation.required_min_grade ?? '—' }}
              </strong>
            </div>
            <div class="grade-comp-item wide">
              <span>GPA加分档位</span>
              <strong :class="gradeComputation.gpa_bonus > 0 ? 'text-green' : ''">
                {{ gradeComputation.gpa_tier || '未达标' }}
              </strong>
            </div>
          </div>
        </div>

        <!-- 错误提示 -->
        <div v-if="gradeModalError" class="grade-error-msg">{{ gradeModalError }}</div>
      </div>

      <!-- 保存成功状态 -->
      <div v-else class="submit-cert-success">
        <div class="cert-success-icon">&#10003;</div>
        <h3>成绩已保存</h3>
        <p v-if="gradeComputation">{{ gradeModalYear }} 学年共 {{ gradeModalCourses.length }} 门课程，加权平均分 {{ gradeComputation.weighted_average }}，学业基本分 {{ gradeComputation.academic_base_score }}，GPA 加分 {{ gradeComputation.gpa_bonus > 0 ? '+' + gradeComputation.gpa_bonus : '0' }}。</p>
        <el-button type="primary" @click="closeGradeModal">完成</el-button>
      </div>

      <template v-if="!gradeModalSaved" #footer>
        <el-button @click="closeGradeModal">取消</el-button>
        <button class="cert-submit-btn" :disabled="gradeModalSaving || !gradeModalCourses.length" @click="saveGradeCourses">
          {{ gradeModalSaving ? '保存中...' : '💾 保存成绩' }}
        </button>
      </template>
    </el-dialog>
  </main>
</template>
