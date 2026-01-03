<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NLayout, NLayoutHeader, NLayoutContent,
  NCard, NButton, NSpace, NEmpty, NDataTable, NBreadcrumb,
  NBreadcrumbItem, NTag, NIcon, NModal, NForm, NFormItem,
  NInput, NSwitch,
  useMessage
} from 'naive-ui'
import { projectsApi, recordingsApi, type Project, type Recording } from '@/api/client'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const projectSlug = computed(() => route.params.slug as string)
const loading = ref(false)
const project = ref<Project | null>(null)
const recordings = ref<Recording[]>([])

// Recording modal
const showRecordModal = ref(false)
const recordingForm = ref({
  url: '',
  title: '',
  showCursor: true,
})
const startingRecord = ref(false)

async function loadProject() {
  loading.value = true
  try {
    const [projectRes, recordingsRes] = await Promise.all([
      projectsApi.get(projectSlug.value),
      projectsApi.listRecordings(projectSlug.value),
    ])
    project.value = projectRes.data
    recordings.value = recordingsRes.data.recordings
  } catch (error: any) {
    message.error(error.displayMessage || '加载项目失败')
  } finally {
    loading.value = false
  }
}

async function startRecording() {
  if (!recordingForm.value.url) {
    message.warning('请输入要录制的网址')
    return
  }

  startingRecord.value = true
  try {
    const { data } = await recordingsApi.startRecording(
      projectSlug.value,
      recordingForm.value.url,
      recordingForm.value.title,
      recordingForm.value.showCursor,
    )

    if (data.success) {
      message.success('录制已启动，浏览器窗口将打开。录制完成后按 F2 或点击停止按钮结束。')
      showRecordModal.value = false
      // Reset form
      recordingForm.value = { url: '', title: '', showCursor: true }
      // Refresh recordings list after a delay
      setTimeout(() => loadProject(), 3000)
    } else {
      message.error(data.message || '启动录制失败')
    }
  } catch (error: any) {
    message.error(error.displayMessage || '启动录制失败')
  } finally {
    startingRecord.value = false
  }
}

function goToEditor(recording: Recording) {
  router.push(`/projects/${projectSlug.value}/${recording.folder_name}`)
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const columns = [
  {
    title: '名称',
    key: 'title',
    render: (row: Recording) => row.title || row.folder_name,
  },
  {
    title: '文件夹',
    key: 'folder_name',
  },
  {
    title: '步骤数',
    key: 'step_count',
    width: 80,
  },
  {
    title: '手册',
    key: 'has_manual',
    width: 80,
    render: (row: Recording) => row.has_manual ? '✅' : '❌',
  },
  {
    title: '视频',
    key: 'has_video',
    width: 80,
    render: (row: Recording) => row.has_video ? '✅' : '❌',
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: 160,
    render: (row: Recording) => formatDate(row.created_at),
  },
]

onMounted(loadProject)
</script>

<template>
  <NLayout class="layout">
    <NLayoutHeader class="header">
      <div class="header-content">
        <NBreadcrumb>
          <NBreadcrumbItem @click="router.push('/')">
            项目列表
          </NBreadcrumbItem>
          <NBreadcrumbItem>
            {{ project?.name || projectSlug }}
          </NBreadcrumbItem>
        </NBreadcrumb>
      </div>
    </NLayoutHeader>

    <NLayoutContent class="content">
      <NCard v-if="project" :title="project.name" class="project-info">
        <template #header-extra>
          <NTag :type="project.status === 'active' ? 'success' : 'default'">
            {{ project.status === 'active' ? '活跃' : '归档' }}
          </NTag>
        </template>

        <p v-if="project.description">{{ project.description }}</p>
        <p v-if="project.base_url">
          <strong>基础URL:</strong> {{ project.base_url }}
        </p>
        <p>
          <strong>录制数量:</strong> {{ recordings.length }}
        </p>
      </NCard>

      <NCard title="录制列表" class="recordings-card">
        <template #header-extra>
          <NSpace>
            <NButton @click="loadProject" :loading="loading">
              刷新
            </NButton>
            <NButton type="primary" @click="showRecordModal = true">
              开始录制
            </NButton>
          </NSpace>
        </template>

        <NEmpty v-if="recordings.length === 0" description="暂无录制">
          <template #extra>
            <NButton type="primary" @click="showRecordModal = true">
              开始录制
            </NButton>
          </template>
        </NEmpty>

        <NDataTable
          v-else
          :columns="columns"
          :data="recordings"
          :row-props="(row: Recording) => ({
            style: 'cursor: pointer',
            onClick: () => goToEditor(row)
          })"
        />
      </NCard>

      <!-- Recording Modal -->
      <NModal
        v-model:show="showRecordModal"
        preset="card"
        title="开始新录制"
        style="width: 500px;"
      >
        <NForm label-placement="left" label-width="100">
          <NFormItem label="录制网址" required>
            <NInput
              v-model:value="recordingForm.url"
              placeholder="https://example.com"
              @keyup.enter="startRecording"
            />
          </NFormItem>

          <NFormItem label="录制标题">
            <NInput
              v-model:value="recordingForm.title"
              placeholder="可选，如：登录功能测试"
            />
          </NFormItem>

          <NFormItem label="显示鼠标">
            <NSwitch v-model:value="recordingForm.showCursor" />
            <span style="margin-left: 8px; color: #666; font-size: 12px;">
              在截图中显示鼠标位置
            </span>
          </NFormItem>
        </NForm>

        <div class="record-tips">
          <p><strong>录制说明：</strong></p>
          <ul>
            <li>点击"开始录制"后，将打开一个新的浏览器窗口</li>
            <li>在浏览器中进行操作，系统会自动记录每个步骤</li>
            <li>完成后按 <kbd>F2</kbd> 键或点击页面右上角的 <span class="stop-btn">Stop</span> 按钮结束录制</li>
          </ul>
        </div>

        <template #footer>
          <NSpace justify="end">
            <NButton @click="showRecordModal = false">取消</NButton>
            <NButton type="primary" :loading="startingRecord" @click="startRecording">
              开始录制
            </NButton>
          </NSpace>
        </template>
      </NModal>
    </NLayoutContent>
  </NLayout>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  background: #f5f7fa;
}

.header {
  background: white;
  padding: 16px 24px;
  border-bottom: 1px solid #e0e0e0;
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
}

.content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.project-info {
  margin-bottom: 24px;
}

.recordings-card {
  margin-bottom: 24px;
}

code {
  background: #f0f0f0;
  padding: 4px 8px;
  border-radius: 4px;
  font-family: monospace;
}

.record-tips {
  margin-top: 16px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  font-size: 13px;
}

.record-tips ul {
  margin: 8px 0 0 20px;
  padding: 0;
}

.record-tips li {
  margin: 4px 0;
}

.record-tips kbd {
  background: #fff;
  border: 1px solid #ccc;
  border-radius: 3px;
  padding: 2px 6px;
  font-family: monospace;
  font-size: 12px;
}

.record-tips .stop-btn {
  display: inline-block;
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}
</style>
