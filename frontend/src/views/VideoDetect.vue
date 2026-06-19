<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadVideo } from '../api/upload'
import { getModels } from '../api'
import { getProfiles } from '../api/detection_profile'
import type { DetectionProfile } from '../api/detection_profile'
import DetectionCanvas from '../components/DetectionCanvas.vue'
import ViolationWarning from '../components/ViolationWarning.vue'
import VideoTimeline from '../components/VideoTimeline.vue'
import type { TimelineMarker } from '../components/VideoTimeline.vue'

interface ModelInfo {
  name: string
  classes: Record<string, string>
  danger_rules: boolean
}

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
const loadingText = ref('正在连接检测服务...')

// Annotation mode: 'all' = 全部标注, 'config' = 配置标注
const annotationMode = ref<'all' | 'config'>('config')

// Class filter for "全部标注" mode
const ALL_CLASS_NAMES = [
  'Person', 'Hardhat', 'Mask', 'Safety Vest', 'Safety Cone', 'Utility Pole',
  'NO-Hardhat', 'NO-Mask', 'NO-Safety Vest',
  'Machinery', 'Vehicle', 'Fire', 'Smoke',
]
const displayClasses = ref<Record<string, boolean>>(
  Object.fromEntries(ALL_CLASS_NAMES.map(n => [n, true])),
)

const availableModels = ref<Record<string, ModelInfo>>({})
const selectedModels = ref<Record<string, boolean>>({})
const modelThresholds = ref<Record<string, number>>({})

// Danger rules state (for ppe model)
const dangerRules = ref({
  detect_no_hardhat: true,
  detect_no_mask: true,
  detect_no_safety_vest: true,
  detect_in_restricted_area: true,
  detect_machinery_close_to_pole: false,
})

// Video-specific settings
const detectionInterval = ref(0.5)
const everyFrame = ref(false)
const saveScreenshots = ref(true)

// Polygon overlays
const conePolygons = ref<number[][][]>([])

// Profile state
const profiles = ref<DetectionProfile[]>([])
const selectedProfileId = ref<number | null>(null)
const configExpanded = ref(false)

// Violation drawer
const drawerVisible = ref(false)
interface ViolationLogItem {
  type: string
  label: string
  color: string
  count: number
}
const violationLog = ref<ViolationLogItem[]>([])

onMounted(async () => {
  try {
    const { data } = await getModels()
    availableModels.value = data.models || {}
    for (const key of Object.keys(data.models || {})) {
      selectedModels.value[key] = true
      modelThresholds.value[key] = key === 'fire' ? 0.5 : 0.25
    }
  } catch {
    availableModels.value = {
      ppe: { name: '安全PPE检测', classes: {}, danger_rules: true },
      fire: { name: '火情烟雾检测', classes: {}, danger_rules: false },
    }
    selectedModels.value = { ppe: true, fire: true }
    modelThresholds.value = { ppe: 0.25, fire: 0.5 }
  }
  await loadProfiles()
})

async function loadProfiles() {
  try {
    const { data } = await getProfiles('video')
    profiles.value = data
  } catch {
    // ignore
  }
}

function compatRules(rules: Record<string, any>): Record<string, any> {
  if (rules.detect_no_safety_vest_or_helmet !== undefined) {
    const val = !!rules.detect_no_safety_vest_or_helmet
    return {
      detect_no_hardhat: val,
      detect_no_mask: val,
      detect_no_safety_vest: val,
      detect_in_restricted_area: rules.detect_in_restricted_area ?? true,
      detect_machinery_close_to_pole: rules.detect_machinery_close_to_pole ?? false,
    }
  }
  return rules
}

function applyProfile(profile: DetectionProfile) {
  if (!profile?.config?.models) return
  const cfg = profile.config
  const ppe = cfg.models.ppe
  const fire = cfg.models.fire
  selectedModels.value = {
    ppe: ppe?.enabled ?? true,
    fire: fire?.enabled ?? false,
  }
  modelThresholds.value = {
    ppe: ppe?.threshold ?? 0.25,
    fire: fire?.threshold ?? 0.25,
  }
  if (ppe?.danger_rules) {
    dangerRules.value = { ...dangerRules.value, ...compatRules(ppe.danger_rules) }
  }
  if (cfg.every_frame != null) everyFrame.value = cfg.every_frame
  if (everyFrame.value) {
    detectionInterval.value = 0
  } else if (cfg.detection_interval != null) {
    detectionInterval.value = cfg.detection_interval
  } else if (cfg.frame_interval != null) {
    detectionInterval.value = Math.max(0.5, cfg.frame_interval / 30)
  }
  if (cfg.save_screenshots != null) saveScreenshots.value = cfg.save_screenshots
}

function onProfileChange(profileId: number | string) {
  const id = Number(profileId)
  selectedProfileId.value = id || null
  if (!id) return
  const profile = profiles.value.find(p => p.id === id)
  if (profile) applyProfile(profile)
}

const selectedModelKeys = computed(() =>
  Object.entries(selectedModels.value)
    .filter(([, v]) => v)
    .map(([k]) => k),
)

const filteredViolations = computed(() => violations.value)

const filteredDetections = computed(() => {
  if (annotationMode.value === 'all') {
    return detections.value.filter((d: any) => displayClasses.value[d.class_name])
  }
  // config mode: show Person + violation-relevant classes from enabled models
  const relevantClasses = new Set<string>()
  relevantClasses.add('Person')
  if (selectedModels.value['ppe']) {
    relevantClasses.add('NO-Hardhat')
    relevantClasses.add('NO-Mask')
    relevantClasses.add('NO-Safety Vest')
  }
  if (selectedModels.value['fire']) {
    relevantClasses.add('Fire')
    relevantClasses.add('Smoke')
  }
  return detections.value.filter((d: any) => relevantClasses.has(d.class_name))
})

watch(violations, (newViolations) => {
  if (!newViolations || newViolations.length === 0) return
  for (const v of newViolations) {
    const existing = violationLog.value.find(item => item.type === v.type)
    if (existing) {
      existing.count = v.count || 1
    } else {
      violationLog.value.push({
        type: v.type,
        label: VIOLATION_LABELS[v.type] || v.type,
        color: VIOLATION_COLORS[v.type] || '#F44336',
        count: v.count || 1,
      })
      if (!drawerVisible.value) {
        drawerVisible.value = true
      }
    }
  }
})

const VIOLATION_LABELS: Record<string, string> = {
  warning_no_hardhat: '未戴安全帽',
  warning_no_mask: '未佩戴口罩',
  warning_no_safety_vest: '未穿反光背心',
  warning_people_in_controlled_area: '进入锥形桶管控区',
  detect_machinery_close_to_pole: '机械靠近电线杆',
  warning_fire: '检测到火焰',
  warning_smoke: '检测到烟雾',
}

const VIOLATION_PRIORITY: Record<string, number> = {
  warning_fire: 10,
  warning_smoke: 9,
  warning_no_hardhat: 5,
  warning_people_in_controlled_area: 4,
  detect_machinery_close_to_pole: 3,
  warning_no_safety_vest: 1,
  warning_no_mask: 1,
}

const VIOLATION_COLORS: Record<string, string> = {
  warning_no_hardhat: '#F44336',
  warning_no_mask: '#FF9800',
  warning_no_safety_vest: '#FF9800',
  warning_people_in_controlled_area: '#E91E63',
  detect_machinery_close_to_pole: '#9C27B0',
  warning_fire: '#FF5722',
  warning_smoke: '#9E9E9E',
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
  violationLog.value = []
  drawerVisible.value = false
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

  // Show loading immediately
  isDetecting.value = true
  wsConnected.value = false
  loadingText.value = '正在连接检测服务...'
  timelineMarkers.value = []
  const encodedPath = encodeURIComponent(filePath.value)
  const wsUrl = `ws://${window.location.host}/ws/video/detect/${encodedPath}`

  ws.value = new WebSocket(wsUrl)

  ws.value.onopen = () => {
    wsConnected.value = true
    const thresholds: Record<string, number> = {}
    for (const key of selectedModelKeys.value) {
      thresholds[key] = modelThresholds.value[key] ?? 0.25
    }
    ws.value?.send(JSON.stringify({
      action: 'start',
      models: selectedModelKeys.value,
      thresholds,
      danger_rules: dangerRules.value,
      every_frame: everyFrame.value,
      detection_interval: detectionInterval.value,
      save_screenshots: saveScreenshots.value,
    }))
  }

  ws.value.onmessage = (event) => {
    const data = JSON.parse(event.data)

    if (data.type === 'info') {
      totalFrames.value = data.total_frames
      duration.value = data.duration
      loadingText.value = '视频已加载，正在初始化检测...'
    } else if (data.type === 'frame') {
      currentFrame.value = data.image
      detections.value = data.detections
      violations.value = data.violations
      conePolygons.value = data.cone_polygons || []
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
    <!-- Collapsible config card -->
    <el-card class="model-config-card">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 600">检测配置</span>
          <div style="display: flex; gap: 8px">
            <el-button size="small" @click="$router.push('/profiles')">管理</el-button>
          </div>
        </div>
      </template>

      <div class="profile-selector-row">
        <span style="font-size: 13px; color: #666; white-space: nowrap">选择配置:</span>
        <el-select
          v-model="selectedProfileId"
          placeholder="手动配置"
          clearable
          style="width: 260px"
          @change="onProfileChange"
        >
          <el-option
            v-for="p in profiles"
            :key="p.id"
            :label="p.name"
            :value="p.id"
          />
        </el-select>
      </div>

      <!-- Summary line -->
      <div class="config-summary">
        <span class="config-tag" :class="{ on: selectedModels.ppe }">PPE</span>
        <span v-if="selectedModels.ppe" class="config-sub">({{ dangerRules.detect_no_hardhat ? '安全帽' : '' }}{{ dangerRules.detect_no_mask ? '口罩' : '' }}{{ dangerRules.detect_no_safety_vest ? '背心' : '' }}{{ dangerRules.detect_in_restricted_area ? '锥形桶' : '' }})</span>
        <span class="config-tag" :class="{ on: selectedModels.fire }">Fire</span>
        <span v-if="selectedModels.fire" class="config-sub">(火焰/烟雾)</span>
        <span class="config-tag">{{ everyFrame ? '逐帧' : detectionInterval + 's' }}</span>
        <el-button link size="small" @click="configExpanded = !configExpanded" style="margin-left: auto">
          {{ configExpanded ? '收起' : '展开' }}详细配置
        </el-button>
      </div>

      <!-- Expanded details (read-only) -->
      <el-collapse-transition>
        <div v-show="configExpanded" class="config-detail">
          <div v-for="(info, key) in availableModels" :key="key" class="model-config-row">
            <div class="model-name-row">
              <span class="model-name">{{ info.name }}</span>
              <el-tag v-if="selectedModels[key]" size="small" type="success" effect="plain">已启用</el-tag>
              <el-tag v-else size="small" type="info" effect="plain">未启用</el-tag>
            </div>
            <div v-if="selectedModels[key]" class="threshold-display">
              <span class="threshold-label">置信度: {{ (modelThresholds[key] * 100).toFixed(0) }}%</span>
            </div>
            <div v-if="selectedModels[key] && info.danger_rules" class="danger-rules-display">
              <span class="danger-rule-hint">危险规则:</span>
              <el-tag v-if="dangerRules.detect_no_hardhat" size="small" type="danger" effect="plain">未戴安全帽</el-tag>
              <el-tag v-if="dangerRules.detect_no_mask" size="small" type="warning" effect="plain">未戴口罩</el-tag>
              <el-tag v-if="dangerRules.detect_no_safety_vest" size="small" type="warning" effect="plain">未穿背心</el-tag>
              <el-tag v-if="dangerRules.detect_in_restricted_area" size="small" type="warning" effect="plain">锥形桶管控区</el-tag>
              <el-tag v-if="dangerRules.detect_machinery_close_to_pole" size="small" type="warning" effect="plain">杆旁机械</el-tag>
            </div>
            <div v-else-if="selectedModels[key] && key === 'fire'" class="danger-rules-display">
              <span class="danger-rule-hint">检测类型:</span>
              <el-tag size="small" type="danger" effect="plain">火焰</el-tag>
              <el-tag size="small" type="warning" effect="plain">烟雾</el-tag>
            </div>
          </div>

          <!-- Video-specific settings (read-only) -->
          <div class="video-params-row" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #f0f0f0">
            <div class="param-item">
              <span class="param-label">逐帧检测:</span>
              <el-switch v-model="everyFrame" size="small" />
            </div>
            <div class="param-item">
              <span class="param-label">检测间隔:</span>
              <span class="threshold-label" :style="{ color: everyFrame ? '#bbb' : 'inherit' }">{{ everyFrame ? '—' : detectionInterval + ' 秒' }}</span>
            </div>
            <div class="param-item">
              <span class="param-label">保存违规截图:</span>
              <el-tag :type="saveScreenshots ? 'success' : 'info'" size="small">{{ saveScreenshots ? '开启' : '关闭' }}</el-tag>
            </div>
          </div>

          <div class="config-edit-hint">
            如需修改配置，请
            <el-button link type="primary" @click="$router.push('/profiles')">前往检测配置管理</el-button>
          </div>
        </div>
      </el-collapse-transition>
    </el-card>

    <div class="page-toolbar">
      <el-radio-group v-model="annotationMode" size="small">
        <el-radio-button value="all">全部标注</el-radio-button>
        <el-radio-button value="config">配置标注</el-radio-button>
      </el-radio-group>
    </div>

    <!-- Class filter for "全部标注" mode -->
    <el-collapse-transition>
      <div v-if="annotationMode === 'all' && currentFrame" class="class-filter-bar">
        <span class="class-filter-label">显示类别:</span>
        <el-checkbox
          v-for="cn in ALL_CLASS_NAMES"
          :key="cn"
          v-model="displayClasses[cn]"
          size="small"
          :label="cn"
        />
      </div>
    </el-collapse-transition>
    <el-row :gutter="20">
      <el-col :span="18">
        <el-card>
          <template #header>
            <span style="font-weight: 600">🎥 视频实时检测</span>
          </template>

          <!-- Upload area (no video, not detecting) -->
          <div v-if="!currentFrame && !isDetecting">
            <el-upload
              drag
              :auto-upload="false"
              :show-file-list="false"
              :on-change="(file: any) => handleUpload(file.raw)"
              :disabled="uploading || isDetecting"
              accept="video/*"
            >
              <div style="padding: 200px 0">
                <el-icon :size="60" color="#409eff"><UploadFilled /></el-icon>
                <p style="margin: 16px 0 8px; font-size: 16px">拖拽视频到此处或点击上传</p>
                <p style="color: #999; font-size: 12px">支持: MP4, AVI, MOV, MKV, FLV | 最大: 200MB</p>
              </div>
            </el-upload>
          </div>

          <!-- Loading state (detecting, first frame not yet arrived) -->
          <div v-else-if="!currentFrame && isDetecting" class="loading-placeholder">
            <el-icon class="loading-spinner" :size="48"><Loading /></el-icon>
            <p class="loading-text">{{ loadingText }}</p>
          </div>

          <template v-else>
            <div
              class="image-wrapper"
            :class="{ 'violation-active': filteredViolations.length > 0 }"
          >
            <DetectionCanvas
              :image="currentFrame"
              :detections="filteredDetections"
              :violations="filteredViolations"
              :cone-polygons="conePolygons"
              :show-labels="true"
            />
            <div v-if="filteredViolations.length > 0" class="violation-overlay" />
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
                <el-button
                  v-if="filePath && !isDetecting"
                  size="default"
                  @click="resetState"
                >
                  重新上传
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

      </el-col>

      <el-col :span="6">
        <el-card style="margin-bottom: 16px">
          <template #header>
            <div class="right-header">
              <span style="font-weight: 600">🚨 违规记录</span>
              <el-button
                v-if="violationLog.length > 0"
                size="small"
                type="danger"
                @click="drawerVisible = true"
              >
                查看详情
              </el-button>
            </div>
          </template>
          <div v-if="violationLog.length === 0" style="color: #999; font-size: 13px; text-align: center; padding: 8px 0">
            暂无违规
          </div>
          <div v-else class="stats-list">
            <div v-for="v in violationLog.slice(0, 5)" :key="v.type" class="stats-row">
              <span style="display: flex; align-items: center; gap: 6px; font-size: 13px">
                <span class="vio-dot" :style="{ background: v.color }"></span>
                {{ v.label }}
              </span>
              <el-tag size="small" type="danger" effect="dark">×{{ v.count }}</el-tag>
            </div>
            <div v-if="violationLog.length > 5" style="font-size: 12px; color: #999; text-align: center; margin-top: 4px">
              还有 {{ violationLog.length - 5 }} 项...
            </div>
          </div>
        </el-card>

        <el-card>
          <template #header>
            <span style="font-weight: 600">📊 检测统计</span>
          </template>
          <div class="stats-list">
            <div class="stats-row">
              <span class="stats-key">检测目标</span>
              <span class="stats-val">{{ isDetecting ? filteredDetections.length : totalObjects }}</span>
            </div>
            <div class="stats-row">
              <span class="stats-key">违规次数</span>
              <span class="stats-val" :class="{ 'has-violation': filteredViolations.length > 0 }">
                {{ isDetecting ? filteredViolations.length : totalViolations }}
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

    <el-drawer
      v-model="drawerVisible"
      title="🚨 违规清单"
      direction="rtl"
      size="380px"
    >
      <template v-if="violationLog.length > 0">
        <div class="drawer-summary">
          本视频共检测到 <strong>{{ violationLog.reduce((s, v) => s + v.count, 0) }}</strong> 次违规
        </div>
        <div class="drawer-list">
          <div v-for="v in violationLog" :key="v.type" class="drawer-item">
            <span class="vio-dot" :style="{ background: v.color }"></span>
            <span class="drawer-label">{{ v.label }}</span>
            <el-tag size="small" type="danger">{{ v.count }}次</el-tag>
          </div>
        </div>
      </template>
      <div v-else style="text-align: center; color: #999; padding: 40px 0">
        暂无违规记录
      </div>
    </el-drawer>

  </div>
</template>

<style scoped>
.model-config-card {
  margin-bottom: 16px;
}
.model-config-card :deep(.el-card__header) {
  padding: 12px 20px;
}
.model-config-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.model-config-row {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 30px;
}
.model-config-row:last-child {
  margin-bottom: 0;
}
.threshold-slider {
  display: flex;
  align-items: center;
  gap: 10px;
}
.threshold-label {
  font-size: 13px;
  color: #666;
  white-space: nowrap;
}
.danger-rules-inline {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-left: 24px;
}
.danger-rules-inline :deep(.el-checkbox__label) {
  font-size: 12px;
}
.profile-selector-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.config-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 8px 0;
  border-top: 1px solid #f0f0f0;
}
.config-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  background: #f0f0f0;
  color: #999;
}
.config-tag.on {
  background: #e6f7ff;
  color: #1890ff;
  font-weight: 600;
}
.config-sub {
  font-size: 12px;
  color: #999;
}
.config-detail {
  padding: 12px 0 4px;
  border-top: 1px solid #f0f0f0;
  margin-top: 8px;
}
.config-edit-hint {
  font-size: 13px;
  color: #999;
}
.danger-rules-display {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.video-params-row {
  display: flex;
  align-items: center;
  gap: 40px;
  flex-wrap: wrap;
}
.param-item {
  display: flex;
  align-items: center;
  gap: 16px;
}
.param-label {
  font-size: 15px;
  color: #666;
  white-space: nowrap;
}

.page-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.image-wrapper {
  position: relative;
  border-radius: 6px;
  overflow: hidden;
  min-height: 500px;
  background: #000;
}

.image-wrapper.violation-active {
  box-shadow:
    0 0 0 4px rgba(244, 67, 54, 0.8),
    0 0 30px rgba(244, 67, 54, 0.4),
    0 0 60px rgba(244, 67, 54, 0.15);
  animation: card-pulse 1.5s ease-in-out infinite;
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
  justify-content: space-between;
}
.violation-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: rgba(255, 0, 0, 0.12);
  animation: overlay-breathe 1.5s ease-in-out infinite;
  z-index: 5;
}
.drawer-summary {
  font-size: 13px;
  color: #666;
  margin-bottom: 16px;
  padding: 8px 12px;
  background: #fff7f7;
  border-radius: 6px;
}
.drawer-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.drawer-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #fafafa;
}
.drawer-label {
  flex: 1;
  font-size: 14px;
  color: #333;
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
@keyframes overlay-breathe {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
.class-filter-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding: 8px 12px;
  margin-bottom: 12px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #f0f0f0;
}
.class-filter-label {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
  margin-right: 4px;
}
.class-filter-bar :deep(.el-checkbox__label) {
  font-size: 12px;
}
.loading-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 200px 0;
  color: #999;
}
.loading-spinner {
  animation: spin 1.5s linear infinite;
}
.loading-text {
  margin-top: 20px;
  font-size: 15px;
  color: #666;
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
