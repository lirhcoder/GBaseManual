<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NLayout, NLayoutHeader, NLayoutContent, NLayoutSider,
  NCard, NButton, NSpace, NBreadcrumb, NBreadcrumbItem,
  NTabs, NTabPane, NInput, NModal, NSelect, NSpin,
  NImage, NScrollbar, NEmpty, NCheckbox, NTooltip,
  useMessage, useDialog
} from 'naive-ui'
import { VueDraggable } from 'vue-draggable-plus'
import { recordingsApi, manualApi, videoApi, type Step, type VideoInfo } from '@/api/client'
import ImageEditor from '@/components/editor/ImageEditor.vue'
import AddStepModal, { type NewStepData } from '@/components/editor/AddStepModal.vue'
import BatchOperations from '@/components/editor/BatchOperations.vue'
import VideoPlayer from '@/components/editor/VideoPlayer.vue'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const dialog = useDialog()

const projectSlug = computed(() => route.params.slug as string)
const recordingName = computed(() => route.params.recording as string)

const loading = ref(false)
const saving = ref(false)
const title = ref('')
const steps = ref<Step[]>([])
const selectedStepId = ref<number | null>(null)
const selectedSteps = ref<Set<number>>(new Set())
const currentLang = ref<'zh' | 'en' | 'ja'>('zh')

// Preview modal
const showPreview = ref(false)
const previewUrl = ref('')

// AI regeneration
const showAIModal = ref(false)
const aiProvider = ref('gemini')
const aiLoading = ref(false)
const singleStepAI = ref<number | null>(null) // Track single step regeneration

// Image editor
const showImageEditor = ref(false)
const editingScreenshot = ref('')
const editingScreenshotUrl = ref('')

// Add step modal
const showAddStepModal = ref(false)
const addStepAfter = ref<number | null>(null)
const addingStep = ref(false)

// Video player
const showVideoPlayer = ref(false)
const videoInfo = ref<VideoInfo | null>(null)

// API Key settings
const showSettingsModal = ref(false)
const apiKeys = ref({
  gemini: '',
  claude: '',
  openai: '',
})

// Load API keys from localStorage
function loadApiKeys() {
  const saved = localStorage.getItem('webManualApiKeys')
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      apiKeys.value = { ...apiKeys.value, ...parsed }
    } catch (e) {
      console.error('Failed to load API keys:', e)
    }
  }
}

// Save API keys to localStorage
function saveApiKeys() {
  localStorage.setItem('webManualApiKeys', JSON.stringify(apiKeys.value))
  message.success('API Key 已保存')
  showSettingsModal.value = false
}

// Get current API key based on provider
function getCurrentApiKey(): string | undefined {
  const key = apiKeys.value[aiProvider.value as keyof typeof apiKeys.value]
  return key || undefined
}

const selectedStep = computed(() => {
  return steps.value.find(s => s.id === selectedStepId.value) || null
})

async function loadRecording() {
  loading.value = true
  try {
    const { data } = await recordingsApi.getSteps(projectSlug.value, recordingName.value)
    title.value = data.title
    steps.value = data.steps
    if (steps.value.length > 0 && !selectedStepId.value) {
      selectedStepId.value = steps.value[0].id
    }
  } catch (error: any) {
    message.error(error.displayMessage || '加载录制失败')
  } finally {
    loading.value = false
  }
}

async function saveStep(step: Step) {
  saving.value = true
  try {
    await recordingsApi.updateStep(projectSlug.value, recordingName.value, step.id, {
      description: step.description,
      description_zh: step.description_zh,
      description_ja: step.description_ja,
      description_en: step.description_en,
      notes: step.notes,
    })
    message.success('保存成功')
  } catch (error: any) {
    message.error(error.displayMessage || '保存失败')
  } finally {
    saving.value = false
  }
}

async function deleteStep(stepId: number) {
  dialog.warning({
    title: '确认删除',
    content: '确定要删除这个步骤吗？此操作不可恢复。',
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await recordingsApi.deleteStep(projectSlug.value, recordingName.value, stepId)
        steps.value = steps.value.filter(s => s.id !== stepId)
        steps.value.forEach((s, i) => s.id = i + 1)
        selectedSteps.value.delete(stepId)
        if (selectedStepId.value === stepId) {
          selectedStepId.value = steps.value[0]?.id || null
        }
        message.success('步骤已删除')
      } catch (error: any) {
        message.error(error.displayMessage || '删除失败')
      }
    }
  })
}

async function deleteSelectedSteps() {
  const idsToDelete = Array.from(selectedSteps.value)
  for (const id of idsToDelete) {
    try {
      await recordingsApi.deleteStep(projectSlug.value, recordingName.value, id)
    } catch (error) {
      // Continue with others
    }
  }
  await loadRecording()
  selectedSteps.value.clear()
  message.success(`已删除 ${idsToDelete.length} 个步骤`)
}

async function onDragEnd() {
  const stepIds = steps.value.map(s => s.id)
  try {
    await recordingsApi.reorderSteps(projectSlug.value, recordingName.value, stepIds)
    steps.value.forEach((s, i) => s.id = i + 1)
    message.success('顺序已更新')
  } catch (error: any) {
    message.error(error.displayMessage || '更新顺序失败')
    loadRecording()
  }
}

function getScreenshotUrl(filename: string) {
  return recordingsApi.getScreenshotUrl(projectSlug.value, recordingName.value, filename)
}

function getActionLabel(action: string) {
  const labels: Record<string, string> = {
    navigate: '导航',
    click: '点击',
    fill: '输入',
    select: '选择',
    check: '勾选',
    uncheck: '取消勾选',
    hover: '悬停',
    scroll: '滚动',
    keyboard: '键盘',
    wait: '等待',
    screenshot: '截图',
    custom: '自定义',
  }
  return labels[action] || action
}

function getDescription(step: Step) {
  if (currentLang.value === 'zh') return step.description_zh || step.description
  if (currentLang.value === 'en') return step.description_en || step.description
  if (currentLang.value === 'ja') return step.description_ja || step.description
  return step.description
}

function setDescription(step: Step, value: string) {
  if (currentLang.value === 'zh') {
    step.description_zh = value
    step.description = value
  } else if (currentLang.value === 'en') {
    step.description_en = value
  } else if (currentLang.value === 'ja') {
    step.description_ja = value
  }
}

function openPreview() {
  previewUrl.value = manualApi.previewHtml(projectSlug.value, recordingName.value, currentLang.value)
  showPreview.value = true
}

function openAIModalForStep(stepId: number) {
  singleStepAI.value = stepId
  showAIModal.value = true
}

function openAIModalForBatch() {
  singleStepAI.value = null
  showAIModal.value = true
}

async function regenerateAI() {
  let stepIds: number[] | undefined

  if (singleStepAI.value !== null) {
    // Single step regeneration
    stepIds = [singleStepAI.value]
  } else if (selectedSteps.value.size > 0) {
    // Batch selected steps
    stepIds = Array.from(selectedSteps.value)
  }
  // else: undefined means all steps

  const apiKey = getCurrentApiKey()
  if (!apiKey) {
    message.warning('请先在设置中配置 API Key')
    showSettingsModal.value = true
    return
  }

  aiLoading.value = true
  try {
    await recordingsApi.regenerateAI(
      projectSlug.value,
      recordingName.value,
      stepIds,
      ['zh', 'en', 'ja'],
      aiProvider.value,
      apiKey
    )
    message.success('AI 描述生成成功')
    showAIModal.value = false
    singleStepAI.value = null
    loadRecording()
  } catch (error: any) {
    message.error(error.displayMessage || 'AI 生成失败，请检查 API Key 配置')
  } finally {
    aiLoading.value = false
  }
}

async function generateManual(format: string) {
  message.loading(`正在生成 ${format.toUpperCase()} 手册...`)
  try {
    const { data } = await manualApi.generate({
      project_slug: projectSlug.value,
      recording_name: recordingName.value,
      format,
      languages: [currentLang.value],
      use_ai: false,
    })
    if (data.success) {
      message.success(`${format.toUpperCase()} 手册生成成功`)
      // Open download
      window.open(manualApi.downloadUrl(projectSlug.value, recordingName.value, format), '_blank')
    } else {
      message.error(data.message || '生成失败')
    }
  } catch (error: any) {
    message.error(error.displayMessage || '生成手册失败')
  }
}

function toggleStepSelection(stepId: number) {
  if (selectedSteps.value.has(stepId)) {
    selectedSteps.value.delete(stepId)
  } else {
    selectedSteps.value.add(stepId)
  }
}

function selectAllSteps() {
  selectedSteps.value = new Set(steps.value.map(s => s.id))
}

function clearSelection() {
  selectedSteps.value.clear()
}

// Image editor functions
function openImageEditor(step: Step) {
  if (!step.screenshot) return
  editingScreenshot.value = step.screenshot
  editingScreenshotUrl.value = getScreenshotUrl(step.screenshot)
  showImageEditor.value = true
}

async function handleImageSave(dataUrl: string) {
  if (!editingScreenshot.value) return

  // Convert data URL to Blob
  const response = await fetch(dataUrl)
  const blob = await response.blob()
  // Remove query params from filename if any
  const cleanFilename = editingScreenshot.value.split('?')[0]
  const file = new File([blob], cleanFilename, { type: 'image/png' })

  try {
    await recordingsApi.replaceScreenshot(
      projectSlug.value,
      recordingName.value,
      cleanFilename,
      file
    )
    message.success('截图已更新')
    // Force reload image by adding timestamp
    const step = steps.value.find(s => s.screenshot?.split('?')[0] === cleanFilename)
    if (step) {
      step.screenshot = `${cleanFilename}?t=${Date.now()}`
    }
  } catch (error: any) {
    message.error(error.displayMessage || '更新截图失败')
  }
}

// Add step functions
function openAddStepModal(afterStepId?: number) {
  addStepAfter.value = afterStepId || null
  showAddStepModal.value = true
}

async function handleAddStep(stepData: NewStepData) {
  addingStep.value = true
  try {
    const { data: newStep } = await recordingsApi.createStep(
      projectSlug.value,
      recordingName.value,
      {
        action: stepData.action,
        description: stepData.description,
        description_zh: stepData.description_zh,
        description_en: stepData.description_en,
        description_ja: stepData.description_ja,
        selector: stepData.selector,
        value: stepData.value,
        url: stepData.url,
        insert_after: stepData.insertAfter,
      }
    )

    // If there's a screenshot, upload it
    if (stepData.screenshot) {
      const filename = `step_${String(newStep.id).padStart(3, '0')}_${Date.now()}.png`
      await recordingsApi.replaceScreenshot(
        projectSlug.value,
        recordingName.value,
        filename,
        stepData.screenshot
      )
      // Update step with screenshot filename
      await recordingsApi.updateStep(
        projectSlug.value,
        recordingName.value,
        newStep.id,
        { screenshot: filename } as any
      )
    }

    message.success('步骤添加成功')
    await loadRecording()
    selectedStepId.value = newStep.id
  } catch (error: any) {
    message.error(error.displayMessage || '添加步骤失败')
  } finally {
    addingStep.value = false
  }
}

// Batch operation handlers
function copySelectedDescriptions() {
  const descriptions = steps.value
    .filter(s => selectedSteps.value.has(s.id))
    .map(s => `${s.id}. ${getDescription(s)}`)
    .join('\n')

  navigator.clipboard.writeText(descriptions)
}

function exportSelectedSteps() {
  const selectedData = steps.value.filter(s => selectedSteps.value.has(s.id))
  const json = JSON.stringify(selectedData, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `steps_${recordingName.value}.json`
  a.click()
  URL.revokeObjectURL(url)
  message.success('已导出选中步骤')
}

// Keyboard shortcuts
function handleKeydown(e: KeyboardEvent) {
  // Ctrl/Cmd + S to save
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault()
    if (selectedStep.value) {
      saveStep(selectedStep.value)
    }
  }

  // Delete key to delete selected step
  if (e.key === 'Delete' && selectedStep.value && !e.ctrlKey && !e.metaKey) {
    const target = e.target as HTMLElement
    // Only delete if not in an input/textarea
    if (!target.matches('input, textarea, [contenteditable]')) {
      deleteStep(selectedStep.value.id)
    }
  }

  // Arrow keys to navigate steps
  if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
    const target = e.target as HTMLElement
    if (!target.matches('input, textarea, [contenteditable]')) {
      e.preventDefault()
      const currentIndex = steps.value.findIndex(s => s.id === selectedStepId.value)
      if (e.key === 'ArrowUp' && currentIndex > 0) {
        selectedStepId.value = steps.value[currentIndex - 1].id
      } else if (e.key === 'ArrowDown' && currentIndex < steps.value.length - 1) {
        selectedStepId.value = steps.value[currentIndex + 1].id
      }
    }
  }
}

// Video functions
async function loadVideoInfo() {
  try {
    const { data } = await videoApi.getInfo(projectSlug.value, recordingName.value)
    videoInfo.value = data
  } catch (err) {
    console.error('Failed to load video info:', err)
  }
}

function toggleVideoPlayer() {
  showVideoPlayer.value = !showVideoPlayer.value
}

async function handleFrameCaptured(stepId: number | null) {
  // Close video player after successful capture
  showVideoPlayer.value = false

  // Reload recording to get updated screenshots
  await loadRecording()
  if (stepId !== null) {
    // Select the step that was updated
    selectedStepId.value = stepId
  }
  // Note: VideoPlayer already shows success message, no need to duplicate
}

onMounted(() => {
  loadApiKeys()
  loadRecording()
  loadVideoInfo()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <NLayout class="editor-layout" has-sider>
    <!-- Sidebar: Step List -->
    <NLayoutSider
      :width="350"
      bordered
      content-style="padding: 0;"
      class="step-sidebar"
    >
      <div class="sidebar-header">
        <NBreadcrumb>
          <NBreadcrumbItem @click="router.push('/')">项目</NBreadcrumbItem>
          <NBreadcrumbItem @click="router.push(`/projects/${projectSlug}`)">
            {{ projectSlug }}
          </NBreadcrumbItem>
        </NBreadcrumb>
        <h3>{{ title }}</h3>
      </div>

      <div class="sidebar-toolbar">
        <BatchOperations
          :selected-count="selectedSteps.size"
          :total-count="steps.length"
          @delete="deleteSelectedSteps"
          @regenerate-ai="openAIModalForBatch"
          @clear-selection="clearSelection"
          @select-all="selectAllSteps"
          @export="exportSelectedSteps"
          @copy-descriptions="copySelectedDescriptions"
        />
      </div>

      <NScrollbar class="step-list-scroll">
        <NSpin :show="loading">
          <VueDraggable
            v-model="steps"
            :animation="200"
            handle=".drag-handle"
            class="step-list"
            @end="onDragEnd"
          >
            <div
              v-for="step in steps"
              :key="step.id"
              class="step-item"
              :class="{ active: selectedStepId === step.id, selected: selectedSteps.has(step.id) }"
              @click="selectedStepId = step.id"
            >
              <NCheckbox
                :checked="selectedSteps.has(step.id)"
                @update:checked="() => toggleStepSelection(step.id)"
                @click.stop
              />
              <div class="drag-handle">⋮⋮</div>
              <div class="step-number">{{ step.id }}</div>
              <div class="step-info">
                <div class="step-action">{{ getActionLabel(step.action) }}</div>
                <div class="step-desc">{{ getDescription(step) }}</div>
              </div>
              <img
                v-if="step.screenshot"
                :src="getScreenshotUrl(step.screenshot)"
                class="step-thumb"
                @error="(e: Event) => (e.target as HTMLImageElement).style.display = 'none'"
              />
              <NTooltip trigger="hover">
                <template #trigger>
                  <NButton
                    text
                    size="tiny"
                    class="insert-step-btn"
                    @click.stop="openAddStepModal(step.id)"
                  >
                    +
                  </NButton>
                </template>
                在此步骤后插入
              </NTooltip>
            </div>
          </VueDraggable>

          <div class="add-step-btn">
            <NButton block dashed @click="openAddStepModal()">
              + 添加步骤
            </NButton>
          </div>
        </NSpin>
      </NScrollbar>
    </NLayoutSider>

    <!-- Main Content: Editor -->
    <NLayout>
      <NLayoutHeader class="editor-header">
        <NSpace>
          <NTooltip trigger="hover">
            <template #trigger>
              <NButton quaternary size="small">快捷键</NButton>
            </template>
            <div style="line-height: 1.8;">
              <div><kbd>Ctrl+S</kbd> 保存当前步骤</div>
              <div><kbd>↑/↓</kbd> 切换步骤</div>
              <div><kbd>Delete</kbd> 删除当前步骤</div>
            </div>
          </NTooltip>
        </NSpace>
        <NSpace>
          <NButton
            v-if="videoInfo?.has_video"
            :type="showVideoPlayer ? 'primary' : 'default'"
            @click="toggleVideoPlayer"
          >
            {{ showVideoPlayer ? '隐藏视频' : '视频截图' }}
          </NButton>
          <NButton @click="openPreview">预览手册</NButton>
          <NButton type="primary" @click="generateManual('html')">导出 HTML</NButton>
          <NButton @click="generateManual('pdf')">导出 PDF</NButton>
          <NButton quaternary @click="showSettingsModal = true">⚙ 设置</NButton>
        </NSpace>
      </NLayoutHeader>

      <NLayoutContent class="editor-content">
        <!-- Video Player -->
        <VideoPlayer
          v-if="showVideoPlayer"
          :project-slug="projectSlug"
          :recording-name="recordingName"
          :selected-step-id="selectedStepId"
          @close="showVideoPlayer = false"
          @frame-captured="handleFrameCaptured"
        />

        <NEmpty v-if="!selectedStep" description="选择一个步骤开始编辑" />

        <template v-else>
          <!-- Screenshot -->
          <NCard title="截图" class="screenshot-card">
            <template #header-extra>
              <NSpace>
                <NButton
                  v-if="selectedStep.screenshot"
                  size="small"
                  @click="openImageEditor(selectedStep)"
                >
                  编辑截图
                </NButton>
              </NSpace>
            </template>

            <div class="screenshot-container">
              <NImage
                v-if="selectedStep.screenshot"
                :src="getScreenshotUrl(selectedStep.screenshot)"
                object-fit="contain"
                style="max-height: 400px; max-width: 100%;"
                :preview-disabled="false"
              />
              <NEmpty v-else description="无截图" />
            </div>
          </NCard>

          <!-- Description Editor -->
          <NCard title="描述编辑" class="desc-card">
            <template #header-extra>
              <NTabs v-model:value="currentLang" type="segment" size="small">
                <NTabPane name="zh" tab="中文" />
                <NTabPane name="en" tab="English" />
                <NTabPane name="ja" tab="日本語" />
              </NTabs>
            </template>

            <NInput
              :value="getDescription(selectedStep)"
              @update:value="(v: string) => setDescription(selectedStep!, v)"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 8 }"
              placeholder="输入步骤描述..."
            />

            <div class="editor-actions">
              <NButton type="primary" :loading="saving" @click="saveStep(selectedStep!)">
                保存
              </NButton>
              <NButton @click="openAIModalForStep(selectedStep!.id)">
                AI 重新生成
              </NButton>
              <NButton type="error" ghost @click="deleteStep(selectedStep!.id)">
                删除步骤
              </NButton>
            </div>
          </NCard>

          <!-- Notes -->
          <NCard title="备注" class="notes-card">
            <NInput
              v-model:value="selectedStep.notes"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 4 }"
              placeholder="添加备注（可选）..."
            />
          </NCard>

          <!-- Meta Info -->
          <NCard title="元信息" size="small">
            <div class="meta-grid">
              <div class="meta-item">
                <span class="meta-label">操作类型</span>
                <span class="meta-value">{{ getActionLabel(selectedStep.action) }}</span>
              </div>
              <div v-if="selectedStep.selector" class="meta-item">
                <span class="meta-label">选择器</span>
                <code class="meta-value">{{ selectedStep.selector }}</code>
              </div>
              <div v-if="selectedStep.value" class="meta-item">
                <span class="meta-label">输入值</span>
                <span class="meta-value">{{ selectedStep.value }}</span>
              </div>
              <div v-if="selectedStep.page_url" class="meta-item">
                <span class="meta-label">页面URL</span>
                <span class="meta-value">{{ selectedStep.page_url }}</span>
              </div>
              <div v-if="selectedStep.page_title" class="meta-item">
                <span class="meta-label">页面标题</span>
                <span class="meta-value">{{ selectedStep.page_title }}</span>
              </div>
            </div>
          </NCard>
        </template>
      </NLayoutContent>
    </NLayout>

    <!-- Preview Modal -->
    <NModal v-model:show="showPreview" preset="card" title="手册预览" style="width: 90%; max-width: 1000px;">
      <iframe
        :src="previewUrl"
        style="width: 100%; height: 70vh; border: none;"
      />
    </NModal>

    <!-- AI Generation Modal -->
    <NModal v-model:show="showAIModal" preset="dialog" title="AI 生成描述" @after-leave="singleStepAI = null">
      <p>使用 AI 分析截图并生成智能描述。</p>
      <p v-if="singleStepAI !== null">
        将为当前步骤（步骤 {{ singleStepAI }}）生成描述。
      </p>
      <p v-else-if="selectedSteps.size > 0">
        将为 <strong>{{ selectedSteps.size }}</strong> 个选中的步骤生成描述。
      </p>
      <p v-else>将为所有 <strong>{{ steps.length }}</strong> 个步骤生成描述。</p>

      <NSelect
        v-model:value="aiProvider"
        :options="[
          { label: 'Gemini (推荐，成本最低)', value: 'gemini' },
          { label: 'Claude', value: 'claude' },
          { label: 'OpenAI', value: 'openai' },
        ]"
        style="margin-top: 16px;"
      />

      <p style="margin-top: 12px; font-size: 12px; color: #666;">
        提示：请先在右上角"设置"中配置 API Key
      </p>

      <template #action>
        <NButton @click="showAIModal = false">取消</NButton>
        <NButton type="primary" :loading="aiLoading" @click="regenerateAI">
          开始生成
        </NButton>
      </template>
    </NModal>

    <!-- Settings Modal -->
    <NModal v-model:show="showSettingsModal" preset="card" title="API Key 设置" style="width: 500px;">
      <p style="margin-bottom: 16px; color: #666;">
        配置 AI 服务的 API Key。密钥保存在浏览器本地，不会上传到服务器。
      </p>

      <div class="settings-form">
        <div class="settings-item">
          <label>Gemini API Key</label>
          <NInput
            v-model:value="apiKeys.gemini"
            type="password"
            show-password-on="click"
            placeholder="输入 Google Gemini API Key"
          />
          <span class="settings-hint">推荐使用，成本最低</span>
        </div>

        <div class="settings-item">
          <label>Claude API Key</label>
          <NInput
            v-model:value="apiKeys.claude"
            type="password"
            show-password-on="click"
            placeholder="输入 Anthropic Claude API Key"
          />
        </div>

        <div class="settings-item">
          <label>OpenAI API Key</label>
          <NInput
            v-model:value="apiKeys.openai"
            type="password"
            show-password-on="click"
            placeholder="输入 OpenAI API Key"
          />
        </div>
      </div>

      <template #footer>
        <NSpace justify="end">
          <NButton @click="showSettingsModal = false">取消</NButton>
          <NButton type="primary" @click="saveApiKeys">保存</NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- Image Editor Modal -->
    <ImageEditor
      v-model:show="showImageEditor"
      :image-url="editingScreenshotUrl"
      :filename="editingScreenshot"
      @save="handleImageSave"
    />

    <!-- Add Step Modal -->
    <AddStepModal
      v-model:show="showAddStepModal"
      :insert-after-step-id="addStepAfter"
      @add="handleAddStep"
    />
  </NLayout>
</template>

<style scoped>
.editor-layout {
  height: 100vh;
}

.step-sidebar {
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e0e0e0;
}

.sidebar-header h3 {
  margin: 8px 0 0;
  font-size: 1.1rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-toolbar {
  padding: 8px 16px;
  border-bottom: 1px solid #e0e0e0;
}

.step-list-scroll {
  flex: 1;
}

.step-list {
  padding: 8px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.step-item:hover {
  background: #f5f5f5;
}

.step-item.active {
  background: #e8f4ff;
  border-color: #1890ff;
}

.step-item.selected {
  background: #f0f9ff;
}

.drag-handle {
  cursor: grab;
  color: #999;
  font-size: 14px;
  padding: 4px;
}

.drag-handle:hover {
  color: #666;
}

.step-number {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1890ff;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: bold;
  flex-shrink: 0;
}

.step-info {
  flex: 1;
  min-width: 0;
}

.step-action {
  font-size: 11px;
  color: #1890ff;
  font-weight: 500;
  text-transform: uppercase;
}

.step-desc {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #333;
}

.step-thumb {
  width: 56px;
  height: 42px;
  object-fit: cover;
  border-radius: 4px;
  flex-shrink: 0;
  border: 1px solid #e0e0e0;
}

.insert-step-btn {
  opacity: 0;
  transition: opacity 0.2s;
  font-size: 16px;
  color: #1890ff;
}

.step-item:hover .insert-step-btn {
  opacity: 1;
}

.add-step-btn {
  padding: 8px;
}

.editor-header {
  padding: 12px 24px;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  justify-content: space-between;
  background: white;
}

/* kbd styles need to be global for tooltips */

.editor-content {
  padding: 24px;
  overflow: auto;
  background: #f8f9fa;
}

.screenshot-card,
.desc-card,
.notes-card {
  margin-bottom: 16px;
}

.screenshot-container {
  display: flex;
  justify-content: center;
  background: #f0f0f0;
  border-radius: 8px;
  padding: 16px;
  min-height: 200px;
}

.editor-actions {
  margin-top: 16px;
  display: flex;
  gap: 8px;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-label {
  font-size: 12px;
  color: #999;
}

.meta-value {
  font-size: 13px;
  color: #333;
  word-break: break-all;
}

code.meta-value {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.settings-item label {
  font-weight: 500;
  color: #333;
}

.settings-hint {
  font-size: 12px;
  color: #18a058;
}
</style>

<style>
/* Global styles for elements rendered outside scoped context (e.g., tooltips) */
kbd {
  background: #333;
  color: #fff;
  border: 1px solid #555;
  border-radius: 4px;
  padding: 2px 8px;
  font-family: monospace;
  font-size: 12px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.2);
}
</style>
