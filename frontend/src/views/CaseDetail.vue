<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getCase, deleteCase, updateCase, type CaseItem } from '../api/case'

const route = useRoute()
const router = useRouter()
const caseItem = ref<CaseItem | null>(null)
const loading = ref(false)
const editing = ref(false)

const editForm = ref({
  title: '',
  case_type: '',
  severity: '',
  scene_description: '',
  recommended_actions: '',
  process_info: '',
})

const CASE_TYPE_LABELS: Record<string, string> = {
  no_hardhat: '未戴头盔',
  dangerous_operation: '危险操作',
  other: '其他',
}

const SEVERITY_LABELS: Record<string, string> = {
  low: '低',
  medium: '中',
  high: '高',
  critical: '紧急',
}

const SEVERITY_COLORS: Record<string, string> = {
  low: '#67c23a',
  medium: '#e6a23c',
  high: '#f56c6c',
  critical: '#909399',
}

const TYPE_COLORS: Record<string, string> = {
  no_hardhat: '#F44336',
  dangerous_operation: '#FF9800',
  other: '#9E9E9E',
}

async function fetchCase() {
  const id = Number(route.params.id)
  loading.value = true
  try {
    const { data } = await getCase(id)
    caseItem.value = data
  } catch {
    ElMessage.error('获取案例详情失败')
  } finally {
    loading.value = false
  }
}

function startEdit() {
  if (!caseItem.value) return
  editForm.value = {
    title: caseItem.value.title,
    case_type: caseItem.value.case_type,
    severity: caseItem.value.severity,
    scene_description: caseItem.value.scene_description,
    recommended_actions: caseItem.value.recommended_actions,
    process_info: caseItem.value.process_info,
  }
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function saveEdit() {
  if (!caseItem.value) return
  try {
    const { data } = await updateCase(caseItem.value.id, editForm.value)
    caseItem.value = data
    editing.value = false
    ElMessage.success('更新成功')
  } catch {
    ElMessage.error('更新失败')
  }
}

async function handleDelete() {
  if (!caseItem.value) return
  try {
    await ElMessageBox.confirm('确定删除此案例？', '确认删除', { type: 'warning' })
    await deleteCase(caseItem.value.id)
    ElMessage.success('删除成功')
    router.push('/cases')
  } catch {
    // cancelled
  }
}

function goToRecord(id: number) {
  router.push(`/detail/${id}`)
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}

function formatActions(text: string): string[] {
  return text.split('\n').filter((l) => l.trim())
}

onMounted(() => {
  fetchCase()
})
</script>

<template>
  <div style="padding: 20px" v-loading="loading">
    <el-card v-if="caseItem">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div style="display: flex; align-items: center; gap: 12px">
            <el-button :icon="ArrowLeft" @click="router.back()" text>返回</el-button>
            <h3 style="margin: 0">{{ caseItem.title }}</h3>
            <el-tag :color="TYPE_COLORS[caseItem.case_type]" style="color: white">
              {{ CASE_TYPE_LABELS[caseItem.case_type] || caseItem.case_type }}
            </el-tag>
            <el-tag :color="SEVERITY_COLORS[caseItem.severity]" style="color: white">
              {{ SEVERITY_LABELS[caseItem.severity] || caseItem.severity }}
            </el-tag>
          </div>
          <div>
            <el-button v-if="!editing" type="primary" size="small" @click="startEdit">编辑</el-button>
            <el-button v-if="!editing" type="danger" size="small" @click="handleDelete">删除</el-button>
          </div>
        </div>
      </template>

      <template v-if="!editing">
        <el-descriptions :column="1" border style="margin-bottom: 20px">
          <el-descriptions-item label="创建时间">{{ formatTime(caseItem.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatTime(caseItem.updated_at) }}</el-descriptions-item>
          <el-descriptions-item label="关联检测记录">
            <el-button v-if="caseItem.source_record_id" type="primary" link @click="goToRecord(caseItem.source_record_id!)">
              {{ caseItem.source_filename || `记录 #${caseItem.source_record_id}` }}
            </el-button>
            <span v-else>无</span>
          </el-descriptions-item>
        </el-descriptions>

        <el-divider>场景描述</el-divider>
        <p style="white-space: pre-wrap; line-height: 1.8; color: #333">{{ caseItem.scene_description }}</p>

        <el-divider>应对措施</el-divider>
        <el-alert
          v-for="(action, i) in formatActions(caseItem.recommended_actions)"
          :key="i"
          :title="action"
          type="warning"
          :closable="false"
          style="margin-bottom: 8px"
        />

        <el-divider>处理信息</el-divider>
        <p style="white-space: pre-wrap; line-height: 1.8; color: #333">{{ caseItem.process_info }}</p>

        <el-divider v-if="caseItem.images && caseItem.images.length > 0">关联图片</el-divider>
        <el-row :gutter="16" v-if="caseItem.images && caseItem.images.length > 0">
          <el-col v-for="(img, i) in caseItem.images" :key="i" :span="6">
            <el-card :body-style="{ padding: '8px' }">
              <img :src="img" :alt="`图片 ${i + 1}`" style="width: 100%; height: auto; display: block; border-radius: 4px" />
            </el-card>
          </el-col>
        </el-row>
      </template>

      <template v-else>
        <el-form :model="editForm" label-width="120px">
          <el-form-item label="案例标题">
            <el-input v-model="editForm.title" />
          </el-form-item>
          <el-form-item label="案例类型">
            <el-select v-model="editForm.case_type">
              <el-option label="未戴头盔" value="no_hardhat" />
              <el-option label="危险操作" value="dangerous_operation" />
              <el-option label="其他" value="other" />
            </el-select>
          </el-form-item>
          <el-form-item label="严重程度">
            <el-select v-model="editForm.severity">
              <el-option label="低" value="low" />
              <el-option label="中" value="medium" />
              <el-option label="高" value="high" />
              <el-option label="紧急" value="critical" />
            </el-select>
          </el-form-item>
          <el-form-item label="场景描述">
            <el-input v-model="editForm.scene_description" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="应对措施">
            <el-input v-model="editForm.recommended_actions" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="处理信息">
            <el-input v-model="editForm.process_info" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="saveEdit">保存</el-button>
            <el-button @click="cancelEdit">取消</el-button>
          </el-form-item>
        </el-form>
      </template>
    </el-card>

    <el-empty v-else-if="!loading" description="案例不存在" />
  </div>
</template>
