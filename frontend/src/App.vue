<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { api, API_BASE, patchJson, postJson } from './api/client'
import { useAppStore } from './stores/app'

type DimensionKey = 'moral' | 'academic' | 'arts_sports'
type OpportunitySource = 'notice' | 'evergreen'

interface Opportunity {
  id: number
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
}

interface BasketItem {
  id: number
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
}

interface AnalyzeResult {
  file_id: number
  filename: string
  extracted_text: string
  has_text_content: boolean
  matches: AnalyzeMatch[]
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

const store = useAppStore()
const route = useRoute()
const router = useRouter()

const studentTabs = ['星盘总览', '机会大厅', '备赛清单', '星轨探索', '智审中心', '荣誉星墙']
const adminTabs = ['数据看板', '用户管理', '活动/比赛发布', '综测审核中心', '规则与材料模板']
const activeStudentTab = ref('星盘总览')
const activeAdminTab = ref('数据看板')
const opportunityMode = ref<OpportunitySource>('notice')
const auditQueue = ref('')

const loading = ref(false)
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
const catalogQuery = reactive({ category: '', level: '', section: '', subcategory: '', keyword: '' })
const selectedOpportunity = ref<Opportunity | null>(null)
const selectedDashboardApplication = ref<ApplicationItem | null>(null)
const selectedAdminUser = ref<AdminUser | null>(null)
const selectedAdminUserItems = ref<AdminUserItem[]>([])
const userEditorVisible = ref(false)
const resetPasswordVisible = ref(false)
const userItemsVisible = ref(false)
const draggedHonorId = ref<number | null>(null)
const brokenOpportunityImages = ref<Set<number>>(new Set())

const filters = reactive({
  dimension: '',
  keyword: '',
})

const materialParsing = ref(false)
const materialSubmitMode = ref<'match' | 'targeted'>('match')
const materialSelectedFiles = ref<File[]>([])
const materialServerFiles = ref<UploadedFile[]>([])
const materialAnalysisResults = ref<AnalyzeResult[]>([])
const materialAddedItems = ref<Array<{ id: string; fileId: number; filename: string; title: string; category: string; category_name?: string; level: string; score: number; confidence: number; status: string }>>([])
const materialExtraKeyword = ref('')
const targetCatalogQuery = reactive({ category: '', level: '', keyword: '' })
const selectedTargetItem = ref<CatalogExplorerItem | null>(null)
const targetRequiredProofs = ref<Array<{ type: string; name: string; description: string }>>([])
const targetProofFiles = ref<Record<string, UploadedFile | null>>({})
const targetCompletionDate = ref('')
const targetAiVerifyResult = ref('')

const honorForm = reactive({ title: '', category: '证书', image_url: '' })
const honorDropOver = ref(false)
const honorEditorVisible = ref(false)
const honorEditForm = reactive({ id: 0, title: '', category: '证书', image_url: '', visibility: 'private' })
const publishForm = reactive({
  source_type: 'notice' as OpportunitySource,
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
    if (filters.keyword && !item.title.includes(filters.keyword.trim())) return false
    return true
  })
})

const opportunityCounts = computed(() => ({
  notice: opportunities.value.filter(item => item.source_type === 'notice').length,
  evergreen: opportunities.value.filter(item => item.source_type === 'evergreen').length,
}))

const completedScoreItems = computed(() => {
  return (summary.value?.ledgers || []).map(item => ({
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

function switchTab(tab: string) {
  if (store.roleMode === 'student') activeStudentTab.value = tab
  else {
    activeAdminTab.value = tab
    if (tab === '用户管理' && canViewAdmin.value) loadAdminUsers()
  }
}

function switchRole(role: 'student' | 'admin') {
  if (role === 'admin' && !canViewAdmin.value) return
  store.switchRole(role)
  router.push(role === 'admin' ? '/admin' : '/student')
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
  if (text.includes('志愿') || text.includes('义务劳动')) return '志愿活动'
  if (text.includes('军训')) return '荣誉称号'
  if (text.includes('文明宿舍')) return '文明宿舍'
  if (text.includes('电子设计') || text.includes('蓝桥杯') || text.includes('竞赛')) return '学科竞赛'
  if (text.includes('证书')) return '专业证书'
  if (text.includes('论文')) return '学术论文'
  if (text.includes('主持') || text.includes('诗歌节') || text.includes('文体') || text.includes('活动')) return '参加活动'
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
      rule_ref: row.section || '',
      recommendation: row.review_remarks || row.ai_reason || (confidence >= 0.85 ? 'AI 建议通过，等待人工复核。' : '建议人工复核材料。'),
    },
    ai_confidence: confidence,
    risk_tags: [
      confidence >= 0.85 ? 'AI高置信' : confidence < 0.7 ? '需人工复核' : '待人工确认',
      ...(missing.length ? ['材料缺失'] : []),
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

const coverImages = [
  'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1531482615713-2afd69097998?auto=format&fit=crop&w=900&q=80',
]

const officialOpportunityImages = [
  { keys: ['电子设计竞赛'], url: '/competition-covers/nuedc.png' },
  { keys: ['蓝桥杯'], url: 'https://assets.lanqiao.cn/lanqiaobei-fe/v8.5.3/dist/favico.png' },
  { keys: ['计算机设计大赛'], url: 'https://jsjds.blcu.edu.cn/images/banner11.PNG' },
  { keys: ['数学建模'], url: 'https://www.mcm.edu.cn/theme/mcm/image/top_cn.jpg' },
  { keys: ['嵌入式芯片'], url: '' },
  { keys: ['集成电路'], url: 'https://univ.ciciec.com/favicon.ico' },
  { keys: ['物联网'], url: 'https://iot.sjtu.edu.cn/favicon.ico' },
  { keys: ['智能汽车'], url: 'https://www.smartcarrace.com/favicon.ico' },
  { keys: ['RoboMaster', '机甲大师'], url: 'https://rm-static.djicdn.com/documents/55708/6d77a3be8b2431741835508145145792.png' },
  { keys: ['华为 ICT'], url: 'https://r-h2.huaweistatic.com/s/hwtalent/lst/huawei.png' },
  { keys: ['信息安全'], url: 'https://www.ciscn.cn/uploads/banner/2025-banner.jpg' },
  { keys: ['创新大赛'], url: 'https://t4.chei.com.cn/ncss/student/img/gp-logo.png' },
  { keys: ['挑战杯'], url: '' },
  { keys: ['大创', '创新创业训练'], url: 'https://gjcxcy.bjtu.edu.cn/favicon.ico' },
]

const honorPresets = [
  { variant: 'honor-gold', brand: 'NCIETCC', type: 'CERTIFICATE', award: '一等奖', subject: '英语翻译挑战赛', date: '2026.01', seal: '荣誉证书' },
  { variant: 'honor-blue', brand: 'Bebras', type: 'PARTICIPATION', award: '优秀', subject: '信息思维挑战', date: '2023', seal: '思维挑战' },
  { variant: 'honor-red', brand: 'HUAWEI', type: 'CERTIFICATION', award: 'HCIA-AI', subject: '人工智能认证', date: '2028.11', seal: 'AI' },
  { variant: 'honor-green', brand: '929 Challenge', type: 'CERTIFICATE', award: 'Top 50', subject: '创业挑战赛', date: '2025.11', seal: '创业' },
  { variant: 'honor-photo', brand: 'Challenge Cup', type: 'SHOWCASE', award: '院赛展示', subject: '创新创业项目', date: '2025.10', seal: '科创' },
]

function opportunityImage(item: Opportunity) {
  if (brokenOpportunityImages.value.has(item.id)) return ''
  if (item.images?.length) return imgUrl(item.images[0])
  const official = officialOpportunityImages.find(entry => entry.keys.some(key => item.title.includes(key)))
  if (official) return official.url ? official.url : ''
  if (item.source_type === 'notice') return coverImages[0]
  return coverImages[item.id % coverImages.length]
}

function opportunityFallbackClass(item: Opportunity) {
  if (item.title.includes('嵌入式') || item.title.includes('芯片')) return 'fallback-chip'
  if (item.title.includes('挑战杯')) return 'fallback-challenge'
  if (item.title.includes('智能汽车')) return 'fallback-smartcar'
  if (item.title.includes('数学建模')) return 'fallback-math'
  if (item.title.includes('电子')) return 'fallback-electronic'
  return 'fallback-default'
}

function opportunityFallbackTitle(item: Opportunity) {
  return item.title.replace('全国大学生', '全国大学生\n').replace('中国大学生', '中国大学生\n')
}

function markOpportunityImageBroken(item: Opportunity) {
  brokenOpportunityImages.value = new Set([...brokenOpportunityImages.value, item.id])
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
  const [catalogData, userItems, submissions] = await Promise.all([
    api<{ items: CatalogExplorerItem[]; filters: CatalogFilters }>('/catalog'),
    api<{ items: Array<{ catalog_item_id?: string }> }>('/user-items'),
    api<{ submissions: Array<{ catalog_item_id?: string; status: string }> }>('/submissions'),
  ])
  catalogItems.value = catalogData.items || []
  catalogFilters.value = catalogData.filters || { categories: [], levels: [], subcategories: [], sections: [] }
  const ids = new Set<string>()
  for (const item of userItems.items || []) {
    if (item.catalog_item_id) ids.add(item.catalog_item_id)
  }
  for (const item of submissions.submissions || []) {
    if (item.catalog_item_id && ['pending', 'auto_approved', 'approved'].includes(item.status)) {
      ids.add(item.catalog_item_id)
    }
  }
  submittedCatalogIds.value = ids
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

async function addCatalogItem(item: CatalogExplorerItem) {
  try {
    await postJson('/user-items', {
      catalog_item_id: item.id,
      source: 'manual',
    })
    submittedCatalogIds.value = new Set([...submittedCatalogIds.value, item.id])
    ElMessage.success(`已添加「${item.title}」到我的星轨`)
    await loadAll()
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
  try {
    const [summaryData, opps, basketData, appData, honorData, templateData, docsData] = await Promise.all([
      api<DashboardSummary>(`/dashboard/summary?user_id=${store.studentId}`),
      api<Opportunity[]>(`/opportunities?user_id=${store.studentId}`),
      api<BasketItem[]>(`/plan-basket?user_id=${store.studentId}`),
      api<{ submissions: any[] }>('/submissions'),
      api<HonorItem[]>(`/honor-wall?user_id=${store.studentId}`),
      api<TemplateData>('/material-templates'),
      api<RuleDocument[]>('/rule-documents'),
    ])
    summary.value = summaryData
    opportunities.value = opps
    basket.value = basketData
    applications.value = (appData.submissions || []).map(mapSubmissionToApplication)
    honors.value = honorData
    templates.value = templateData
    ruleDocs.value = docsData
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
watch(activeStudentTab, tab => { if (tab === '星盘总览') nextTick(renderCharts) })

async function addToBasket(opportunity: Opportunity) {
  await postJson('/plan-basket', {
    user_id: store.studentId,
    opportunity_id: opportunity.id,
    stage: '想参加',
  })
  ElMessage.success('已加入备赛清单')
  await loadAll()
}

async function updateBasket(item: BasketItem) {
  await patchJson(`/plan-basket/${item.id}`, { stage: item.stage, note: item.note })
  ElMessage.success('备赛状态已更新')
  await loadAll()
}

async function removeBasket(item: BasketItem) {
  await api(`/plan-basket/${item.id}`, { method: 'DELETE' })
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
  await postJson('/honor-wall', { user_id: store.studentId, ...honorForm })
  honorForm.title = ''
  honorForm.image_url = ''
  await loadAll()
}

async function addHonorFiles(files: File[]) {
  const images = files.filter(file => file.type.startsWith('image/'))
  if (!images.length) return
  for (const file of images) {
    const result = await uploadSingleFile(file)
    await postJson('/honor-wall', {
      user_id: store.studentId,
      title: honorForm.title.trim() || cleanFileTitle(file.name),
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
  await addHonorFiles(Array.from(input.files || []))
  input.value = ''
}

async function onHonorPageDrop(event: DragEvent) {
  event.preventDefault()
  honorDropOver.value = false
  await addHonorFiles(Array.from(event.dataTransfer?.files || []))
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
    title: honorEditForm.title,
    category: honorEditForm.category,
    image_url: honorEditForm.image_url,
    visibility: honorEditForm.visibility,
  })
  honorEditorVisible.value = false
  ElMessage.success('荣誉信息已更新')
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
    patchJson(`/honor-wall/${from.id}`, { sort_order: target.sort_order }),
    patchJson(`/honor-wall/${target.id}`, { sort_order: fromOrder }),
  ])
  draggedHonorId.value = null
  await loadAll()
}

function selectDashboardApplication(item: ApplicationItem) {
  selectedDashboardApplication.value = item
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
    roi_score: publishForm.source_type === 'evergreen' ? 4.2 : 3.8,
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

function handleMaterialSubmitFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  materialSelectedFiles.value = Array.from(input.files || []).filter(file => {
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    return ['jpg', 'jpeg', 'png', 'bmp', 'webp', 'gif', 'pdf', 'doc', 'docx'].includes(ext)
  })
  materialAnalysisResults.value = []
  materialServerFiles.value = []
  input.value = ''
}

function onMaterialSubmitDrop(event: DragEvent) {
  event.preventDefault()
  materialSelectedFiles.value = Array.from(event.dataTransfer?.files || []).filter(file => {
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    return ['jpg', 'jpeg', 'png', 'bmp', 'webp', 'gif', 'pdf', 'doc', 'docx'].includes(ext)
  })
  materialAnalysisResults.value = []
  materialServerFiles.value = []
}

function removeMaterialSelectedFile(index: number) {
  materialSelectedFiles.value.splice(index, 1)
}

function matchConfidenceClass(value: number) {
  if (value >= 80) return 'conf-high'
  if (value >= 40) return 'conf-medium'
  return 'conf-low'
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
    materialAnalysisResults.value = analysis.results || []
    ElMessage.success(`AI分析完成，共匹配 ${materialAnalysisResults.value.reduce((sum, item) => sum + item.matches.length, 0)} 个综测项目`)
  } catch (error) {
    ElMessage.error(`AI分析失败：${(error as Error).message}`)
  } finally {
    materialParsing.value = false
  }
}

async function submitMatchedMaterial(result: AnalyzeResult, match: AnalyzeMatch) {
  try {
    const response = await postJson<{ status: string; proofs_complete?: boolean }>('/submissions', {
      catalog_item_id: match.id,
      uploaded_file_ids: [result.file_id],
      ai_confidence: match.confidence,
      ai_decision: match.decision || (match.confidence >= 80 ? 'high' : 'medium'),
      ai_reason: match.reason || '',
    })
    materialAddedItems.value.push({
      id: match.id,
      fileId: result.file_id,
      filename: result.filename,
      title: match.title,
      category: match.category,
      category_name: match.category_name,
      level: match.level,
      score: match.score,
      confidence: match.confidence,
      status: response.status,
    })
    ElMessage.success(response.status === 'auto_approved' ? 'AI自动通过，已写入我的星轨' : '已提交审核，管理端会收到这条材料')
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

async function submitTargetedMaterial() {
  if (!selectedTargetItem.value) {
    ElMessage.warning('请先选择综测项目')
    return
  }
  const uploadedIds = Object.values(targetProofFiles.value).filter(Boolean).map(file => file?.id).filter(Boolean) as number[]
  if (!uploadedIds.length) {
    ElMessage.warning('请至少上传一份证明材料')
    return
  }
  materialParsing.value = true
  try {
    let aiConfidence = 60
    let aiDecision = 'medium'
    let aiReason = ''
    const verify = await api<{ results: AnalyzeResult[] }>('/analyze', {
      method: 'POST',
      body: JSON.stringify({
        uploaded_file_ids: uploadedIds,
        keyword: selectedTargetItem.value.title,
      }),
    })
    for (const result of verify.results || []) {
      for (const match of result.matches || []) {
        if (match.id === selectedTargetItem.value.id && match.confidence > aiConfidence) {
          aiConfidence = match.confidence
          aiReason = match.reason || ''
        }
      }
    }
    aiDecision = aiConfidence >= 80 ? 'high' : aiConfidence >= 40 ? 'medium' : 'low'
    const response = await postJson<{ status: string; proofs_complete?: boolean }>('/submissions', {
      catalog_item_id: selectedTargetItem.value.id,
      uploaded_file_ids: uploadedIds,
      completion_date: targetCompletionDate.value,
      ai_confidence: aiConfidence,
      ai_decision: aiDecision,
      ai_reason: aiReason,
    })
    targetAiVerifyResult.value = `AI置信度 ${aiConfidence.toFixed(1)}%，${response.status === 'auto_approved' ? '已自动通过' : '已进入管理端待审核'}`
    ElMessage.success(response.status === 'auto_approved' ? 'AI自动通过，已写入我的星轨' : '已提交审核，管理端会收到这条材料')
    await loadAll()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    materialParsing.value = false
  }
}

async function loadAdminQueue() {
  const statusMap: Record<string, string> = {
    high_confidence: '',
    needs_more: 'pending',
    risk: 'pending',
    approved: 'approved',
    rejected: 'rejected',
  }
  const status = statusMap[auditQueue.value] ?? auditQueue.value
  const data = await api<{ submissions: any[] }>(`/admin/submissions?per_page=200${status ? `&status=${status}` : ''}`)
  let rows = (data.submissions || []).map(mapSubmissionToApplication)
  if (auditQueue.value === 'high_confidence') rows = rows.filter(item => item.ai_confidence >= 0.85 && item.status === 'pending_human')
  if (auditQueue.value === 'risk') rows = rows.filter(item => item.ai_confidence < 0.7 || item.status === 'needs_more')
  if (auditQueue.value === 'needs_more') rows = rows.filter(item => item.status === 'pending_human' && item.ai_confidence < 0.85)
  adminApplications.value = orderAuditRows(rows)
}

async function decide(app: ApplicationItem, decision: 'approved' | 'rejected' | 'needs_more') {
  const score = decision === 'approved' ? Number(app.suggested_score || 0) : undefined
  await api(`/admin/submissions/${app.id}`, {
    method: 'PUT',
    body: JSON.stringify({
    action: decision === 'approved' ? 'approve' : 'reject',
    score,
    comment: decision === 'approved' ? '人工复核通过，写入综测流水。' : decision === 'needs_more' ? '请补齐学校/学院通知、参赛名单或官方结果证明。' : '材料与细则不匹配，驳回。',
    remarks: decision === 'approved' ? '人工复核通过，写入综测流水。' : decision === 'needs_more' ? '请补齐学校/学院通知、参赛名单或官方结果证明。' : '材料与细则不匹配，驳回。',
    rule_ref: app.ai_review?.rule_ref || '',
    }),
  })
  ElMessage.success('审核结果已保存')
  await loadAll()
}

onMounted(loadAll)
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

      <div class="role-switch">
        <button v-if="canViewAdmin" :class="{ active: store.roleMode === 'admin' }" @click="switchRole('admin')">管理端</button>
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
              :class="{ selected: submittedCatalogIds.has(item.id) }"
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
                <button v-else class="btn-primary-sm" @click="addCatalogItem(item)">+ 添加</button>
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
            <button :class="{ active: opportunityMode === 'notice' }" @click="opportunityMode = 'notice'">
              近期通知 <span>{{ opportunityCounts.notice }}</span>
            </button>
            <button :class="{ active: opportunityMode === 'evergreen' }" @click="opportunityMode = 'evergreen'">
              常驻赛事 <span>{{ opportunityCounts.evergreen }}</span>
            </button>
          </div>

          <div class="toolbar hall-toolbar">
            <el-input v-model="filters.keyword" placeholder="搜索比赛、活动、证书" clearable />
            <el-select v-model="filters.dimension" placeholder="综测归属" clearable>
              <el-option label="德育" value="moral" />
              <el-option label="学业" value="academic" />
              <el-option label="文体" value="arts_sports" />
            </el-select>
          </div>

          <div class="section-header">
            <h2>{{ opportunityMode === 'notice' ? '学院/学校近期通知' : '电子信息方向常驻备赛库' }}</h2>
            <p>{{ opportunityMode === 'notice' ? '只展示近期由学校或学院发布的活动通知。' : '不等通知也能提前准备的长期赛事。最终能否加分仍以细则和通知审核为准。' }}</p>
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
                  <span>{{ item.category }}</span>
                  <strong>{{ opportunityFallbackTitle(item) }}</strong>
                </div>
                <span class="image-tag">{{ item.category }}</span>
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
                      {{ item.in_basket ? '已加入' : '加入备赛清单' }}
                    </button>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section v-show="activeStudentTab === '备赛清单'" class="page-stack">
          <article v-for="item in basket" :key="item.id" class="basket-row">
            <img :src="opportunityImage(item.opportunity)" alt="" />
            <div>
              <span class="source">{{ item.opportunity.category }}</span>
              <h3>{{ item.opportunity.title }}</h3>
              <p>{{ item.opportunity.credit_hint }}</p>
            </div>
            <el-select v-model="item.stage" @change="updateBasket(item)">
              <el-option v-for="stage in ['想参加', '已报名', '备赛中', '材料待提交', '已结算']" :key="stage" :label="stage" :value="stage" />
            </el-select>
            <el-input v-model="item.note" placeholder="备赛备注" @change="updateBasket(item)" />
            <el-button text type="danger" @click="removeBasket(item)">移出</el-button>
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
                    <div>
                      <strong>{{ match.title }}</strong>
                      <p>{{ match.description }}</p>
                      <div class="source-match-badges">
                        <span>{{ match.category_name || match.category }}</span>
                        <span>{{ match.level }}</span>
                        <span>+{{ match.score }}分</span>
                      </div>
                    </div>
                    <div class="source-confidence">
                      <span :class="matchConfidenceClass(match.confidence)">{{ match.confidence.toFixed(1) }}%</span>
                      <button class="source-primary-small" :disabled="isMaterialAdded(result, match)" @click="submitMatchedMaterial(result, match)">
                        {{ isMaterialAdded(result, match) ? '已提交' : '提交审核' }}
                      </button>
                    </div>
                  </div>
                </article>
              </div>
            </div>
          </div>

          <div v-else class="targeted-submit-grid">
            <div class="source-card">
              <header>选择综测项目</header>
              <div class="target-filters">
                <select v-model="targetCatalogQuery.category">
                  <option value="">全部板块</option>
                  <option value="moral">品德行为</option>
                  <option value="academic">学业表现</option>
                  <option value="sports">文体表现</option>
                </select>
                <select v-model="targetCatalogQuery.level">
                  <option value="">全部级别</option>
                  <option value="国家级">国家级</option>
                  <option value="省级">省级</option>
                  <option value="校级">校级</option>
                  <option value="院级">院级</option>
                  <option value="班级">班级</option>
                </select>
                <input v-model="targetCatalogQuery.keyword" placeholder="输入项目名称关键词搜索..." />
              </div>
              <div class="target-results">
                <article
                  v-for="item in filteredTargetCatalogItems"
                  :key="item.id"
                  :class="['target-catalog-card', { active: selectedTargetItem?.id === item.id }]"
                  @click="selectTargetCatalogItem(item)"
                >
                  <strong>{{ item.title }}</strong>
                  <p>{{ item.description }}</p>
                  <span>{{ item.category_name }}</span>
                  <span>{{ item.level }}</span>
                  <b>+{{ item.score }}分</b>
                </article>
              </div>
            </div>

            <div class="source-card">
              <header>上传证明材料</header>
              <template v-if="selectedTargetItem">
                <div class="selected-target">
                  <strong>{{ selectedTargetItem.title }}</strong>
                  <span>+{{ selectedTargetItem.score }}分</span>
                </div>
                <div v-for="proof in targetRequiredProofs" :key="proof.type" class="target-proof-row">
                  <div>
                    <strong>{{ proof.name }}</strong>
                    <p>{{ proof.description }}</p>
                  </div>
                  <label>
                    <input type="file" accept=".jpg,.jpeg,.png,.bmp,.webp,.pdf,.doc,.docx" @change="event => handleTargetProofSelect(event, proof.type)" />
                    {{ targetProofFiles[proof.type]?.name || '上传' }}
                  </label>
                </div>
                <label class="target-date">
                  项目完成日期
                  <input v-model="targetCompletionDate" type="date" />
                </label>
                <p v-if="targetAiVerifyResult" class="target-ai-result">{{ targetAiVerifyResult }}</p>
                <button class="source-primary-btn" :disabled="materialParsing" @click="submitTargetedMaterial">
                  {{ materialParsing ? '提交中...' : '提交审核' }}
                </button>
              </template>
              <div v-else class="analysis-empty">
                <p>先在左侧选择要申报的综测项目</p>
              </div>
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
                <strong>点击或拖拽图片添加</strong>
                <span>上传后会立即出现在荣誉墙中</span>
              </label>
              <el-button type="primary" @click="createHonor">添加文字荣誉</el-button>
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

        <section v-show="activeAdminTab === '活动/比赛发布'" class="publish-page">
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
                <span class="ai-subtitle" v-if="!aiExpanded">{{ aiParsed ? '已解析，可继续核对表单' : '粘贴通知一键填表' }}</span>
                <span class="chevron">{{ aiExpanded ? '⌃' : '⌄' }}</span>
              </div>
            </button>

            <Transition name="slide">
              <div v-if="aiExpanded" class="ai-body">
                <p class="ai-hint">粘贴公众号文章、群通知或比赛通知，AI 帮你先自动填表，发布前必须人工核对。</p>
                <div class="form-row">
                  <label class="form-label">通知/公众号文章</label>
                  <textarea
                    v-model="aiNoticeText"
                    class="form-input form-textarea"
                    placeholder="粘贴活动通知、公众号文章正文或 OCR 后的文字内容..."
                    rows="4"
                  />
                </div>
                <div class="form-row">
                  <label class="form-label">群消息补充 <span class="optional">（选填）</span></label>
                  <textarea
                    v-model="aiGroupMessage"
                    class="form-input form-textarea"
                    placeholder="粘贴报名群、补充说明、转发文案等..."
                    rows="2"
                  />
                </div>
                <button class="btn-primary ai-parse-btn" :disabled="aiParsing || !aiNoticeText.trim()" @click="runAiParse">
                  {{ aiParsing ? '解析中...' : 'AI 智能解析' }}
                </button>
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
                        <option value="notice">近期通知</option>
                        <option value="evergreen">常驻赛事</option>
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
          <span>{{ selectedOpportunity.category }}</span>
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
        <el-button @click="honorEditorVisible = false">取消</el-button>
        <el-button type="primary" @click="saveHonorEdit">保存</el-button>
      </template>
    </el-dialog>
  </main>
</template>
