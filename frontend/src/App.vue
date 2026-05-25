<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
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

type UploadedFile = { name: string; url: string; type?: string }

const store = useAppStore()

const studentTabs = ['星盘总览', '机会大厅', '备赛清单', '智审中心', '荣誉星墙']
const adminTabs = ['数据看板', '活动/比赛发布', '综测审核中心', '规则与材料模板']
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
const selectedOpportunity = ref<Opportunity | null>(null)
const selectedDashboardApplication = ref<ApplicationItem | null>(null)
const draggedHonorId = ref<number | null>(null)
const brokenOpportunityImages = ref<Set<number>>(new Set())

const filters = reactive({
  dimension: '',
  keyword: '',
})

const certForm = reactive({
  opportunity_id: undefined as number | undefined,
  title: '',
  dimension: 'academic' as DimensionKey,
  award_level: '',
})
const certMaterials = reactive<Record<string, boolean>>({})
const certFiles = ref<UploadedFile[]>([])
const materialDraftFiles = ref<UploadedFile[]>([])
const materialSourceUrl = ref('')
const materialParsing = ref(false)
const certDropOver = ref(false)

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

const radarRef = ref<HTMLDivElement | null>(null)
const barRef = ref<HTMLDivElement | null>(null)

const modeLabel = computed(() => (store.roleMode === 'student' ? '学生端' : '管理端'))
const currentTabs = computed(() => (store.roleMode === 'student' ? studentTabs : adminTabs))
const currentActiveTab = computed(() => (store.roleMode === 'student' ? activeStudentTab.value : activeAdminTab.value))
const activeRuleDoc = computed(() => ruleDocs.value.find(doc => doc.is_active) || templates.value?.active_rule_document || null)

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

const adminDashboardRows = computed(() => adminApplications.value.slice(0, 5))
const adminDashboardFocus = computed(() => {
  if (selectedDashboardApplication.value) {
    const fresh = adminApplications.value.find(item => item.id === selectedDashboardApplication.value?.id)
    if (fresh) return fresh
  }
  return adminApplications.value.find(item => item.status === 'pending_human') || adminApplications.value[0] || null
})

function switchTab(tab: string) {
  if (store.roleMode === 'student') activeStudentTab.value = tab
  else activeAdminTab.value = tab
}

function switchRole(role: 'student' | 'admin') {
  store.switchRole(role)
  nextTick(renderCharts)
}

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
    pending_ai: '待 AI 初审',
    pending_human: '待人工审核',
    needs_more: '需补材料',
    approved: '已入账',
    rejected: '已驳回',
  }
  return map[status] || status
}

function statusTagType(status: string) {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger' | 'primary'> = {
    pending_ai: 'info',
    pending_human: 'success',
    needs_more: 'warning',
    approved: 'success',
    rejected: 'danger',
  }
  return map[status] || 'info'
}

function statusText(app: ApplicationItem) {
  if (app.status === 'needs_more') return '信息存疑需复核'
  if (app.status === 'rejected') return '材料不符合要求'
  if (app.ai_confidence >= 0.85 && app.status !== 'rejected') return 'AI 建议通过'
  if (app.ai_confidence < 0.6) return '材料需人工复核'
  return '材料需人工复核'
}

function auditTagClass(tag: string) {
  if (tag.includes('高置信') || tag.includes('待人工确认') || tag.includes('通过')) return 'tag-positive'
  if (tag.includes('复核') || tag.includes('待确认') || tag.includes('需确认')) return 'tag-warning'
  if (tag.includes('缺失') || tag.includes('不足') || tag.includes('无法') || tag.includes('严重')) return 'tag-danger'
  return 'tag-neutral'
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

async function loadAll() {
  loading.value = true
  try {
    const [summaryData, opps, basketData, appData, honorData, templateData, statsData, adminAppData, docsData] = await Promise.all([
      api<DashboardSummary>(`/dashboard/summary?user_id=${store.studentId}`),
      api<Opportunity[]>(`/opportunities?user_id=${store.studentId}`),
      api<BasketItem[]>(`/plan-basket?user_id=${store.studentId}`),
      api<ApplicationItem[]>(`/certifications?user_id=${store.studentId}`),
      api<HonorItem[]>(`/honor-wall?user_id=${store.studentId}`),
      api<TemplateData>('/material-templates'),
      api<any>('/admin/stats'),
      api<ApplicationItem[]>('/admin/certifications'),
      api<RuleDocument[]>('/rule-documents'),
    ])
    summary.value = summaryData
    opportunities.value = opps
    basket.value = basketData
    applications.value = appData
    honors.value = honorData
    templates.value = templateData
    adminStats.value = statsData
    adminApplications.value = orderAuditRows(adminAppData)
    ruleDocs.value = docsData
    for (const material of templateData.strict_materials) {
      if (!(material in certMaterials)) certMaterials[material] = false
    }
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
  certForm.opportunity_id = opportunity.id
  certForm.title = `${opportunity.title} 综测认证`
  certForm.dimension = opportunity.dimension
  activeStudentTab.value = '智审中心'
}

function markCertMaterial(keyword: string) {
  const target = Object.keys(certMaterials).find(item => item.includes(keyword))
  if (target) certMaterials[target] = true
}

function cleanFileTitle(name: string) {
  return name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim().slice(0, 48)
}

function guessDimension(text: string): DimensionKey {
  if (text.includes('主持') || text.includes('诗歌') || text.includes('文体') || text.includes('观众')) return 'arts_sports'
  if (text.includes('志愿') || text.includes('义务') || text.includes('学生工作') || text.includes('安全教育')) return 'moral'
  return 'academic'
}

function inferOpportunityFromText(text: string) {
  return opportunities.value.find(item => {
    const compactTitle = item.title.replace(/\s/g, '')
    return compactTitle.includes(text.slice(0, 4)) || text.includes(compactTitle.slice(0, 6))
  })
}

async function uploadSingleFile(file: File) {
  const form = new FormData()
  form.append('file', file)
  return api<{ filename: string; url: string }>('/upload', { method: 'POST', body: form })
}

async function addCertProofFiles(files: File[]) {
  if (!files.length) return
  for (const file of files) {
    const result = await uploadSingleFile(file)
    certFiles.value.push({ name: file.name, url: result.url, type: file.type || file.name.split('.').pop() })
    if (file.type.startsWith('image/')) markCertMaterial('结果证明')
    if (/\.(pdf|doc|docx)$/i.test(file.name)) {
      markCertMaterial('通知')
      markCertMaterial('官方来源')
    }
  }
  ElMessage.success(`已添加 ${files.length} 份证明材料`)
}

async function handleCertProofSelect(event: Event) {
  const input = event.target as HTMLInputElement
  await addCertProofFiles(Array.from(input.files || []))
  input.value = ''
}

async function onCertProofDrop(event: DragEvent) {
  event.preventDefault()
  certDropOver.value = false
  await addCertProofFiles(Array.from(event.dataTransfer?.files || []))
}

async function addMaterialDraftFiles(files: File[], type: 'image' | 'document') {
  if (!files.length) return
  for (const file of files) {
    const result = await uploadSingleFile(file)
    const uploaded = { name: file.name, url: result.url, type }
    materialDraftFiles.value.push(uploaded)
    certFiles.value.push(uploaded)
  }
  runMaterialAiFill()
  ElMessage.success('AI 已读取材料并回填下方表单')
}

async function handleMaterialFileSelect(event: Event, type: 'image' | 'document') {
  const input = event.target as HTMLInputElement
  await addMaterialDraftFiles(Array.from(input.files || []), type)
  input.value = ''
}

async function onMaterialDrop(event: DragEvent, type: 'image' | 'document') {
  event.preventDefault()
  await addMaterialDraftFiles(Array.from(event.dataTransfer?.files || []), type)
}

function runMaterialAiFill() {
  const text = [
    ...materialDraftFiles.value.map(file => file.name),
    materialSourceUrl.value,
  ].join(' ')
  if (!text.trim()) {
    ElMessage.warning('请先上传图片/文件或填写通知链接')
    return
  }
  materialParsing.value = true
  const matched = inferOpportunityFromText(text)
  if (matched) {
    certForm.opportunity_id = matched.id
    certForm.title = `${matched.title} 综测认证`
    certForm.dimension = matched.dimension
  } else {
    certForm.title = certForm.title || `${cleanFileTitle(materialDraftFiles.value[0]?.name || '材料')} 认证`
    certForm.dimension = guessDimension(text)
  }
  if (!certForm.award_level) {
    if (text.includes('一等奖')) certForm.award_level = '一等奖'
    else if (text.includes('二等奖')) certForm.award_level = '二等奖'
    else if (text.includes('三等奖')) certForm.award_level = '三等奖'
    else if (text.includes('证书') || text.toLowerCase().includes('hcia')) certForm.award_level = '证书通过'
    else certForm.award_level = '待人工确认'
  }
  markCertMaterial('通知')
  markCertMaterial('参赛')
  markCertMaterial('参与')
  markCertMaterial('结果')
  markCertMaterial('官方来源')
  materialParsing.value = false
}

async function submitCertification() {
  if (!certForm.title.trim()) {
    ElMessage.warning('请填写认证标题')
    return
  }
  await postJson('/certifications', {
    user_id: store.studentId,
    opportunity_id: certForm.opportunity_id,
    title: certForm.title,
    dimension: certForm.dimension,
    award_level: certForm.award_level,
    material_manifest: { ...certMaterials },
    files: certFiles.value,
  })
  ElMessage.success('已提交，AI 初审后进入管理端复核')
  certForm.opportunity_id = undefined
  certForm.title = ''
  certForm.award_level = ''
  certFiles.value = []
  Object.keys(certMaterials).forEach(key => { certMaterials[key] = false })
  await loadAll()
}

async function uploadPublishImageFile(file: File, target: 'cover' | 'qr') {
  const form = new FormData()
  form.append('file', file)
  const result = await api<{ filename: string; url: string }>('/upload', { method: 'POST', body: form })
  const item = { name: file.name, url: result.url, localUrl: URL.createObjectURL(file) }
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

async function loadAdminQueue() {
  const rows = await api<ApplicationItem[]>(`/admin/certifications${auditQueue.value ? `?queue=${auditQueue.value}` : ''}`)
  adminApplications.value = orderAuditRows(rows)
}

async function decide(app: ApplicationItem, decision: 'approved' | 'rejected' | 'needs_more') {
  const score = decision === 'approved' ? Number(app.suggested_score || 0) : undefined
  await postJson(`/admin/certifications/${app.id}/decision`, {
    decision,
    score,
    comment: decision === 'approved' ? '人工复核通过，写入综测流水。' : decision === 'needs_more' ? '请补齐学校/学院通知、参赛名单或官方结果证明。' : '材料与细则不匹配，驳回。',
    rule_ref: app.ai_review?.rule_ref || '',
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
        <button :class="{ active: store.roleMode === 'student' }" @click="switchRole('student')">学生端</button>
        <button :class="{ active: store.roleMode === 'admin' }" @click="switchRole('admin')">管理端</button>
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
              <strong>{{ store.roleMode === 'student' ? summary?.user.name || '张三' : '王五' }}</strong>
              <small>{{ store.roleMode === 'student' ? '学生账号' : '管理员（队长）' }}</small>
            </span>
          </button>
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
          <span>{{ store.roleMode === 'student' ? summary?.user.name || '张三' : '王五' }}</span>
          <small>{{ store.roleMode === 'student' ? '电子信息工程' : '管理端审核员' }}</small>
        </div>
      </header>

      <template v-if="store.roleMode === 'student'">
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

        <section v-show="activeStudentTab === '智审中心'" class="page-stack">
          <div class="panel material-intake-panel">
            <div class="material-intake-head">
              <div>
                <span class="eyebrow">AI 材料识别</span>
                <h2>先把你手上的资料丢进来，系统自动回填认证表</h2>
                <p>支持奖状截图、比赛通知 PDF/Word、报名表、公众号文章或官网链接；识别后仍可手动修改。</p>
              </div>
              <el-button type="primary" :loading="materialParsing" @click="runMaterialAiFill">AI 识别并回填</el-button>
            </div>
            <div class="material-drop-grid">
              <label class="big-upload-card" @dragover.prevent @drop.prevent="event => onMaterialDrop(event, 'image')">
                <input type="file" multiple accept=".jpg,.jpeg,.png,.webp" @change="event => handleMaterialFileSelect(event, 'image')" />
                <strong>上传奖状/截图</strong>
                <span>点击选择，或把图片拖进来</span>
                <em>拖拽图片区</em>
              </label>
              <label class="big-upload-card" @dragover.prevent @drop.prevent="event => onMaterialDrop(event, 'document')">
                <input type="file" multiple accept=".pdf,.doc,.docx" @change="event => handleMaterialFileSelect(event, 'document')" />
                <strong>上传通知/报名表</strong>
                <span>PDF、Word、名单、证明材料</span>
                <em>拖拽文件区</em>
              </label>
              <div class="big-upload-card link-intake">
                <strong>粘贴官网/公众号链接</strong>
                <el-input v-model="materialSourceUrl" placeholder="https://..." @change="runMaterialAiFill" />
                <span>只填写真实可打开的链接；没有就留空。</span>
              </div>
            </div>
            <div v-if="materialDraftFiles.length" class="file-list material-file-list">
              <span v-for="file in materialDraftFiles" :key="file.url">{{ file.name }}</span>
            </div>
          </div>

          <div class="grid form-grid cert-grid">
          <div class="panel">
            <h2>提交综测加分认证</h2>
            <el-form label-position="top">
              <el-form-item label="关联活动/比赛">
                <el-select v-model="certForm.opportunity_id" filterable clearable placeholder="可选">
                  <el-option v-for="item in opportunities" :key="item.id" :label="item.title" :value="item.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="认证标题">
                <el-input v-model="certForm.title" placeholder="例如：蓝桥杯省级三等奖认证" />
              </el-form-item>
              <el-form-item label="综测归属">
                <el-radio-group v-model="certForm.dimension">
                  <el-radio-button label="moral">德育</el-radio-button>
                  <el-radio-button label="academic">学业</el-radio-button>
                  <el-radio-button label="arts_sports">文体</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="奖项/结果">
                <el-input v-model="certForm.award_level" placeholder="省级三等奖、参与、证书通过等" />
              </el-form-item>
              <el-form-item label="严格材料清单">
                <div class="check-list">
                  <el-checkbox v-for="material in templates?.strict_materials" :key="material" v-model="certMaterials[material]">
                    {{ material }}
                  </el-checkbox>
                </div>
              </el-form-item>
              <el-form-item label="上传证明材料">
                <label
                  :class="['proof-upload-box', { active: certDropOver }]"
                  @dragover.prevent="certDropOver = true"
                  @dragleave.prevent="certDropOver = false"
                  @drop="onCertProofDrop"
                >
                  <input type="file" multiple accept=".jpg,.jpeg,.png,.webp,.pdf,.doc,.docx" @change="handleCertProofSelect" />
                  <strong>点击或拖拽上传证明材料</strong>
                  <span>比赛通知、参赛名单、结果证明、官方来源证明都可以放在这里。</span>
                </label>
                <div class="file-list">
                  <span v-for="file in certFiles" :key="file.url">{{ file.name }}</span>
                </div>
              </el-form-item>
              <el-button type="primary" size="large" @click="submitCertification">提交 AI 初审</el-button>
            </el-form>
          </div>
          <div class="panel">
            <h2>我的认证进度</h2>
            <article v-for="item in applications" :key="item.id" class="audit-card">
              <div class="audit-head">
                <strong>{{ item.title }}</strong>
                <el-tag :type="statusTagType(item.status)" effect="light">{{ statusLabel(item.status) }}</el-tag>
              </div>
              <p>AI 置信度 {{ Math.round(item.ai_confidence * 100) }}% ｜ 建议 {{ item.suggested_score }} 分</p>
              <div class="risk-tags">
                <span v-for="tag in item.risk_tags" :key="tag" :class="auditTagClass(tag)">{{ tag }}</span>
              </div>
              <p class="muted">{{ item.admin_comment || item.ai_review?.recommendation }}</p>
            </article>
          </div>
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
              <strong>{{ adminStats?.opportunity_count ?? 0 }}</strong>
              <em>项</em>
            </article>
            <article class="dashboard-kpi kpi-green">
              <span>◎ 认证申请总数</span>
              <strong>{{ adminStats?.application_count ?? 0 }}</strong>
              <em>条</em>
            </article>
            <article class="dashboard-kpi kpi-red">
              <span>ⓘ 当前待处理</span>
              <strong>{{ adminStats?.pending_count ?? 0 }}</strong>
              <em>条</em>
            </article>
            <article class="dashboard-kpi kpi-gray">
              <span>◴ 已入账原始分</span>
              <strong>{{ adminStats?.approved_score ?? 0 }}</strong>
              <em>分</em>
            </article>
          </div>

          <div class="dashboard-main-grid">
            <section class="dashboard-panel review-list-panel">
              <div class="panel-title-row">
                <h2>实时综测审核列表</h2>
                <button class="panel-action">进入审核中心</button>
              </div>
              <div class="dashboard-filters">
                <input class="dashboard-input" placeholder="搜索学生姓名或材料..." />
                <select class="dashboard-input">
                  <option>审核状态</option>
                  <option>待人工审核</option>
                  <option>需补材料</option>
                  <option>已驳回</option>
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
                  <span>{{ item.student_name || '张三' }}</span>
                  <span>{{ item.award_level || item.dimension }}</span>
                  <span>{{ item.title }}</span>
                  <strong :class="confidenceClass(item.ai_confidence)">{{ Math.round(item.ai_confidence * 100) }}%</strong>
                  <span :class="['dashboard-status', confidenceClass(item.ai_confidence)]">{{ statusLabel(item.status) }}</span>
                  <button class="dashboard-link" @click="selectDashboardApplication(item)">查看详情</button>
                </div>
              </div>
            </section>

            <aside class="dashboard-panel student-detail-panel">
              <h2>学生综测详情</h2>
              <div v-if="adminDashboardFocus" class="student-detail-card">
                <h3>{{ adminDashboardFocus.student_name || '张三' }} <span>电子信息工程</span></h3>
                <div class="detail-matrix">
                  <span>材料名称</span><strong>{{ adminDashboardFocus.title }}</strong>
                  <span>当前建议</span><strong>{{ adminDashboardFocus.suggested_score }} 分</strong>
                  <span>审核状态</span><strong>{{ statusLabel(adminDashboardFocus.status) }}</strong>
                </div>
              </div>
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
