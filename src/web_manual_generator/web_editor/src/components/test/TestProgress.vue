<template>
  <n-modal
    v-model:show="showModal"
    preset="card"
    :title="title"
    style="width: 900px; max-width: 95vw;"
    :bordered="false"
    :closable="!running"
    :mask-closable="!running"
    :segmented="{ content: true, footer: 'soft' }"
  >
    <div class="test-progress">
      <!-- 进度条 -->
      <div class="progress-section">
        <n-progress
          type="line"
          :percentage="progressPercent"
          :status="progressStatus"
          :height="24"
          :border-radius="4"
          :fill-border-radius="4"
        >
          {{ currentStep }} / {{ totalSteps }}
        </n-progress>
      </div>

      <!-- 当前步骤 -->
      <div v-if="running && !debugPaused" class="current-step">
        <n-spin size="small" />
        <span>{{ currentStepDescription || '准备中...' }}</span>
      </div>

      <!-- AI 分析结果面板（在运行中也显示） -->
      <div v-if="aiAnalysis && (running || debugPaused)" class="ai-analysis-panel">
        <n-card size="small" :bordered="true">
          <template #header>
            <n-space align="center">
              <n-icon :component="SparklesOutline" size="18" color="#8b5cf6" />
              <span>AI 分析</span>
              <n-tag v-if="aiAnalysis.should_skip" type="warning" size="small">建议跳过</n-tag>
              <n-tag v-if="aiAnalysis.should_modify" type="info" size="small">建议修改</n-tag>
              <n-tag v-if="!aiAnalysis.should_skip && !aiAnalysis.should_modify" type="success" size="small">可执行</n-tag>
            </n-space>
          </template>

          <div class="ai-analysis-content">
            <div class="ai-row">
              <span class="ai-label">步骤 #{{ aiAnalysis.step_id }}:</span>
              <span>{{ currentStepDescription }}</span>
            </div>

            <div v-if="aiAnalysis.analysis_text" class="ai-row">
              <span class="ai-label">分析:</span>
              <span class="ai-text">{{ aiAnalysis.analysis_text }}</span>
            </div>

            <div v-if="aiAnalysis.should_skip && aiAnalysis.skip_reason" class="ai-row skip-reason">
              <span class="ai-label">跳过原因:</span>
              <span>{{ aiAnalysis.skip_reason }}</span>
            </div>

            <div v-if="aiAnalysis.should_modify && aiAnalysis.suggested_selector" class="ai-row">
              <span class="ai-label">建议选择器:</span>
              <code class="selector-suggestion">{{ aiAnalysis.suggested_selector }}</code>
            </div>

            <div v-if="aiAnalysis.confidence" class="ai-row">
              <span class="ai-label">置信度:</span>
              <n-progress
                type="line"
                :percentage="Math.round(aiAnalysis.confidence * 100)"
                :height="14"
                :border-radius="4"
                style="width: 120px; display: inline-block;"
              />
              <span style="margin-left: 8px;">{{ Math.round(aiAnalysis.confidence * 100) }}%</span>
            </div>
          </div>
        </n-card>
      </div>

      <!-- Debug 模式暂停面板 -->
      <div v-if="debugPaused" class="debug-panel">
        <n-alert type="warning" :bordered="false">
          <template #header>
            <n-space align="center">
              <n-icon :component="PauseCircleOutline" size="20" />
              <span>测试已暂停 - 等待操作</span>
            </n-space>
          </template>
          <div class="debug-info">
            <div class="debug-row">
              <span class="debug-label">当前步骤:</span>
              <span>{{ currentStepDescription }}</span>
            </div>
            <div v-if="pendingSelectorFix" class="debug-row">
              <span class="debug-label">建议选择器:</span>
              <code class="selector-suggestion">{{ pendingSelectorFix }}</code>
            </div>
          </div>
        </n-alert>

        <!-- 用户AI提示词输入 -->
        <div class="user-prompt-section">
          <n-collapse :default-expanded-names="[]">
            <n-collapse-item title="自定义 AI 指令" name="prompt">
              <template #header-extra>
                <n-tag v-if="userAiPrompt" size="small" type="info">已设置</n-tag>
              </template>
              <n-input
                v-model:value="userAiPrompt"
                type="textarea"
                :rows="2"
                placeholder="输入额外指令给AI（如：忽略弹窗、等待特定元素、使用特定定位策略等）"
              />
              <n-text depth="3" style="font-size: 12px; margin-top: 4px; display: block;">
                提示词将影响AI的分析和决策，可用于处理特殊情况
              </n-text>
            </n-collapse-item>
          </n-collapse>
        </div>

        <div class="debug-actions">
          <n-space>
            <n-button type="primary" @click="handleDebugAction('continue')" :loading="sendingAction">
              <template #icon><n-icon :component="PlayOutline" /></template>
              继续执行
            </n-button>
            <n-button type="info" @click="handleDebugAction('retry')" :loading="sendingAction">
              <template #icon><n-icon :component="RefreshOutline" /></template>
              重试步骤
            </n-button>
            <n-button type="warning" @click="handleDebugAction('skip')" :loading="sendingAction">
              <template #icon><n-icon :component="PlaySkipForwardOutline" /></template>
              跳过步骤
            </n-button>
            <n-button @click="showModifySelector = true">
              <template #icon><n-icon :component="CreateOutline" /></template>
              修改选择器
            </n-button>
            <n-button type="error" @click="handleDebugAction('abort')" :loading="sendingAction">
              <template #icon><n-icon :component="StopCircleOutline" /></template>
              终止测试
            </n-button>
          </n-space>
        </div>

        <!-- 修改选择器弹窗 -->
        <n-modal v-model:show="showModifySelector" preset="dialog" title="修改选择器">
          <n-input
            v-model:value="newSelector"
            type="textarea"
            :rows="3"
            placeholder="输入新的选择器 (如 button:has-text('登录'))"
          />
          <template #action>
            <n-space>
              <n-button @click="showModifySelector = false">取消</n-button>
              <n-button type="primary" @click="handleModifySelector" :disabled="!newSelector">
                应用并重试
              </n-button>
            </n-space>
          </template>
        </n-modal>
      </div>

      <!-- 结果摘要 -->
      <div v-if="!running && result" class="result-summary">
        <n-alert :type="result.success ? 'success' : 'error'">
          <template #header>
            {{ result.success ? '测试通过' : '测试失败' }}
          </template>
          <n-space>
            <n-tag :type="result.success ? 'success' : 'error'">
              通过: {{ result.passed_steps }} / {{ result.total_steps }}
            </n-tag>
            <n-tag v-if="result.failed_steps > 0" type="error">
              失败: {{ result.failed_steps }}
            </n-tag>
            <n-tag type="info">
              耗时: {{ formatDuration(result.duration_ms) }}
            </n-tag>
          </n-space>
        </n-alert>
      </div>

      <!-- 步骤详情列表 -->
      <div class="steps-container">
        <n-scrollbar style="max-height: 450px">
          <n-collapse v-model:expanded-names="expandedSteps" accordion>
            <n-collapse-item
              v-for="step in detailedSteps"
              :key="step.step_id"
              :name="step.step_id"
            >
              <template #header>
                <div class="step-header" :class="{ passed: step.passed, failed: !step.passed, pending: step.pending }">
                  <n-icon v-if="step.pending" :component="TimeOutline" class="pending-icon" />
                  <n-icon v-else-if="step.passed" :component="CheckmarkCircle" class="pass-icon" />
                  <n-icon v-else :component="CloseCircle" class="fail-icon" />
                  <span class="step-id">#{{ step.step_id }}</span>
                  <n-tag size="small" :type="getActionTagType(step.action_type)">
                    {{ step.action_type }}
                  </n-tag>
                  <span class="step-desc">{{ step.description }}</span>
                  <span v-if="step.execution_time_ms" class="step-time">
                    {{ step.execution_time_ms }}ms
                  </span>
                </div>
              </template>

              <div class="step-detail">
                <!-- 执行信息和操作按钮 -->
                <div class="detail-section detail-header-section">
                  <div class="detail-row">
                    <span class="detail-label">状态:</span>
                    <n-tag :type="step.passed ? 'success' : 'error'" size="small">
                      {{ step.passed ? '通过' : '失败' }}
                    </n-tag>
                    <n-button
                      v-if="!running"
                      size="tiny"
                      type="primary"
                      ghost
                      class="rerun-btn"
                      @click.stop="handleRerunFromStep(step.step_id)"
                    >
                      <template #icon>
                        <n-icon><RefreshOutline /></n-icon>
                      </template>
                      从此步骤重新运行
                    </n-button>
                  </div>
                  <div v-if="step.execution_error" class="detail-row error-row">
                    <span class="detail-label">错误:</span>
                    <span class="error-message">{{ step.execution_error }}</span>
                  </div>
                </div>

                <!-- 验证结果 -->
                <div v-if="step.verifications && step.verifications.length > 0" class="verifications">
                  <div class="section-title">验证结果</div>
                  <div
                    v-for="(v, idx) in step.verifications"
                    :key="idx"
                    class="verification-item"
                    :class="{ passed: v.passed, failed: !v.passed }"
                  >
                    <div class="verification-header">
                      <n-icon :component="v.passed ? CheckmarkCircle : CloseCircle" />
                      <span class="verification-type">{{ getVerificationLabel(v.type) }}</span>
                      <n-tag v-if="v.diff_ratio !== undefined" size="tiny" :type="v.passed ? 'success' : 'error'">
                        差异: {{ (v.diff_ratio * 100).toFixed(1) }}%
                      </n-tag>
                    </div>
                    <div v-if="v.message" class="verification-message">{{ v.message }}</div>

                    <!-- 截图对比 -->
                    <div v-if="v.type === 'screenshot' && v.screenshots" class="screenshot-compare">
                      <div class="screenshot-item">
                        <div class="screenshot-label">基准图</div>
                        <img :src="getScreenshotUrl(v.screenshots.baseline)" @error="handleImgError" />
                      </div>
                      <div class="screenshot-item">
                        <div class="screenshot-label">实际图</div>
                        <img :src="getScreenshotUrl(v.screenshots.actual)" @error="handleImgError" />
                      </div>
                      <div v-if="v.screenshots.diff" class="screenshot-item diff">
                        <div class="screenshot-label">差异图</div>
                        <img :src="getScreenshotUrl(v.screenshots.diff)" @error="handleImgError" />
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 元素信息 -->
                <div v-if="step.selector" class="detail-section">
                  <div class="detail-row">
                    <span class="detail-label">选择器:</span>
                    <code class="selector-code">{{ step.selector }}</code>
                  </div>
                </div>
              </div>
            </n-collapse-item>
          </n-collapse>

          <!-- 空状态 -->
          <n-empty v-if="detailedSteps.length === 0 && running" description="等待测试开始..." />
        </n-scrollbar>
      </div>
    </div>

    <template #footer>
      <n-space justify="end">
        <n-button v-if="running" @click="handleCancel" :loading="cancelling">
          取消测试
        </n-button>
        <n-button v-if="!running && result" @click="handleViewReport" type="primary">
          查看完整报告
        </n-button>
        <n-button v-if="!running" @click="handleClose">
          关闭
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import {
  NModal,
  NProgress,
  NSpace,
  NButton,
  NScrollbar,
  NIcon,
  NAlert,
  NSpin,
  NTag,
  NCollapse,
  NCollapseItem,
  NEmpty,
  NInput,
  NCard,
  NText,
} from 'naive-ui'
import {
  CheckmarkCircle,
  CloseCircle,
  TimeOutline,
  RefreshOutline,
  PlayOutline,
  PlaySkipForwardOutline,
  PauseCircleOutline,
  StopCircleOutline,
  CreateOutline,
  SparklesOutline,
} from '@vicons/ionicons5'
import { testingApi, recordingsApi } from '@/api/client'
import type { DebugAction, AIAnalysis } from '@/api/client'

interface Verification {
  type: string
  passed: boolean
  message?: string
  diff_ratio?: number
  screenshots?: {
    baseline?: string
    actual?: string
    diff?: string
  }
}

interface DetailedStep {
  step_id: number
  step_description: string
  description: string
  action_type: string
  executed: boolean
  execution_error: string | null
  execution_time_ms: number
  passed: boolean
  pending?: boolean
  verifications: Verification[]
  selector?: string
}

interface TestResult {
  test_id: string
  status: string
  success: boolean
  total_steps: number
  passed_steps: number
  failed_steps: number
  duration_ms: number
  steps: DetailedStep[]
}

const props = defineProps<{
  show: boolean
  testId: string
  projectId: string
  recordingId: string
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'complete': [result: TestResult]
  'rerunFromStep': [stepId: number]
}>()

const showModal = ref(false)
const running = ref(true)
const cancelling = ref(false)
const currentStep = ref(0)
const totalSteps = ref(0)
const currentStepDescription = ref('')
const detailedSteps = ref<DetailedStep[]>([])
const result = ref<TestResult | null>(null)
const expandedSteps = ref<number[]>([])

// Debug模式状态
const debugPaused = ref(false)
const debugMode = ref(false)
const aiInTheLoop = ref(false)
const pendingSelectorFix = ref<string | null>(null)
const showModifySelector = ref(false)
const newSelector = ref('')
const sendingAction = ref(false)

// AI分析状态
const aiAnalysis = ref<AIAnalysis | null>(null)
const waitingForConfirmation = ref(false)
const userAiPrompt = ref('')

let ws: WebSocket | null = null

const title = computed(() => {
  if (running.value) return '测试执行中...'
  if (result.value?.success) return '✓ 测试完成'
  return '✗ 测试失败'
})

const progressPercent = computed(() => {
  if (totalSteps.value === 0) return 0
  return Math.round((currentStep.value / totalSteps.value) * 100)
})

const progressStatus = computed(() => {
  if (running.value) return 'default'
  if (result.value?.success) return 'success'
  return 'error'
})

watch(() => props.show, (val) => {
  showModal.value = val
  if (val && props.testId) {
    // Reset state
    running.value = true
    currentStep.value = 0
    totalSteps.value = 0
    detailedSteps.value = []
    result.value = null
    expandedSteps.value = []
    // Reset debug state
    debugPaused.value = false
    debugMode.value = false
    aiInTheLoop.value = false
    pendingSelectorFix.value = null
    newSelector.value = ''
    showModifySelector.value = false
    // Reset AI analysis state
    aiAnalysis.value = null
    waitingForConfirmation.value = false
    userAiPrompt.value = ''
    startWebSocket()
  }
})

watch(showModal, (val) => {
  emit('update:show', val)
  if (!val && ws) {
    ws.close()
    ws = null
  }
})

const startWebSocket = () => {
  const wsUrl = testingApi.getWebSocketUrl(props.testId)
  ws = new WebSocket(wsUrl)

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)

    if (data.error) {
      running.value = false
      return
    }

    currentStep.value = data.current_step
    totalSteps.value = data.total_steps
    currentStepDescription.value = data.current_step_description

    // 更新Debug模式状态
    debugMode.value = data.debug_mode || false
    debugPaused.value = data.debug_paused || false
    aiInTheLoop.value = data.ai_in_the_loop || false
    pendingSelectorFix.value = data.pending_selector_fix || null
    waitingForConfirmation.value = data.waiting_for_confirmation || false

    // 更新AI分析结果
    aiAnalysis.value = data.ai_analysis || null

    // 添加进行中的步骤
    if (data.current_step > detailedSteps.value.length) {
      detailedSteps.value.push({
        step_id: data.current_step,
        step_description: data.current_step_description,
        description: data.current_step_description,
        action_type: data.action_type || 'unknown',
        executed: false,
        execution_error: null,
        execution_time_ms: 0,
        passed: true,
        pending: true,
        verifications: [],
      })
    }

    // 检查是否完成
    if (['completed', 'failed', 'cancelled'].includes(data.status)) {
      running.value = false
      debugPaused.value = false
      fetchResult()
    }
  }

  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
    running.value = false
  }

  ws.onclose = () => {
    if (running.value) {
      setTimeout(fetchResult, 1000)
    }
  }
}

const fetchResult = async () => {
  try {
    const response = await testingApi.getResult(props.testId)
    if (response.data) {
      const data = response.data
      result.value = data

      // 更新详细步骤信息
      if (data.steps) {
        detailedSteps.value = data.steps.map((s: any) => ({
          step_id: s.step_id,
          step_description: s.step_description,
          description: s.step_description,
          action_type: s.action_type || 'unknown',
          executed: s.executed,
          execution_error: s.execution_error,
          execution_time_ms: s.execution_time_ms || 0,
          passed: s.passed,
          pending: false,
          verifications: s.verifications || [],
          selector: s.selector,
        }))

        // 自动展开失败的步骤
        expandedSteps.value = detailedSteps.value
          .filter(s => !s.passed)
          .map(s => s.step_id)
      }

      emit('complete', result.value!)
    }
  } catch (error) {
    console.error('Failed to fetch result:', error)
  }
}

const handleCancel = async () => {
  cancelling.value = true
  try {
    await testingApi.cancel(props.testId)
  } catch (error) {
    console.error('Failed to cancel:', error)
  }
  cancelling.value = false
}

const handleViewReport = () => {
  if (result.value) {
    const reportUrl = testingApi.getReportUrl(props.projectId, props.recordingId, result.value.test_id)
    window.open(reportUrl, '_blank')
  }
}

const handleClose = () => {
  showModal.value = false
}

const handleRerunFromStep = (stepId: number) => {
  emit('rerunFromStep', stepId)
  showModal.value = false
}

// Debug模式操作
const handleDebugAction = async (action: DebugAction) => {
  sendingAction.value = true
  try {
    // 传递用户AI提示词（如果有）
    await testingApi.sendDebugAction(props.testId, action, undefined, userAiPrompt.value || undefined)
    // 操作发送成功后，等待WebSocket更新状态
  } catch (error) {
    console.error('Failed to send debug action:', error)
  }
  sendingAction.value = false
}

const handleModifySelector = async () => {
  if (!newSelector.value) return

  sendingAction.value = true
  try {
    await testingApi.sendDebugAction(props.testId, 'modify', newSelector.value)
    showModifySelector.value = false
    newSelector.value = ''
  } catch (error) {
    console.error('Failed to modify selector:', error)
  }
  sendingAction.value = false
}

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const minutes = Math.floor(ms / 60000)
  const seconds = ((ms % 60000) / 1000).toFixed(0)
  return `${minutes}m ${seconds}s`
}

const getActionTagType = (action: string): 'default' | 'info' | 'success' | 'warning' | 'error' => {
  const types: Record<string, 'default' | 'info' | 'success' | 'warning' | 'error'> = {
    click: 'info',
    fill: 'success',
    navigate: 'warning',
    select: 'info',
    check: 'success',
    hover: 'default',
    scroll: 'default',
    keyboard: 'info',
    wait: 'warning',
  }
  return types[action] || 'default'
}

const getVerificationLabel = (type: string): string => {
  const labels: Record<string, string> = {
    screenshot: '截图对比',
    element: '元素检查',
    ai_screenshot: 'AI截图对比',
  }
  return labels[type] || type
}

const getScreenshotUrl = (filename: string | undefined): string => {
  if (!filename) return ''
  // 如果是完整路径，转换为API URL
  if (filename.includes('/') || filename.includes('\\')) {
    return `/api/v1/test/screenshot/${props.testId}/${encodeURIComponent(filename)}`
  }
  return recordingsApi.getScreenshotUrl(props.projectId, props.recordingId, filename)
}

const handleImgError = (e: Event) => {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
}

onUnmounted(() => {
  if (ws) {
    ws.close()
    ws = null
  }
})
</script>

<style scoped>
.test-progress {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.progress-section {
  padding: 8px 0;
}

.current-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: #e8f4ff;
  border-radius: 6px;
  font-size: 14px;
  border: 1px solid #b3d8ff;
}

.result-summary {
  margin-bottom: 8px;
}

.steps-container {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
  background: #fafafa;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  font-size: 13px;
}

.step-header.passed {
  color: #18a058;
}

.step-header.failed {
  color: #d03050;
}

.step-header.pending {
  color: #2080f0;
}

.pass-icon {
  color: #18a058;
}

.fail-icon {
  color: #d03050;
}

.pending-icon {
  color: #2080f0;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.step-id {
  font-weight: 600;
  min-width: 32px;
}

.step-desc {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #333;
}

.step-time {
  font-size: 11px;
  color: #999;
  margin-left: auto;
}

.step-detail {
  padding: 12px 16px;
  background: white;
  border-top: 1px solid #eee;
}

.detail-section {
  margin-bottom: 12px;
}

.detail-header-section .detail-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.rerun-btn {
  margin-left: auto;
}

.detail-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
}

.detail-label {
  font-weight: 500;
  color: #666;
  min-width: 60px;
}

.error-row {
  background: #fff2f0;
  padding: 8px;
  border-radius: 4px;
  border: 1px solid #ffccc7;
}

.error-message {
  color: #d03050;
  font-family: monospace;
  font-size: 12px;
  word-break: break-all;
}

.selector-code {
  background: #f0f0f0;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
  word-break: break-all;
}

.verifications {
  margin-top: 12px;
}

.section-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: #333;
  font-size: 13px;
}

.verification-item {
  padding: 10px;
  border-radius: 6px;
  margin-bottom: 8px;
  border: 1px solid #e0e0e0;
}

.verification-item.passed {
  background: #f6ffed;
  border-color: #b7eb8f;
}

.verification-item.failed {
  background: #fff2f0;
  border-color: #ffccc7;
}

.verification-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.verification-type {
  font-weight: 500;
}

.verification-message {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

.screenshot-compare {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.screenshot-item {
  text-align: center;
}

.screenshot-label {
  font-size: 11px;
  color: #666;
  margin-bottom: 4px;
  font-weight: 500;
}

.screenshot-item img {
  max-width: 100%;
  max-height: 150px;
  border: 1px solid #ddd;
  border-radius: 4px;
  object-fit: contain;
  background: #f5f5f5;
}

.screenshot-item.diff img {
  border-color: #ff4d4f;
}

/* Debug Panel Styles */
.debug-panel {
  margin-bottom: 16px;
}

.debug-info {
  margin-top: 12px;
}

.debug-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.debug-label {
  font-weight: 600;
  color: #666;
  min-width: 80px;
  flex-shrink: 0;
}

.selector-suggestion {
  background: #fff3cd;
  padding: 4px 8px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
  word-break: break-all;
  border: 1px solid #ffc107;
}

.debug-actions {
  margin-top: 16px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

/* AI Analysis Panel Styles */
.ai-analysis-panel {
  margin-bottom: 16px;
}

.ai-analysis-panel :deep(.n-card) {
  border-color: #e9d5ff;
  background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%);
}

.ai-analysis-panel :deep(.n-card-header) {
  padding-bottom: 8px;
}

.ai-analysis-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
}

.ai-label {
  font-weight: 600;
  color: #6b21a8;
  min-width: 80px;
  flex-shrink: 0;
}

.ai-text {
  color: #4c1d95;
  line-height: 1.5;
}

.ai-row.skip-reason {
  background: #fef3c7;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid #f59e0b;
}

.ai-row.skip-reason .ai-label {
  color: #92400e;
}

.ai-row.skip-reason span {
  color: #78350f;
}

/* User Prompt Section */
.user-prompt-section {
  margin-top: 16px;
  padding: 8px 0;
}

.user-prompt-section :deep(.n-collapse-item__header) {
  font-size: 13px;
  font-weight: 500;
}

.user-prompt-section :deep(.n-collapse-item__content-inner) {
  padding-top: 8px;
}
</style>
