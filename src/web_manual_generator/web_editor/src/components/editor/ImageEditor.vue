<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import {
  NModal, NButton, NSpace, NButtonGroup, NColorPicker,
  NInputNumber, NTooltip, NDivider, useMessage
} from 'naive-ui'
import { fabric } from 'fabric'

const props = defineProps<{
  show: boolean
  imageUrl: string
  filename: string
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'save', dataUrl: string): void
}>()

const message = useMessage()

const canvasContainer = ref<HTMLDivElement>()
const canvasEl = ref<HTMLCanvasElement>()
let canvas: fabric.Canvas | null = null

const mode = ref<'select' | 'rect' | 'circle' | 'arrow' | 'text' | 'highlight' | 'crop'>('select')
const strokeColor = ref('#ef4444')
const strokeWidth = ref(3)
const fontSize = ref(20)

// Crop state
const cropRect = ref<fabric.Rect | null>(null)
const isCropping = ref(false)

// History for undo/redo
const history = ref<string[]>([])
const historyIndex = ref(-1)

function initCanvas() {
  if (!canvasEl.value || !canvasContainer.value) return

  // Get container size
  const containerWidth = canvasContainer.value.clientWidth - 40
  const maxHeight = window.innerHeight * 0.6

  canvas = new fabric.Canvas(canvasEl.value, {
    selection: true,
    preserveObjectStacking: true,
    renderOnAddRemove: true,
    skipTargetFind: false,
  })

  // Load background image
  fabric.Image.fromURL(props.imageUrl, (img) => {
    if (!canvas || !img.width || !img.height) return

    // Calculate scale to fit container
    const scale = Math.min(
      containerWidth / img.width,
      maxHeight / img.height,
      1
    )

    canvas.setWidth(img.width * scale)
    canvas.setHeight(img.height * scale)

    img.scaleToWidth(img.width * scale)
    canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas))

    // Save initial state
    saveHistory()
  }, { crossOrigin: 'anonymous' })

  // Event listeners
  canvas.on('mouse:down', handleMouseDown)
  canvas.on('mouse:move', handleMouseMove)
  canvas.on('mouse:up', handleMouseUp)
  canvas.on('object:modified', saveHistory)
  canvas.on('object:added', saveHistory)

  // Double-click to edit text
  canvas.on('mouse:dblclick', (e: fabric.IEvent<MouseEvent>) => {
    if (e.target && (e.target.type === 'i-text' || e.target.type === 'textbox')) {
      const text = e.target as fabric.Textbox
      text.enterEditing()
      text.selectAll()
      canvas?.renderAll()
    }
  })
}

let isDrawing = false
let startX = 0
let startY = 0
let currentShape: fabric.Object | null = null

function handleMouseDown(e: fabric.IEvent<MouseEvent>) {
  if (!canvas || mode.value === 'select') return

  // If clicking on an existing object, don't start drawing new shape
  // This allows adjusting existing objects even in drawing mode
  if (e.target) {
    return
  }

  const pointer = canvas.getPointer(e.e)
  startX = pointer.x
  startY = pointer.y
  isDrawing = true

  if (mode.value === 'rect') {
    currentShape = new fabric.Rect({
      left: startX,
      top: startY,
      width: 0,
      height: 0,
      fill: 'transparent',
      stroke: strokeColor.value,
      strokeWidth: strokeWidth.value,
      selectable: true,
      hasControls: true,
      hasBorders: true,
    })
    canvas.add(currentShape)
  } else if (mode.value === 'circle') {
    currentShape = new fabric.Circle({
      left: startX,
      top: startY,
      radius: 0,
      fill: 'transparent',
      stroke: strokeColor.value,
      strokeWidth: strokeWidth.value,
      selectable: true,
      hasControls: true,
      hasBorders: true,
    })
    canvas.add(currentShape)
  } else if (mode.value === 'highlight') {
    currentShape = new fabric.Rect({
      left: startX,
      top: startY,
      width: 0,
      height: 0,
      fill: 'rgba(255, 255, 0, 0.3)',
      stroke: 'transparent',
      strokeWidth: 0,
      selectable: true,
      hasControls: true,
      hasBorders: true,
    })
    canvas.add(currentShape)
  } else if (mode.value === 'arrow') {
    // Create arrow line (arrowhead will be added on mouse up)
    currentShape = new fabric.Line([startX, startY, startX, startY], {
      stroke: strokeColor.value,
      strokeWidth: strokeWidth.value,
      originX: 'center',
      originY: 'center',
    })
    canvas.add(currentShape)
  } else if (mode.value === 'text') {
    isDrawing = false

    // Use IText which auto-sizes to content
    const text = new fabric.IText('', {
      left: startX,
      top: startY,
      fontSize: fontSize.value,
      fill: strokeColor.value,
      fontFamily: 'Arial, sans-serif',
      selectable: true,
      hasControls: true,
      editable: true,
    })
    canvas.add(text)
    canvas.setActiveObject(text)
    canvas.renderAll()

    // Switch to select mode and enter editing
    mode.value = 'select'

    // Enter editing mode with delay to ensure proper focus
    setTimeout(() => {
      if (canvas) {
        text.enterEditing()
        canvas.renderAll()
      }
    }, 100)
    return
  } else if (mode.value === 'crop') {
    // Remove existing crop rect
    if (cropRect.value) {
      canvas.remove(cropRect.value)
    }
    cropRect.value = new fabric.Rect({
      left: startX,
      top: startY,
      width: 0,
      height: 0,
      fill: 'rgba(0, 0, 0, 0.3)',
      stroke: '#1890ff',
      strokeWidth: 2,
      strokeDashArray: [5, 5],
      selectable: true,
    })
    canvas.add(cropRect.value)
    isCropping.value = true
  }
}

function handleMouseMove(e: fabric.IEvent<MouseEvent>) {
  if (!canvas || !isDrawing) return

  const pointer = canvas.getPointer(e.e)
  const width = pointer.x - startX
  const height = pointer.y - startY

  if (mode.value === 'crop' && cropRect.value) {
    // Handle crop separately since it doesn't use currentShape
    cropRect.value.set({
      width: Math.abs(width),
      height: Math.abs(height),
      left: width < 0 ? pointer.x : startX,
      top: height < 0 ? pointer.y : startY,
    })
    canvas.renderAll()
    return
  }

  if (!currentShape) return

  if (mode.value === 'rect' || mode.value === 'highlight') {
    (currentShape as fabric.Rect).set({
      width: Math.abs(width),
      height: Math.abs(height),
      left: width < 0 ? pointer.x : startX,
      top: height < 0 ? pointer.y : startY,
    })
  } else if (mode.value === 'circle') {
    const radius = Math.sqrt(width * width + height * height) / 2
    ;(currentShape as fabric.Circle).set({ radius })
  } else if (mode.value === 'arrow') {
    (currentShape as fabric.Line).set({
      x2: pointer.x,
      y2: pointer.y,
    })
  }

  canvas.renderAll()
}

function handleMouseUp(e: fabric.IEvent<MouseEvent>) {
  if (!canvas) return

  // Handle arrow: replace line with arrow group
  if (mode.value === 'arrow' && currentShape && isDrawing) {
    const line = currentShape as fabric.Line
    const x1 = line.x1 || 0
    const y1 = line.y1 || 0
    const x2 = line.x2 || 0
    const y2 = line.y2 || 0

    // Only create arrow if line has some length
    const length = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    if (length > 10) {
      // Remove the temporary line
      canvas.remove(line)

      // Create arrow with arrowhead
      const arrow = createArrow(x1, y1, x2, y2, strokeColor.value, strokeWidth.value)
      canvas.add(arrow)
      canvas.setActiveObject(arrow)
      canvas.renderAll()
    } else {
      canvas.remove(line)
    }
    currentShape = null
  } else if (currentShape && isDrawing) {
    // For other shapes (rect, circle, highlight), keep them selected after drawing
    const shape = currentShape
    // Check if shape has meaningful size
    const width = (shape as any).width || (shape as any).radius * 2 || 0
    const height = (shape as any).height || (shape as any).radius * 2 || 0
    if (width > 5 || height > 5) {
      // Ensure shape is selectable
      shape.set({
        selectable: true,
        hasControls: true,
        hasBorders: true,
        evented: true,
      })
      canvas.setActiveObject(shape)
      canvas.renderAll()
    } else {
      // Remove too small shapes
      canvas.remove(shape)
    }
    currentShape = null
  }

  isDrawing = false

  if (mode.value === 'crop' && cropRect.value) {
    canvas.setActiveObject(cropRect.value)
    canvas.renderAll()
  }
}

function createArrow(x1: number, y1: number, x2: number, y2: number, color: string, lineWidth: number): fabric.Group {
  const headLength = Math.max(15, lineWidth * 4)
  const angle = Math.atan2(y2 - y1, x2 - x1)

  // Main line
  const line = new fabric.Line([x1, y1, x2, y2], {
    stroke: color,
    strokeWidth: lineWidth,
    strokeLineCap: 'round',
  })

  // Arrowhead points
  const headAngle = Math.PI / 6 // 30 degrees
  const x3 = x2 - headLength * Math.cos(angle - headAngle)
  const y3 = y2 - headLength * Math.sin(angle - headAngle)
  const x4 = x2 - headLength * Math.cos(angle + headAngle)
  const y4 = y2 - headLength * Math.sin(angle + headAngle)

  // Arrowhead as triangle
  const arrowHead = new fabric.Triangle({
    left: x2,
    top: y2,
    width: headLength,
    height: headLength,
    fill: color,
    angle: (angle * 180 / Math.PI) + 90,
    originX: 'center',
    originY: 'center',
  })

  // Group line and arrowhead
  const group = new fabric.Group([line, arrowHead], {
    selectable: true,
    hasControls: true,
  })

  return group
}

function setMode(newMode: typeof mode.value) {
  mode.value = newMode
  if (canvas) {
    canvas.isDrawingMode = false
    // Always allow selection of objects
    canvas.selection = true

    // Make all objects selectable
    canvas.forEachObject((obj) => {
      obj.selectable = true
      obj.evented = true
    })

    // Deselect all when switching to a drawing mode
    if (newMode !== 'select') {
      canvas.discardActiveObject()
    }
    canvas.renderAll()
  }
}

function applyCrop() {
  if (!canvas || !cropRect.value) return

  const rect = cropRect.value
  const left = rect.left || 0
  const top = rect.top || 0
  const width = rect.width || 0
  const height = rect.height || 0

  if (width < 10 || height < 10) {
    message.warning('裁剪区域太小')
    return
  }

  // Remove crop rect before exporting
  canvas.remove(cropRect.value)
  cropRect.value = null

  // Get cropped data URL
  const dataUrl = canvas.toDataURL({
    format: 'png',
    left,
    top,
    width,
    height,
  })

  // Reload with cropped image
  fabric.Image.fromURL(dataUrl, (img) => {
    if (!canvas || !img.width || !img.height) return

    canvas.clear()
    canvas.setWidth(img.width)
    canvas.setHeight(img.height)
    canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas))

    isCropping.value = false
    mode.value = 'select'
    saveHistory()
  })
}

function cancelCrop() {
  if (canvas && cropRect.value) {
    canvas.remove(cropRect.value)
    cropRect.value = null
  }
  isCropping.value = false
  mode.value = 'select'
}

function deleteSelected() {
  if (!canvas) return
  const active = canvas.getActiveObjects()
  if (active.length > 0) {
    active.forEach(obj => canvas!.remove(obj))
    canvas.discardActiveObject()
    canvas.renderAll()
    saveHistory()
  }
}

function saveHistory() {
  if (!canvas) return

  // Remove future history if we're not at the end
  if (historyIndex.value < history.value.length - 1) {
    history.value = history.value.slice(0, historyIndex.value + 1)
  }

  const json = JSON.stringify(canvas.toJSON())
  history.value.push(json)
  historyIndex.value = history.value.length - 1

  // Limit history size
  if (history.value.length > 50) {
    history.value.shift()
    historyIndex.value--
  }
}

function undo() {
  if (!canvas || historyIndex.value <= 0) return

  historyIndex.value--
  const json = history.value[historyIndex.value]
  canvas.loadFromJSON(json, () => {
    canvas?.renderAll()
  })
}

function redo() {
  if (!canvas || historyIndex.value >= history.value.length - 1) return

  historyIndex.value++
  const json = history.value[historyIndex.value]
  canvas.loadFromJSON(json, () => {
    canvas?.renderAll()
  })
}

function clearAnnotations() {
  if (!canvas) return

  // Keep only background image
  const objects = canvas.getObjects()
  objects.forEach(obj => canvas!.remove(obj))
  canvas.renderAll()
  saveHistory()
}

function save() {
  if (!canvas) return

  // Remove crop rect if exists
  if (cropRect.value) {
    canvas.remove(cropRect.value)
    cropRect.value = null
  }

  const dataUrl = canvas.toDataURL({
    format: 'png',
    quality: 1,
  })

  emit('save', dataUrl)
  emit('update:show', false)
}

function close() {
  emit('update:show', false)
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    nextTick(() => {
      initCanvas()
    })
  } else {
    if (canvas) {
      canvas.dispose()
      canvas = null
    }
    history.value = []
    historyIndex.value = -1
    cropRect.value = null
    isCropping.value = false
  }
})

onUnmounted(() => {
  if (canvas) {
    canvas.dispose()
  }
})
</script>

<template>
  <NModal
    :show="show"
    @update:show="$emit('update:show', $event)"
    preset="card"
    title="编辑截图"
    style="width: 90%; max-width: 1200px;"
    :mask-closable="false"
    :trap-focus="false"
    :auto-focus="false"
  >
    <div class="image-editor">
      <!-- Toolbar -->
      <div class="toolbar">
        <NButtonGroup>
          <NTooltip trigger="hover">
            <template #trigger>
              <NButton
                :type="mode === 'select' ? 'primary' : 'default'"
                @click="setMode('select')"
              >
                选择
              </NButton>
            </template>
            选择和移动对象
          </NTooltip>

          <NTooltip trigger="hover">
            <template #trigger>
              <NButton
                :type="mode === 'rect' ? 'primary' : 'default'"
                @click="setMode('rect')"
              >
                矩形
              </NButton>
            </template>
            绘制矩形框
          </NTooltip>

          <NTooltip trigger="hover">
            <template #trigger>
              <NButton
                :type="mode === 'circle' ? 'primary' : 'default'"
                @click="setMode('circle')"
              >
                圆形
              </NButton>
            </template>
            绘制圆形
          </NTooltip>

          <NTooltip trigger="hover">
            <template #trigger>
              <NButton
                :type="mode === 'arrow' ? 'primary' : 'default'"
                @click="setMode('arrow')"
              >
                箭头
              </NButton>
            </template>
            绘制箭头/线条
          </NTooltip>

          <NTooltip trigger="hover">
            <template #trigger>
              <NButton
                :type="mode === 'text' ? 'primary' : 'default'"
                @click="setMode('text')"
              >
                文字
              </NButton>
            </template>
            添加文字标注
          </NTooltip>

          <NTooltip trigger="hover">
            <template #trigger>
              <NButton
                :type="mode === 'highlight' ? 'primary' : 'default'"
                @click="setMode('highlight')"
              >
                高亮
              </NButton>
            </template>
            添加高亮区域
          </NTooltip>

          <NTooltip trigger="hover">
            <template #trigger>
              <NButton
                :type="mode === 'crop' ? 'primary' : 'default'"
                @click="setMode('crop')"
              >
                裁剪
              </NButton>
            </template>
            裁剪图片
          </NTooltip>
        </NButtonGroup>

        <NDivider vertical />

        <NSpace align="center">
          <span>颜色:</span>
          <NColorPicker
            v-model:value="strokeColor"
            :modes="['hex']"
            size="small"
            style="width: 80px;"
          />

          <span>线宽:</span>
          <NInputNumber
            v-model:value="strokeWidth"
            :min="1"
            :max="20"
            size="small"
            style="width: 80px;"
          />

          <span>字号:</span>
          <NInputNumber
            v-model:value="fontSize"
            :min="12"
            :max="72"
            size="small"
            style="width: 80px;"
          />
        </NSpace>

        <NDivider vertical />

        <NSpace>
          <NButton @click="undo" :disabled="historyIndex <= 0">
            撤销
          </NButton>
          <NButton @click="redo" :disabled="historyIndex >= history.length - 1">
            重做
          </NButton>
          <NButton @click="deleteSelected">
            删除选中
          </NButton>
          <NButton type="error" ghost @click="clearAnnotations">
            清除标注
          </NButton>
        </NSpace>
      </div>

      <!-- Crop toolbar -->
      <div v-if="isCropping" class="crop-toolbar">
        <NSpace>
          <span>调整裁剪区域后点击确认</span>
          <NButton type="primary" @click="applyCrop">确认裁剪</NButton>
          <NButton @click="cancelCrop">取消</NButton>
        </NSpace>
      </div>

      <!-- Canvas container -->
      <div ref="canvasContainer" class="canvas-container">
        <canvas ref="canvasEl"></canvas>
      </div>
    </div>

    <template #footer>
      <NSpace justify="end">
        <NButton @click="close">取消</NButton>
        <NButton type="primary" @click="save">保存</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
.image-editor {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Ensure fabric.js hidden textarea can receive input */
.canvas-container :deep(textarea) {
  position: absolute !important;
  opacity: 0 !important;
  z-index: 1000 !important;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 8px;
  flex-wrap: wrap;
}

.crop-toolbar {
  padding: 12px;
  background: #e6f7ff;
  border: 1px solid #91d5ff;
  border-radius: 8px;
}

.canvas-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
  background: #e0e0e0;
  border-radius: 8px;
  min-height: 400px;
  overflow: auto;
}

canvas {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
</style>
