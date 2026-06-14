<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  violations: any[]
}>()

const expanded = ref(false)

const VIOLATION_LABELS: Record<string, string> = {
  warning_no_hardhat: '未戴安全帽',
  warning_no_safety_vest: '未穿反光背心',
  warning_close_to_machinery: '靠近作业机械',
  warning_close_to_vehicle: '靠近施工车辆',
  warning_people_in_controlled_area: '进入锥形桶管控区',
  warning_people_in_utility_pole_controlled_area: '进入电线杆管控区',
  warning_fire: '检测到火焰',
  warning_smoke: '检测到烟雾',
}

const VIOLATION_ICONS: Record<string, string> = {
  warning_no_hardhat: '🚫',
  warning_no_safety_vest: '🦺',
  warning_close_to_machinery: '⚠️',
  warning_close_to_vehicle: '⚠️',
  warning_people_in_controlled_area: '🚧',
  warning_people_in_utility_pole_controlled_area: '⚡',
  warning_fire: '🔥',
  warning_smoke: '💨',
}

const firstViolation = computed(() => props.violations[0])
const remainingViolations = computed(() => props.violations.slice(1))
</script>

<template>
  <el-card shadow="always" class="violation-card">
    <template #header>
      <div class="violation-header">
        <span class="violation-header-icon">🚨</span>
        <span class="violation-header-title">违规告警</span>
        <el-tag size="small" type="danger" effect="dark" round class="violation-badge">
          {{ violations.length }}项
        </el-tag>
      </div>
    </template>

    <div class="violation-body">
      <div class="violation-row primary-row">
        <span class="vio-icon">{{ VIOLATION_ICONS[firstViolation.type] || '🔴' }}</span>
        <span class="vio-label">{{ VIOLATION_LABELS[firstViolation.type] || firstViolation.type }}</span>
        <span class="vio-count">{{ firstViolation.count }}次</span>
      </div>

      <template v-if="remainingViolations.length > 0">
        <Transition name="slide">
          <div v-if="expanded" class="remaining-list">
            <div v-for="v in remainingViolations" :key="v.type" class="violation-row secondary-row">
              <span class="vio-icon">{{ VIOLATION_ICONS[v.type] || '🔴' }}</span>
              <span class="vio-label">{{ VIOLATION_LABELS[v.type] || v.type }}</span>
              <span class="vio-count">{{ v.count }}次</span>
            </div>
          </div>
        </Transition>

        <div class="expand-bar">
          <el-button text type="primary" size="small" @click="expanded = !expanded">
            <template v-if="expanded">
              收起 ▲
            </template>
            <template v-else>
              展开全部 ({{ remainingViolations.length }}项) ▼
            </template>
          </el-button>
        </div>
      </template>
    </div>
  </el-card>
</template>

<style scoped>
.violation-card {
  margin-top: 20px;
  border: 2px solid #f44336;
  border-radius: 10px;
  overflow: hidden;
}

:deep(.el-card__header) {
  background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
  border-bottom: 2px solid #f44336;
  padding: 14px 20px;
}

.violation-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.violation-header-icon {
  font-size: 22px;
}

.violation-header-title {
  font-size: 16px;
  font-weight: 700;
  color: #d32f2f;
}

.violation-badge {
  font-weight: 700;
  margin-left: auto;
}

.violation-body {
  padding: 4px 0;
}

.violation-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 8px;
  margin-bottom: 6px;
}

.primary-row {
  background: #fff3f3;
  border: 1px solid #ffcdd2;
  font-weight: 700;
  font-size: 15px;
}

.secondary-row {
  background: #fafafa;
  border: 1px solid #f5f5f5;
  font-size: 14px;
}

.remaining-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.vio-icon {
  font-size: 18px;
  width: 26px;
  text-align: center;
  flex-shrink: 0;
}

.vio-label {
  flex: 1;
  color: #333;
}

.vio-count {
  font-weight: 700;
  color: #d32f2f;
  font-size: 15px;
  flex-shrink: 0;
}

.expand-bar {
  text-align: center;
  padding-top: 8px;
  border-top: 1px dashed #e0e0e0;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 300px;
}
</style>
