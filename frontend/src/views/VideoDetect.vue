<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadVideo } from '../api/upload'
import DetectionCanvas from '../components/DetectionCanvas.vue'
import ViolationWarning from '../components/ViolationWarning.vue'
import VideoTimeline from '../components/VideoTimeline.vue'
import type { TimelineMarker } from '../components/VideoTimeline.vue'

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
const timelineMarkers = ref<TimelineMarker[]>([])

const VIOLATION_LABELS: Record<string, string> = {
  warning_no_hardhat: '未戴安全帽',
  warning_no_safety_vest: '未穿反光背心',
  warning_close_to_machinery: '靠近作业机械',
  warning_close_to_vehicle: '靠近施工车辆',
  warning_people_in_controlled_area: '进入锥形桶管控区',
  warning_people_in_utility_pole_controlled_area: '进入电线杆管控区',
}

const VIOLATION_PRIORITY: Record<string, number> = {
  warning_no_hardhat: 5,
  warning_people_in_controlled_area: 4,
  warning_people_in_utility_pole_controlled_area: 4,
  warning_close_to_machinery: 3,
  warning_close_to_vehicle: 3,
  warning_no_safety_vest: 1,
}

const VIOLATION_COLORS: Record<string, string> = {
  warning_no_hardhat: '#F44336',
  warning_no_safety_vest: '#FF9800',
  warning_close_to_machinery: '#FF5722',
  warning_close_to_vehicle: '#FFC107',
  warning_people_in_controlled_area: '#E91E63',
  warning_people_in_utility_pole_controlled_area: '#9C27B0',
}

function hasMarkerAtFrame(frame: number): boolean {
  return timelineMarkers.value.some(m => m.frame === frame)
}

function addTimelineMarkers(frameNumber: number, frameTime: number, frameViolations: any[]) {
  if (hasMarkerAtFrame(frameNumber)) return
  const top = frameViolations.reduce((a: any, b: any) =>
    (VIOLATION_PRIORITY[a.type] || 0) >= (VIOLATION_PRIORITY[b.type] || 0) ? a : b,
  )
  timelineMarkers.value.push({
    frame: frameNumber,
    time: frameTime,
    type: top.type,
    color: VIOLATION_COLORS[top.type] || '#F44336',
  })
}

function resetState() {
  currentFrame.value = ''
  detections.value = []
  violations.value = []
  frameNumber.value = 0
  timestamp.value = 0
  isDetecting.value = false
  wsConnected.value = false
  totalFrames.value = 0
  duration.value = 0
  totalObjects.value = 0
  totalViolations.value = 0
  timelineMarkers.value = []
  filePath.value = ''
}

async function handleUpload(file: File) {
  uploading.value = true
  try {
    resetState()
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

  timelineMarkers.value = []
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
        addTimelineMarkers(data.frame_number, data.timestamp, data.violations)
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
  resetState()
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
      <el-col :span="18">
        <el-card>
          <template #header>
            <span style="font-weight: 600">🎥 视频实时检测</span>
          </template>

          <div v-if="!currentFrame">
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

          <template v-else>
            <div
              class="image-wrapper"
              :class="{ 'violation-active': violations.length > 0 }"
            >
              <DetectionCanvas
                :image="currentFrame"
                :detections="detections"
                :violations="violations"
                :show-labels="true"
              />
            </div>

            <div class="control-bar">
              <div class="control-left">
                <el-button
                  v-if="isDetecting"
                  :type="paused ? 'success' : 'warning'"
                  size="default"
                  @click="togglePause"
                >
                  {{ paused ? '▶ 继续' : '⏸ 暂停' }}
                </el-button>
                <el-button
                  v-if="isDetecting"
                  type="danger"
                  size="default"
                  @click="stopDetect"
                >
                  ⏹ 停止
                </el-button>
                <el-tag v-if="wsConnected" type="success" effect="dark" size="small">● 已连接</el-tag>
                <el-tag v-else-if="!isDetecting && filePath" type="info" size="small">● 未开始</el-tag>
              </div>
              <div class="control-right">
                <span class="info-text">帧 {{ frameNumber }} / {{ totalFrames }}</span>
                <span class="info-divider">|</span>
                <span class="info-text">{{ timestamp.toFixed(1) }}s / {{ duration.toFixed(1) }}s</span>
              </div>
            </div>

            <VideoTimeline
              :current-frame="frameNumber"
              :total-frames="totalFrames"
              :markers="timelineMarkers"
            />
          </template>
        </el-card>

        <ViolationWarning v-if="violations.length > 0" :violations="violations" />
      </el-col>

      <el-col :span="6">
        <el-card v-if="violations.length > 0" style="margin-bottom: 16px">
          <template #header>
            <div class="right-header">
              <span style="font-weight: 600; color: #d32f2f">🚨 当前帧违规</span>
            </div>
          </template>
          <div v-for="v in violations" :key="v.type" class="right-violation-row">
            <span
              class="vio-dot"
              :style="{ background: VIOLATION_COLORS[v.type] || '#F44336' }"
            ></span>
            <span class="vio-label">{{ VIOLATION_LABELS[v.type] || v.type }}</span>
            <el-tag size="small" type="danger" effect="dark">{{ v.count }}次</el-tag>
          </div>
        </el-card>

        <el-card>
          <template #header>
            <span style="font-weight: 600">📊 检测统计</span>
          </template>
          <div class="stats-list">
            <div class="stats-row">
              <span class="stats-key">检测目标</span>
              <span class="stats-val">{{ isDetecting ? detections.length : totalObjects }}</span>
            </div>
            <div class="stats-row">
              <span class="stats-key">违规次数</span>
              <span class="stats-val" :class="{ 'has-violation': totalViolations > 0 }">
                {{ isDetecting ? violations.length : totalViolations }}
              </span>
            </div>
            <div class="stats-divider"></div>
            <div class="stats-row">
              <span class="stats-key">当前帧</span>
              <span class="stats-val-sm">{{ frameNumber }} / {{ totalFrames }}</span>
            </div>
            <div class="stats-row">
              <span class="stats-key">已用时间</span>
              <span class="stats-val-sm">{{ timestamp.toFixed(1) }}s</span>
            </div>
            <div class="stats-row" v-if="duration">
              <span class="stats-key">总时长</span>
              <span class="stats-val-sm">{{ duration.toFixed(1) }}s</span>
            </div>
          </div>
        </el-card>

        <el-card v-if="!isDetecting && filePath" style="margin-top: 16px">
          <el-button type="primary" size="large" @click="connectWebSocket" style="width: 100%">
            ▶ 开始检测
          </el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.image-wrapper {
  position: relative;
  border-radius: 6px;
  overflow: hidden;
}

.image-wrapper.violation-active {
  box-shadow:
    0 0 0 3px rgba(244, 67, 54, 0.6),
    0 0 25px rgba(244, 67, 54, 0.25);
  animation: card-pulse 2s ease-in-out infinite;
}

.image-wrapper.violation-active::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 50%;
  background: rgba(255, 0, 0, 0.1);
  pointer-events: none;
  z-index: 10;
  animation: overlay-pulse 2s ease-in-out infinite;
}

.control-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0 4px;
  flex-wrap: wrap;
  gap: 8px;
}

.control-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-text {
  font-size: 13px;
  color: #666;
}

.info-divider {
  color: #ddd;
}

.right-header {
  display: flex;
  align-items: center;
}

.right-violation-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;
}

.right-violation-row:last-child {
  border-bottom: none;
}

.vio-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.vio-label {
  flex: 1;
  font-size: 13px;
  color: #333;
}

.stats-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stats-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats-key {
  font-size: 13px;
  color: #666;
}

.stats-val {
  font-size: 18px;
  font-weight: 700;
  color: #333;
}

.stats-val.has-violation {
  color: #d32f2f;
}

.stats-val-sm {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.stats-divider {
  height: 1px;
  background: #eee;
  margin: 2px 0;
}

@keyframes card-pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(244, 67, 54, 0.6), 0 0 20px rgba(244, 67, 54, 0.2); }
  50% { box-shadow: 0 0 0 3px rgba(244, 67, 54, 0.8), 0 0 40px rgba(244, 67, 54, 0.35); }
}

@keyframes overlay-pulse {
  0%, 100% { background: rgba(255, 0, 0, 0.08); }
  50% { background: rgba(255, 0, 0, 0.15); }
}
</style>
