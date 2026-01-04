import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor with better error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    let errorMessage = '请求失败'

    if (error.response) {
      const status = error.response.status
      const detail = error.response.data?.detail || error.response.data?.message

      switch (status) {
        case 400:
          errorMessage = detail || '请求参数错误'
          break
        case 404:
          errorMessage = detail || '资源未找到'
          break
        case 422:
          errorMessage = detail || '数据验证失败'
          break
        case 500:
          errorMessage = detail || '服务器内部错误'
          break
        default:
          errorMessage = detail || `请求失败 (${status})`
      }
    } else if (error.request) {
      errorMessage = '网络连接失败，请检查服务器是否运行'
    }

    error.displayMessage = errorMessage
    console.error('API Error:', errorMessage, error)
    return Promise.reject(error)
  }
)

export default api


// ==================== Projects API ====================

export interface Project {
  id: string
  slug: string
  name: string
  description: string
  base_url: string | null
  created_at: string
  updated_at: string
  recording_count: number
  tags: string[]
  status: string
}

export interface Recording {
  id: string
  folder_name: string
  title: string
  title_zh: string
  title_ja: string
  title_en: string
  created_at: string
  updated_at: string
  step_count: number
  has_manual: boolean
  has_video: boolean
  status: string
  tags: string[]
}

export interface Step {
  id: number
  action: string
  timestamp: string
  selector: string | null
  value: string | null
  url: string | null
  key: string | null
  description: string
  description_zh: string
  description_ja: string
  description_en: string
  screenshot: string | null
  element_screenshot: string | null
  page_title: string | null
  page_url: string | null
  notes: string | null
}

export const projectsApi = {
  list: (status?: string) =>
    api.get<{ projects: Project[]; total: number }>('/projects', { params: { status } }),

  get: (slug: string) =>
    api.get<Project>(`/projects/${slug}`),

  create: (data: { name: string; slug?: string; description?: string; base_url?: string; tags?: string[] }) =>
    api.post<Project>('/projects', data),

  update: (slug: string, data: Partial<Project>) =>
    api.put<Project>(`/projects/${slug}`, data),

  delete: (slug: string, force = false) =>
    api.delete(`/projects/${slug}`, { params: { force } }),

  listRecordings: (slug: string) =>
    api.get<{ recordings: Recording[]; total: number }>(`/projects/${slug}/recordings`),
}


// ==================== Recordings API ====================

export interface StepCreate {
  action: string
  description?: string
  description_zh?: string
  description_en?: string
  description_ja?: string
  selector?: string
  value?: string
  url?: string
  insert_after?: number
}

export const recordingsApi = {
  getSteps: (projectSlug: string, recordingName: string) =>
    api.get<{ title: string; steps: Step[]; metadata: Record<string, any> }>(
      `/recordings/${projectSlug}/${recordingName}/steps`
    ),

  createStep: (projectSlug: string, recordingName: string, data: StepCreate) =>
    api.post<Step>(`/recordings/${projectSlug}/${recordingName}/steps`, data),

  updateStep: (projectSlug: string, recordingName: string, stepId: number, data: Partial<Step>) =>
    api.put<Step>(`/recordings/${projectSlug}/${recordingName}/steps/${stepId}`, data),

  deleteStep: (projectSlug: string, recordingName: string, stepId: number) =>
    api.delete(`/recordings/${projectSlug}/${recordingName}/steps/${stepId}`),

  deleteRecording: (projectSlug: string, recordingName: string) =>
    api.delete(`/recordings/${projectSlug}/${recordingName}`),

  reorderSteps: (projectSlug: string, recordingName: string, stepIds: number[]) =>
    api.post(`/recordings/${projectSlug}/${recordingName}/steps/reorder`, { step_ids: stepIds }),

  getScreenshotUrl: (projectSlug: string, recordingName: string, filename: string) =>
    `/api/v1/recordings/${projectSlug}/${recordingName}/screenshots/${filename}`,

  replaceScreenshot: (projectSlug: string, recordingName: string, filename: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.put(`/recordings/${projectSlug}/${recordingName}/screenshots/${filename}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  cropScreenshot: (projectSlug: string, recordingName: string, filename: string, crop: { x: number; y: number; width: number; height: number }) =>
    api.post(`/recordings/${projectSlug}/${recordingName}/screenshots/${filename}/crop`, crop),

  annotateScreenshot: (projectSlug: string, recordingName: string, filename: string, annotations: any[]) =>
    api.post(`/recordings/${projectSlug}/${recordingName}/screenshots/${filename}/annotate`, { annotations }),

  regenerateAI: (projectSlug: string, recordingName: string, stepIds?: number[], languages = ['zh', 'en', 'ja'], provider = 'gemini', apiKey?: string) =>
    api.post(`/recordings/${projectSlug}/${recordingName}/ai/regenerate`, {
      step_ids: stepIds,
      languages,
      provider,
      api_key: apiKey,
    }),

  startRecording: (projectSlug: string, url: string, title?: string, showCursor = true) =>
    api.post<{ success: boolean; message: string; recording_name?: string }>('/recordings/start', {
      project_slug: projectSlug,
      url,
      title: title || '',
      show_cursor: showCursor,
    }),
}


// ==================== Manual API ====================

export const manualApi = {
  preview: (projectSlug: string, recordingName: string, language = 'zh') =>
    api.get<{ html_content: string; title: string }>(
      `/manual/preview/${projectSlug}/${recordingName}`,
      { params: { language } }
    ),

  previewHtml: (projectSlug: string, recordingName: string, language = 'zh') =>
    `/api/v1/manual/preview/${projectSlug}/${recordingName}/html?language=${language}`,

  generate: (data: { project_slug: string; recording_name: string; format: string; languages: string[]; use_ai: boolean; provider?: string }) =>
    api.post('/manual/generate', data),

  downloadUrl: (projectSlug: string, recordingName: string, format: string) =>
    `/api/v1/manual/download/${projectSlug}/${recordingName}/${format}`,
}


// ==================== Video API ====================

export interface VideoInfo {
  has_video: boolean
  filename?: string
  size?: number
  chapters?: Array<{
    time: number
    time_formatted: string
    title: string
    title_zh: string
    title_ja: string
    title_en: string
  }>
}

export const videoApi = {
  getVideoUrl: (projectSlug: string, recordingName: string) =>
    `/api/v1/recordings/${projectSlug}/${recordingName}/video`,

  getInfo: (projectSlug: string, recordingName: string) =>
    api.get<VideoInfo>(`/recordings/${projectSlug}/${recordingName}/video/info`),

  captureFrame: (projectSlug: string, recordingName: string, imageBlob: Blob, stepId?: number) => {
    const formData = new FormData()
    formData.append('file', imageBlob, 'capture.png')
    const url = stepId
      ? `/recordings/${projectSlug}/${recordingName}/video/capture?step_id=${stepId}`
      : `/recordings/${projectSlug}/${recordingName}/video/capture`
    return api.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  setStepScreenshot: (projectSlug: string, recordingName: string, stepId: number, imageBlob: Blob) => {
    const formData = new FormData()
    formData.append('file', imageBlob, 'screenshot.png')
    return api.post(`/recordings/${projectSlug}/${recordingName}/steps/${stepId}/screenshot`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}


// ==================== Testing API ====================

export interface TestConfig {
  screenshotCompare: boolean
  compareMode: 'pixel' | 'ai'
  threshold: number
  aiStrictness: 'lenient' | 'normal' | 'strict'
  elementCheck: boolean
  headless: boolean
  stepDelay: number
  startFromStep?: number  // 从第几步开始验证（之前的步骤快速回放）
  aiProvider?: 'gemini' | 'claude' | 'openai'
  googleApiKey?: string
  anthropicApiKey?: string
  openaiApiKey?: string
  // Debug模式配置
  debugMode?: boolean
  aiInTheLoop?: boolean
  aiAutoSkip?: boolean
  aiAutoFix?: boolean
  pauseOnFailure?: boolean
  maxAutoRetries?: number
  // 测试变量（用于密码等敏感信息）
  testVariables?: Record<string, string>
}

export interface AIAnalysis {
  step_id: number
  action_type: string
  analysis_type: string  // "pre_execution" | "failure_diagnosis" | "skip_decision"
  should_skip: boolean
  skip_reason: string
  should_modify: boolean
  suggested_selector: string
  confidence: number
  analysis_text: string
  screenshot_path: string
}

export interface DebugStatus {
  paused: boolean
  debug_mode: boolean
  ai_in_the_loop: boolean
  pending_selector_fix: string | null
  waiting_for_confirmation: boolean
  current_step: number
  current_step_description: string
  ai_analysis: AIAnalysis | null
  user_ai_prompt: string
}

export type DebugAction = 'continue' | 'retry' | 'skip' | 'modify' | 'abort'

export interface TestRunResponse {
  test_id: string
  status: string
  message: string
}

export interface TestStatus {
  test_id: string
  status: string
  current_step: number
  total_steps: number
  current_step_description: string
  progress_percent: number
}

export interface TestResult {
  test_id: string
  status: string
  success: boolean
  total_steps: number
  passed_steps: number
  failed_steps: number
  duration_ms: number
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  steps: TestStepResult[]
}

export interface TestStepResult {
  step_id: number
  step_description: string
  action_type: string
  executed: boolean
  execution_error: string | null
  execution_time_ms: number
  passed: boolean
  verifications: any[]
}

export interface TestRunInfo {
  test_id: string
  status: string
  success: boolean
  total_steps: number
  passed_steps: number
  failed_steps: number
  started_at: string | null
  run_dir: string
}

export const testingApi = {
  run: (projectSlug: string, recordingName: string, config: TestConfig) =>
    api.post<TestRunResponse>(`/test/run/${projectSlug}/${recordingName}`, {
      screenshot_compare: config.screenshotCompare,
      screenshot_compare_mode: config.compareMode,
      element_check: config.elementCheck,
      threshold: config.threshold,
      ai_strictness: config.aiStrictness,
      headless: config.headless,
      step_delay: config.stepDelay,
      start_from_step: config.startFromStep || 1,
      ai_provider: config.aiProvider || 'gemini',
      google_api_key: config.googleApiKey || null,
      anthropic_api_key: config.anthropicApiKey || null,
      openai_api_key: config.openaiApiKey || null,
      // Debug模式配置
      debug_mode: config.debugMode || false,
      ai_in_the_loop: config.aiInTheLoop || false,
      ai_auto_skip: config.aiAutoSkip ?? true,
      ai_auto_fix: config.aiAutoFix ?? true,
      pause_on_failure: config.pauseOnFailure ?? true,
      max_auto_retries: config.maxAutoRetries ?? 2,
      // 测试变量
      test_variables: config.testVariables || {},
    }),

  getStatus: (testId: string) =>
    api.get<TestStatus>(`/test/status/${testId}`),

  getResult: (testId: string) =>
    api.get<TestResult>(`/test/result/${testId}`),

  cancel: (testId: string) =>
    api.post(`/test/cancel/${testId}`),

  listRuns: (projectSlug: string, recordingName: string) =>
    api.get<TestRunInfo[]>(`/test/runs/${projectSlug}/${recordingName}`),

  getReportUrl: (projectSlug: string, recordingName: string, testId: string) =>
    `/api/v1/test/report/${projectSlug}/${recordingName}/${testId}`,

  getWebSocketUrl: (testId: string) => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${wsProtocol}//${host}/api/v1/test/ws/${testId}`
  },

  exportScriptUrl: (projectSlug: string, recordingName: string, language = 'zh', headless = false, stepDelay = 0.5) =>
    `/api/v1/test/export/${projectSlug}/${recordingName}?language=${language}&headless=${headless}&step_delay=${stepDelay}`,

  // Debug模式API
  sendDebugAction: (testId: string, action: DebugAction, newSelector?: string, userAiPrompt?: string) =>
    api.post(`/test/debug/${testId}`, { action, new_selector: newSelector, user_ai_prompt: userAiPrompt }),

  getDebugStatus: (testId: string) =>
    api.get<DebugStatus>(`/test/debug/status/${testId}`),
}
