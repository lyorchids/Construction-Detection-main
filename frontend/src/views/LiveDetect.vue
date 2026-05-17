<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import DetectionCanvas from '../components/DetectionCanvas.vue'
import { useDetectionStore } from '../stores/detection'

const route = useRoute()
const store = useDetectionStore()

const ws = ref<WebSocket | null>(null)
const paused = ref(false)
const filePath = ref(route.query.file as string || '')

const VIOLATION_LABELS: Record<string, string> = {
  warning_no_hardhat: '未戴安全帽',
  warning_close_to_machinery: '靠近作业机械',
  warning_close_to_vehicle: '靠近施工车辆',
  warning_people_in_controlled_area: '进入管控区',
}

function connectWebSocket() {
  if (!filePath.value) {
    ElMessage.warning('请先上传文件')
    return
  }

  const encodedPath = encodeURIComponent(filePath.value)
  const wsUrl = `ws://${window.location.host}/ws/video/detect/${encodedPath}`

  ws.value = new WebSocket(wsUrl)

  ws.value.onopen = () => {
    store.setWsConnected(true)
    ElMessage.success('WebSocket 已连接')
    ws.value?.send(JSON.stringify({ action: 'start' }))
    store.setDetecting(true)
  }

  ws.value.onmessage = (event) => {
    const data = JSON.parse(event.data)

    if (data.type === 'info') {
      ElMessage.info(`视频信息: ${data.total_frames} 帧, ${data.duration.toFixed(1)}s`)
    } else if (data.type === 'frame') {
      store.updateFrame({
        image: data.image,
        detections: data.detections,
        violations: data.violations,
        frame_number: data.frame_number,
        timestamp: data.timestamp,
      })

      if (data.violations && data.violations.length > 0) {
        const msgs = data.violations.map((v: any) =>
          `${VIOLATION_LABELS[v.type] || v.type}: ${v.count}次`,
        ).join(', ')
        ElMessage.warning({ message: `检测到违规: ${msgs}`, duration: 3000 })
      }
    } else if (data.type === 'error') {
      ElMessage.error(data.message)
      store.setDetecting(false)
    } else if (data.type === 'paused') {
      paused.value = true
    } else if (data.type === 'resumed') {
      paused.value = false
    } else if (data.type === 'stopped') {
      store.setDetecting(false)
      store.setWsConnected(false)
    }
  }

  ws.value.onclose = () => {
    store.setWsConnected(false)
    store.setDetecting(false)
  }

  ws.value.onerror = () => {
    ElMessage.error('WebSocket 连接错误')
    store.setDetecting(false)
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
  store.reset()
}

onUnmounted(() => {
  stopDetect()
})
</script>

<template>
  <div style="padding: 20px">
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>实时检测画面</span>
              <div>
                <el-tag v-if="store.wsConnected" type="success" style="margin-right: 8px">
                  已连接
                </el-tag>
                <el-tag v-else type="info" style="margin-right: 8px">
                  未连接
                </el-tag>
                <el-button
                  v-if="store.isDetecting"
                  :type="paused ? 'success' : 'warning'"
                  size="small"
                  @click="togglePause"
                >
                  {{ paused ? '继续' : '暂停' }}
                </el-button>
                <el-button
                  v-if="store.isDetecting"
                  type="danger"
                  size="small"
                  @click="stopDetect"
                >
                  停止
                </el-button>
              </div>
            </div>
          </template>

          <DetectionCanvas
            v-if="store.currentFrame"
            :image="store.currentFrame"
            :detections="store.detections"
            :violations="store.violations"
            :show-labels="true"
          />
          <el-empty v-else description="等待检测画面..." />
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card style="margin-bottom: 20px">
          <template #header>检测统计</template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="帧号">{{ store.frameNumber }}</el-descriptions-item>
            <el-descriptions-item label="时间">{{ store.timestamp.toFixed(1) }}s</el-descriptions-item>
            <el-descriptions-item label="目标数">{{ store.detections.length }}</el-descriptions-item>
            <el-descriptions-item label="违规数">{{ store.violations.length }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card v-if="store.violations.length > 0">
          <template #header>
            <span style="color: #F44336">违规告警</span>
          </template>
          <el-alert
            v-for="(v, i) in store.violations"
            :key="i"
            :title="`${VIOLATION_LABELS[v.type] || v.type}: ${v.count}次`"
            type="warning"
            :closable="false"
            style="margin-bottom: 8px"
          />
        </el-card>

        <el-card v-if="!store.isDetecting">
          <template #header>开始检测</template>
          <el-input
            v-model="filePath"
            placeholder="输入文件路径或上传文件"
            style="margin-bottom: 12px"
          />
          <el-button type="primary" @click="connectWebSocket" style="width: 100%">
            开始检测
          </el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
