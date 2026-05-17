<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getRecord, getViolations, generateAIReport, type AIReport, type RecordItem } from '../api/history'
import { createCaseFromRecord } from '../api/case'

const router = useRouter()

const route = useRoute()
const record = ref<RecordItem | null>(null)
const violations = ref<any[]>([])
const loading = ref(false)
const analyzing = ref(false)
const savingCase = ref(false)
const aiReport = ref<AIReport | null>(null)

const VIOLATION_LABELS: Record<string, string> = {
  warning_no_hardhat: '未戴安全帽',
  warning_no_safety_vest: '未穿反光背心',
  warning_close_to_machinery: '靠近作业机械',
  warning_close_to_vehicle: '靠近施工车辆',
  warning_people_in_controlled_area: '进入管控区',
  warning_people_in_utility_pole_controlled_area: '进入电线杆危险区',
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
    warning_no_safety_vest: 'low',
    warning_close_to_machinery: 'medium',
    warning_close_to_vehicle: 'medium',
    warning_people_in_controlled_area: 'high',
    warning_people_in_utility_pole_controlled_area: 'high',
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
  try {
    const { data } = await generateAIReport(id)
    aiReport.value = data
    ElMessage.success('AI分析完成')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'AI分析失败，请检查配置')
  } finally {
    analyzing.value = false
  }
}

function downloadAIReport() {
  if (!aiReport.value) return

  const content = generateReportText(aiReport.value)
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `AI分析报告_${aiReport.value.basic_info.file_name}_${aiReport.value.basic_info.report_id}.txt`
  link.click()
  URL.revokeObjectURL(url)
}

function generateReportText(report: AIReport): string {
  const lines: string[] = []

  lines.push('='.repeat(50))
  lines.push(report.report_title)
  lines.push('='.repeat(50))
  lines.push('')

  lines.push('一、基本信息')
  lines.push('-'.repeat(30))
  lines.push(`报告编号: ${report.basic_info.report_id}`)
  lines.push(`生成时间: ${report.basic_info.report_time}`)
  lines.push(`文件名: ${report.basic_info.file_name}`)
  lines.push(`检测类型: ${report.basic_info.detection_type === 'image' ? '图片' : '视频'}`)
  lines.push(`检测时长: ${report.basic_info.detection_duration}秒`)
  lines.push(`检测目标: ${report.basic_info.total_targets}个`)
  lines.push('')

  lines.push('二、检测概况')
  lines.push('-'.repeat(30))
  lines.push(`违规总数: ${report.summary.total_violations}`)
  lines.push(`风险等级: ${severityLabels[report.summary.risk_level] || report.summary.risk_level}`)
  lines.push(`违规率: ${report.summary.violation_rate}`)
  lines.push('')

  lines.push('三、违规详情')
  lines.push('-'.repeat(30))
  for (const v of report.violation_details) {
    lines.push(`[${v.type}] ${v.count}次 | 首次: ${v.first_time} | 严重程度: ${severityLabels[v.severity] || v.severity}`)
    lines.push(`  描述: ${v.description}`)
    lines.push(`  建议: ${v.suggestion}`)
    lines.push('')
  }

  lines.push('四、安全评估')
  lines.push('-'.repeat(30))
  lines.push(`PPE符合率: ${report.safety_assessment.ppe_compliance}`)
  lines.push(`距离符合率: ${report.safety_assessment.proximity_compliance}`)
  lines.push(`管控区符合率: ${report.safety_assessment.restricted_area_compliance}`)
  lines.push('')

  lines.push('五、总体建议')
  lines.push('-'.repeat(30))
  lines.push(report.overall_suggestion)
  lines.push('')

  lines.push('='.repeat(50))
  lines.push(report.expert_signature)
  lines.push('='.repeat(50))

  return lines.join('\n')
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
        <el-descriptions-item label="未穿反光背心（警告）">{{ record.v_no_safety_vest || 0 }}</el-descriptions-item>
        <el-descriptions-item label="靠近作业机械">{{ record.v_close_to_machinery || 0 }}</el-descriptions-item>
        <el-descriptions-item label="靠近施工车辆">{{ record.v_close_to_vehicle || 0 }}</el-descriptions-item>
        <el-descriptions-item label="进入管控区">{{ record.v_in_controlled_area || 0 }}</el-descriptions-item>
        <el-descriptions-item label="进入电线杆区域">{{ record.v_in_pole_area || 0 }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="aiReport" style="margin-bottom: 20px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>AI分析结果</span>
          <el-button type="primary" size="small" @click="downloadAIReport">
            下载报告
          </el-button>
        </div>
      </template>

      <el-descriptions :column="2" border style="margin-bottom: 20px">
        <el-descriptions-item label="报告编号">{{ aiReport.basic_info.report_id }}</el-descriptions-item>
        <el-descriptions-item label="风险等级">
          <el-tag :color="severityColors[aiReport.summary.risk_level]" style="color: white">
            {{ severityLabels[aiReport.summary.risk_level] }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="违规总数">{{ aiReport.summary.total_violations }}</el-descriptions-item>
        <el-descriptions-item label="违规率">{{ aiReport.summary.violation_rate }}</el-descriptions-item>
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
        <el-table-column prop="suggestion" label="整改建议" />
      </el-table>

      <el-divider>安全评估</el-divider>

      <el-descriptions :column="3" border>
        <el-descriptions-item label="PPE符合率">{{ aiReport.safety_assessment.ppe_compliance }}</el-descriptions-item>
        <el-descriptions-item label="距离符合率">{{ aiReport.safety_assessment.proximity_compliance }}</el-descriptions-item>
        <el-descriptions-item label="管控区符合率">{{ aiReport.safety_assessment.restricted_area_compliance }}</el-descriptions-item>
      </el-descriptions>

      <el-divider>总体建议</el-divider>

      <el-alert
        :title="aiReport.overall_suggestion"
        type="info"
        :closable="false"
      />

      <div style="text-align: right; margin-top: 20px; color: #999; font-size: 12px">
        {{ aiReport.expert_signature }}
      </div>
    </el-card>

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
            <img
              :src="v.screenshot_path"
              :alt="v.violation_type"
              style="width: 100%; height: auto; display: block; border-radius: 4px"
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