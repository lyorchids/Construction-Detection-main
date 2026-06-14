<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  modelValue: boolean
  profile?: any
  profileType: 'image' | 'video'
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  'save': [data: any]
}>()

const visible = ref(false)
watch(() => props.modelValue, (v) => { visible.value = v })

const form = ref({
  name: '',
  type: 'image' as 'image' | 'video',
  description: '',
  ppeEnabled: true,
  ppeThreshold: 0.25,
  fireEnabled: false,
  fireThreshold: 0.25,
  dangerNoHardhat: true,
  dangerNoMask: true,
  dangerNoSafetyVest: true,
  dangerNearMachinery: true,
  dangerRestrictedArea: true,
  dangerPoleArea: false,
  dangerMachineryPole: false,
  frameInterval: 10,
  saveScreenshots: true,
})

function compatRules(rules: Record<string, any>): Record<string, boolean> {
  // Handle old configs that use detect_no_safety_vest_or_helmet
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

watch(() => props.profile, (p) => {
  if (p) {
    const cfg = p.config || {}
    const ppe = cfg.models?.ppe || {}
    const fire = cfg.models?.fire || {}
    const rules = compatRules(ppe.danger_rules || {})
    form.value = {
      name: p.name || '',
      type: p.type || 'image',
      description: p.description || '',
      ppeEnabled: ppe.enabled ?? true,
      ppeThreshold: ppe.threshold ?? 0.25,
      fireEnabled: fire.enabled ?? false,
      fireThreshold: fire.threshold ?? 0.25,
      dangerNoHardhat: rules.detect_no_hardhat ?? true,
      dangerNoMask: rules.detect_no_mask ?? true,
      dangerNoSafetyVest: rules.detect_no_safety_vest ?? true,
      dangerNearMachinery: rules.detect_near_machinery_or_vehicle ?? true,
      dangerRestrictedArea: rules.detect_in_restricted_area ?? true,
      dangerPoleArea: rules.detect_in_utility_pole_restricted_area ?? false,
      dangerMachineryPole: rules.detect_machinery_close_to_pole ?? false,
      frameInterval: cfg.frame_interval ?? 10,
      saveScreenshots: cfg.save_screenshots ?? true,
    }
  } else {
    form.value = {
      name: '',
      type: props.profileType,
      description: '',
      ppeEnabled: true,
      ppeThreshold: 0.25,
      fireEnabled: false,
      fireThreshold: 0.25,
      dangerNoHardhat: true,
      dangerNoMask: true,
      dangerNoSafetyVest: true,
      dangerNearMachinery: true,
      dangerRestrictedArea: true,
      dangerPoleArea: false,
      dangerMachineryPole: false,
      frameInterval: 10,
      saveScreenshots: true,
    }
  }
}, { immediate: true })

function buildConfig() {
  const models: Record<string, any> = {}
  if (form.value.ppeEnabled) {
    models.ppe = {
      enabled: true,
      threshold: form.value.ppeThreshold,
      danger_rules: {
        detect_no_hardhat: form.value.dangerNoHardhat,
        detect_no_mask: form.value.dangerNoMask,
        detect_no_safety_vest: form.value.dangerNoSafetyVest,
        detect_near_machinery_or_vehicle: form.value.dangerNearMachinery,
        detect_in_restricted_area: form.value.dangerRestrictedArea,
        detect_in_utility_pole_restricted_area: form.value.dangerPoleArea,
        detect_machinery_close_to_pole: form.value.dangerMachineryPole,
      },
    }
  } else {
    models.ppe = { enabled: false, threshold: form.value.ppeThreshold }
  }
  if (form.value.fireEnabled) {
    models.fire = { enabled: true, threshold: form.value.fireThreshold }
  } else {
    models.fire = { enabled: false, threshold: form.value.fireThreshold }
  }
  const cfg: any = { models }
  if (form.value.type === 'video') {
    cfg.frame_interval = form.value.frameInterval
    cfg.save_screenshots = form.value.saveScreenshots
  }
  return cfg
}

function handleSave() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入配置名称')
    return
  }
  if (!form.value.ppeEnabled && !form.value.fireEnabled) {
    ElMessage.warning('请至少启用一个模型')
    return
  }
  emit('save', {
    id: props.profile?.id,
    name: form.value.name.trim(),
    type: form.value.type,
    description: form.value.description.trim(),
    config: buildConfig(),
  })
  visible.value = false
}

function handleClose() {
  visible.value = false
}

watch(visible, (v) => { emit('update:modelValue', v) })
</script>

<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="visible = $event"
    :title="profile ? '编辑配置' : '新建配置'"
    width="600px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form :model="form" label-position="top">
      <el-row :gutter="16">
        <el-col :span="16">
          <el-form-item label="配置名称">
            <el-input v-model="form.name" placeholder="例如: 全面检测" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="类型">
            <el-select v-model="form.type" :disabled="!!profile" style="width: 100%">
              <el-option label="图片检测" value="image" />
              <el-option label="视频检测" value="video" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="描述">
        <el-input v-model="form.description" placeholder="可选描述" />
      </el-form-item>

      <el-divider content-position="left">模型配置</el-divider>

      <el-card shadow="never" class="model-card">
        <el-checkbox v-model="form.ppeEnabled" label="PPE — 安全PPE检测" size="large" />
        <template v-if="form.ppeEnabled">
          <div class="threshold-row">
            <span class="threshold-label">置信度: {{ (form.ppeThreshold * 100).toFixed(0) }}%</span>
            <el-slider v-model="form.ppeThreshold" :min="0.05" :max="0.95" :step="0.05" size="small" style="width: 200px" />
          </div>
          <div class="danger-rules">
            <div class="rules-title">危险检测规则:</div>
            <el-checkbox v-model="form.dangerNoHardhat">未戴安全帽</el-checkbox>
            <el-checkbox v-model="form.dangerNoMask">未佩戴口罩</el-checkbox>
            <el-checkbox v-model="form.dangerNoSafetyVest">未穿反光背心</el-checkbox>
            <el-checkbox v-model="form.dangerNearMachinery">靠近机械/车辆</el-checkbox>
            <el-checkbox v-model="form.dangerRestrictedArea">进入锥形桶管控区</el-checkbox>
            <el-checkbox v-model="form.dangerPoleArea">进入电线杆管控区</el-checkbox>
            <el-checkbox v-model="form.dangerMachineryPole">机械靠近电线杆</el-checkbox>
          </div>
        </template>
      </el-card>

      <el-card shadow="never" class="model-card" style="margin-top: 12px">
        <el-checkbox v-model="form.fireEnabled" label="Fire — 火情烟雾检测" size="large" />
        <template v-if="form.fireEnabled">
          <div class="threshold-row">
            <span class="threshold-label">置信度: {{ (form.fireThreshold * 100).toFixed(0) }}%</span>
            <el-slider v-model="form.fireThreshold" :min="0.05" :max="0.95" :step="0.05" size="small" style="width: 200px" />
          </div>
        </template>
      </el-card>

      <template v-if="form.type === 'video'">
        <el-divider content-position="left">视频参数</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="帧检测间隔">
              <div class="threshold-row">
                <el-slider v-model="form.frameInterval" :min="1" :max="60" :step="1" size="small" style="width: 160px" />
                <span class="threshold-label">{{ form.frameInterval }} 帧</span>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保存违规截图">
              <el-switch v-model="form.saveScreenshots" />
            </el-form-item>
          </el-col>
        </el-row>
      </template>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.model-card {
  border: 1px solid #e8e8e8;
}
.threshold-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0 0 24px;
}
.threshold-label {
  font-size: 13px;
  color: #666;
  white-space: nowrap;
}
.danger-rules {
  margin: 8px 0 0 24px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.rules-title {
  width: 100%;
  font-size: 13px;
  color: #888;
  margin-bottom: 4px;
}
</style>
