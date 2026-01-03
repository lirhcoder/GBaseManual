<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  NLayout, NLayoutHeader, NLayoutContent,
  NCard, NButton, NSpace, NEmpty, NGrid, NGi,
  NTag, NModal, NForm, NFormItem, NInput,
  useMessage, useDialog
} from 'naive-ui'
import { projectsApi, type Project } from '@/api/client'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()

const loading = ref(false)
const projects = ref<Project[]>([])
const showCreateModal = ref(false)
const newProject = ref({
  name: '',
  description: '',
  base_url: '',
})

async function loadProjects() {
  loading.value = true
  try {
    const { data } = await projectsApi.list()
    projects.value = data.projects
  } catch (error) {
    message.error('加载项目列表失败')
  } finally {
    loading.value = false
  }
}

async function createProject() {
  if (!newProject.value.name) {
    message.warning('请输入项目名称')
    return
  }
  try {
    const { data } = await projectsApi.create(newProject.value)
    message.success('项目创建成功')
    projects.value.unshift(data)
    showCreateModal.value = false
    newProject.value = { name: '', description: '', base_url: '' }
  } catch (error) {
    message.error('创建项目失败')
  }
}

function goToProject(slug: string) {
  router.push(`/projects/${slug}`)
}

function confirmDelete(project: Project) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除项目 "${project.name}" 吗？此操作不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await projectsApi.delete(project.slug, true)
        projects.value = projects.value.filter(p => p.slug !== project.slug)
        message.success('项目已删除')
      } catch (error) {
        message.error('删除失败')
      }
    },
  })
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

onMounted(loadProjects)
</script>

<template>
  <NLayout class="layout">
    <NLayoutHeader class="header">
      <div class="header-content">
        <h1>Web Manual Generator</h1>
        <NButton type="primary" @click="showCreateModal = true">
          + 新建项目
        </NButton>
      </div>
    </NLayoutHeader>

    <NLayoutContent class="content">
      <NEmpty v-if="!loading && projects.length === 0" description="暂无项目">
        <template #extra>
          <NButton type="primary" @click="showCreateModal = true">
            创建第一个项目
          </NButton>
        </template>
      </NEmpty>

      <NGrid v-else :x-gap="16" :y-gap="16" cols="1 m:2 l:3">
        <NGi v-for="project in projects" :key="project.id">
          <NCard
            class="project-card"
            :title="project.name"
            hoverable
            @click="goToProject(project.slug)"
          >
            <template #header-extra>
              <NTag :type="project.status === 'active' ? 'success' : 'default'" size="small">
                {{ project.status === 'active' ? '活跃' : '归档' }}
              </NTag>
            </template>

            <p class="description">{{ project.description || '暂无描述' }}</p>

            <div class="meta">
              <span>录制: {{ project.recording_count }}</span>
              <span>更新: {{ formatDate(project.updated_at) }}</span>
            </div>

            <template #footer>
              <NSpace>
                <NButton size="small" @click.stop="goToProject(project.slug)">
                  查看
                </NButton>
                <NButton size="small" type="error" ghost @click.stop="confirmDelete(project)">
                  删除
                </NButton>
              </NSpace>
            </template>
          </NCard>
        </NGi>
      </NGrid>
    </NLayoutContent>

    <!-- Create Project Modal -->
    <NModal
      v-model:show="showCreateModal"
      title="新建项目"
      preset="dialog"
      positive-text="创建"
      negative-text="取消"
      @positive-click="createProject"
    >
      <NForm>
        <NFormItem label="项目名称" required>
          <NInput v-model:value="newProject.name" placeholder="例如：用户管理系统" />
        </NFormItem>
        <NFormItem label="描述">
          <NInput
            v-model:value="newProject.description"
            type="textarea"
            placeholder="项目描述（可选）"
          />
        </NFormItem>
        <NFormItem label="基础URL">
          <NInput v-model:value="newProject.base_url" placeholder="https://example.com" />
        </NFormItem>
      </NForm>
    </NModal>
  </NLayout>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  background: #f5f7fa;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 0 24px;
  height: 64px;
  display: flex;
  align-items: center;
}

.header-content {
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header h1 {
  color: white;
  font-size: 1.5rem;
  margin: 0;
}

.content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.project-card {
  cursor: pointer;
  transition: transform 0.2s;
}

.project-card:hover {
  transform: translateY(-2px);
}

.description {
  color: #666;
  margin: 0 0 16px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  color: #999;
}
</style>
