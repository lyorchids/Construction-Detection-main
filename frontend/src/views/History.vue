<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Delete } from '@element-plus/icons-vue'
import { getRecords, deleteRecord, generateAIReportByDate, downloadAIReportWordByDate, type RecordItem, type AIReport } from '../api/history'

const router = useRouter()
const records = ref<RecordItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const fileTypeFilter = ref('')

const dateRange = ref<[Date, Date] | null>(null)

const VIOLATION_LABELS: Record<string, string> = {
  warning_no_hardhat: '未戴安全帽',
  warning_no_mask: '未佩戴口罩',
  warning_no_safety_vest: '未穿反光背心',
  warning_people_in_controlled_area: '进入锥形桶管控区',
  detect_machinery_close_to_pole: '机械靠近电线杆',
  warning_fire: '检测到火焰',
  warning_smoke: '检测到烟雾',
}

const vtypeColor: Record<string, string> = {
  warning_no_hardhat: '#F44336',
  warning_no_mask: '#FF9800',
  warning_no_safety_vest: '#FF9800',
  warning_people_in_controlled_area: '#E91E63',
  detect_machinery_close_to_pole: '#9C27B0',
  warning_fire: '#FF5722',
  warning_smoke: '#9E9E9E',
}

const severityColors: Record<string, string> = {
  low: '#67c23a',
  medium: '#e6a23c',
  high: '#f56c6c',
}

const severityLabels: Record<string, string> = {
  low: '低危',
  medium: '中危',
  high: '高危',
}

const trendLabels: Record<string, string> = {
  increasing: '↑ 上升',
  decreasing: '↓ 下降',
  stable: '→ 平稳',
}

const trendColors: Record<string, string> = {
  increasing: '#f56c6c',
  decreasing: '#67c23a',
  stable: '#909399',
}

const dialogVisible = ref(false)
const dialogRecord = ref<RecordItem | null>(null)
const aiDialogVisible = ref(false)
const aiReport = ref<AIReport | null>(null)
const analyzing = ref(false)
const downloading = ref(false)
const loadingVisible = ref(false)
const loadingText = ref('')

const violationFields: { key: string; label: string; color: string }[] = [
  { key: 'warning_no_hardhat', label: '未戴安全帽', color: '#F44336' },
  { key: 'warning_no_mask', label: '未佩戴口罩', color: '#FF9800' },
  { key: 'warning_no_safety_vest', label: '未穿反光背心', color: '#FF9800' },
  { key: 'warning_people_in_controlled_area', label: '进入锥形桶管控区', color: '#E91E63' },
  { key: 'detect_machinery_close_to_pole', label: '机械靠近电线杆', color: '#9C27B0' },
  { key: 'warning_fire', label: '检测到火焰', color: '#FF5722' },
  { key: 'warning_smoke', label: '检测到烟雾', color: '#9E9E9E' },
]

const activeViolations = computed(() => {
  const r = dialogRecord.value
  if (!r) return []
  return violationFields
    .filter(f => (r.violations[f.key] ?? 0) > 0)
    .map(f => ({ label: f.label, count: r.violations[f.key] ?? 0, color: f.color }))
})

const dailyOverview = computed(() => {
  const ov = aiReport.value?.daily_overview
  if (!ov || !ov.dates || ov.dates.length === 0) return null
  return ov.dates.map(dateStr => {
    const day = ov.daily_counts[dateStr] || { total: 0 }
    const types = Object.entries(day)
      .filter(([k]) => k !== 'total')
      .sort((a, b) => Number(b[1]) - Number(a[1]))
      .map(([k, v]) => ({ type: VIOLATION_LABELS[k] || k, count: v, color: vtypeColor[k] || '#999' }))
    return { date: dateStr, total: day.total, types, trend: ov.trend }
  })
})

function showViolations(row: RecordItem) {
  dialogRecord.value = row
  dialogVisible.value = true
}

async function fetchRecords() {
  loading.value = true
  try {
    const params: any = {
      page: page.value,
      page_size: pageSize.value,
      file_type: fileTypeFilter.value || undefined,
    }
    if (dateRange.value && dateRange.value[0] && dateRange.value[1]) {
      params.start_date = formatDate(dateRange.value[0])
      params.end_date = formatDate(dateRange.value[1])
    }
    const { data } = await getRecords(params)
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

function formatDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function formatDuration(sec: number): string {
  if (sec === 0) return '-'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}分${s}秒`
}

function handleSearch() {
  page.value = 1
  fetchRecords()
}

function handleClear() {
  dateRange.value = null
  page.value = 1
  fetchRecords()
}

async function handleDateAIAnalysis() {
  if (!dateRange.value || !dateRange.value[0] || !dateRange.value[1]) {
    ElMessage.warning('请选择日期范围')
    return
  }
  const [start, end] = dateRange.value

  const startStr = formatDate(start)
  const endStr = formatDate(end)

  analyzing.value = true
  loadingText.value = '正在生成时段AI分析报告，请稍候...'
  loadingVisible.value = true
  try {
    const { data } = await generateAIReportByDate(startStr, endStr)
    aiReport.value = data
    loadingVisible.value = false
    aiDialogVisible.value = true
    ElMessage.success('AI分析完成')
  } catch (error: any) {
    loadingVisible.value = false
    const msg = error.response?.data?.detail || 'AI分析失败，请检查配置'
    ElMessage.error(msg)
  } finally {
    analyzing.value = false
  }
}

async function downloadDateAIReport() {
  if (!aiReport.value || !dateRange.value) return
  const [start, end] = dateRange.value
  const startStr = formatDate(start)
  const endStr = formatDate(end)

  downloading.value = true
  loadingText.value = '正在生成下载文件，请稍候...'
  loadingVisible.value = true
  try {
    const res = await downloadAIReportWordByDate(startStr, endStr)
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `AI分析报告_${startStr}_${endStr}.docx`
    link.click()
    URL.revokeObjectURL(url)
    loadingVisible.value = false
    ElMessage.success('下载完成')
  } catch {
    loadingVisible.value = false
    ElMessage.error('下载报告失败')
  } finally {
    downloading.value = false
  }
}

onMounted(() => {
  fetchRecords()
})
</script>

<template>
  <div style="padding: 20px">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px">
          <h3 style="margin: 0">检测历史记录</h3>
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width: 260px"
              clearable
            />
            <el-button type="primary" :icon="Search" @click="handleSearch">
              搜索
            </el-button>
            <el-button :icon="Delete" @click="handleClear">
              清空
            </el-button>
            <el-button
              type="warning"
              :loading="analyzing"
              @click="handleDateAIAnalysis"
            >
              AI报告
            </el-button>
            <el-select
              v-model="fileTypeFilter"
              placeholder="文件类型"
              clearable
              style="width: 130px"
              @change="handleFilterChange"
            >
              <el-option label="全部" value="" />
              <el-option label="图片" value="image" />
              <el-option label="视频" value="video" />
            </el-select>
          </div>
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

    <el-dialog v-model="loadingVisible" width="300px" :close-on-click-modal="false" :show-close="false" center>
      <div style="text-align: center; padding: 28px 12px">
        <div style="margin-bottom: 20px; display: inline-block; width: 36px; height: 36px; border: 3px solid #e0e0e0; border-top-color: #409eff; border-radius: 50%; animation: spin 0.8s linear infinite" />
        <p style="margin: 0; font-size: 15px; color: #606266">{{ loadingText }}</p>
      </div>
    </el-dialog>

    <el-dialog v-model="aiDialogVisible" title="AI分析报告（时段分析）" width="750px" :close-on-click-modal="false">
      <template v-if="aiReport">
        <el-descriptions :column="2" border style="margin-bottom: 20px">
          <el-descriptions-item v-if="aiReport.basic_info.analysis_period" label="分析时段">
            {{ aiReport.basic_info.analysis_period }}
          </el-descriptions-item>
          <el-descriptions-item v-if="aiReport.basic_info.total_records != null" label="涉及记录">
            {{ aiReport.basic_info.total_records }} 条
          </el-descriptions-item>
          <el-descriptions-item label="报告编号">{{ aiReport.basic_info.report_id }}</el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag :color="severityColors[aiReport.summary.risk_level]" style="color: white">
              {{ severityLabels[aiReport.summary.risk_level] }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="违规总数">{{ aiReport.summary.total_violations }}</el-descriptions-item>
        </el-descriptions>

        <el-divider v-if="dailyOverview && dailyOverview.length > 0">每日违规概览</el-divider>

        <template v-if="dailyOverview && dailyOverview.length > 0">
          <el-table :data="dailyOverview" stripe>
            <el-table-column prop="date" label="日期" width="120" />
            <el-table-column prop="total" label="违规数" width="80" />
            <el-table-column label="主要违规类型">
              <template #default="{ row }">
                <span v-for="(t, i) in row.types.slice(0, 3)" :key="i" style="margin-right: 8px">
                  <span :style="{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: t.color, marginRight: '4px' }"></span>
                  {{ t.type }} {{ t.count }}
                </span>
                <span v-if="row.types.length > 3" style="color: #999">等{{ row.types.length }}类</span>
              </template>
            </el-table-column>
            <el-table-column label="趋势" width="100">
              <template #default="{ row }">
                <span :style="{ color: trendColors[row.trend] }">{{ trendLabels[row.trend] }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div style="margin-top: 10px; font-size: 12px; color: #999; text-align: right">
            趋势说明：将最早一天与最晚一天的违规数比较得出的变化方向
          </div>
        </template>

        <el-divider>违规详情</el-divider>

        <el-table :data="aiReport.violation_details" v-if="aiReport.violation_details.length > 0">
          <el-table-column prop="type" label="违规类型" />
          <el-table-column prop="count" label="次数" width="80" />
          <el-table-column prop="first_time" label="首次出现" width="110" />
          <el-table-column label="严重程度" width="100">
            <template #default="{ row }">
              <el-tag :color="severityColors[row.severity]" style="color: white">
                {{ severityLabels[row.severity] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" />
        </el-table>

        <el-divider>安全评估</el-divider>

        <div style="margin-bottom: 12px">
          <strong>综合评价</strong>
          <p style="margin: 8px 0; line-height: 1.6">{{ aiReport.safety_assessment.overall_evaluation }}</p>
        </div>
        <div style="margin-bottom: 12px">
          <strong>风险因素</strong>
          <ul style="margin: 8px 0; padding-left: 20px">
            <li v-for="(rf, i) in aiReport.safety_assessment.risk_factors" :key="i">{{ rf }}</li>
          </ul>
        </div>
        <div>
          <strong>主要发现</strong>
          <p style="margin: 8px 0; line-height: 1.6">{{ aiReport.safety_assessment.key_findings }}</p>
        </div>

        <el-divider>总体建议</el-divider>

        <el-alert
          :title="aiReport.overall_suggestion"
          type="info"
          :closable="false"
        />

        <div style="text-align: right; margin-top: 20px; color: #999; font-size: 12px">
          {{ aiReport.expert_signature }}
        </div>
      </template>

      <template #footer>
        <el-button @click="aiDialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="downloading" @click="downloadDateAIReport">下载报告</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
@keyframes spin {
  to { transform: rotate(360deg) }
}
</style>
