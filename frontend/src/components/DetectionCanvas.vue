<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

interface Detection {
  bbox: [number, number, number, number]
  confidence: number
  class_id: number
  class_name: string
  track_id: number | null
  is_moving: boolean
  source_model?: string
  is_violation?: boolean
  violation_labels?: string[]
}

interface Violation {
  type: string
  count: number
}

const props = defineProps<{
  image: string
  detections: Detection[]
  violations: Violation[]
  conePolygons?: number[][][]
  polePolygons?: number[][][]
  showLabels: boolean
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const imgRef = ref<HTMLImageElement | null>(null)

const VIOLATION_TYPES: Record<string, string> = {
  warning_no_hardhat: '⚠ 未戴安全帽',
  warning_no_mask: '⚠ 未戴口罩',
  warning_no_safety_vest: '⚠ 未穿反光背心',
  warning_people_in_controlled_area: '⚠ 进入管控区',
  warning_people_in_utility_pole_controlled_area: '⚠ 进入电线杆管控区',
  warning_fire: '🔥 火焰',
  warning_smoke: '💨 烟雾',
}

const VIOLATION_COLORS: Record<string, string> = {
  warning_no_hardhat: '#F44336',
  warning_no_mask: '#FF9800',
  warning_no_safety_vest: '#FF9800',
  warning_people_in_controlled_area: '#FFC107',
  warning_people_in_utility_pole_controlled_area: '#795548',
  warning_fire: '#F44336',
  warning_smoke: '#E53935',
}

const CLASS_COLORS: Record<string, string> = {
  Hardhat: '#2196F3',
  Mask: '#4CAF50',
  'NO-Hardhat': '#FF5722',
  'NO-Mask': '#FF9800',
  'NO-Safety Vest': '#FF9800',
  Person: '#4CAF50',
  'Safety Cone': '#FFEB3B',
  'Safety Vest': '#4CAF50',
  Machinery: '#9C27B0',
  'Utility Pole': '#795548',
  Vehicle: '#00BCD4',
  Fire: '#FF5722',
  Smoke: '#9E9E9E',
}

function draw() {
  const canvas = canvasRef.value
  const img = imgRef.value
  if (!canvas || !img) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const w = img.naturalWidth || 640
  const h = img.naturalHeight || 480
  canvas.width = w
  canvas.height = h
  canvas.style.aspectRatio = `${w} / ${h}`
  canvas.style.width = '100%'
  canvas.style.height = 'auto'

  ctx.drawImage(img, 0, 0, w, h)

  // Draw cone polygons (semi-transparent yellow)
  if (props.conePolygons) {
    for (const poly of props.conePolygons) {
      if (poly.length < 3) continue
      ctx.beginPath()
      ctx.moveTo(poly[0][0], poly[0][1])
      for (let i = 1; i < poly.length; i++) {
        ctx.lineTo(poly[i][0], poly[i][1])
      }
      ctx.closePath()
      ctx.fillStyle = 'rgba(255, 235, 59, 0.25)'
      ctx.fill()
      ctx.strokeStyle = 'rgba(255, 235, 59, 0.7)'
      ctx.lineWidth = 2
      ctx.stroke()
    }
  }

  // Draw pole polygons (semi-transparent purple)
  if (props.polePolygons) {
    for (const poly of props.polePolygons) {
      if (poly.length < 3) continue
      ctx.beginPath()
      ctx.moveTo(poly[0][0], poly[0][1])
      for (let i = 1; i < poly.length; i++) {
        ctx.lineTo(poly[i][0], poly[i][1])
      }
      ctx.closePath()
      ctx.fillStyle = 'rgba(156, 39, 176, 0.20)'
      ctx.fill()
      ctx.strokeStyle = 'rgba(156, 39, 176, 0.6)'
      ctx.lineWidth = 2
      ctx.stroke()
    }
  }

  const baseWidth = Math.max(2, canvas.width / 300)
  const fontSize = Math.max(14, canvas.width / 56)

  for (const det of props.detections) {
    const [x1, y1, x2, y2] = det.bbox
    const vl = det.violation_labels?.filter(Boolean) ?? []
    const isViolation = !!(det.is_violation && vl.length > 0)
    const color = isViolation
      ? (VIOLATION_COLORS[vl[0]] || '#F44336')
      : (CLASS_COLORS[det.class_name] || '#FFFFFF')
    const lineWidth = isViolation ? baseWidth * 2 : baseWidth

    ctx.strokeStyle = color
    ctx.lineWidth = lineWidth
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)

    if (props.showLabels) {
      const label = isViolation
        ? `${vl.map(t => VIOLATION_TYPES[t] || t).join(' | ')} ${(det.confidence * 100).toFixed(0)}%`
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

watch(() => [props.image, props.detections, props.conePolygons, props.polePolygons], () => {
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
  <canvas ref="canvasRef" style="width: 100%; display: block; border-radius: 4px" />
</template>
