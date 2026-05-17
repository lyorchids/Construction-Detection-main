<script setup lang="ts">
import { ref, onMounted } from 'vue'
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
  warning_close_to_machinery: '靠近作业机械',
  warning_close_to_vehicle: '靠近施工车辆',
  warning_people_in_controlled_area: '进入管控区',
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
        <el-table-column label="未戴安全帽" width="100" align="center">
          <template #default="{ row }">
            {{ row.v_no_hardhat || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="未穿背心" width="100" align="center">
          <template #default="{ row }">
            {{ row.v_no_safety_vest || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="靠近机械" width="100" align="center">
          <template #default="{ row }">
            {{ row.v_close_to_machinery || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="靠近车辆" width="100" align="center">
          <template #default="{ row }">
            {{ row.v_close_to_vehicle || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="进入管控区" width="100" align="center">
          <template #default="{ row }">
            {{ row.v_in_controlled_area || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="进入杆区" width="100" align="center">
          <template #default="{ row }">
            {{ row.v_in_pole_area || 0 }}
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
  </div>
</template>
