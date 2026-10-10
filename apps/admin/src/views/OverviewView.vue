<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { adminApi, type AdminOverview } from '@/api/admin';
import { reportError } from '@/utils/error';

/**
 * 每个年级的字库目标字数（仅用于展示完成度，来源 05-1 §8.2 的看板示例）。
 * 目标是运营口径，不是技术常量，因此放在组件里而非后端。
 */
const GRADE_CHAR_TARGET = 500;

/** 状态中文名（与内容包 status 取值对齐）。 */
const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  pending_review: '待审核',
  published: '已上架',
  offline: '已下架',
};

const loading = ref(false);
const overview = ref<AdminOverview | null>(null);
const loadError = ref('');

const total = computed(() => overview.value?.characters.total ?? 0);

/** 年级完成度：固定展示 1–6 年级，缺数据按 0 处理。 */
const gradeRows = computed(() => {
  const byGrade = overview.value?.characters.by_grade ?? {};
  return [1, 2, 3, 4, 5, 6].map((grade) => {
    const count = byGrade[String(grade)] ?? 0;
    return {
      grade,
      count,
      percent: Math.min(100, Math.round((count / GRADE_CHAR_TARGET) * 100)),
    };
  });
});

/** 未归类到 1–6 年级的记录（例如年级字段缺失）。 */
const ungroupedChars = computed(() => overview.value?.characters.by_grade['未知'] ?? 0);

/** 上架状态的分布，按数量倒序。 */
const statusRows = computed(() => {
  const byStatus = overview.value?.characters.by_status ?? {};
  return Object.entries(byStatus)
    .map(([status, count]) => ({ status, label: STATUS_LABELS[status] ?? status, count }))
    .sort((a, b) => b.count - a.count);
});

/** 素材完备率：上架前应绑定配图 / 音频（05-1 §3.2 / §八）。 */
const assetRows = computed(() => {
  const assets = overview.value?.characters.assets;
  const base = total.value || 1;
  return [
    { key: 'audio', label: '读音音频', count: assets?.audio ?? 0, target: total.value },
    { key: 'image', label: '配图', count: assets?.image ?? 0, target: total.value },
    { key: 'stroke_order', label: '笔顺数据', count: assets?.stroke_order ?? 0, target: total.value },
  ].map((row) => ({ ...row, percent: Math.round((row.count / base) * 100) }));
});

const inviteUsagePercent = computed(() => {
  const invites = overview.value?.invites;
  if (!invites || invites.capacity <= 0) return 0;
  return Math.min(100, Math.round((invites.used_count / invites.capacity) * 100));
});

async function load(): Promise<void> {
  loading.value = true;
  loadError.value = '';
  try {
    overview.value = await adminApi.overview();
  } catch (err) {
    loadError.value = reportError(err, '加载概览失败');
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div v-loading="loading">
    <div class="page-header">
      <h2>概览</h2>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-alert v-if="loadError" class="block-gap" type="error" :closable="false" show-icon :title="loadError" />

    <template v-if="overview">
      <el-row :gutter="16">
        <el-col :span="4"><el-card shadow="never"><div class="metric"><span>汉字总数</span><strong>{{ overview.characters.total }}</strong></div></el-card></el-col>
        <el-col :span="4"><el-card shadow="never"><div class="metric"><span>古诗</span><strong>{{ overview.content.poems }}</strong></div></el-card></el-col>
        <el-col :span="4"><el-card shadow="never"><div class="metric"><span>自编单元</span><strong>{{ overview.content.curriculum_units }}</strong></div></el-card></el-col>
        <el-col :span="4"><el-card shadow="never"><div class="metric"><span>关卡</span><strong>{{ overview.content.lessons }}</strong></div></el-card></el-col>
        <el-col :span="4"><el-card shadow="never"><div class="metric"><span>故事</span><strong>{{ overview.content.stories }}</strong></div></el-card></el-col>
        <el-col :span="4"><el-card shadow="never"><div class="metric"><span>徽章</span><strong>{{ overview.content.badges }}</strong></div></el-card></el-col>
      </el-row>

      <el-row :gutter="16" class="block-gap">
        <el-col :span="4"><el-card shadow="never"><div class="metric"><span>邀请码总数</span><strong>{{ overview.invites.total }}</strong></div></el-card></el-col>
        <el-col :span="4"><el-card shadow="never"><div class="metric"><span>有效邀请码</span><strong>{{ overview.invites.active }}</strong></div></el-card></el-col>
        <el-col :span="4"><el-card shadow="never"><div class="metric"><span>已吊销</span><strong>{{ overview.invites.revoked }}</strong></div></el-card></el-col>
        <el-col :span="4"><el-card shadow="never"><div class="metric"><span>已注册账号</span><strong>{{ overview.accounts }}</strong></div></el-card></el-col>
        <el-col :span="4"><el-card shadow="never"><div class="metric"><span>素材条目</span><strong>{{ overview.content.assets }}</strong></div></el-card></el-col>
        <el-col :span="4"><el-card shadow="never"><div class="metric"><span>审计日志</span><strong>{{ overview.audit_logs }}</strong></div></el-card></el-col>
      </el-row>

      <el-row :gutter="16" class="block-gap">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header><span class="card-title">字库完成度（按年级）</span></template>
            <p class="page-hint">
              展示口径：每个年级 {{ GRADE_CHAR_TARGET }} 字（运营目标，见 05-1 §八）。
              <template v-if="ungroupedChars > 0">另有 {{ ungroupedChars }} 条未标注年级。</template>
            </p>
            <div v-for="row in gradeRows" :key="row.grade" class="progress-row">
              <span class="progress-label">{{ row.grade }} 年级</span>
              <el-progress
                class="progress-bar"
                :percentage="row.percent"
                :stroke-width="12"
                :format="() => `${row.count} / ${GRADE_CHAR_TARGET}`"
              />
            </div>
          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card shadow="never">
            <template #header><span class="card-title">素材完备率</span></template>
            <p class="page-hint">上架前应绑定配图与读音音频（05-1 §3.2）。</p>
            <div v-for="row in assetRows" :key="row.key" class="progress-row">
              <span class="progress-label">{{ row.label }}</span>
              <el-progress
                class="progress-bar"
                :percentage="row.percent"
                :stroke-width="12"
                :status="row.percent >= 100 ? 'success' : undefined"
                :format="() => `${row.count} / ${row.target}`"
              />
            </div>

            <el-divider />

            <div class="progress-row">
              <span class="progress-label">汉字上架状态</span>
              <div class="status-tags">
                <el-tag v-for="row in statusRows" :key="row.status" size="small" effect="plain">
                  {{ row.label }} {{ row.count }}
                </el-tag>
                <span v-if="statusRows.length === 0" class="page-hint">暂无数据</span>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-card class="block-gap" shadow="never">
        <template #header><span class="card-title">邀请码用量</span></template>
        <div class="progress-row">
          <span class="progress-label">已用 / 总量</span>
          <el-progress
            class="progress-bar"
            :percentage="inviteUsagePercent"
            :stroke-width="14"
            :format="() => `${overview?.invites.used_count ?? 0} / ${overview?.invites.capacity ?? 0}`"
          />
        </div>
        <p class="page-hint">
          共 {{ overview.invites.batches }} 个批次；完整邀请码仅在生成时返回一次，之后只保留提示片段（05-1 §6.1）。
        </p>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.block-gap {
  margin-top: 16px;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.metric span {
  color: #909399;
  font-size: 13px;
}

.metric strong {
  font-size: 22px;
  font-weight: 600;
  line-height: 1;
}

.card-title {
  font-weight: 600;
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.progress-label {
  flex: none;
  width: 88px;
  color: #606266;
  font-size: 13px;
}

.progress-bar {
  flex: 1;
}

.status-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
