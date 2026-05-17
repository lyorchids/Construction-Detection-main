<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

interface Detection {
  bbox: [number, number, number, number]
  confidence: number
  class_id: number
  class_name: string
  track_id: number | null
  is_moving: boolean
}

interface Violation {
  type: string
  count: number
}

const props = defineProps<{
  image: string
  detections: Detection[]
  violations: Violation[]
  showLabels: boolean
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const imgRef = ref<HTMLImageElement | null>(null)

const VIOLATION_TYPES: Record<string, string> = {
  warning_no_hardhat: '⚠ 未戴安全帽',
  warning_close_to_machinery: '⚠ 靠近作业机械',
  warning_close_to_vehicle: '⚠ 靠近施工车辆',
  warning_people_in_controlled_area: '⚠ 进入管控区',
}

const CLASS_COLORS: Record<string, string> = {
  Hardhat: '#2196F3',
  Mask: '#4CAF50',
  'NO-Hardhat': '#F44336',
  'NO-Mask': '#FF9800',
  'NO-Safety Vest': '#FF9800',
  Person: '#4CAF50',
  'Safety Cone': '#FFEB3B',
  'Safety Vest': '#4CAF50',
  Machinery: '#9C27B0',
  'Utility Pole': '#795548',
  Vehicle: '#00BCD4',
}

function isViolationClass(className: string): boolean {
  return ['NO-Hardhat', 'NO-Mask', 'NO-Safety Vest'].includes(className)
}

function draw() {
  const canvas = canvasRef.value
  const img = imgRef.value
  if (!canvas || !img) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  canvas.width = img.naturalWidth || 640
  canvas.height = img.naturalHeight || 480

  ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

  const lineWidth = Math.max(2, canvas.width / 320)
  const fontSize = Math.max(12, canvas.width / 64)

  for (const det of props.detections) {
    const [x1, y1, x2, y2] = det.bbox
    const isViolation = isViolationClass(det.class_name)
    const color = isViolation ? '#F44336' : (CLASS_COLORS[det.class_name] || '#FFFFFF')

    ctx.strokeStyle = color
    ctx.lineWidth = lineWidth
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)

    if (props.showLabels) {
      const label = isViolation
        ? `${VIOLATION_TYPES[`warning_${det.class_name.toLowerCase().replace(/-/g, '_').replace(/ /g, '_')}`] || det.class_name} ${(det.confidence * 100).toFixed(0)}%`
        : `${det.class_name} ${(det.confidence * 100).toFixed(0)}%`

      ctx.font = `bold ${fontSize}px sans-serif`
      const textWidth = ctx.measureText(label).width
      const textHeight = fontSize + 8

      ctx.fillStyle = color
      ctx.fillRect(x1, y1 - textHeight, textWidth + 8, textHeight)

      ctx.fillStyle = '#FFFFFF'
      ctx.fillText(label, x1 + 4, y1 - 4)
    }
  }
}

watch(() => [props.image, props.detections], () => {
  if (props.image) {
    const img = new Image()
    img.onload = () => {
      imgRef.value = img
      draw()
    }
    img.src = `data:image/jpeg;base64,${props.image}`
  }
})

onMounted(() => {
  if (props.image) {
    const img = new Image()
    img.onload = () => {
      imgRef.value = img
      draw()
    }
    img.src = `data:image/jpeg;base64,${props.image}`
  }
})
</script>

<template>
  <canvas ref="canvasRef" style="width: 100%; height: auto; display: block; border-radius: 4px" />
</template>
