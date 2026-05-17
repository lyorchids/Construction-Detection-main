<script setup lang="ts">
import { computed } from 'vue'

export interface TimelineMarker {
  frame: number
  time: number
  type: string
  color: string
}

const props = defineProps<{
  currentFrame: number
  totalFrames: number
  markers: TimelineMarker[]
}>()

const progress = computed(() => {
  if (props.totalFrames <= 0) return 0
  return Math.min((props.currentFrame / props.totalFrames) * 100, 100)
})
</script>

<template>
  <div class="timeline">
    <div class="timeline-track">
      <div class="timeline-fill" :style="{ width: progress + '%' }"></div>
      <div
        v-for="(m, i) in markers"
        :key="i"
        class="timeline-marker"
        :style="{
          left: (m.frame / totalFrames * 100) + '%',
          background: m.color,
          borderColor: m.color,
        }"
        :title="`帧 ${m.frame} (${m.time.toFixed(1)}s): ${m.type}`"
      ></div>
      <div class="timeline-thumb" :style="{ left: progress + '%' }"></div>
    </div>
    <div class="timeline-info">
      <span>{{ currentFrame }} / {{ totalFrames }} 帧</span>
      <span>{{ progress.toFixed(0) }}%</span>
    </div>
  </div>
</template>

<style scoped>
.timeline {
  padding: 12px 0 4px;
}

.timeline-track {
  position: relative;
  height: 8px;
  background: #e8e8e8;
  border-radius: 4px;
  cursor: pointer;
  overflow: visible;
}

.timeline-fill {
  height: 100%;
  background: linear-gradient(90deg, #42a5f5, #1e88e5);
  border-radius: 4px;
  transition: width 0.15s linear;
  max-width: 100%;
}

.timeline-marker {
  position: absolute;
  top: 50%;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  border: 1.5px solid;
  box-shadow: 0 0 3px rgba(0, 0, 0, 0.25);
}

.timeline-thumb {
  position: absolute;
  top: 50%;
  width: 14px;
  height: 14px;
  background: #fff;
  border: 2.5px solid #1e88e5;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  z-index: 3;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
  transition: left 0.15s linear;
}

.timeline-info {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 12px;
  color: #999;
}
</style>
