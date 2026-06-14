<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getRecords, deleteRecord, type RecordItem } from '../api/history'

const router = useRouter()
const records = ref<RecordItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const fileTypeFilter = ref('')

const VIOLATION_LABELS: Record<string, string> = {
  warning_no_hardhat: '未戴安全帽',
  warning_no_mask: '未佩戴口罩',
  warning_no_safety_vest: '未穿反光背心',
  warning_close_to_machinery: '靠近作业机械',
  warning_close_to_vehicle: '靠近施工车辆',
  warning_people_in_controlled_area: '进入锥形桶管控区',
  warning_people_in_utility_pole_controlled_area: '进入电线杆管控区',
  warning_fire: '检测到火焰',
  warning_smoke: '检测到烟雾',
}

const dialogVisible = ref(false)
const dialogRecord = ref<RecordItem | null>(null)

const violationFields: { key: keyof RecordItem; label: string; color: string }[] = [
  { key: 'v_no_hardhat', label: '未戴安全帽', color: '#F44336' },
  { key: 'v_no_safety_vest', label: '未穿反光背心', color: '#FF9800' },
  { key: 'v_close_to_machinery', label: '靠近作业机械', color: '#FF5722' },
  { key: 'v_close_to_vehicle', label: '靠近施工车辆', color: '#FFC107' },
  { key: 'v_in_controlled_area', label: '进入锥形桶管控区', color: '#E91E63' },
  { key: 'v_in_pole_area', label: '进入电线杆管控区', color: '#9C27B0' },
]

const activeViolations = computed(() => {
  const r = dialogRecord.value
  if (!r) return []
  return violationFields
    .filter(f => (r[f.key] ?? 0) > 0)
    .map(f => ({ label: f.label, count: r[f.key] ?? 0, color: f.color }))
})

function showViolations(row: RecordItem) {
  dialogRecord.value = row
  dialogVisible.value = true
}

async function fetchRecords() {
  loading.value = true
  try {
    const { data } = await getRecords({
      page: page.value,
      page_size: pageSize.value,
      file_type: fileTypeFilter.value || undefined,
    })
    records.value = data.items
    total.value = data.total
  } catch (error: any) {
    ElMessage.error('获取记录失败')
  } finally {
    loading.value = false
  }
}

function handlePageChange(p: number) {
  page.value = p
  fetchRecords()
}

function handleFilterChange() {
  page.value = 1
  fetchRecords()
}

function viewDetail(id: number) {
  router.push(`/detail/${id}`)
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除此记录及其关联数据？', '确认删除', {
      type: 'warning',
    })
    await deleteRecord(id)
    ElMessage.success('删除成功')
    fetchRecords()
  } catch {
    // cancelled
  }
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}

function formatDuration(sec: number): string {
  if (sec === 0) return '-'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}分${s}秒`
}

onMounted(() => {
  fetchRecords()
})
</script>

<template>
  <div style="padding: 20px">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <h3 style="margin: 0">检测历史记录</h3>
          <el-select
            v-model="fileTypeFilter"
            placeholder="文件类型"
            clearable
            style="width: 150px"
            @change="handleFilterChange"
          >
            <el-option label="全部" value="" />
            <el-option label="图片" value="image" />
            <el-option label="视频" value="video" />
          </el-select>
        </div>
      </template>

      <el-table :data="records" v-loading="loading" stripe>
        <el-table-column prop="filename" label="文件名" min-width="150" />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.file_type === 'image' ? 'success' : 'primary'" size="small">
              {{ row.file_type === 'image' ? '图片' : '视频' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="检测时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.detect_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_objects" label="目标数" width="80" />
        <el-table-column label="违规数" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.violation_count > 0" type="danger" size="small">
              {{ row.violation_count }}
            </el-tag>
            <span v-else>0</span>
          </template>
        </el-table-column>
        <el-table-column label="违规" width="100" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="showViolations(row)">
              查看违规
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="时长" width="100">
          <template #default="{ row }">
            {{ formatDuration(row.duration) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetail(row.id)">
              查看
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 20px; justify-content: center"
        @current-change="handlePageChange"
      />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      title="违规明细"
      width="500px"
      :close-on-click-modal="false"
    >
      <template v-if="dialogRecord">
        <div style="margin-bottom: 12px; font-size: 13px; color: #666">
          文件: {{ dialogRecord.filename }}
        </div>
        <el-table :data="activeViolations" stripe>
          <el-table-column label="违规类型" min-width="180">
            <template #default="{ row }">
              <span :style="{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: row.color, marginRight: '8px' }"></span>
              {{ row.label }}
            </template>
          </el-table-column>
          <el-table-column label="次数" width="80" align="center">
            <template #default="{ row }">
              <el-tag type="danger" size="small">{{ row.count }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="activeViolations.length === 0" style="text-align: center; color: #999; padding: 20px">
          无违规记录
        </div>
      </template>
    </el-dialog>
  </div>
</template>
