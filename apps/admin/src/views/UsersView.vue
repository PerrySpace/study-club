<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus';

import {
  adminApi,
  type AdminUser,
  type AdminUserReport,
  type ReportTrendPoint,
  type UserProfilePayload,
  type UserStats,
} from '@/api/admin';
import { reportError } from '@/utils/error';

/**
 * 用户列表（账号级）。
 *
 * ⚠️ 隐私边界（05-1 §1.3）：列表只呈现**账号级**信息（用户名 / 手机号掩码 / 状态 /
 * 注册与登录时间 / 档案数）。手机号只在列表里掩码显示，明文必须走单独的、可审计的接口。
 *
 * 「学习报告」抽屉是唯一的**下钻**入口，且下钻到的是**聚合值**（已认 / 掌握 / 正确率 /
 * 连续天数），不是逐题明细 —— 这既是隐私边界，也是家长真正看得懂的口径。
 */

const STATUS_LABELS: Record<string, string> = {
  active: '正常',
  disabled: '已禁用',
  deleted: '已注销',
};

const STATUS_OPTIONS = [
  { value: 'active', label: '正常' },
  { value: 'disabled', label: '已禁用' },
];

const loading = ref(false);
const items = ref<AdminUser[]>([]);
const total = ref(0);
const stats = ref<UserStats | null>(null);

const query = reactive({
  status: '',
  keyword: '',
  /** 「有档案 / 无档案」筛选；'' = 不筛 */
  has_children: '' as '' | 'true' | 'false',
  /** 注册时间区间（YYYY-MM-DD，上界含当天） */
  registered_from: '',
  registered_to: '',
  page: 1,
  page_size: 20,
});

/** 表格多选：批量启用/禁用用。 */
const selection = ref<AdminUser[]>([]);

const activeCount = computed(() => stats.value?.by_status?.active ?? 0);
const disabledCount = computed(() => stats.value?.by_status?.disabled ?? 0);

function statusLabel(status?: string): string {
  return STATUS_LABELS[status ?? ''] ?? status ?? '—';
}

function statusTagType(status?: string): 'success' | 'info' | 'warning' | 'danger' {
  switch (status) {
    case 'active':
      return 'success';
    case 'disabled':
      return 'danger';
    default:
      return 'info';
  }
}

function formatTime(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

/** 0–1 → 百分数文本。 */
function pct(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${Math.round(value * 100)}%`;
}

// ---------------------------------------------------------------------------
// 列表
// ---------------------------------------------------------------------------
async function loadStats(): Promise<void> {
  try {
    stats.value = await adminApi.userStats();
  } catch (err) {
    reportError(err, '加载用户统计失败');
  }
}

async function load(): Promise<void> {
  loading.value = true;
  try {
    const data = await adminApi.listUsers({
      page: query.page,
      page_size: query.page_size,
      status: query.status || undefined,
      keyword: query.keyword || undefined,
      has_children: query.has_children === '' ? undefined : query.has_children === 'true',
      registered_from: query.registered_from || undefined,
      registered_to: query.registered_to || undefined,
    });
    items.value = data.items;
    total.value = data.pagination.total;
  } catch (err) {
    reportError(err, '加载用户列表失败');
  } finally {
    loading.value = false;
  }
}

function handleSearch(): void {
  query.page = 1;
  void load();
}

function handleReset(): void {
  query.status = '';
  query.keyword = '';
  query.has_children = '';
  query.registered_from = '';
  query.registered_to = '';
  query.page = 1;
  void load();
}

function handlePageChange(page: number): void {
  query.page = page;
  void load();
}

function handleSizeChange(size: number): void {
  query.page_size = size;
  query.page = 1;
  void load();
}

async function toggleStatus(row: AdminUser): Promise<void> {
  const next = row.status === 'disabled' ? 'active' : 'disabled';
  const actionText = next === 'disabled' ? '禁用' : '启用';
  try {
    await ElMessageBox.confirm(
      next === 'disabled'
        ? `禁用后「${row.username ?? row.display_name ?? row._id}」将无法登入，已有学习数据保留。确认禁用？`
        : `确认重新启用「${row.username ?? row.display_name ?? row._id}」？`,
      `${actionText}账号`,
      { confirmButtonText: actionText, cancelButtonText: '取消', type: 'warning' },
    );
  } catch {
    return;
  }
  try {
    await adminApi.setUserStatus(row._id, next);
    ElMessage.success(`已${actionText}`);
    await load();
    await loadStats();
  } catch (err) {
    reportError(err, `${actionText}失败`);
  }
}

// ---------------------------------------------------------------------------
// 编辑账号资料
// ---------------------------------------------------------------------------
const editVisible = ref(false);
const editSubmitting = ref(false);
const editTarget = ref<AdminUser | null>(null);
const editFormRef = ref<FormInstance>();

interface EditForm {
  display_name: string;
  avatar_key: string;
  access_tier: 'open' | 'invite_only';
}

const editForm = reactive<EditForm>({
  display_name: '',
  avatar_key: '',
  access_tier: 'open',
});

/**
 * 头像档位 —— 必须与 `packages/core` 的 `AVATAR` 枚举逐字一致。
 *
 * 后台多写一个客户端不认的 key，孩子端就会退化成「没有头像」；
 * 少写则用户以为后台坏了。改这里前先看 core 的 AVATAR。
 */
const AVATAR_KEYS = ['rabbit', 'panda', 'fox', 'cat', 'dog', 'bear', 'penguin', 'owl'];
const AVATAR_LABELS: Record<string, string> = {
  rabbit: '兔子',
  panda: '熊猫',
  fox: '狐狸',
  cat: '小猫',
  dog: '小狗',
  bear: '小熊',
  penguin: '企鹅',
  owl: '猫头鹰',
};

const editRules: FormRules<EditForm> = {
  display_name: [{ max: 24, message: '昵称不超过 24 字', trigger: 'blur' }],
};

function accountName(row: AdminUser | null): string {
  if (!row) return '';
  return row.username ?? row.display_name ?? row._id;
}

function openEdit(row: AdminUser): void {
  editTarget.value = row;
  editForm.display_name = row.display_name ?? '';
  editForm.avatar_key = row.avatar_key ?? '';
  editForm.access_tier = row.access_tier === 'invite_only' ? 'invite_only' : 'open';
  editVisible.value = true;
  void editFormRef.value?.clearValidate();
}

function buildEditPayload(): UserProfilePayload {
  const payload: UserProfilePayload = {
    display_name: editForm.display_name.trim() || null,
    avatar_key: editForm.avatar_key || null,
    access_tier: editForm.access_tier,
  };
  return payload;
}

async function submitEdit(): Promise<void> {
  const target = editTarget.value;
  if (!target) return;
  const valid = await editFormRef.value?.validate().catch(() => false);
  if (!valid) return;

  editSubmitting.value = true;
  try {
    await adminApi.updateUser(target._id, buildEditPayload());
    ElMessage.success('已保存');
    editVisible.value = false;
    await load();
  } catch (err) {
    reportError(err, '保存失败');
  } finally {
    editSubmitting.value = false;
  }
}

// ---------------------------------------------------------------------------
// 注销账号（软删）
// ---------------------------------------------------------------------------
async function removeUser(row: AdminUser): Promise<void> {
  const name = accountName(row);
  try {
    await ElMessageBox.confirm(
      `注销后「${name}」将无法登录，设备上的会话会全部失效。` +
        (row.children_count
          ? `该账号下的 ${row.children_count} 个孩子档案及其学习记录会保留（儿童数据不随账号注销而删除）。`
          : '该账号没有孩子档案。') +
        '此操作不可撤销。',
      '注销账号',
      { confirmButtonText: '确认注销', cancelButtonText: '取消', type: 'warning' },
    );
  } catch {
    return;
  }
  try {
    await adminApi.deleteUser(row._id);
    ElMessage.success(`已注销「${name}」`);
    await Promise.all([load(), loadStats()]);
  } catch (err) {
    reportError(err, '注销失败');
  }
}

// ---------------------------------------------------------------------------
// 批量启用 / 禁用
// ---------------------------------------------------------------------------
async function bulkSetStatus(status: 'active' | 'disabled'): Promise<void> {
  const rows = selection.value;
  if (!rows.length) {
    ElMessage.warning('请先勾选要操作的账号');
    return;
  }
  const actionText = status === 'disabled' ? '禁用' : '启用';
  try {
    await ElMessageBox.confirm(
      `确认${actionText}选中的 ${rows.length} 个账号？` +
        (status === 'disabled' ? '禁用后这些账号将无法登入，学习数据保留。' : ''),
      `批量${actionText}`,
      { confirmButtonText: actionText, cancelButtonText: '取消', type: 'warning' },
    );
  } catch {
    return;
  }
  try {
    const res = await adminApi.bulkUserStatus(
      rows.map((r) => r._id),
      status,
    );
    // 部分成功要把失败的 id 如实说出来 —— 静默吞掉会让人以为全改成了
    if (res.failed.length) {
      ElMessage.warning(
        `${actionText}完成：成功 ${res.succeeded.length} 个，失败 ${res.failed.length} 个（${res.failed
          .map((f) => f.id)
          .join('、')}）`,
      );
    } else {
      ElMessage.success(`已${actionText} ${res.succeeded.length} 个账号`);
    }
    selection.value = [];
    await Promise.all([load(), loadStats()]);
  } catch (err) {
    reportError(err, `批量${actionText}失败`);
  }
}

// ---------------------------------------------------------------------------
// 学习报告（抽屉）
// ---------------------------------------------------------------------------
const reportVisible = ref(false);
const reportLoading = ref(false);
const report = ref<AdminUserReport | null>(null);
const reportDays = ref(7);
const reportAccountName = ref('');

/** 趋势柱的高度上限（按题量归一化）；全部为 0 时给一个最小值，避免柱子全塌成 0。 */
const trendMax = computed(() => {
  const list = report.value?.trend ?? [];
  return Math.max(1, ...list.map((p) => p.total));
});

function trendBarHeight(p: ReportTrendPoint): string {
  const ratio = p.total / trendMax.value;
  return `${Math.max(6, Math.round(ratio * 100))}%`;
}

/** 正确率决定柱子颜色：低于 60% 提醒家长该复习了。 */
function trendBarType(p: ReportTrendPoint): 'good' | 'warn' | 'low' {
  if (p.total === 0) return 'low';
  if (p.accuracy >= 0.8) return 'good';
  if (p.accuracy >= 0.6) return 'warn';
  return 'low';
}

function trendLabel(date: string): string {
  const parts = date.split('-');
  return parts.length === 3 ? `${parts[1]}/${parts[2]}` : date;
}

async function openReport(row: AdminUser): Promise<void> {
  reportVisible.value = true;
  report.value = null;
  reportAccountName.value = row.username ?? row.display_name ?? row._id;
  await fetchReport(row._id);
}

async function fetchReport(id: string): Promise<void> {
  reportLoading.value = true;
  try {
    report.value = await adminApi.userReport(id, reportDays.value);
  } catch (err) {
    reportError(err, '加载学习报告失败');
  } finally {
    reportLoading.value = false;
  }
}

function changeDays(): void {
  if (!report.value) return;
  void fetchReport(report.value.account._id);
}

onMounted(() => {
  void load();
  void loadStats();
});
</script>

<template>
  <div>
    <div class="page-header">
      <h2>用户</h2>
    </div>

    <p class="page-hint">
      仅呈现<b>账号级</b>信息，不含学习明细；手机号以掩码显示（05-1 §1.3）。
      账号支持「用户名 / 手机号」两种登录标识，注册时二者至少填一个。
    </p>

    <div class="stat-row">
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">账号总数</div>
        <div class="stat-value">{{ stats?.total ?? 0 }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">正常</div>
        <div class="stat-value">{{ activeCount }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">已禁用</div>
        <div class="stat-value">{{ disabledCount }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">孩子档案</div>
        <div class="stat-value">{{ stats?.children ?? 0 }}</div>
      </el-card>
    </div>

    <div class="filter-bar">
      <el-input v-model="query.keyword" placeholder="搜索用户名 / 手机号 / 昵称" clearable style="width: 220px" />
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px">
        <el-option v-for="item in STATUS_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="query.has_children" placeholder="孩子档案" clearable style="width: 130px">
        <el-option label="有档案" value="true" />
        <el-option label="无档案" value="false" />
      </el-select>
      <el-date-picker
        v-model="query.registered_from"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="注册起"
        style="width: 140px"
      />
      <el-date-picker
        v-model="query.registered_to"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="注册止"
        style="width: 140px"
      />
      <el-button type="primary" @click="handleSearch">查询</el-button>
      <el-button @click="handleReset">重置</el-button>
    </div>

    <!-- 批量操作：仅在有勾选时出现，避免常驻占位 -->
    <div v-if="selection.length" class="bulk-bar">
      <span class="bulk-bar__text">已选 {{ selection.length }} 个账号</span>
      <el-button size="small" @click="bulkSetStatus('active')">批量启用</el-button>
      <el-button size="small" type="danger" plain @click="bulkSetStatus('disabled')">
        批量禁用
      </el-button>
      <el-button size="small" text @click="selection = []">取消选择</el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="items"
      border
      stripe
      size="small"
      @selection-change="(rows: AdminUser[]) => (selection = rows)"
    >
      <el-table-column type="selection" width="42" />
      <el-table-column label="用户名" min-width="130">
        <template #default="{ row }">
          <span :class="{ 'text-dim': !row.username }">{{ row.username || '（未设置）' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="手机号" width="150">
        <template #default="{ row }">
          <span :class="{ 'text-dim': !row.has_phone }">{{ row.phone_masked || '（未绑定）' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="昵称" min-width="110">
        <template #default="{ row }">{{ row.display_name || '—' }}</template>
      </el-table-column>
      <el-table-column label="档案数" width="80" align="center">
        <template #default="{ row }">{{ row.children_count ?? 0 }}</template>
      </el-table-column>
      <el-table-column label="准入" width="100">
        <template #default="{ row }">
          <el-tag size="small" effect="plain" type="info">
            {{ row.access_tier === 'invite_only' ? '邀请制' : '开放' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="86">
        <template #default="{ row }">
          <el-tag size="small" effect="plain" :type="statusTagType(row.status)">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="注册时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="最后登录" width="170">
        <template #default="{ row }">{{ formatTime(row.last_login_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openReport(row)">学习报告</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button
            link
            :type="row.status === 'disabled' ? 'primary' : 'danger'"
            :disabled="row.status === 'deleted'"
            @click="toggleStatus(row)"
          >
            {{ row.status === 'disabled' ? '启用' : '禁用' }}
          </el-button>
          <el-popconfirm
            title="注销后该账号无法登录且不可撤销；孩子档案与学习记录会保留。确认注销？"
            confirm-button-text="注销"
            cancel-button-text="取消"
            @confirm="removeUser(row)"
          >
            <template #reference>
              <el-button link type="danger" :disabled="row.status === 'deleted'">注销</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        :current-page="query.page"
        :page-size="query.page_size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <!-- 学习报告 -->
    <el-drawer v-model="reportVisible" :title="`学习报告 · ${reportAccountName}`" size="720px">
      <div v-loading="reportLoading" class="report">
        <template v-if="report">
          <div class="report-toolbar">
            <span class="report-toolbar__label">趋势窗口</span>
            <el-radio-group v-model="reportDays" size="small" @change="changeDays">
              <el-radio-button :value="7">近 7 天</el-radio-button>
              <el-radio-button :value="30">近 30 天</el-radio-button>
              <el-radio-button :value="90">近 90 天</el-radio-button>
            </el-radio-group>
            <span class="report-toolbar__meta">
              档案 {{ report.totals.children }} 个 · 账号状态 {{ statusLabel(report.account.status) }}
            </span>
          </div>

          <!-- 两个大数字：已认 vs 掌握。这一列是整份报告里最有用的一处 -->
          <div class="hero-row">
            <div class="hero hero--learned">
              <div class="hero__label">已认汉字</div>
              <div class="hero__value">{{ report.totals.learned }}</div>
              <div class="hero__hint">见过面、有记录的汉字</div>
            </div>
            <div class="hero hero--mastered">
              <div class="hero__label">掌握汉字</div>
              <div class="hero__value">{{ report.totals.mastered }}</div>
              <div class="hero__hint">连续答对 ≥3 次或复习间隔已拉长</div>
            </div>
            <div class="hero hero--rate">
              <div class="hero__label">掌握率</div>
              <div class="hero__value">{{ pct(report.totals.mastery_rate) }}</div>
              <div class="hero__hint">掌握 ÷ 已认</div>
            </div>
          </div>

          <p class="report-note">
            「已认」与「掌握」是故意分开的两个数：只认过一面的字<b>不进掌握</b>，
            答错会清零连续次数 —— 掌握是可以撤销的。两张数差得多，说明复习该加量了。
          </p>

          <div class="metric-grid">
            <div class="metric">
              <div class="metric__label">复习中</div>
              <div class="metric__value">{{ report.totals.reviewing }}</div>
            </div>
            <div class="metric">
              <div class="metric__label">学习中</div>
              <div class="metric__value">{{ report.totals.learning }}</div>
            </div>
            <div class="metric">
              <div class="metric__label">待清错题</div>
              <div class="metric__value">{{ report.totals.wrong }}</div>
            </div>
            <div class="metric">
              <div class="metric__label">完成关卡</div>
              <div class="metric__value">{{ report.totals.lessons }}</div>
            </div>
            <div class="metric">
              <div class="metric__label">古诗诵读</div>
              <div class="metric__value">{{ report.totals.poems }}</div>
            </div>
            <div class="metric">
              <div class="metric__label">获得徽章</div>
              <div class="metric__value">{{ report.totals.badges }}</div>
            </div>
          </div>

          <!-- 趋势：柱高按当日题量归一，颜色按正确率 -->
          <div class="trend-block">
            <div class="trend-block__header">
              <b>最近 {{ report.window_days }} 天答题趋势</b>
              <span class="trend-legend">
                <i class="dot dot--good"></i>≥80%
                <i class="dot dot--warn"></i>60–79%
                <i class="dot dot--low"></i>&lt;60%
              </span>
            </div>
            <div v-if="report.trend.length" class="trend">
              <div
                v-for="point in report.trend"
                :key="point.date"
                class="trend__col"
                :title="`${point.date}：${point.total} 题，正确 ${point.correct}，正确率 ${pct(point.accuracy)}`"
              >
                <div class="trend__bar-wrap">
                  <div
                    class="trend__bar"
                    :class="`trend__bar--${trendBarType(point)}`"
                    :style="{ height: trendBarHeight(point) }"
                  ></div>
                </div>
                <div class="trend__count">{{ point.total }}</div>
                <div class="trend__date">{{ trendLabel(point.date) }}</div>
              </div>
            </div>
            <el-empty v-else description="窗口内没有答题记录" :image-size="60" />
          </div>

          <!-- 分档案明细 -->
          <div class="children-block">
            <b>各档案明细</b>
            <el-table :data="report.children" border stripe size="small" class="children-table">
              <el-table-column label="昵称" min-width="110">
                <template #default="{ row }">{{ row.nickname || '（未命名）' }}</template>
              </el-table-column>
              <el-table-column label="年级" width="70" align="center">
                <template #default="{ row }">{{ row.grade ? `${row.grade}` : '—' }}</template>
              </el-table-column>
              <el-table-column label="已认" width="70" align="center" prop="learned" />
              <el-table-column label="掌握" width="70" align="center">
                <template #default="{ row }">
                  <b class="text-mastered">{{ row.mastered }}</b>
                </template>
              </el-table-column>
              <el-table-column label="掌握率" width="80" align="center">
                <template #default="{ row }">{{ pct(row.mastery_rate) }}</template>
              </el-table-column>
              <el-table-column label="正确率" width="80" align="center">
                <template #default="{ row }">{{ pct(row.accuracy) }}</template>
              </el-table-column>
              <el-table-column label="错题" width="70" align="center">
                <template #default="{ row }">{{ row.wrong_count }}</template>
              </el-table-column>
              <el-table-column label="连续" width="70" align="center">
                <template #default="{ row }">{{ row.streak_days }} 天</template>
              </el-table-column>
              <el-table-column label="最近学习" width="160">
                <template #default="{ row }">{{ formatTime(row.last_study_at) }}</template>
              </el-table-column>
            </el-table>
            <el-empty
              v-if="!report.children.length"
              description="该账号下还没有孩子档案"
              :image-size="60"
            />
          </div>
        </template>
      </div>
    </el-drawer>
    <!-- 编辑账号资料 -->
    <el-dialog
      v-model="editVisible"
      :title="`编辑账号 · ${accountName(editTarget)}`"
      width="520px"
    >
      <el-alert type="info" :closable="false" show-icon class="edit-alert">
        <template #title>这里只能改展示资料</template>
        用户名与手机号是<b>登录标识</b>（带唯一索引，改动等于换账号），因此不在此处提供编辑。
      </el-alert>

      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="86px">
        <el-form-item label="昵称" prop="display_name">
          <el-input
            v-model="editForm.display_name"
            maxlength="24"
            show-word-limit
            placeholder="家长给孩子起的称呼"
          />
        </el-form-item>
        <el-form-item label="头像">
          <div class="avatar-picker">
            <button
              v-for="key in AVATAR_KEYS"
              :key="key"
              type="button"
              class="avatar-picker__item"
              :class="{ 'avatar-picker__item--active': editForm.avatar_key === key }"
              @click="editForm.avatar_key = key"
            >
              {{ AVATAR_LABELS[key] ?? key }}
            </button>
            <el-button link size="small" @click="editForm.avatar_key = ''">清除</el-button>
          </div>
        </el-form-item>
        <el-form-item label="准入档位">
          <el-radio-group v-model="editForm.access_tier">
            <el-radio value="open">开放注册</el-radio>
            <el-radio value="invite_only">仅邀请码</el-radio>
          </el-radio-group>
          <div class="form-tip">影响该账号能看到的注册入口文案，不影响已有账号登录。</div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.bulk-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding: 8px 12px;
  border: 1px solid #d9e0ff;
  border-radius: 6px;
  background: #f4f6ff;
}

.bulk-bar__text {
  color: #606266;
  font-size: 13px;
  font-weight: 600;
}

.avatar-picker {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.avatar-picker__item {
  padding: 5px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #fff;
  color: #606266;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.avatar-picker__item:hover {
  border-color: #c6b9ff;
  color: #6b4fd8;
}

.avatar-picker__item--active {
  border-color: #7a5af8;
  background: #f2eeff;
  color: #5b34d6;
  font-weight: 600;
}

.edit-alert {
  margin-bottom: 16px;
}

.form-tip {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
}

.stat-label {
  color: #909399;
  font-size: 12px;
}

.stat-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 700;
  color: #303133;
}

.text-dim {
  color: #c0c4cc;
}

.text-mastered {
  color: #67c23a;
}

/* ----------------------------- 学习报告 ----------------------------- */
.report {
  min-height: 200px;
}

.report-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.report-toolbar__label {
  color: #909399;
  font-size: 13px;
}

.report-toolbar__meta {
  margin-left: auto;
  color: #909399;
  font-size: 12px;
}

.hero-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.hero {
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid #ebeef5;
}

.hero--learned {
  background: #f4f6ff;
  border-color: #d9e0ff;
}

.hero--mastered {
  background: #f0f9eb;
  border-color: #d5efc4;
}

.hero--rate {
  background: #fdf6ec;
  border-color: #f5e0c0;
}

.hero__label {
  color: #606266;
  font-size: 12px;
}

.hero__value {
  margin: 4px 0 2px;
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
  color: #303133;
}

.hero--mastered .hero__value {
  color: #529b2e;
}

.hero__hint {
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
}

.report-note {
  margin: 12px 0 16px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fafafa;
  color: #606266;
  font-size: 12px;
  line-height: 1.7;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 20px;
}

.metric {
  padding: 10px 8px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  text-align: center;
}

.metric__label {
  color: #909399;
  font-size: 12px;
}

.metric__value {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.trend-block {
  margin-bottom: 20px;
}

.trend-block__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.trend-legend {
  color: #909399;
  font-size: 12px;
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin: 0 4px 0 10px;
  border-radius: 50%;
}

.dot--good {
  background: #67c23a;
}

.dot--warn {
  background: #e6a23c;
}

.dot--low {
  background: #f56c6c;
}

.trend {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 140px;
  padding: 0 2px;
  overflow-x: auto;
}

.trend__col {
  flex: 0 0 28px;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}

.trend__bar-wrap {
  flex: 1;
  display: flex;
  align-items: flex-end;
  width: 100%;
}

.trend__bar {
  width: 100%;
  border-radius: 4px 4px 0 0;
  transition: height 0.2s;
}

.trend__bar--good {
  background: #85ce61;
}

.trend__bar--warn {
  background: #f3d19e;
}

.trend__bar--low {
  background: #fab6b6;
}

.trend__count {
  margin-top: 3px;
  color: #606266;
  font-size: 11px;
}

.trend__date {
  color: #a8abb2;
  font-size: 11px;
  transform: scale(0.92);
}

.children-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.children-table {
  margin-top: 4px;
}
</style>
