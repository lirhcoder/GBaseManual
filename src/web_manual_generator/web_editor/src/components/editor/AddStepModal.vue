<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  NModal, NForm, NFormItem, NInput, NSelect, NUpload,
  NButton, NSpace, NImage, useMessage
} from 'naive-ui'
import type { UploadFileInfo } from 'naive-ui'

const props = defineProps<{
  show: boolean
  insertAfterStepId?: number | null
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'add', step: NewStepData): void
}>()

export interface NewStepData {
  action: string
  description: string
  description_zh: string
  description_en: string
  description_ja: string
  selector?: string
  value?: string
  url?: string
  screenshot?: File
  insertAfter?: number
}

const message = useMessage()

const actionOptions = [
  { label: '点击 (click)', value: 'click' },
  { label: '输入 (fill)', value: 'fill' },
  { label: '导航 (navigate)', value: 'navigate' },
  { label: '选择 (select)', value: 'select' },
  { label: '勾选 (check)', value: 'check' },
  { label: '取消勾选 (uncheck)', value: 'uncheck' },
  { label: '悬停 (hover)', value: 'hover' },
  { label: '滚动 (scroll)', value: 'scroll' },
  { label: '等待 (wait)', value: 'wait' },
  { label: '截图 (screenshot)', value: 'screenshot' },
  { label: '自定义 (custom)', value: 'custom' },
]

const form = ref({
  action: 'click',
  description: '',
  description_zh: '',
  description_en: '',
  description_ja: '',
  selector: '',
  value: '',
  url: '',
})

const uploadedFile = ref<File | null>(null)
const previewUrl = ref<string | null>(null)

const showSelector = computed(() => {
  return ['click', 'fill', 'select', 'check', 'uncheck', 'hover', 'scroll'].includes(form.value.action)
})

const showValue = computed(() => {
  return ['fill', 'select'].includes(form.value.action)
})

const showUrl = computed(() => {
  return form.value.action === 'navigate'
})

function handleUpload({ file }: { file: UploadFileInfo }) {
  if (file.file) {
    uploadedFile.value = file.file
    previewUrl.value = URL.createObjectURL(file.file)
  }
  return false // Prevent default upload
}

function removeFile() {
  uploadedFile.value = null
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = null
  }
}

function validate(): boolean {
  if (!form.value.action) {
    message.warning('请选择操作类型')
    return false
  }
  if (!form.value.description && !form.value.description_zh) {
    message.warning('请输入步骤描述')
    return false
  }
  if (showSelector.value && !form.value.selector) {
    message.warning('请输入选择器')
    return false
  }
  if (showUrl.value && !form.value.url) {
    message.warning('请输入URL')
    return false
  }
  return true
}

function submit() {
  if (!validate()) return

  const stepData: NewStepData = {
    action: form.value.action,
    description: form.value.description || form.value.description_zh,
    description_zh: form.value.description_zh || form.value.description,
    description_en: form.value.description_en,
    description_ja: form.value.description_ja,
    selector: form.value.selector || undefined,
    value: form.value.value || undefined,
    url: form.value.url || undefined,
    screenshot: uploadedFile.value || undefined,
    insertAfter: props.insertAfterStepId || undefined,
  }

  emit('add', stepData)
  close()
}

function close() {
  // Reset form
  form.value = {
    action: 'click',
    description: '',
    description_zh: '',
    description_en: '',
    description_ja: '',
    selector: '',
    value: '',
    url: '',
  }
  removeFile()
  emit('update:show', false)
}
</script>

<template>
  <NModal
    :show="show"
    @update:show="$emit('update:show', $event)"
    preset="card"
    title="添加新步骤"
    style="width: 600px;"
  >
    <NForm label-placement="left" label-width="80">
      <NFormItem label="操作类型" required>
        <NSelect
          v-model:value="form.action"
          :options="actionOptions"
          placeholder="选择操作类型"
        />
      </NFormItem>

      <NFormItem v-if="showSelector" label="选择器">
        <NInput
          v-model:value="form.selector"
          placeholder="CSS选择器，如 #login-btn, .submit"
        />
      </NFormItem>

      <NFormItem v-if="showValue" label="输入值">
        <NInput
          v-model:value="form.value"
          placeholder="输入的值或选择的选项"
        />
      </NFormItem>

      <NFormItem v-if="showUrl" label="URL">
        <NInput
          v-model:value="form.url"
          placeholder="https://example.com"
        />
      </NFormItem>

      <NFormItem label="描述 (中文)" required>
        <NInput
          v-model:value="form.description_zh"
          type="textarea"
          :autosize="{ minRows: 2 }"
          placeholder="步骤描述（中文）"
        />
      </NFormItem>

      <NFormItem label="Description">
        <NInput
          v-model:value="form.description_en"
          type="textarea"
          :autosize="{ minRows: 2 }"
          placeholder="Step description (English)"
        />
      </NFormItem>

      <NFormItem label="説明">
        <NInput
          v-model:value="form.description_ja"
          type="textarea"
          :autosize="{ minRows: 2 }"
          placeholder="ステップの説明（日本語）"
        />
      </NFormItem>

      <NFormItem label="截图">
        <div class="upload-area">
          <NUpload
            v-if="!previewUrl"
            accept="image/*"
            :max="1"
            :default-upload="false"
            @change="handleUpload"
          >
            <NButton>上传截图</NButton>
          </NUpload>
          <div v-else class="preview-container">
            <NImage
              :src="previewUrl"
              width="200"
              object-fit="contain"
            />
            <NButton size="small" type="error" ghost @click="removeFile">
              移除
            </NButton>
          </div>
        </div>
      </NFormItem>
    </NForm>

    <template #footer>
      <NSpace justify="end">
        <NButton @click="close">取消</NButton>
        <NButton type="primary" @click="submit">添加</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
.upload-area {
  width: 100%;
}

.preview-container {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
</style>
