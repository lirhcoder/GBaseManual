<script setup lang="ts">
import { computed } from 'vue'
import {
  NDropdown, NButton, NSpace, NBadge, useDialog, useMessage
} from 'naive-ui'
import type { DropdownOption } from 'naive-ui'

const props = defineProps<{
  selectedCount: number
  totalCount: number
}>()

const emit = defineEmits<{
  (e: 'delete'): void
  (e: 'regenerate-ai'): void
  (e: 'clear-selection'): void
  (e: 'select-all'): void
  (e: 'export'): void
  (e: 'copy-descriptions'): void
}>()

const dialog = useDialog()
const message = useMessage()

const hasSelection = computed(() => props.selectedCount > 0)
const allSelected = computed(() => props.selectedCount === props.totalCount && props.totalCount > 0)

const options: DropdownOption[] = [
  {
    label: 'AI 重新生成描述',
    key: 'regenerate',
    disabled: false,
  },
  {
    label: '复制描述到剪贴板',
    key: 'copy',
    disabled: false,
  },
  {
    label: '导出选中步骤',
    key: 'export',
    disabled: false,
  },
  {
    type: 'divider',
    key: 'd1',
  },
  {
    label: '删除选中步骤',
    key: 'delete',
    props: {
      style: 'color: #d03050;'
    }
  },
]

function handleSelect(key: string) {
  switch (key) {
    case 'regenerate':
      emit('regenerate-ai')
      break
    case 'copy':
      emit('copy-descriptions')
      message.success('已复制到剪贴板')
      break
    case 'export':
      emit('export')
      break
    case 'delete':
      confirmDelete()
      break
  }
}

function confirmDelete() {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除选中的 ${props.selectedCount} 个步骤吗？此操作不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: () => {
      emit('delete')
    }
  })
}

function toggleSelection() {
  if (allSelected.value) {
    emit('clear-selection')
  } else {
    emit('select-all')
  }
}
</script>

<template>
  <div class="batch-operations">
    <NSpace align="center">
      <NButton size="small" @click="toggleSelection">
        {{ allSelected ? '取消全选' : '全选' }}
      </NButton>

      <NBadge :value="selectedCount" :show="selectedCount > 0">
        <NDropdown
          trigger="click"
          :options="options"
          :disabled="!hasSelection"
          @select="handleSelect"
        >
          <NButton size="small" :disabled="!hasSelection">
            批量操作
          </NButton>
        </NDropdown>
      </NBadge>

      <span v-if="hasSelection" class="selection-info">
        已选 {{ selectedCount }} / {{ totalCount }}
      </span>
    </NSpace>
  </div>
</template>

<style scoped>
.batch-operations {
  padding: 8px 0;
}

.selection-info {
  font-size: 12px;
  color: #666;
}
</style>
