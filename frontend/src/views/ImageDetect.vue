<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadImage } from '../api/upload'
import api from '../api'
import DetectionCanvas from '../components/DetectionCanvas.vue'

const uploading = ref(false)
const detecting = ref(false)
const progress = ref(0)
const currentFrame = ref('')
const detections = ref<any[]>([])
const violations = ref<any[]>([])
const totalObjects = ref(0)

const VIOLATION_LABELS: Record<string, string> = {
  warning_no_hardhat: '未戴安全帽',
  warning_close_to_machinery: '靠近作业机械',
  warning_close_to_vehicle: '靠近施工车辆',
  warning_people_in_controlled_area: '进入管控区',
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
    const { data } = await api.post('/image/detect', { file_path: filePath })
    currentFrame.value = data.image
    detections.value = data.detections
    violations.value = data.violations
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
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>图片检测结果</span>
              <el-button v-if="currentFrame" size="small" @click="reset">重新上传</el-button>
            </div>
          </template>

          <DetectionCanvas
            v-if="currentFrame"
            :image="currentFrame"
            :detections="detections"
            :violations="violations"
            :show-labels="true"
          />
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
        <el-card style="margin-bottom: 20px">
          <template #header>检测统计</template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="目标数">{{ totalObjects }}</el-descriptions-item>
            <el-descriptions-item label="违规数">{{ violations.length }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card v-if="violations.length > 0">
          <template #header>
            <span style="color: #F44336">违规告警</span>
          </template>
          <el-alert
            v-for="(v, i) in violations"
            :key="i"
            :title="`${VIOLATION_LABELS[v.type] || v.type}: ${v.count}次`"
            type="warning"
            :closable="false"
            style="margin-bottom: 8px"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
