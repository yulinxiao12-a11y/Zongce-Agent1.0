<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

type AuthMode = 'login' | 'register'

const router = useRouter()
const mode = ref<AuthMode>('login')
const loading = ref(false)
const error = ref('')

const loginForm = reactive({
  student_id: '',
  password: '',
})

const registerForm = reactive({
  student_id: '',
  name: '',
  password: '',
  confirm: '',
  department: '电子与信息学院',
  class_name: '',
})

const submitLabel = computed(() => (mode.value === 'login' ? '登录' : '注册'))

function selectMode(next: AuthMode) {
  mode.value = next
  error.value = ''
}

function errorMessage(err: unknown) {
  if (err instanceof Error) return err.message
  return '网络错误，请重试'
}

async function postJson(path: string, body: unknown) {
  const response = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload.error || payload.message || payload.detail || `HTTP ${response.status}`)
  }
  return payload
}

async function submitLogin() {
  const payload = await postJson('/api/auth/login', {
    student_id: loginForm.student_id.trim(),
    password: loginForm.password,
  })
  if (payload.role === 'admin') {
    window.location.assign('/admin/submissions')
    return
  }
  await router.push('/student')
}

async function submitRegister() {
  if (registerForm.password !== registerForm.confirm) {
    throw new Error('两次密码输入不一致')
  }
  if (!/^\d+$/.test(registerForm.student_id.trim())) {
    throw new Error('学号只能包含数字')
  }

  await postJson('/api/auth/register', {
    student_id: registerForm.student_id.trim(),
    name: registerForm.name.trim(),
    password: registerForm.password,
    department: registerForm.department.trim(),
    class_name: registerForm.class_name.trim(),
  })
  await router.push('/student')
}

async function handleSubmit() {
  error.value = ''
  loading.value = true
  try {
    if (mode.value === 'login') await submitLogin()
    else await submitRegister()
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-container">
      <div class="login-brand">
        <div class="brand-icon" aria-hidden="true"><span /></div>
        <h2>综测星轨</h2>
        <p>电子与信息学院</p>
        <p class="brand-subtitle">智能加分管理 · AI材料识别 · 一键计算综测成绩</p>
      </div>

      <div class="login-form-area">
        <div class="login-tabs">
          <button class="login-tab" :class="{ active: mode === 'login' }" type="button" @click="selectMode('login')">登录</button>
          <button class="login-tab" :class="{ active: mode === 'register' }" type="button" @click="selectMode('register')">注册</button>
        </div>

        <form v-if="mode === 'login'" @submit.prevent="handleSubmit">
          <div class="form-group">
            <label>学号</label>
            <input v-model="loginForm.student_id" autocomplete="username" placeholder="请输入学号" required type="text" />
          </div>
          <div class="form-group">
            <label>密码</label>
            <input v-model="loginForm.password" autocomplete="current-password" placeholder="请输入密码" required type="password" />
          </div>
          <div class="form-error" :class="{ show: error }">{{ error }}</div>
          <button class="btn btn-primary login-submit" :disabled="loading" type="submit">{{ submitLabel }}</button>
        </form>

        <form v-else @submit.prevent="handleSubmit">
          <div class="form-group">
            <label>学号</label>
            <input v-model="registerForm.student_id" autocomplete="username" placeholder="请输入学号" required type="text" />
            <div class="input-hint">请输入你的学号</div>
          </div>
          <div class="form-group">
            <label>姓名</label>
            <input v-model="registerForm.name" autocomplete="name" placeholder="请输入真实姓名" required type="text" />
          </div>
          <div class="form-group">
            <label>密码</label>
            <input v-model="registerForm.password" autocomplete="new-password" minlength="6" placeholder="至少6位，可含数字和大小写字母" required type="password" />
          </div>
          <div class="form-group">
            <label>确认密码</label>
            <input v-model="registerForm.confirm" autocomplete="new-password" placeholder="再次输入密码" required type="password" />
          </div>
          <div class="form-group">
            <label>院系（可选）</label>
            <input v-model="registerForm.department" type="text" />
          </div>
          <div class="form-group">
            <label>班级（可选）</label>
            <input v-model="registerForm.class_name" placeholder="如：通信2101班" type="text" />
          </div>
          <div class="form-error" :class="{ show: error }">{{ error }}</div>
          <button class="btn btn-primary login-submit" :disabled="loading" type="submit">{{ submitLabel }}</button>
        </form>

        <p class="login-default">建议用真实姓名和真实学号注册登录，否则会影响项目AI置信度</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8eef4 0%, #e2ebf4 50%, #f5f6f8 100%);
  padding: 32px;
}

.login-container {
  display: flex;
  max-width: 900px;
  width: min(100%, 900px);
  background: #ffffff;
  border-radius: 14px;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.16);
  overflow: hidden;
}

.login-brand {
  flex: 1;
  background: linear-gradient(135deg, #07132b, #0f2340);
  color: #ffffff;
  padding: 60px 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
}

.brand-icon {
  position: relative;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: conic-gradient(#ffffff 0 73%, transparent 73% 100%);
  margin-bottom: 18px;
}

.brand-icon::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: conic-gradient(transparent 0 75%, #ffffff 75% 100%);
  transform: rotate(45deg);
}

.brand-icon span {
  position: absolute;
  left: 29px;
  top: -4px;
  width: 7px;
  height: 66px;
  background: #07132b;
  transform: rotate(0deg);
  transform-origin: center;
}

.brand-icon::after {
  content: '';
  position: absolute;
  left: 27px;
  top: 27px;
  width: 36px;
  height: 7px;
  background: #07132b;
  transform: rotate(45deg);
  transform-origin: left center;
}

.login-brand h2 {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 8px;
}

.login-brand p {
  opacity: 0.82;
  font-size: 14px;
  margin: 0;
}

.brand-subtitle {
  margin-top: 14px !important;
  font-size: 12px !important;
  opacity: 0.62 !important;
}

.login-form-area {
  flex: 1;
  padding: 50px 40px;
}

.login-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  background: #f8f9fb;
  border-radius: 10px;
  padding: 4px;
}

.login-tab {
  flex: 1;
  border: 0;
  text-align: center;
  padding: 10px 20px;
  cursor: pointer;
  font: inherit;
  font-size: 15px;
  font-weight: 700;
  color: #64748b;
  border-radius: 8px;
  background: transparent;
  transition: 0.2s ease;
}

.login-tab.active {
  color: #ffffff;
  background: #31598c;
  box-shadow: 0 8px 16px rgba(49, 89, 140, 0.22);
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 6px;
}

.form-group input {
  width: 100%;
  padding: 11px 14px;
  border: 1.5px solid #e5e7eb;
  border-radius: 8px;
  font: inherit;
  font-size: 14px;
  outline: none;
  transition: 0.2s ease;
}

.form-group input:focus {
  border-color: #31598c;
  box-shadow: 0 0 0 3px rgba(49, 89, 140, 0.12);
}

.input-hint {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}

.form-error {
  color: #dc2626;
  min-height: 18px;
  font-size: 12px;
  margin-bottom: 8px;
  opacity: 0;
}

.form-error.show {
  opacity: 1;
}

.login-submit {
  width: 100%;
  justify-content: center;
  padding: 12px;
  font-size: 14px;
  border-radius: 8px;
  background: #31598c;
}

.login-submit:disabled {
  opacity: 0.72;
  cursor: wait;
}

.login-default {
  text-align: center;
  margin-top: 20px;
  font-size: 11px;
  color: #94a3b8;
}

@media (max-width: 760px) {
  .login-page {
    padding: 18px;
  }

  .login-container {
    flex-direction: column;
    max-width: 420px;
  }

  .login-brand {
    padding: 40px 30px;
  }

  .login-form-area {
    padding: 30px;
  }
}
</style>
