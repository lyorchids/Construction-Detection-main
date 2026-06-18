<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getRecord, getViolations, generateAIReport, downloadAIReportWord, type AIReport, type RecordItem } from '../api/history'
import { createCaseFromRecord } from '../api/case'

const router = useRouter()

const route = useRoute()
const record = ref<RecordItem | null>(null)
const violations = ref<any[]>([])
const loading = ref(false)
const analyzing = ref(false)
const savingCase = ref(false)
const aiReport = ref<AIReport | null>(null)
const dialogVisible = ref(false)
const downloading = ref(false)
const loadingVisible = ref(false)
const loadingText = ref('')

const VIOLATION_LABELS: Record<string, string> = {
  warning_no_hardhat: '未戴安全帽',
  warning_no_mask: '未佩戴口罩',
  warning_no_safety_vest: '未穿反光背心',
  warning_people_in_controlled_area: '进入管控区',
  warning_people_in_utility_pole_controlled_area: '进入电线杆危险区',
  warning_fire: '检测到火焰',
  warning_smoke: '检测到烟雾',
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

function violationLevel(vtype: string): string {
  const levels: Record<string, string> = {
    warning_no_hardhat: 'high',
    warning_no_mask: 'low',
    warning_no_safety_vest: 'low',
    warning_people_in_controlled_area: 'high',
    warning_people_in_utility_pole_controlled_area: 'high',
    warning_fire: 'high',
    warning_smoke: 'high',
  }
  return levels[vtype] || 'medium'
}

function getSeverityColor(vtype: string): string {
  const level = violationLevel(vtype)
  return level === 'high' ? '#f56c6c' : level === 'medium' ? '#e6a23c' : '#67c23a'
}

onMounted(async () => {
  const id = Number(route.params.id)
  loading.value = true
  try {
    const [recordRes, violationsRes] = await Promise.all([
      getRecord(id),
      getViolations(id),
    ])
    record.value = recordRes.data
    violations.value = violationsRes.data
  } catch {
    ElMessage.error('获取详情失败')
  } finally {
    loading.value = false
  }
})

async function saveAsCase() {
  if (!record.value) return
  const id = Number(route.params.id)
  savingCase.value = true
  try {
    const { data } = await createCaseFromRecord(id)
    ElMessage.success('已保存为案例')
    router.push(`/cases/${data.id}`)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存为案例失败')
  } finally {
    savingCase.value = false
  }
}

async function handleAIAnalysis() {
  if (!record.value || record.value.violation_count === 0) {
    ElMessage.warning('该记录没有违规，无法生成AI分析报告')
    return
  }

  const id = Number(route.params.id)
  analyzing.value = true
  loadingText.value = '正在生成AI分析报告，请稍候...'
  loadingVisible.value = true
  try {
    const { data } = await generateAIReport(id)
    aiReport.value = data
    loadingVisible.value = false
    dialogVisible.value = true
    ElMessage.success('AI分析完成')
  } catch (error: any) {
    loadingVisible.value = false
    ElMessage.error(error.response?.data?.detail || 'AI分析失败，请检查配置')
  } finally {
    analyzing.value = false
  }
}

async function downloadAIReport() {
  if (!aiReport.value) return
  downloading.value = true
  loadingText.value = '正在生成下载文件，请稍候...'
  loadingVisible.value = true
  try {
    const recordId = route.params.id
    const res = await downloadAIReportWord(Number(recordId))
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `AI分析报告_${aiReport.value.basic_info.file_name}_${aiReport.value.basic_info.report_id}.docx`
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

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}
</script>

<template>
  <div style="padding: 20px" v-loading="loading">
    <el-card v-if="record" style="margin-bottom: 20px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div style="display: flex; align-items: center; gap: 12px">
            <el-button :icon="ArrowLeft" @click="router.back()" text>返回</el-button>
            <h3 style="margin: 0">检测详情</h3>
          </div>
          <el-button
            type="warning"
            :loading="savingCase"
            :disabled="!record || record.violation_count === 0"
            @click="saveAsCase"
          >
            {{ record && record.violation_count > 0 ? '保存为案例' : '无违规' }}
          </el-button>
          <el-button
            type="success"
            :loading="analyzing"
            :disabled="!record || record.violation_count === 0"
            @click="handleAIAnalysis"
          >
            {{ record && record.violation_count > 0 ? 'AI分析报告' : '无违规' }}
          </el-button>
        </div>
      </template>
        <el-descriptions :column="3" border>
        <el-descriptions-item label="文件名">{{ record.filename }}</el-descriptions-item>
        <el-descriptions-item label="类型">
          <el-tag :type="record.file_type === 'image' ? 'success' : 'primary'" size="small">
            {{ record.file_type === 'image' ? '图片' : '视频' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="检测时间">{{ formatTime(record.detect_time) }}</el-descriptions-item>
        <el-descriptions-item label="目标数">{{ record.total_objects }}</el-descriptions-item>
        <el-descriptions-item label="违规数">
          <el-tag v-if="record.violation_count > 0" type="danger">{{ record.violation_count }}</el-tag>
          <span v-else>0</span>
        </el-descriptions-item>
        <el-descriptions-item label="时长">{{ record.duration.toFixed(1) }}s</el-descriptions-item>
        <el-descriptions-item label="未戴安全帽">{{ record.v_no_hardhat || 0 }}</el-descriptions-item>
        <el-descriptions-item label="未戴口罩">{{ record.v_no_mask || 0 }}</el-descriptions-item>
        <el-descriptions-item label="未穿反光背心（警告）">{{ record.v_no_safety_vest || 0 }}</el-descriptions-item>
        <el-descriptions-item label="进入管控区">{{ record.v_in_controlled_area || 0 }}</el-descriptions-item>
        <el-descriptions-item label="进入电线杆区域">{{ record.v_in_pole_area || 0 }}</el-descriptions-item>
        <el-descriptions-item label="火焰">{{ record.v_fire || 0 }}</el-descriptions-item>
        <el-descriptions-item label="烟雾">{{ record.v_smoke || 0 }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-dialog v-model="loadingVisible" width="300px" :close-on-click-modal="false" :show-close="false" center>
      <div style="text-align: center; padding: 28px 12px">
        <div style="margin-bottom: 20px; display: inline-block; width: 36px; height: 36px; border: 3px solid #e0e0e0; border-top-color: #409eff; border-radius: 50%; animation: spin 0.8s linear infinite" />
        <p style="margin: 0; font-size: 15px; color: #606266">{{ loadingText }}</p>
      </div>
    </el-dialog>

    <el-dialog v-model="dialogVisible" title="AI分析报告" width="700px" :close-on-click-modal="false">
      <template v-if="aiReport">
        <el-descriptions :column="2" border style="margin-bottom: 20px">
          <el-descriptions-item label="报告编号">{{ aiReport.basic_info.report_id }}</el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag :color="severityColors[aiReport.summary.risk_level]" style="color: white">
              {{ severityLabels[aiReport.summary.risk_level] }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="违规总数">{{ aiReport.summary.total_violations }}</el-descriptions-item>
        </el-descriptions>

        <el-divider>违规详情</el-divider>

        <el-table :data="aiReport.violation_details" v-if="aiReport.violation_details.length > 0">
          <el-table-column prop="type" label="违规类型" />
          <el-table-column prop="count" label="次数" width="80" />
          <el-table-column prop="first_time" label="首次发现" width="100" />
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
        <el-button @click="dialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="downloading" @click="downloadAIReport">下载报告</el-button>
      </template>
    </el-dialog>

    <el-card v-if="violations.length > 0">
      <template #header>
        <h3 style="margin: 0">违规截图 ({{ violations.length }})</h3>
      </template>
      <el-row :gutter="16">
        <el-col
          v-for="v in violations"
          :key="v.id"
          :xs="12"
          :sm="8"
          :md="6"
          :lg="4"
          style="margin-bottom: 16px"
        >
          <el-card :body-style="{ padding: '8px', border: `2px solid ${getSeverityColor(v.violation_type)}` }">
            <el-image
              :src="v.screenshot_path"
              :alt="v.violation_type"
              :preview-src-list="[v.screenshot_path]"
              fit="contain"
              style="width: 100%; height: auto; display: block; border-radius: 4px; cursor: zoom-in"
            />
            <div style="padding: 8px 4px 0">
              <p :style="{ margin: '0', fontSize: '12px', color: getSeverityColor(v.violation_type) }">
                {{ VIOLATION_LABELS[v.violation_type] || v.violation_type }}
              </p>
              <p style="margin: 4px 0 0; font-size: 11px; color: #999">
                帧 {{ v.frame_number }} | {{ v.timestamp.toFixed(1) }}s
              </p>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <el-empty v-else-if="!loading" description="暂无违规记录" />
  </div>
</template>

<style scoped>
@keyframes spin {
  to { transform: rotate(360deg) }
}
</style>