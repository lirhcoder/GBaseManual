<template>
  <div class="video-player">
    <div class="video-header">
      <n-space align="center">
        <n-icon size="20"><VideocamOutline /></n-icon>
        <span class="title">Video Preview</span>
        <n-tag v-if="videoInfo?.has_video" type="success" size="small">Available</n-tag>
        <n-tag v-else type="warning" size="small">No Video</n-tag>
      </n-space>
      <n-button quaternary size="small" @click="$emit('close')">
        <template #icon><n-icon><CloseOutline /></n-icon></template>
      </n-button>
    </div>

    <div v-if="videoInfo?.has_video" class="video-container">
      <video
        ref="videoRef"
        :src="videoUrl"
        controls
        @loadedmetadata="onVideoLoaded"
        @timeupdate="onTimeUpdate"
      />

      <div class="video-controls">
        <n-space vertical>
          <n-space align="center">
            <span class="time-display">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>
            <n-button-group size="small">
              <n-button @click="seekRelative(-5)" title="Back 5s">-5s</n-button>
              <n-button @click="seekRelative(-1)" title="Back 1s">-1s</n-button>
              <n-button @click="togglePlay">{{ isPlaying ? 'Pause' : 'Play' }}</n-button>
              <n-button @click="seekRelative(1)" title="Forward 1s">+1s</n-button>
              <n-button @click="seekRelative(5)" title="Forward 5s">+5s</n-button>
            </n-button-group>
          </n-space>

          <n-space align="center">
            <n-button type="primary" @click="captureFrame">
              <template #icon><n-icon><CameraOutline /></n-icon></template>
              Capture Frame
            </n-button>

            <n-select
              v-if="selectedStepId !== null"
              v-model:value="captureTarget"
              :options="captureTargetOptions"
              size="small"
              style="width: 200px"
            />
          </n-space>

          <div v-if="capturedImage" class="capture-preview">
            <img :src="capturedImage" alt="Captured frame" />
            <n-space>
              <n-button type="primary" size="small" @click="saveCapture">
                <template #icon><n-icon><SaveOutline /></n-icon></template>
                {{ captureTarget === 'new' ? 'Save as New' : `Apply to Step ${selectedStepId}` }}
              </n-button>
              <n-button size="small" @click="capturedImage = null">Cancel</n-button>
            </n-space>
          </div>
        </n-space>
      </div>

      <!-- Chapters / Step markers -->
      <div v-if="chapters.length > 0" class="chapters-list">
        <n-divider>Chapters</n-divider>
        <n-space vertical size="small">
          <n-button
            v-for="chapter in chapters"
            :key="chapter.time"
            text
            size="small"
            @click="seekTo(chapter.time)"
          >
            {{ chapter.time_formatted }} - {{ chapter.title_zh || chapter.title }}
          </n-button>
        </n-space>
      </div>
    </div>

    <div v-else class="no-video">
      <n-empty description="No video available for this recording" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  NButton,
  NButtonGroup,
  NSpace,
  NIcon,
  NTag,
  NSelect,
  NDivider,
  NEmpty,
  useMessage,
} from 'naive-ui'
import {
  VideocamOutline,
  CloseOutline,
  CameraOutline,
  SaveOutline,
} from '@vicons/ionicons5'
import { videoApi, type VideoInfo } from '../../api/client'

const props = defineProps<{
  projectSlug: string
  recordingName: string
  selectedStepId: number | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'frameCaptured', stepId: number | null): void
}>()

const message = useMessage()

const videoRef = ref<HTMLVideoElement | null>(null)
const videoInfo = ref<VideoInfo | null>(null)
const currentTime = ref(0)
const duration = ref(0)
const isPlaying = ref(false)
const capturedImage = ref<string | null>(null)
const capturedBlob = ref<Blob | null>(null)
const captureTarget = ref<'new' | number>('new')

const videoUrl = computed(() =>
  videoApi.getVideoUrl(props.projectSlug, props.recordingName)
)

const chapters = computed(() => videoInfo.value?.chapters || [])

const captureTargetOptions = computed(() => {
  const options = [{ label: 'Save as new screenshot', value: 'new' as const }]
  if (props.selectedStepId !== null) {
    options.unshift({
      label: `Replace Step ${props.selectedStepId} screenshot`,
      value: props.selectedStepId,
    })
  }
  return options
})

// Update capture target when selected step changes
watch(() => props.selectedStepId, (newId) => {
  if (newId !== null) {
    captureTarget.value = newId
  } else {
    captureTarget.value = 'new'
  }
})

onMounted(async () => {
  try {
    const res = await videoApi.getInfo(props.projectSlug, props.recordingName)
    videoInfo.value = res.data
  } catch (err) {
    console.error('Failed to load video info:', err)
  }
})

function onVideoLoaded() {
  if (videoRef.value) {
    duration.value = videoRef.value.duration
  }
}

function onTimeUpdate() {
  if (videoRef.value) {
    currentTime.value = videoRef.value.currentTime
    isPlaying.value = !videoRef.value.paused
  }
}

function togglePlay() {
  if (!videoRef.value) return
  if (videoRef.value.paused) {
    videoRef.value.play()
  } else {
    videoRef.value.pause()
  }
}

function seekTo(time: number) {
  if (videoRef.value) {
    videoRef.value.currentTime = time
  }
}

function seekRelative(delta: number) {
  if (videoRef.value) {
    videoRef.value.currentTime = Math.max(0, Math.min(duration.value, videoRef.value.currentTime + delta))
  }
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

function captureFrame() {
  if (!videoRef.value) return

  const video = videoRef.value
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

  // Get as data URL for preview
  capturedImage.value = canvas.toDataURL('image/png')

  // Get as blob for upload
  canvas.toBlob((blob) => {
    if (blob) {
      capturedBlob.value = blob
    }
  }, 'image/png')
}

async function saveCapture() {
  if (!capturedBlob.value) return

  try {
    const stepId = captureTarget.value === 'new' ? undefined : captureTarget.value

    if (stepId !== undefined) {
      // Replace step screenshot
      await videoApi.setStepScreenshot(props.projectSlug, props.recordingName, stepId, capturedBlob.value)
      message.success(`Screenshot updated for step ${stepId}`)
    } else {
      // Save as new (just capture, don't associate)
      await videoApi.captureFrame(props.projectSlug, props.recordingName, capturedBlob.value)
      message.success('Frame captured and saved')
    }

    emit('frameCaptured', stepId ?? null)
    capturedImage.value = null
    capturedBlob.value = null
  } catch (err: any) {
    message.error(err.displayMessage || 'Failed to save capture')
  }
}
</script>

<style scoped>
.video-player {
  background: var(--n-color);
  border-radius: 8px;
  border: 1px solid var(--n-border-color);
  overflow: hidden;
}

.video-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--n-color-modal);
  border-bottom: 1px solid var(--n-border-color);
}

.video-header .title {
  font-weight: 600;
}

.video-container {
  padding: 16px;
}

.video-container video {
  width: 100%;
  max-height: 400px;
  background: #000;
  border-radius: 4px;
}

.video-controls {
  margin-top: 12px;
}

.time-display {
  font-family: monospace;
  font-size: 14px;
  color: var(--n-text-color-3);
}

.capture-preview {
  margin-top: 12px;
  padding: 12px;
  background: var(--n-color-modal);
  border-radius: 4px;
}

.capture-preview img {
  max-width: 300px;
  max-height: 200px;
  border-radius: 4px;
  margin-bottom: 8px;
  display: block;
}

.chapters-list {
  margin-top: 16px;
}

.no-video {
  padding: 40px;
  text-align: center;
}
</style>
