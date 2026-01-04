<template>
  <n-modal
    v-model:show="showModal"
    preset="card"
    title="运行自动化测试"
    style="width: 550px"
    :bordered="false"
    :segmented="{ content: true, footer: 'soft' }"
  >
    <n-form
      ref="formRef"
      :model="config"
      label-placement="left"
      label-width="auto"
    >
      <!-- 起始步骤选项（仅当 startFromStep > 1 时显示） -->
      <n-alert v-if="config.startFromStep > 1" type="info" :bordered="false" style="margin-bottom: 16px">
        将从第 <strong>{{ config.startFromStep }}</strong> 步开始验证，之前的步骤将快速回放（不验证）
      </n-alert>

      <n-divider title-placement="left">验证选项</n-divider>

      <n-form-item label="截图对比">
        <n-switch v-model:value="config.screenshotCompare" />
        <n-text depth="3" style="margin-left: 12px">检测UI变化</n-text>
      </n-form-item>

      <n-form-item v-if="config.screenshotCompare" label="对比方式">
        <n-radio-group v-model:value="config.compareMode">
          <n-radio-button value="pixel">像素对比</n-radio-button>
          <n-radio-button value="ai">AI智能对比</n-radio-button>
        </n-radio-group>
      </n-form-item>

      <n-form-item
        v-if="config.screenshotCompare && config.compareMode === 'pixel'"
        label="差异阈值"
      >
        <n-slider
          v-model:value="config.threshold"
          :min="0"
          :max="0.5"
          :step="0.01"
          :format-tooltip="(v: number) => `${(v * 100).toFixed(0)}%`"
          style="width: 200px"
        />
        <n-text style="margin-left: 12px; min-width: 50px">
          {{ (config.threshold * 100).toFixed(0) }}%
        </n-text>
      </n-form-item>

      <n-form-item
        v-if="config.screenshotCompare && config.compareMode === 'ai'"
        label="严格程度"
      >
        <n-select
          v-model:value="config.aiStrictness"
          :options="strictnessOptions"
          style="width: 200px"
        />
      </n-form-item>

      <n-form-item label="元素检查">
        <n-switch v-model:value="config.elementCheck" />
        <n-text depth="3" style="margin-left: 12px">验证元素存在性</n-text>
      </n-form-item>

      <n-divider title-placement="left">AI 设置</n-divider>

      <n-form-item label="AI 提供商">
        <n-select
          v-model:value="config.aiProvider"
          :options="providerOptions"
          style="width: 200px"
        />
      </n-form-item>

      <n-form-item v-if="config.aiProvider === 'gemini'" label="Google API Key">
        <n-input
          v-model:value="config.googleApiKey"
          type="password"
          show-password-on="click"
          placeholder="输入 Google API Key"
          style="width: 300px"
        />
      </n-form-item>

      <n-form-item v-if="config.aiProvider === 'claude'" label="Anthropic API Key">
        <n-input
          v-model:value="config.anthropicApiKey"
          type="password"
          show-password-on="click"
          placeholder="输入 Anthropic API Key"
          style="width: 300px"
        />
      </n-form-item>

      <n-form-item v-if="config.aiProvider === 'openai'" label="OpenAI API Key">
        <n-input
          v-model:value="config.openaiApiKey"
          type="password"
          show-password-on="click"
          placeholder="输入 OpenAI API Key"
          style="width: 300px"
        />
      </n-form-item>

      <n-text depth="3" style="font-size: 12px; display: block; margin-bottom: 16px;">
        AI 功能用于：智能截图对比、元素定位后备、状态验证等
      </n-text>

      <n-divider title-placement="left">
        <n-space align="center">
          <span>测试变量</span>
          <n-tag size="small" type="warning">敏感信息</n-tag>
        </n-space>
      </n-divider>

      <n-form-item label="登录密码">
        <n-input
          v-model:value="testPassword"
          type="password"
          show-password-on="click"
          placeholder="输入测试账号的密码（录制时被掩码）"
          style="width: 300px"
        />
      </n-form-item>

      <n-text depth="3" style="font-size: 12px; display: block; margin-bottom: 16px;">
        密码会在测试时自动填入空的密码字段，不会保存到文件
      </n-text>

      <n-divider title-placement="left">执行选项</n-divider>

      <n-form-item label="无头模式">
        <n-switch v-model:value="config.headless" />
        <n-text depth="3" style="margin-left: 12px">后台运行，不显示浏览器</n-text>
      </n-form-item>

      <n-form-item label="步骤延迟">
        <n-input-number
          v-model:value="config.stepDelay"
          :min="0"
          :max="5"
          :step="0.1"
          style="width: 120px"
        />
        <n-text style="margin-left: 8px">秒</n-text>
      </n-form-item>

      <n-divider title-placement="left">
        <n-space align="center">
          <span>Debug 模式</span>
          <n-tag size="small" type="info">AI-in-the-loop</n-tag>
        </n-space>
      </n-divider>

      <n-form-item label="调试模式">
        <n-switch v-model:value="config.debugMode" />
        <n-text depth="3" style="margin-left: 12px">失败时暂停，可单步执行</n-text>
      </n-form-item>

      <n-form-item label="AI全程参与">
        <n-switch v-model:value="config.aiInTheLoop" />
        <n-text depth="3" style="margin-left: 12px">AI分析每个步骤，智能跳过/修复</n-text>
      </n-form-item>

      <n-collapse-transition :show="config.aiInTheLoop || config.debugMode">
        <div class="debug-options">
          <n-form-item v-if="config.aiInTheLoop" label="自动跳过">
            <n-switch v-model:value="config.aiAutoSkip" />
            <n-text depth="3" style="margin-left: 12px">跳过不必要的步骤（如快速重定向）</n-text>
          </n-form-item>

          <n-form-item label="自动修复">
            <n-switch v-model:value="config.aiAutoFix" />
            <n-text depth="3" style="margin-left: 12px">选择器失败时AI自动尝试修复</n-text>
          </n-form-item>

          <n-form-item v-if="config.aiAutoFix" label="最大重试">
            <n-input-number
              v-model:value="config.maxAutoRetries"
              :min="0"
              :max="5"
              :step="1"
              style="width: 80px"
            />
            <n-text style="margin-left: 8px">次</n-text>
          </n-form-item>

          <n-form-item v-if="config.debugMode" label="失败时暂停">
            <n-switch v-model:value="config.pauseOnFailure" />
            <n-text depth="3" style="margin-left: 12px">等待用户决策（跳过/重试/修改）</n-text>
          </n-form-item>
        </div>
      </n-collapse-transition>
    </n-form>

    <template #footer>
      <n-space justify="end">
        <n-button @click="handleCancel">取消</n-button>
        <n-button type="primary" @click="handleStart" :loading="loading">
          <template #icon>
            <n-icon><PlayOutline /></n-icon>
          </template>
          开始测试
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import {
  NModal,
  NForm,
  NFormItem,
  NSwitch,
  NRadioGroup,
  NRadioButton,
  NSlider,
  NSelect,
  NInputNumber,
  NInput,
  NButton,
  NSpace,
  NDivider,
  NText,
  NIcon,
  NAlert,
  NTag,
  NCollapseTransition,
} from 'naive-ui'
import { PlayOutline } from '@vicons/ionicons5'

// localStorage keys for persisting API keys
const STORAGE_KEYS = {
  googleApiKey: 'webmanual_google_api_key',
  anthropicApiKey: 'webmanual_anthropic_api_key',
  openaiApiKey: 'webmanual_openai_api_key',
}

interface TestConfig {
  screenshotCompare: boolean
  compareMode: 'pixel' | 'ai'
  threshold: number
  aiStrictness: 'lenient' | 'normal' | 'strict'
  elementCheck: boolean
  headless: boolean
  stepDelay: number
  startFromStep: number
  aiProvider: 'gemini' | 'claude' | 'openai'
  googleApiKey: string
  anthropicApiKey: string
  openaiApiKey: string
  // Debug模式
  debugMode: boolean
  aiInTheLoop: boolean
  aiAutoSkip: boolean
  aiAutoFix: boolean
  pauseOnFailure: boolean
  maxAutoRetries: number
  // 测试变量
  testVariables: Record<string, string>
}

const props = defineProps<{
  show: boolean
  startFromStep?: number  // 从第几步开始验证（之前的步骤快速回放）
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'start': [config: TestConfig]
}>()

const showModal = ref(false)
const loading = ref(false)
const testPassword = ref('')  // 测试密码（单独存储，不保存到localStorage）

const config = reactive<TestConfig>({
  screenshotCompare: true,
  compareMode: 'pixel',
  threshold: 0.10,  // 10% - 考虑动态内容
  aiStrictness: 'normal',
  elementCheck: true,
  headless: false,  // 默认显示浏览器，方便观察测试过程
  stepDelay: 0.5,
  startFromStep: 1,
  aiProvider: 'gemini',
  googleApiKey: '',
  anthropicApiKey: '',
  openaiApiKey: '',
  // Debug模式默认值
  debugMode: false,
  aiInTheLoop: false,
  aiAutoSkip: true,
  aiAutoFix: true,
  pauseOnFailure: true,
  maxAutoRetries: 2,
  // 测试变量（运行时构建）
  testVariables: {},
})

const strictnessOptions = [
  { label: '宽松 - 只关注主要功能', value: 'lenient' },
  { label: '一般 - 检查功能和布局', value: 'normal' },
  { label: '严格 - 检查所有细节', value: 'strict' },
]

const providerOptions = [
  { label: 'Google Gemini', value: 'gemini' },
  { label: 'Anthropic Claude', value: 'claude' },
  { label: 'OpenAI GPT-4', value: 'openai' },
]

// Load API keys from localStorage on mount
const loadApiKeys = () => {
  const googleKey = localStorage.getItem(STORAGE_KEYS.googleApiKey)
  const anthropicKey = localStorage.getItem(STORAGE_KEYS.anthropicApiKey)
  const openaiKey = localStorage.getItem(STORAGE_KEYS.openaiApiKey)

  if (googleKey) config.googleApiKey = googleKey
  if (anthropicKey) config.anthropicApiKey = anthropicKey
  if (openaiKey) config.openaiApiKey = openaiKey
}

// Save API keys to localStorage when they change
const saveApiKey = (key: keyof typeof STORAGE_KEYS, value: string) => {
  if (value) {
    localStorage.setItem(STORAGE_KEYS[key], value)
  } else {
    localStorage.removeItem(STORAGE_KEYS[key])
  }
}

// Watch for API key changes and persist them
watch(() => config.googleApiKey, (val) => saveApiKey('googleApiKey', val))
watch(() => config.anthropicApiKey, (val) => saveApiKey('anthropicApiKey', val))
watch(() => config.openaiApiKey, (val) => saveApiKey('openaiApiKey', val))

onMounted(() => {
  loadApiKeys()
})

watch(() => props.show, (val) => {
  showModal.value = val
  if (val) {
    // 重置或设置起始步骤
    config.startFromStep = props.startFromStep || 1
    // Reload API keys from localStorage in case they were updated elsewhere
    loadApiKeys()
  }
})

watch(showModal, (val) => {
  emit('update:show', val)
})

const handleCancel = () => {
  showModal.value = false
}

const handleStart = () => {
  // 构建测试变量（如果有密码则添加）
  const testVariables: Record<string, string> = {}
  if (testPassword.value) {
    // 使用多个关键字匹配密码字段
    testVariables['#password'] = testPassword.value
    testVariables['password'] = testPassword.value
    testVariables['密码'] = testPassword.value
  }

  emit('start', {
    ...config,
    testVariables,
  })
  showModal.value = false
}
</script>

<style scoped>
.debug-options {
  padding: 8px 16px;
  background: #f8f9fa;
  border-radius: 8px;
  margin-top: 8px;
  border: 1px solid #e9ecef;
}
</style>
