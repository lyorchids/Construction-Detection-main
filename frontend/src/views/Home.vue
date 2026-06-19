<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { getStats } from '../api/history'

const todayCount = ref(0)
const todayViolations = ref(0)
const totalCount = ref(0)
const totalViolations = ref(0)
const loading = ref(false)

const dynamicViolations = ref<{ label: string; count: number }[]>([])

const pieChartRef = ref<HTMLDivElement | null>(null)
const lineChartRef = ref<HTMLDivElement | null>(null)
let pieChart: echarts.ECharts | null = null
let lineChart: echarts.ECharts | null = null

const VIOLATION_LABELS: Record<string, string> = {
  warning_no_hardhat: '未戴安全帽',
  warning_no_mask: '未佩戴口罩',
  warning_no_safety_vest: '未穿反光背心',
  warning_people_in_controlled_area: '进入管控区',
  detect_machinery_close_to_pole: '机械靠近电线杆',
  warning_fire: '检测到火焰',
  warning_smoke: '检测到烟雾',
}

async function fetchStats() {
  loading.value = true
  try {
    const { data } = await getStats()
    totalCount.value = data.total_records
    totalViolations.value = data.total_violations
    todayCount.value = data.today_records
    todayViolations.value = data.today_violations

    if (data.violation_by_type) {
      const sorted = Object.entries(data.violation_by_type)
        .filter(([, count]) => count > 0)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 6)
      dynamicViolations.value = sorted.map(([type, count]) => ({
        label: VIOLATION_LABELS[type] || type,
        count,
      }))
    }

    renderPieChart(data.violation_by_type)
    renderLineChart(data.last_7_days)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载数据失败')
  } finally {
    loading.value = false
  }
}

function renderPieChart(violationByType: Record<string, number>) {
  if (!pieChartRef.value) return

  const chartData = Object.entries(violationByType).map(([type, count]) => ({
    name: VIOLATION_LABELS[type] || type,
    value: count,
  }))

  if (chartData.length === 0) {
    chartData.push({ name: '暂无数据', value: 0 })
  }

  pieChart = echarts.init(pieChartRef.value)
  pieChart.setOption({
    title: { text: '违规类型分布', left: 'center' },
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        data: chartData,
        label: { show: true, formatter: '{b}: {c}次' },
      },
    ],
  })
}

function renderLineChart(last7Days: { date: string; count: number }[]) {
  if (!lineChartRef.value) return

  lineChart = echarts.init(lineChartRef.value)
  lineChart.setOption({
    title: { text: '近7天检测趋势', left: 'center' },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: last7Days.map((d) => d.date),
    },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'line',
        data: last7Days.map((d) => d.count),
        smooth: true,
        areaStyle: { opacity: 0.3 },
      },
    ],
  })
}

onMounted(() => {
  fetchStats()
  window.addEventListener('resize', () => {
    pieChart?.resize()
    lineChart?.resize()
  })
})

onUnmounted(() => {
  pieChart?.dispose()
  lineChart?.dispose()
})
</script>

<template>
  <div style="padding: 20px" v-loading="loading">
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="今日检测次数" :value="todayCount" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="今日违规数" :value="todayViolations">
            <template #suffix>
              <el-icon style="color: #F44336"><WarningFilled /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总检测次数" :value="totalCount" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总违规数" :value="totalViolations">
            <template #suffix>
              <el-icon style="color: #F44336"><WarningFilled /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <div ref="pieChartRef" style="width: 100%; height: 350px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <div ref="lineChartRef" style="width: 100%; height: 350px" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px" v-if="dynamicViolations.length">
      <el-col :span="Math.floor(24 / dynamicViolations.length)" v-for="v in dynamicViolations" :key="v.label">
        <el-card shadow="hover">
          <el-statistic :title="v.label" :value="v.count" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>