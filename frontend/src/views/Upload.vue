<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadImage, uploadVideo } from '../api/upload'
import { useRouter } from 'vue-router'

const router = useRouter()
const uploading = ref(false)
const progress = ref(0)
const fileType = ref<'image' | 'video'>('image')

const ALLOWED_IMAGE = ['image/jpeg', 'image/png', 'image/bmp', 'image/webp']
const ALLOWED_VIDEO = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo', 'video/x-matroska', 'video/x-flv']
const MAX_IMAGE_SIZE = 10 * 1024 * 1024
const MAX_VIDEO_SIZE = 200 * 1024 * 1024

function beforeUpload(file: File): boolean {
  const isImage = fileType.value === 'image'
  const allowed = isImage ? ALLOWED_IMAGE : ALLOWED_VIDEO
  const maxSize = isImage ? MAX_IMAGE_SIZE : MAX_VIDEO_SIZE

  if (!allowed.includes(file.type)) {
    ElMessage.error(`不支持的文件格式，请选择 ${isImage ? '图片' : '视频'} 文件`)
    return false
  }

  if (file.size > maxSize) {
    ElMessage.error(`文件大小超过限制 (${maxSize / 1024 / 1024}MB)`)
    return false
  }

  return true
}

async function handleUpload(file: File) {
  if (!beforeUpload(file)) return

  uploading.value = true
  progress.value = 0

  try {
    const uploadFn = fileType.value === 'image' ? uploadImage : uploadVideo
    const { data } = await uploadFn(file)
    progress.value = 100
    ElMessage.success('上传成功')
    router.push({ name: 'LiveDetect', query: { file: data.file_path } })
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div style="max-width: 600px; margin: 40px auto">
    <el-card>
      <template #header>
        <h3 style="margin: 0">上传文件进行安全检测</h3>
      </template>

      <el-radio-group v-model="fileType" style="margin-bottom: 20px">
        <el-radio-button value="image">图片</el-radio-button>
        <el-radio-button value="video">视频</el-radio-button>
      </el-radio-group>

      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        :on-change="(file: any) => handleUpload(file.raw)"
        :disabled="uploading"
        accept="image/*,video/*"
      >
        <div style="padding: 40px 0">
          <el-icon :size="60" color="#409eff"><UploadFilled /></el-icon>
          <p style="margin: 16px 0 8px; font-size: 16px">
            拖拽文件到此处或点击上传
          </p>
          <p style="color: #999; font-size: 12px">
            支持:
            {{ fileType === 'image' ? 'JPG, PNG, BMP, WebP' : 'MP4, AVI, MOV, MKV, FLV' }}
            | 最大:
            {{ fileType === 'image' ? '10MB' : '200MB' }}
          </p>
        </div>
      </el-upload>

      <el-progress
        v-if="uploading"
        :percentage="progress"
        style="margin-top: 20px"
      />
    </el-card>
  </div>
</template>
