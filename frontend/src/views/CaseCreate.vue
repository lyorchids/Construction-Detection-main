<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createCase, createCaseFromRecord, type CaseCreateData } from '../api/case'
import { getRecord, getViolations } from '../api/history'

const router = useRouter()
const route = useRoute()
const saving = ref(false)
const sourceRecordId = ref<number | undefined>(
  route.query.record_id ? Number(route.query.record_id) : undefined,
)
const loadingRecord = ref(false)
const recordInfo = ref<string>('')

const form = ref<CaseCreateData>({
  title: '',
  case_type: 'no_hardhat',
  severity: 'medium',
  scene_description: '',
  recommended_actions: '',
  process_info: '',
  source_record_id: null,
})

const CASE_TYPE_OPTIONS = [
  { value: 'no_hardhat', label: '未戴头盔' },
  { value: 'dangerous_operation', label: '危险操作' },
  { value: 'other', label: '其他' },
]

const SEVERITY_OPTIONS = [
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
  { value: 'critical', label: '紧急' },
]

async function loadRecordInfo() {
  if (!sourceRecordId.value) return
  loadingRecord.value = true
  try {
    const { data: rec } = await getRecord(sourceRecordId.value)
    recordInfo.value = `${rec.filename} (${rec.file_type === 'image' ? '图片' : '视频'}) - ${rec.total_objects}个目标, ${rec.violation_count}次违规`

    const { data: violations } = await getViolations(sourceRecordId.value)
    const typeLabels: Record<string, string> = {
      warning_no_hardhat: '未戴安全帽',
      warning_no_mask: '未佩戴口罩',
      warning_no_safety_vest: '未穿反光背心',
      warning_people_in_controlled_area: '进入管控区',
      warning_people_in_utility_pole_controlled_area: '进入电线杆区',
      warning_fire: '检测到火焰',
      warning_smoke: '检测到烟雾',
    }
    const typeCounts: Record<string, number> = {}
    for (const v of violations) {
      typeCounts[v.violation_type] = (typeCounts[v.violation_type] || 0) + 1
    }
    const descLines = [`在"${rec.filename}"的检测中，发现以下安全隐患：`]
    for (const [vt, cnt] of Object.entries(typeCounts)) {
      descLines.push(`- ${typeLabels[vt] || vt}：${cnt}次`)
    }
    descLines.push(`共检测到${rec.total_objects}个目标，违规${rec.violation_count}次。`)

    const firstViolation = violations[0]
    const typeMap: Record<string, string> = {
      warning_no_hardhat: 'no_hardhat',
      warning_people_in_controlled_area: 'dangerous_operation',
      warning_people_in_utility_pole_controlled_area: 'dangerous_operation',
    }
    const mappedType = typeMap[firstViolation?.violation_type] || 'other'
    const defaultActions: Record<string, string> = {
      no_hardhat: '1. 立即要求该工人停止作业并正确佩戴安全帽\n2. 对工人进行现场安全教育\n3. 通知班组长加强监督\n4. 全员通报',
      dangerous_operation: '1. 立即发出警告，要求人员与设备保持安全距离\n2. 设置安全警示线和标志\n3. 对相关人员进行安全交底',
      other: '1. 立即制止违规行为\n2. 对相关人员进行安全教育\n3. 完善现场安全管理措施',
    }

    form.value.title = `${typeLabels[firstViolation?.violation_type] || '安全'}违规案例`
    form.value.case_type = mappedType
    form.value.scene_description = descLines.join('\n')
    form.value.recommended_actions = defaultActions[mappedType] || defaultActions.other
    form.value.source_record_id = sourceRecordId.value
  } catch {
    ElMessage.error('加载检测记录信息失败')
  } finally {
    loadingRecord.value = false
  }
}

async function handleSubmit() {
  saving.value = true
  try {
    const { data } = await createCase(form.value)
    ElMessage.success('案例创建成功')
    router.push(`/cases/${data.id}`)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '创建失败')
  } finally {
    saving.value = false
  }
}

function handleFromRecord() {
  if (!sourceRecordId.value) {
    ElMessage.warning('请输入检测记录ID')
    return
  }
  loadingRecord.value = true
  createCaseFromRecord(sourceRecordId.value)
    .then(({ data }) => {
      ElMessage.success('从记录创建案例成功')
      router.push(`/cases/${data.id}`)
    })
    .catch((error: any) => {
      ElMessage.error(error.response?.data?.detail || '创建失败')
    })
    .finally(() => {
      loadingRecord.value = false
    })
}

onMounted(() => {
  if (sourceRecordId.value) {
    loadRecordInfo()
  }
})
</script>

<template>
  <div style="padding: 20px">
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card>
          <template #header>
            <h3 style="margin: 0">新建案例</h3>
          </template>

          <el-form :model="form" label-width="120px">
            <el-form-item label="案例标题">
              <el-input v-model="form.title" placeholder="请输入案例标题" />
            </el-form-item>
            <el-form-item label="案例类型">
              <el-select v-model="form.case_type">
                <el-option v-for="opt in CASE_TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="严重程度">
              <el-select v-model="form.severity">
                <el-option v-for="opt in SEVERITY_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="场景描述">
              <el-input v-model="form.scene_description" type="textarea" :rows="5" placeholder="请描述违规场景" />
            </el-form-item>
            <el-form-item label="应对措施">
              <el-input v-model="form.recommended_actions" type="textarea" :rows="4" placeholder="推荐的安全管理措施" />
            </el-form-item>
            <el-form-item label="处理信息">
              <el-input v-model="form.process_info" type="textarea" :rows="3" placeholder="实际处理过程和结果" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="handleSubmit">创建案例</el-button>
              <el-button @click="router.back()">取消</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card>
          <template #header>
            <h3 style="margin: 0">从检测记录创建</h3>
          </template>
          <el-form label-width="100px">
            <el-form-item label="记录ID">
              <el-input-number v-model="sourceRecordId" :min="1" style="width: 100%" />
            </el-form-item>
            <el-form-item>
              <el-button type="success" :loading="loadingRecord" @click="handleFromRecord" style="width: 100%">
                从记录自动创建
              </el-button>
            </el-form-item>
          </el-form>
          <el-alert v-if="recordInfo" :title="recordInfo" type="info" :closable="false" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
