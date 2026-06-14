<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProfiles, deleteProfile, createProfile, updateProfile } from '../api/detection_profile'
import type { DetectionProfile } from '../api/detection_profile'
import DetectionProfileDialog from '../components/DetectionProfileDialog.vue'

const profiles = ref<DetectionProfile[]>([])
const loading = ref(false)
const activeTab = ref('all')
const dialogVisible = ref(false)
const editingProfile = ref<any>(null)

const filteredProfiles = computed(() => {
  if (activeTab.value === 'all') return profiles.value
  return profiles.value.filter(p => p.type === activeTab.value)
})

onMounted(() => loadProfiles())

async function loadProfiles() {
  loading.value = true
  try {
    const { data } = await getProfiles()
    profiles.value = data
  } catch {
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

function getModelsSummary(config: any): string {
  const models = config?.models || {}
  const parts: string[] = []
  if (models.ppe?.enabled) parts.push('PPE')
  if (models.fire?.enabled) parts.push('Fire')
  return parts.join(' + ') || '无'
}

function openCreate() {
  editingProfile.value = null
  dialogVisible.value = true
}

function openEdit(profile: DetectionProfile) {
  editingProfile.value = profile
  dialogVisible.value = true
}

async function handleSave(data: any) {
  try {
    if (data.id) {
      await updateProfile(data.id, { name: data.name, description: data.description, config: data.config })
      ElMessage.success('配置已更新')
    } else {
      await createProfile({ name: data.name, type: data.type, description: data.description, config: data.config })
      ElMessage.success('配置已创建')
    }
    await loadProfiles()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

async function handleDelete(profile: DetectionProfile) {
  try {
    await ElMessageBox.confirm(`确定删除配置 "${profile.name}"？`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteProfile(profile.id)
    ElMessage.success('配置已删除')
    await loadProfiles()
  } catch {
    // cancelled
  }
}
</script>

<template>
  <div style="padding: 20px">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 600">检测配置管理</span>
          <el-button type="primary" @click="openCreate">+ 新建配置</el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="全部" name="all" />
        <el-tab-pane label="图片检测" name="image" />
        <el-tab-pane label="视频检测" name="video" />
      </el-tabs>

      <el-table :data="filteredProfiles" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="row.type === 'image' ? 'primary' : 'success'" size="small">
              {{ row.type === 'image' ? '图片检测' : '视频检测' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="模型" width="120">
          <template #default="{ row }">
            {{ getModelsSummary(row.config) }}
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="视频参数" width="160">
          <template #default="{ row }">
            <template v-if="row.type === 'video' && row.config">
              <span style="font-size: 12px; color: #666">
                间隔: {{ row.config.frame_interval || 1 }}帧
                <template v-if="row.config.save_screenshots"> | 截图</template>
              </span>
            </template>
            <span v-else style="color: #ccc">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="170">
          <template #default="{ row }">
            {{ new Date(row.updated_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <DetectionProfileDialog
      v-model="dialogVisible"
      :profile="editingProfile"
      :profile-type="editingProfile?.type || 'image'"
      @save="handleSave"
    />
  </div>
</template>
