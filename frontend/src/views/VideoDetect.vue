<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadVideo } from '../api/upload'
import DetectionCanvas from '../components/DetectionCanvas.vue'

const uploading = ref(false)
const ws = ref<WebSocket | null>(null)
const paused = ref(false)
const filePath = ref('')
const currentFrame = ref('')
const detections = ref<any[]>([])
const violations = ref<any[]>([])
const frameNumber = ref(0)
const timestamp = ref(0)
const isDetecting = ref(false)
const wsConnected = ref(false)
const totalFrames = ref(0)
const duration = ref(0)
const totalObjects = ref(0)
const totalViolations = ref(0)

const VIOLATION_LABELS: Record<string, string> = {
  warning_no_hardhat: '未戴安全帽',
  warning_close_to_machinery: '靠近作业机械',
  warning_close_to_vehicle: '靠近施工车辆',
  warning_people_in_controlled_area: '进入管控区',
}

async function handleUpload(file: File) {
  uploading.value = true
  try {
    const { data } = await uploadVideo(file)
    filePath.value = data.file_path
    ElMessage.success('上传成功')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

function connectWebSocket() {
  if (!filePath.value) {
    ElMessage.warning('请先上传视频文件')
    return
  }

  const encodedPath = encodeURIComponent(filePath.value)
  const wsUrl = `ws://${window.location.host}/ws/video/detect/${encodedPath}`

  ws.value = new WebSocket(wsUrl)

  ws.value.onopen = () => {
    wsConnected.value = true
    isDetecting.value = true
    ws.value?.send(JSON.stringify({ action: 'start' }))
  }

  ws.value.onmessage = (event) => {
    const data = JSON.parse(event.data)

    if (data.type === 'info') {
      totalFrames.value = data.total_frames
      duration.value = data.duration
    } else if (data.type === 'frame') {
      currentFrame.value = data.image
      detections.value = data.detections
      violations.value = data.violations
      frameNumber.value = data.frame_number
      timestamp.value = data.timestamp

      if (data.violations && data.violations.length > 0) {
        const msgs = data.violations.map((v: any) =>
          `${VIOLATION_LABELS[v.type] || v.type}: ${v.count}次`,
        ).join(', ')
        ElMessage.warning({ message: `检测到违规: ${msgs}`, duration: 3000 })
      }
    } else if (data.type === 'complete') {
      totalObjects.value = data.total_objects
      totalViolations.value = data.total_violations
      isDetecting.value = false
      wsConnected.value = false
      ElMessage.success(`检测完成: ${data.total_objects} 个目标, ${data.total_violations} 次违规`)
    } else if (data.type === 'error') {
      ElMessage.error(data.message)
      isDetecting.value = false
      wsConnected.value = false
    } else if (data.type === 'paused') {
      paused.value = true
    } else if (data.type === 'resumed') {
      paused.value = false
    } else if (data.type === 'stopped') {
      isDetecting.value = false
      wsConnected.value = false
    }
  }

  ws.value.onclose = () => {
    wsConnected.value = false
    isDetecting.value = false
  }

  ws.value.onerror = () => {
    ElMessage.error('WebSocket 连接错误')
    isDetecting.value = false
    wsConnected.value = false
  }
}

function togglePause() {
  if (!ws.value) return
  if (paused.value) {
    ws.value.send(JSON.stringify({ action: 'resume' }))
  } else {
    ws.value.send(JSON.stringify({ action: 'pause' }))
  }
}

function stopDetect() {
  if (ws.value) {
    ws.value.send(JSON.stringify({ action: 'stop' }))
    ws.value.close()
  }
  currentFrame.value = ''
  detections.value = []
  violations.value = []
  frameNumber.value = 0
  timestamp.value = 0
  isDetecting.value = false
  wsConnected.value = false
  filePath.value = ''
}

onUnmounted(() => {
  if (ws.value) {
    ws.value.send(JSON.stringify({ action: 'stop' }))
    ws.value.close()
  }
})
</script>

<template>
  <div style="padding: 20px">
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>视频实时检测</span>
              <div>
                <el-tag v-if="wsConnected" type="success" style="margin-right: 8px">已连接</el-tag>
                <el-tag v-else type="info" style="margin-right: 8px">未连接</el-tag>
                <el-button v-if="isDetecting" :type="paused ? 'success' : 'warning'" size="small" @click="togglePause">
                  {{ paused ? '继续' : '暂停' }}
                </el-button>
                <el-button v-if="isDetecting" type="danger" size="small" @click="stopDetect">停止</el-button>
              </div>
            </div>
          </template>

          <DetectionCanvas
            v-if="currentFrame"
            :image="currentFrame"
            :detections="detections"
            :violations="violations"
            :show-labels="true"
          />
          <div v-else>
            <el-upload
              drag
              :auto-upload="false"
              :show-file-list="false"
              :on-change="(file: any) => handleUpload(file.raw)"
              :disabled="uploading || isDetecting"
              accept="video/*"
            >
              <div style="padding: 40px 0">
                <el-icon :size="60" color="#409eff"><UploadFilled /></el-icon>
                <p style="margin: 16px 0 8px; font-size: 16px">拖拽视频到此处或点击上传</p>
                <p style="color: #999; font-size: 12px">支持: MP4, AVI, MOV, MKV, FLV | 最大: 200MB</p>
              </div>
            </el-upload>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card style="margin-bottom: 20px">
          <template #header>检测统计</template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="帧号">{{ frameNumber }} / {{ totalFrames }}</el-descriptions-item>
            <el-descriptions-item label="时间">{{ timestamp.toFixed(1) }}s / {{ duration.toFixed(1) }}s</el-descriptions-item>
            <el-descriptions-item label="目标数">{{ detections.length }}</el-descriptions-item>
            <el-descriptions-item label="违规数">{{ violations.length }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card v-if="violations.length > 0" style="margin-bottom: 20px">
          <template #header><span style="color: #F44336">违规告警</span></template>
          <el-alert
            v-for="(v, i) in violations"
            :key="i"
            :title="`${VIOLATION_LABELS[v.type] || v.type}: ${v.count}次`"
            type="warning"
            :closable="false"
            style="margin-bottom: 8px"
          />
        </el-card>

        <el-card v-if="!isDetecting && filePath">
          <template #header>开始检测</template>
          <el-button type="primary" @click="connectWebSocket" style="width: 100%">开始检测</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
