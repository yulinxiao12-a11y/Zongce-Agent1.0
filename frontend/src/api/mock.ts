type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE'

const ruleVersion = '2024-07-12-electronic-info-v1'
const demoStateVersion = '2026-05-18-v5'

const officialImages = {
  lanqiao: 'https://assets.lanqiao.cn/lanqiaobei-fe/v8.5.3/dist/favico.png',
  jsjds: 'https://jsjds.blcu.edu.cn/images/banner11.PNG',
  mcm: 'https://www.mcm.edu.cn/theme/mcm/image/top_cn.jpg',
  robomaster: 'https://rm-static.djicdn.com/documents/55708/6d77a3be8b2431741835508145145792.png',
  ciscn: 'https://www.ciscn.cn/uploads/banner/2025-banner.jpg',
  challenge: 'https://tiaozhanbei.net/static/images/mobile/mobile_header_logo.svg',
}

const state = loadState()

function loadState() {
  const saved = localStorage.getItem('zongce-static-demo')
  if (saved) {
    const parsed = JSON.parse(saved)
    if (parsed.demo_version === demoStateVersion) return parsed
  }
  return {
    demo_version: demoStateVersion,
    opportunities: [
      {
        id: 1,
        source_type: 'notice',
        source_label: '近期通知',
        title: '电信学院院办值班人员补招',
        category: '院务助理',
        dimension: 'moral',
        dimension_label: '德育',
        organizer: '电子与信息学院综合事务部',
        location: '白云校区学院办公室',
        start_time: '2026-05-25 起，每周一次',
        deadline: '2026-06-20 20:00',
        season_months: '',
        credit_hint: '可作为学院工作与综合素质经历，是否加分以学院证明和综测细则审核为准。',
        rule_ref: '德育附加分：学院组织的服务、劳动、学生工作经历按证明材料人工核验。',
        official_url: '',
        registration_url: '',
        contact_email: '',
        article_url: '',
        group_qr_url: '/uploads/opportunity-demo/office-duty-cover.jpg',
        description: '参考活动素材整理：协助老师处理办公室日常事务，每周一次，每次两节课。演示版已将报名截止延后。',
        requirements: ['报名表', '排班确认', '工作记录', '学院证明', '个人身份匹配证明'],
        tags: ['学院工作', '德育', '院办值班'],
        attachments: [],
        images: ['/uploads/opportunity-demo/office-duty-cover.jpg'],
        roi_score: 4.1,
        in_basket: false,
      },
      {
        id: 2,
        source_type: 'notice',
        source_label: '近期通知',
        title: '白云校区学生处学生助理招新',
        category: '学生工作',
        dimension: 'moral',
        dimension_label: '德育',
        organizer: '学生处',
        location: '白云校区学生处',
        start_time: '2026-06-01 起',
        deadline: '2026-06-25 20:00',
        season_months: '',
        credit_hint: '学生助理经历可作为综合素质材料，需提交招募通知、报名表、录用或工作证明。',
        rule_ref: '德育附加分：学生工作、志愿服务或义务劳动按学院证明材料人工核验。',
        official_url: '',
        registration_url: '',
        contact_email: '',
        article_url: '',
        group_qr_url: '/uploads/opportunity-demo/student-office-qr.jpg',
        description: '参考活动素材整理：面向白云校区在校学生招募学生助理，协助二级学院事务、大型活动和临时工作。',
        requirements: ['报名表', '录用通知', '工作时长证明', '组织方证明', '个人身份匹配证明'],
        tags: ['学生助理', '报名表', '德育'],
        attachments: [{ name: '学生处招新报名表.docx', url: '/uploads/opportunity-demo/student-office-form.docx' }],
        images: ['/uploads/opportunity-demo/student-office-qr.jpg'],
        roi_score: 4,
        in_basket: false,
      },
      {
        id: 3,
        source_type: 'notice',
        source_label: '近期通知',
        title: '粤风赓续·文脉兴湾诗歌节知识竞赛观众招募',
        category: '文化活动',
        dimension: 'arts_sports',
        dimension_label: '文体',
        organizer: '易班发展中心',
        location: '广州校区学术报告厅',
        start_time: '2026-06-12 19:00',
        deadline: '2026-06-10 18:30',
        season_months: '',
        credit_hint: '文化艺术类活动可作为文体材料，需以活动签到、主办方证明和综测细则核验。',
        rule_ref: '文体附加分：参加学校、学院组织的文化艺术活动按活动证明人工核验。',
        official_url: '',
        registration_url: '',
        contact_email: '',
        article_url: '',
        group_qr_url: '/uploads/opportunity-demo/lingnan-poetry-cover.jpg',
        description: '参考活动素材整理：三月三诗歌节之岭南文韵知识竞赛决赛观众招募，参与现场互动与文化知识学习。',
        requirements: ['活动通知', '报名或签到记录', '活动参与证明', '个人身份匹配证明'],
        tags: ['文化艺术', '文体', '观众招募'],
        attachments: [],
        images: ['/uploads/opportunity-demo/lingnan-poetry-cover.jpg'],
        roi_score: 3.8,
        in_basket: false,
      },
      {
        id: 4,
        source_type: 'notice',
        source_label: '近期通知',
        title: '主持人请就位决赛观众报名',
        category: '文艺活动',
        dimension: 'arts_sports',
        dimension_label: '文体',
        organizer: '白云校区学生组织',
        location: '图书馆 113 报告厅',
        start_time: '2026-06-18 19:00',
        deadline: '2026-06-16 17:00',
        season_months: '',
        credit_hint: '文艺活动参与记录需保留报名记录、签到和活动证明；能否加分以学院审核为准。',
        rule_ref: '文体附加分：文艺活动参与或获奖按学校/学院认定材料核验。',
        official_url: '',
        registration_url: '',
        contact_email: '',
        article_url: '',
        group_qr_url: '/uploads/opportunity-demo/host-final-cover.jpg',
        description: '参考活动海报整理：主持人比赛决赛观众报名，活动对象为白云校区本科学生。',
        requirements: ['活动通知', '报名记录', '现场签到', '活动参与证明'],
        tags: ['主持', '文体', '决赛'],
        attachments: [],
        images: ['/uploads/opportunity-demo/host-final-cover.jpg'],
        roi_score: 3.7,
        in_basket: false,
      },
      {
        id: 5,
        source_type: 'notice',
        source_label: '近期通知',
        title: '广州校区反诈小课堂咨询群',
        category: '安全教育',
        dimension: 'moral',
        dimension_label: '德育',
        organizer: '安全教育工作组',
        location: '线上咨询群',
        start_time: '2026-06-05 起',
        deadline: '2026-06-30 23:59',
        season_months: '',
        credit_hint: '安全教育类活动通常需活动通知、签到或学习证明，具体加分以学院通知为准。',
        rule_ref: '德育附加分：思想教育、安全教育、公益活动等需结合活动证明人工核验。',
        official_url: '',
        registration_url: '',
        contact_email: '',
        article_url: '',
        group_qr_url: '/uploads/opportunity-demo/anti-fraud-qr.jpg',
        description: '参考活动素材整理：面向广州校区同学提供反诈宣传、咨询答疑和案例学习。演示版延长报名时间。',
        requirements: ['活动通知', '入群或报名记录', '学习/签到证明', '个人身份匹配证明'],
        tags: ['安全教育', '德育', '线上'],
        attachments: [],
        images: ['/uploads/opportunity-demo/anti-fraud-qr.jpg'],
        roi_score: 3.6,
        in_basket: false,
      },
      ...[
        ['全国大学生电子设计竞赛', '重点科技竞赛', 'https://nuedc.xjtu.edu.cn/', '通常 7-8 月', '面向电子信息类学生的综合硬件设计竞赛。', '/competition-covers/nuedc.png'],
        ['蓝桥杯全国软件和信息技术专业人才大赛', '学科竞赛', 'https://dasai.lanqiao.cn/', '通常 3-6 月', '包含软件、电子、嵌入式等赛道。', officialImages.lanqiao],
        ['中国大学生计算机设计大赛', '学科竞赛', 'https://jsjds.blcu.edu.cn/', '通常 3-8 月', '以计算机应用设计为核心。', officialImages.jsjds],
        ['全国大学生数学建模竞赛', '学科竞赛', 'https://www.mcm.edu.cn/index.moma', '通常 9 月', '三人组队完成建模、求解与论文撰写。', officialImages.mcm],
        ['RoboMaster 机甲大师高校系列赛', '重点科技竞赛', 'https://www.robomaster.com/zh-CN', '通常全年分阶段', '大型机器人竞技与工程项目。', officialImages.robomaster],
        ['全国大学生信息安全竞赛', '学科竞赛', 'https://www.ciscn.cn/', '通常 4-8 月', '面向信息安全作品和攻防实践。', officialImages.ciscn],
        ['挑战杯系列竞赛', '创新创业', 'https://tiaozhanbei.net/', '通常按大挑/小挑周期', '包含学术科技作品和创业计划竞赛。', officialImages.challenge],
      ].map((row, index) => ({
        id: index + 6,
        source_type: 'evergreen',
        source_label: '常驻备赛',
        title: row[0],
        category: row[1],
        dimension: 'academic',
        dimension_label: '学业',
        organizer: '赛事组委会',
        location: '',
        start_time: '',
        deadline: '',
        season_months: row[3],
        credit_hint: '实际能否加分以学院/学校通知和综测细则审核为准。',
        rule_ref: '学业附加分：按竞赛级别、奖项和材料链人工核验。',
        official_url: row[2],
        registration_url: '',
        contact_email: '',
        article_url: '',
        group_qr_url: '',
        description: row[4],
        requirements: ['官方通知', '报名或参赛名单', '获奖或结果证明', '个人身份匹配证明'],
        tags: ['常驻赛事', '电子信息'],
        attachments: [],
        images: [row[5]],
        roi_score: 4.8 - index * 0.1,
        in_basket: index < 2,
      })),
    ],
    basket: [
      { id: 1, stage: '备赛中', note: '先刷历年题，6 月前组队。', opportunity_id: 6 },
      { id: 2, stage: '想参加', note: '关注学院是否转发通知。', opportunity_id: 7 },
    ],
    applications: [
      makeApplication(1, 1, 7, '蓝桥杯省级三等奖认证', 'academic', '省级三等奖', 0.91, 6, 'pending_human', ['AI高置信', '待人工确认']),
      makeApplication(2, 2, 6, '全国大学生电子设计竞赛省级二等奖认证', 'academic', '省级二等奖', 0.93, 18, 'pending_human', ['AI高置信']),
      makeApplication(3, 1, undefined, '匿名竞赛三等奖认证', 'academic', '省级三等奖', 0.62, 0, 'needs_more', ['材料链不完整', '建议复核']),
      makeApplication(4, 1, 2, '学院志愿服务 8 小时认证', 'moral', '8 小时', 0.98, 2, 'pending_human', ['AI高置信']),
      makeApplication(5, 2, 9, '全国大学生数学建模竞赛省级一等奖认证', 'academic', '省级一等奖', 0.95, 10, 'pending_human', ['AI高置信']),
      makeApplication(6, 2, undefined, '华为 ICT 大赛校赛参与证明认证', 'academic', '校赛参与', 0.52, 1, 'needs_more', ['来源缺失', '结果证明不足']),
      makeApplication(7, 1, undefined, '全国大学生物联网设计竞赛校级二等奖认证', 'academic', '校级二等奖', 0.9, 5, 'pending_human', ['AI高置信']),
      makeApplication(8, 2, 11, '全国大学生信息安全竞赛校级一等奖认证', 'academic', '校级一等奖', 0.88, 5, 'pending_human', ['AI高置信']),
      makeApplication(9, 1, 12, '挑战杯院赛项目立项认证', 'academic', '院赛立项', 0.71, 2, 'needs_more', ['结果待确认', '成员排序需复核']),
      makeApplication(10, 1, undefined, '华为 HCIA-AI 证书认证', 'academic', '专业证书', 0.92, 4, 'pending_human', ['AI高置信', '需确认证书等级']),
    ],
    honors: [
      { id: 1, title: '全国高校创新英语挑战赛一等奖', category: '证书', image_url: '/uploads/honor-demo/english-challenge.png', sort_order: 1, visibility: 'private' },
      { id: 2, title: 'Bebras 信息思维挑战优秀', category: '证书', image_url: '/uploads/honor-demo/bebras-2023.jpg', sort_order: 2, visibility: 'private' },
      { id: 3, title: '华为 HCIA-AI 认证', category: '证书', image_url: '/uploads/honor-demo/huawei-hcia-ai.png', sort_order: 3, visibility: 'private' },
      { id: 4, title: '中葡创业挑战赛 Top 50', category: '竞赛', image_url: '/uploads/honor-demo/macau-929.png', sort_order: 4, visibility: 'private' },
      { id: 5, title: '挑战杯院赛项目展示', category: '竞赛', image_url: '/uploads/honor-demo/challenge-cup-photo.jpg', sort_order: 5, visibility: 'private' },
    ],
    ruleDocs: [
      {
        id: 1,
        name: '2025年7月电信学院综测细则（公示版）',
        version: ruleVersion,
        file_url: '/uploads/rules/current-zongce-rules.docx',
        notes: '静态演示环境使用内置细则版本。',
        is_active: 1,
        uploaded_at: new Date().toISOString(),
      },
    ],
    logs: [
      { id: 1, actor: '王五', action: '更新审核队列', detail: '新增 5 条演示材料' },
      { id: 2, actor: '张三', action: '新增荣誉墙', detail: '华为 HCIA-AI 认证' },
    ],
  }
}

function makeApplication(id: number, user_id: number, opportunity_id: number | undefined, title: string, dimension: string, award_level: string, confidence: number, score: number, status: string, risk_tags: string[]) {
  return {
    id,
    user_id,
    opportunity_id: opportunity_id || null,
    title,
    dimension,
    award_level,
    material_manifest: { 结果证明: true },
    files: [],
    ai_review: {
      recognized_text: title,
      missing_materials: confidence > 0.85 ? [] : ['活动或比赛通知', '官方来源证明'],
      rule_ref: '按综测细则和学院通知人工核验。',
      recommendation: confidence > 0.85 ? 'AI 建议通过，等待人工确认。' : '建议补充材料后复核。',
    },
    ai_confidence: confidence,
    risk_tags,
    suggested_score: score,
    status,
    admin_comment: status === 'needs_more' ? '请补充官方通知或结果页截图。' : '',
    student_name: user_id === 2 ? '李四' : '张三',
    opportunity_title: '',
  }
}

function saveState() {
  localStorage.setItem('zongce-static-demo', JSON.stringify(state))
}

function bodyJson(options: RequestInit) {
  if (!options.body || options.body instanceof FormData) return {}
  return JSON.parse(String(options.body))
}

function fileToDataUrl(file: File) {
  return new Promise<string>((resolve) => {
    if (!file.type.startsWith('image/')) {
      resolve('')
      return
    }
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => resolve('')
    reader.readAsDataURL(file)
  })
}

function hydrateOpportunity(item: any) {
  return {
    ...item,
    dimension_label: item.dimension === 'moral' ? '德育' : item.dimension === 'arts_sports' ? '文体' : '学业',
    source_label: item.source_type === 'notice' ? '近期通知' : '常驻备赛',
    in_basket: state.basket.some((basket: any) => basket.opportunity_id === item.id),
  }
}

function basketRow(item: any) {
  return { ...item, opportunity: hydrateOpportunity(state.opportunities.find((opp: any) => opp.id === item.opportunity_id)) }
}

function dashboardSummary() {
  return {
    user: { name: '张三', college: '电子与信息学院', major: '电子信息工程' },
    score: {
      rule_version: ruleVersion,
      total: 85.15,
      details: [
        { key: 'moral', label: '德育', base: 70, raw_add: 7, normalized_add: 7, deduction: 0, score: 77, weight: 0.2, weighted: 15.4, cap: 30 },
        { key: 'academic', label: '学业', base: 80, raw_add: 13, normalized_add: 13, deduction: 0, score: 93, weight: 0.65, weighted: 60.45, cap: 20 },
        { key: 'arts_sports', label: '文体', base: 60, raw_add: 2, normalized_add: 2, deduction: 0, score: 62, weight: 0.15, weighted: 9.3, cap: 40 },
      ],
    },
    pending_score: 19,
    goal_gap: 4.85,
    ledgers: [
      { title: '志愿服务 8 小时', dimension: 'moral', score: 2, rule_ref: '德育志愿活动4小时1分' },
      { title: '军训副排长', dimension: 'moral', score: 2, rule_ref: '德育军训荣誉校级' },
      { title: '院级文明宿舍标兵', dimension: 'moral', score: 3, rule_ref: '德育文明宿舍院级标兵' },
      { title: '校级学科竞赛三等奖', dimension: 'academic', score: 3, rule_ref: '学业其他竞赛校级三等奖' },
      { title: '蓝桥杯省级三等奖', dimension: 'academic', score: 6, rule_ref: '学业其他竞赛省级三等奖' },
      { title: '华为 HCIA-AI 证书', dimension: 'academic', score: 4, rule_ref: '学业专业技术等级证书' },
      { title: '主持人请就位决赛观众', dimension: 'arts_sports', score: 1, rule_ref: '文体活动校级参与' },
      { title: '诗歌节知识竞赛观众', dimension: 'arts_sports', score: 1, rule_ref: '文体文化活动校级参与' },
    ],
    pending_applications: state.applications.filter((item: any) => ['pending_human', 'needs_more'].includes(item.status)),
  }
}

export async function mockApi<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || 'GET').toUpperCase() as Method
  const cleanPath = path.split('?')[0]
  const query = new URLSearchParams(path.split('?')[1] || '')

  if (method === 'GET' && cleanPath === '/dashboard/summary') return dashboardSummary() as T
  if (method === 'GET' && cleanPath === '/opportunities') return state.opportunities.map(hydrateOpportunity) as T
  if (method === 'GET' && cleanPath === '/plan-basket') return state.basket.map(basketRow) as T
  if (method === 'GET' && cleanPath === '/certifications') return state.applications.filter((item: any) => item.user_id === 1) as T
  if (method === 'GET' && cleanPath === '/honor-wall') return [...state.honors].sort((a: any, b: any) => a.sort_order - b.sort_order) as T
  if (method === 'GET' && cleanPath === '/rule-documents') return state.ruleDocs as T
  if (method === 'GET' && cleanPath === '/material-templates') {
    return {
      rule_version: ruleVersion,
      active_rule_document: state.ruleDocs.find((doc: any) => doc.is_active),
      strict_materials: ['活动或比赛通知', '参赛或参与证明', '结果证明', '官方来源证明', '个人身份匹配证明'],
      dimensions: [
        { key: 'moral', label: '德育', base: 70, cap: 30, weight: 0.2 },
        { key: 'academic', label: '学业', base: 80, cap: 20, weight: 0.65 },
        { key: 'arts_sports', label: '文体', base: 60, cap: 40, weight: 0.15 },
      ],
      notes: ['AI 初审不代表最终通过，人工审核通过后才写入 ScoreLedger。'],
    } as T
  }
  if (method === 'GET' && cleanPath === '/admin/stats') {
    return {
      opportunity_count: state.opportunities.length,
      application_count: state.applications.length,
      pending_count: state.applications.filter((item: any) => ['pending_human', 'needs_more'].includes(item.status)).length,
      approved_score: 5,
      logs: state.logs,
    } as T
  }
  if (method === 'GET' && cleanPath === '/admin/certifications') {
    const queue = query.get('queue')
    let rows = [...state.applications]
    if (queue === 'high_confidence') rows = rows.filter((item: any) => item.ai_confidence >= 0.85 && item.status === 'pending_human')
    else if (queue === 'needs_more') rows = rows.filter((item: any) => item.status === 'needs_more')
    else if (queue === 'risk') rows = rows.filter((item: any) => item.status === 'needs_more' || item.ai_confidence < 0.7)
    else if (queue) rows = rows.filter((item: any) => item.status === queue)
    return rows as T
  }

  if (method === 'POST' && cleanPath === '/plan-basket') {
    const body = bodyJson(options)
    const item = { id: Date.now(), stage: body.stage || '想参加', note: '', opportunity_id: body.opportunity_id }
    state.basket.push(item)
    saveState()
    return basketRow(item) as T
  }
  if (method === 'PATCH' && cleanPath.startsWith('/plan-basket/')) {
    const id = Number(cleanPath.split('/').pop())
    const item = state.basket.find((row: any) => row.id === id)
    Object.assign(item, bodyJson(options))
    saveState()
    return basketRow(item) as T
  }
  if (method === 'DELETE' && cleanPath.startsWith('/plan-basket/')) {
    const id = Number(cleanPath.split('/').pop())
    state.basket = state.basket.filter((row: any) => row.id !== id)
    saveState()
    return {} as T
  }
  if (method === 'POST' && cleanPath === '/ai/parse-opportunity') {
    const body = bodyJson(options)
    return { title: 'AI 识别活动标题', category: '活动通知', dimension: 'academic', location: '待确认', deadline: '待确认', description: body.raw_text || '' } as T
  }
  if (method === 'POST' && cleanPath === '/opportunities') {
    const body = bodyJson(options)
    const item = { id: Date.now(), ...body, source_label: body.source_type === 'notice' ? '近期通知' : '常驻备赛', dimension_label: '学业', in_basket: false }
    state.opportunities.unshift(item)
    saveState()
    return item as T
  }
  if (method === 'POST' && cleanPath === '/certifications') {
    const body = bodyJson(options)
    const item = makeApplication(Date.now(), 1, body.opportunity_id, body.title, body.dimension, body.award_level, 0.46, 6, 'needs_more', ['材料缺失', '需人工复核'])
    state.applications.unshift(item)
    saveState()
    return item as T
  }
  if (method === 'POST' && cleanPath === '/honor-wall') {
    const body = bodyJson(options)
    const item = { id: Date.now(), title: body.title, category: body.category, image_url: body.image_url || '', sort_order: state.honors.length + 1, visibility: 'private' }
    state.honors.push(item)
    saveState()
    return item as T
  }
  if (method === 'PATCH' && cleanPath.startsWith('/honor-wall/')) {
    const id = Number(cleanPath.split('/').pop())
    const item = state.honors.find((row: any) => row.id === id)
    Object.assign(item, bodyJson(options))
    saveState()
    return item as T
  }
  if (method === 'POST' && cleanPath.includes('/admin/certifications/')) {
    const id = Number(cleanPath.split('/')[3])
    const item = state.applications.find((row: any) => row.id === id)
    Object.assign(item, { status: bodyJson(options).decision, admin_comment: bodyJson(options).comment || '' })
    saveState()
    return item as T
  }
  if (method === 'POST' && cleanPath.includes('/rule-documents/')) {
    const id = Number(cleanPath.split('/')[2])
    state.ruleDocs.forEach((doc: any) => { doc.is_active = doc.id === id ? 1 : 0 })
    saveState()
    return state.ruleDocs.find((doc: any) => doc.id === id) as T
  }
  if (method === 'POST' && cleanPath === '/upload' && options.body instanceof FormData) {
    const file = options.body.get('files') || options.body.get('file')
    return { filename: file instanceof File ? file.name : 'demo.png', url: file instanceof File ? await fileToDataUrl(file) : '' } as T
  }
  if (method === 'POST' && cleanPath === '/rule-documents/upload') {
    const item = { id: Date.now(), name: '新上传综测细则', version: 'demo-rule-v2', file_url: '', notes: '', is_active: 1, uploaded_at: new Date().toISOString() }
    state.ruleDocs.forEach((doc: any) => { doc.is_active = 0 })
    state.ruleDocs.unshift(item)
    saveState()
    return item as T
  }
  return {} as T
}
