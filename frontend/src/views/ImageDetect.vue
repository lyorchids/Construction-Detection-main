<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadImage } from '../api/upload'
import api, { getModels } from '../api'
import { getProfiles, createProfile } from '../api/detection_profile'
import type { DetectionProfile } from '../api/detection_profile'
import DetectionCanvas from '../components/DetectionCanvas.vue'
import ViolationWarning from '../components/ViolationWarning.vue'
import DetectionProfileDialog from '../components/DetectionProfileDialog.vue'

interface ModelInfo {
  name: string
  classes: Record<string, string>
  danger_rules: boolean
}

const uploading = ref(false)
const detecting = ref(false)
const progress = ref(0)
const currentFrame = ref('')
const detections = ref<any[]>([])
const violations = ref<any[]>([])
const totalObjects = ref(0)

// Annotation mode: 'all' = 全部标注, 'config' = 配置标注
const annotationMode = ref<'all' | 'config'>('all')

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
  detect_near_machinery_or_vehicle: true,
  detect_in_restricted_area: true,
  detect_in_utility_pole_restricted_area: false,
  detect_machinery_close_to_pole: false,
})

// Polygon overlays
const conePolygons = ref<number[][][]>([])
const polePolygons = ref<number[][][]>([])

// Collapsible config
const configExpanded = ref(false)

// Profile state
const profiles = ref<DetectionProfile[]>([])
const selectedProfileId = ref<number | null>(null)
const dialogVisible = ref(false)

onMounted(async () => {
  try {
    const { data } = await getModels()
    availableModels.value = data.models || {}
    for (const key of Object.keys(data.models || {})) {
      selectedModels.value[key] = true
      modelThresholds.value[key] = 0.25
    }
  } catch {
    availableModels.value = {
      ppe: { name: '安全PPE检测', classes: {}, danger_rules: true },
      fire: { name: '火情烟雾检测', classes: {}, danger_rules: false },
    }
    selectedModels.value = { ppe: true, fire: true }
    modelThresholds.value = { ppe: 0.25, fire: 0.25 }
  }
  await loadProfiles()
})

async function loadProfiles() {
  try {
    const { data } = await getProfiles('image')
    profiles.value = data
  } catch {
    // ignore
  }
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
  // config mode: only Person + active violation targets
  return detections.value.filter((d: any) => d.class_name === 'Person' || d.is_violation)
})

const VIOLATION_LABELS: Record<string, string> = {
  warning_no_hardhat: '未戴安全帽',
  warning_no_mask: '未佩戴口罩',
  warning_no_safety_vest: '未穿反光背心',
  warning_close_to_machinery: '靠近作业机械',
  warning_close_to_vehicle: '靠近施工车辆',
  warning_people_in_controlled_area: '进入管控区',
  warning_people_in_utility_pole_controlled_area: '进入电线杆管控区',
  warning_fire: '检测到火焰',
  warning_smoke: '检测到烟雾',
}

function compatRules(rules: Record<string, any>): Record<string, any> {
  if (rules.detect_no_safety_vest_or_helmet !== undefined) {
    const val = !!rules.detect_no_safety_vest_or_helmet
    return {
      detect_no_hardhat: val,
      detect_no_mask: val,
      detect_no_safety_vest: val,
      detect_near_machinery_or_vehicle: rules.detect_near_machinery_or_vehicle ?? true,
      detect_in_restricted_area: rules.detect_in_restricted_area ?? true,
      detect_in_utility_pole_restricted_area: rules.detect_in_utility_pole_restricted_area ?? false,
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
}

function onProfileChange(profileId: number | string) {
  const id = Number(profileId)
  selectedProfileId.value = id || null
  if (!id) return
  const profile = profiles.value.find(p => p.id === id)
  if (profile) applyProfile(profile)
}

async function saveAsProfile() {
  dialogVisible.value = true
}

async function handleSaveProfile(data: any) {
  try {
    await createProfile(data)
    ElMessage.success('配置已保存')
    await loadProfiles()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

async function handleUpload(file: File) {
  uploading.value = true
  try {
    const { data } = await uploadImage(file)
    progress.value = 100
    ElMessage.success('上传成功，开始检测...')
    await detectImage(data.file_path)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function detectImage(filePath: string) {
  detecting.value = true
  try {
    const thresholds: Record<string, number> = {}
    for (const key of selectedModelKeys.value) {
      thresholds[key] = modelThresholds.value[key] ?? 0.25
    }
    const { data } = await api.post('/image/detect', {
      file_path: filePath,
      models: selectedModelKeys.value,
      thresholds,
      danger_rules: dangerRules.value,
    })
    currentFrame.value = data.image
    detections.value = data.detections
    violations.value = data.violations
    conePolygons.value = data.cone_polygons || []
    polePolygons.value = data.pole_polygons || []
    totalObjects.value = data.total_objects

    if (data.violations.length > 0) {
      const msgs = data.violations.map((v: any) =>
        `${VIOLATION_LABELS[v.type] || v.type}: ${v.count}次`,
      ).join(', ')
      ElMessage.warning({ message: `检测到违规: ${msgs}`, duration: 5000 })
    } else {
      ElMessage.success('检测完成，未发现违规')
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '检测失败')
  } finally {
    detecting.value = false
  }
}

function reset() {
  currentFrame.value = ''
  detections.value = []
  violations.value = []
  totalObjects.value = 0
  progress.value = 0
}
</script>

<template>
  <div style="padding: 20px">
    <!-- Collapsible config card -->
    <el-card class="model-config-card">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 600">检测配置</span>
          <div style="display: flex; gap: 8px">
            <el-button size="small" @click="saveAsProfile">+ 保存</el-button>
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
        <span v-if="selectedModels.ppe" class="config-sub">({{ dangerRules.detect_no_hardhat ? '安全帽' : '' }}{{ dangerRules.detect_no_mask ? '口罩' : '' }}{{ dangerRules.detect_no_safety_vest ? '背心' : '' }}{{ dangerRules.detect_near_machinery_or_vehicle ? '机械' : '' }}{{ dangerRules.detect_in_restricted_area ? '锥形桶' : '' }})</span>
        <span class="config-tag" :class="{ on: selectedModels.fire }">Fire</span>
        <el-button link size="small" @click="configExpanded = !configExpanded" style="margin-left: auto">
          {{ configExpanded ? '收起' : '展开' }}详细配置
        </el-button>
      </div>

      <!-- Expanded details -->
      <el-collapse-transition>
        <div v-show="configExpanded" class="config-detail">
          <div v-for="(info, key) in availableModels" :key="key" class="model-config-row">
            <el-checkbox v-model="selectedModels[key]" :label="info.name" size="large" />
            <div v-if="selectedModels[key]" class="threshold-slider">
              <span class="threshold-label">置信度: {{ (modelThresholds[key] * 100).toFixed(0) }}%</span>
              <el-slider
                v-model="modelThresholds[key]"
                :min="0.05"
                :max="0.95"
                :step="0.05"
                size="small"
                style="width: 160px"
              />
            </div>
            <div v-if="selectedModels[key] && info.danger_rules" class="danger-rules-inline">
              <el-checkbox v-model="dangerRules.detect_no_hardhat" size="small">未戴安全帽</el-checkbox>
              <el-checkbox v-model="dangerRules.detect_no_mask" size="small">未戴口罩</el-checkbox>
              <el-checkbox v-model="dangerRules.detect_no_safety_vest" size="small">未穿背心</el-checkbox>
              <el-checkbox v-model="dangerRules.detect_near_machinery_or_vehicle" size="small">靠近机械/车辆</el-checkbox>
              <el-checkbox v-model="dangerRules.detect_in_restricted_area" size="small">锥形桶管控区</el-checkbox>
              <el-checkbox v-model="dangerRules.detect_in_utility_pole_restricted_area" size="small">电线杆管控区</el-checkbox>
              <el-checkbox v-model="dangerRules.detect_machinery_close_to_pole" size="small">杆旁机械</el-checkbox>
            </div>
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
      <el-col :span="16">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>图片检测结果</span>
              <div style="display: flex; align-items: center; gap: 12px">
                <el-button v-if="currentFrame" size="small" @click="reset">重新上传</el-button>
              </div>
            </div>
          </template>

          <div
            v-if="currentFrame"
            class="image-wrapper"
          >
            <DetectionCanvas
              :image="currentFrame"
              :detections="filteredDetections"
              :violations="filteredViolations"
              :cone-polygons="conePolygons"
              :pole-polygons="polePolygons"
              :show-labels="true"
            />
          </div>
          <div v-else>
            <el-upload
              drag
              :auto-upload="false"
              :show-file-list="false"
              :on-change="(file: any) => handleUpload(file.raw)"
              :disabled="uploading || detecting"
              accept="image/*"
            >
              <div style="padding: 40px 0">
                <el-icon :size="60" color="#409eff"><UploadFilled /></el-icon>
                <p style="margin: 16px 0 8px; font-size: 16px">
                  拖拽图片到此处或点击上传
                </p>
                <p style="color: #999; font-size: 12px">
                  支持: JPG, PNG, BMP, WebP | 最大: 10MB
                </p>
              </div>
            </el-upload>

            <el-progress
              v-if="uploading || detecting"
              :percentage="detecting ? 100 : progress"
              :status="detecting ? 'success' : undefined"
              style="margin-top: 20px"
            />
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <ViolationWarning v-if="filteredViolations.length > 0" :violations="filteredViolations" />
      </el-col>
    </el-row>

    <DetectionProfileDialog
      v-model="dialogVisible"
      :profile="null"
      profile-type="image"
      @save="handleSaveProfile"
    />
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

.page-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.image-wrapper {
  position: relative;
  border-radius: 6px;
  overflow: hidden;
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

</style>
