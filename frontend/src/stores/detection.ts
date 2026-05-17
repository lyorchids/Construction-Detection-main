import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface DetectionState {
  isDetecting: boolean
  wsConnected: boolean
  currentFrame: string
  detections: Detection[]
  violations: Violation[]
  frameNumber: number
  timestamp: number
}

export interface Detection {
  bbox: [number, number, number, number]
  confidence: number
  class_id: number
  class_name: string
  track_id: number | null
  is_moving: boolean
}

export interface Violation {
  type: string
  count: number
}

export const useDetectionStore = defineStore('detection', () => {
  const isDetecting = ref(false)
  const wsConnected = ref(false)
  const currentFrame = ref('')
  const detections = ref<Detection[]>([])
  const violations = ref<Violation[]>([])
  const frameNumber = ref(0)
  const timestamp = ref(0)

  function setDetecting(value: boolean) {
    isDetecting.value = value
  }

  function setWsConnected(value: boolean) {
    wsConnected.value = value
  }

  function updateFrame(data: {
    image: string
    detections: Detection[]
    violations: Violation[]
    frame_number: number
    timestamp: number
  }) {
    currentFrame.value = data.image
    detections.value = data.detections
    violations.value = data.violations
    frameNumber.value = data.frame_number
    timestamp.value = data.timestamp
  }

  function reset() {
    isDetecting.value = false
    wsConnected.value = false
    currentFrame.value = ''
    detections.value = []
    violations.value = []
    frameNumber.value = 0
    timestamp.value = 0
  }

  return {
    isDetecting,
    wsConnected,
    currentFrame,
    detections,
    violations,
    frameNumber,
    timestamp,
    setDetecting,
    setWsConnected,
    updateFrame,
    reset,
  }
})
