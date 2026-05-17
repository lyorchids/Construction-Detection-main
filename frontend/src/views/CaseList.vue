<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCases, deleteCase, type CaseItem } from '../api/case'

const router = useRouter()
const cases = ref<CaseItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filterType = ref('')
const filterSeverity = ref('')
const keyword = ref('')

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

async function fetchCases() {
  loading.value = true
  try {
    const { data } = await getCases({
      page: page.value,
      page_size: pageSize.value,
      case_type: filterType.value || undefined,
      severity: filterSeverity.value || undefined,
      keyword: keyword.value || undefined,
    })
    cases.value = data.items
    total.value = data.total
  } catch {
    ElMessage.error('获取案例列表失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchCases()
}

function handlePageChange(p: number) {
  page.value = p
  fetchCases()
}

function viewDetail(id: number) {
  router.push(`/cases/${id}`)
}

function goCreate() {
  router.push('/cases/create')
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除此案例？', '确认删除', { type: 'warning' })
    await deleteCase(id)
    ElMessage.success('删除成功')
    fetchCases()
  } catch {
    // cancelled
  }
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchCases()
})
</script>

<template>
  <div style="padding: 20px">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px">
          <h3 style="margin: 0">历史案例库</h3>
          <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap">
            <el-input
              v-model="keyword"
              placeholder="搜索标题/描述"
              clearable
              style="width: 200px"
              @keyup.enter="handleSearch"
            />
            <el-select v-model="filterType" placeholder="案例类型" clearable style="width: 140px" @change="handleSearch">
              <el-option label="全部" value="" />
              <el-option label="未戴头盔" value="no_hardhat" />
              <el-option label="危险操作" value="dangerous_operation" />
              <el-option label="其他" value="other" />
            </el-select>
            <el-select v-model="filterSeverity" placeholder="严重程度" clearable style="width: 120px" @change="handleSearch">
              <el-option label="全部" value="" />
              <el-option label="低" value="low" />
              <el-option label="中" value="medium" />
              <el-option label="高" value="high" />
              <el-option label="紧急" value="critical" />
            </el-select>
            <el-button type="primary" @click="goCreate">新建案例</el-button>
          </div>
        </div>
      </template>

      <el-table :data="cases" v-loading="loading" stripe>
        <el-table-column prop="title" label="案例标题" min-width="180" />
        <el-table-column label="案例类型" width="120">
          <template #default="{ row }">
            <el-tag :color="TYPE_COLORS[row.case_type]" style="color: white">
              {{ CASE_TYPE_LABELS[row.case_type] || row.case_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="严重程度" width="100">
          <template #default="{ row }">
            <el-tag :color="SEVERITY_COLORS[row.severity]" style="color: white">
              {{ SEVERITY_LABELS[row.severity] || row.severity }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="关联记录" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.source_record_id" type="info" size="small">{{ row.source_record_id }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetail(row.id)">查看</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
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
