# 综测星轨（Zongce Agent）

独立实现的综测智能体比赛演示项目。系统包含学生端与管理端，围绕“机会发现、备赛规划、严格材料认证、人工复核入账、荣誉展示”形成完整闭环。

## 技术栈

- 前端：Vue 3、Vite、TypeScript、Pinia、Element Plus、ECharts
- 后端：FastAPI、SQLAlchemy、SQLite
- AI：OpenAI-compatible API，通过环境变量配置，不在代码中保存密钥

## 启动

后端：

```powershell
cd backend
copy .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`。

## AI 环境变量

在 `backend/.env` 中配置：

```env
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=你的密钥
AI_TEXT_MODEL=gpt-4.1-mini
AI_VISION_MODEL=gpt-4.1-mini
```

没有配置密钥时，系统会走严格兜底初审：标记“AI未配置、需人工复核”，不会自动通过。

## 演示数据说明

演示账号和页面文案只使用张三、李四、王五等匿名姓名。假数据素材中的真实姓名、手机号、邮箱不会进入数据库种子、页面或日志。
