<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';

import {
  adminApi,
  type AdminInvite,
  type InviteBatchResult,
  type InviteChannel,
} from '@/api/admin';
import { reportError } from '@/utils/error';

const CHANNEL_LABELS: Record<InviteChannel, string> = {
  self: '自用',
  friend: '朋友',
  community: '社群',
  test: '测试',
};

interface InviteStatus {
  label: string;
  type: 'success' | 'info' | 'warning' | 'danger';
}

const loading = ref(false);
const items = ref<AdminInvite[]>([]);
const total = ref(0);

const query = reactive({
  batch_id: '',
  channel: '',
  page: 1,
  page_size: 20,
});

// ---------------------------------------------------------------------------
// 生成批次
// ---------------------------------------------------------------------------
interface InviteForm {
  count: number;
  channel: InviteChannel;
  /** 留空 = 长期有效；用 undefined 而非 null，以匹配 el-input-number 的取值类型 */
  expires_in_days: number | undefined;
  batch_id: string;
  note: string;
}

const createVisible = ref(false);
const creating = ref(false);
const form = reactive<InviteForm>({
  count: 10,
  channel: 'test',
  expires_in_days: undefined,
  batch_id: '',
  note: '',
});

const resultVisible = ref(false);
const batchResult = ref<InviteBatchResult | null>(null);

// ---------------------------------------------------------------------------
// 列表
// ---------------------------------------------------------------------------
function formatTime(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

function statusOf(row: AdminInvite): InviteStatus {
  if (row.revoked_at) return { label: '已吊销', type: 'info' };
  if (row.expires_at && new Date(row.expires_at).getTime() < Date.now()) {
    return { label: '已过期', type: 'warning' };
  }
  // 一码一账号：used_count 只可能是 0 或 1
  if (row.used_count >= 1) return { label: '已激活', type: 'warning' };
  return { label: '未使用', type: 'success' };
}

async function load(): Promise<void> {
  loading.value = true;
  try {
    const data = await adminApi.listInvites({
      page: query.page,
      page_size: query.page_size,
      batch_id: query.batch_id || undefined,
      channel: query.channel || undefined,
    });
    items.value = data.items;
    total.value = data.pagination.total;
  } catch (err) {
    reportError(err, '加载邀请码列表失败');
  } finally {
    loading.value = false;
  }
}

function handleSearch(): void {
  query.page = 1;
  void load();
}

function handleReset(): void {
  query.batch_id = '';
  query.channel = '';
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

// ---------------------------------------------------------------------------
// 生成
// ---------------------------------------------------------------------------
function openCreate(): void {
  form.count = 10;
  form.channel = 'test';
  form.expires_in_days = undefined;
  form.batch_id = '';
  form.note = '';
  createVisible.value = true;
}

async function submitCreate(): Promise<void> {
  creating.value = true;
  try {
    batchResult.value = await adminApi.createInvites({
      count: form.count,
      // 恒为 1：邀请码即账号登录标识，一码一账号（见 InviteBatchInput 的注释）
      max_uses: 1,
      channel: form.channel,
      expires_in_days: form.expires_in_days ?? undefined,
      batch_id: form.batch_id || undefined,
      note: form.note || undefined,
    });
    createVisible.value = false;
    resultVisible.value = true;
    await load();
  } catch (err) {
    reportError(err, '生成邀请码失败');
  } finally {
    creating.value = false;
  }
}

// ---------------------------------------------------------------------------
// 吊销
// ---------------------------------------------------------------------------
async function revoke(row: AdminInvite): Promise<void> {
  try {
    await adminApi.revokeInvite(row._id);
    ElMessage.success(`已吊销 ${row.code_hint}`);
    await load();
  } catch (err) {
    reportError(err, '吊销失败');
  }
}

// ---------------------------------------------------------------------------
// 复制
// ---------------------------------------------------------------------------
async function copy(text: string, tip = '已复制'): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success(tip);
  } catch {
    ElMessage.warning('当前浏览器不允许自动复制，请手动选中复制');
  }
}

function copyAllCodes(): void {
  const codes = batchResult.value?.codes.map((item) => item.code) ?? [];
  if (codes.length === 0) return;
  void copy(codes.join('\n'), `已复制 ${codes.length} 个邀请码`);
}

onMounted(load);
</script>

<template>
  <div>
    <div class="page-header">
      <h2>邀请码</h2>
      <el-button type="primary" @click="openCreate">生成邀请码</el-button>
    </div>

    <p class="page-hint">
      完整邀请码<b>仅在生成时显示一次</b>，之后只保留提示片段（05-1 §6.1）。需要补发请重新生成一批。
      <br />
      <b>一码一账号</b>：邀请码即账号的登录标识，一个码只能注册一个账号（02-5 §2.2 / 03-1 §3.1）；
      家庭内部共用同一码与同一密码，需要隔离就再发一个码。
    </p>

    <div class="filter-bar">
      <el-input v-model="query.batch_id" placeholder="按批次号筛选" clearable style="width: 240px" />
      <el-select v-model="query.channel" placeholder="渠道" clearable style="width: 140px">
        <el-option v-for="(label, value) in CHANNEL_LABELS" :key="value" :label="label" :value="value" />
      </el-select>
      <el-button type="primary" @click="handleSearch">查询</el-button>
      <el-button @click="handleReset">重置</el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe size="small">
      <el-table-column label="邀请码" min-width="150">
        <template #default="{ row }"><span class="mono">{{ row.code_hint }}</span></template>
      </el-table-column>
      <el-table-column label="批次" min-width="200">
        <template #default="{ row }"><span class="mono">{{ row.batch_id }}</span></template>
      </el-table-column>
      <el-table-column label="渠道" width="90">
        <template #default="{ row }">{{ CHANNEL_LABELS[row.channel as InviteChannel] ?? row.channel }}</template>
      </el-table-column>
      <el-table-column label="激活" width="90">
        <template #default="{ row }">
          <span :class="{ 'text-dim': row.used_count < 1 }">
            {{ row.used_count >= 1 ? '已激活' : '未使用' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" effect="plain" :type="statusOf(row).type">{{ statusOf(row).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="有效期至" width="180">
        <template #default="{ row }">{{ row.expires_at ? formatTime(row.expires_at) : '长期有效' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="备注" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ row.note || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-popconfirm
            title="吊销后该邀请码立即失效，已注册账号不受影响。确认吊销？"
            confirm-button-text="吊销"
            cancel-button-text="取消"
            @confirm="revoke(row)"
          >
            <template #reference>
              <el-button link type="danger" :disabled="Boolean(row.revoked_at)">吊销</el-button>
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

    <!-- 生成对话框 -->
    <el-dialog v-model="createVisible" title="生成邀请码" width="480px">
      <el-form label-width="96px">
        <el-form-item label="数量">
          <el-input-number v-model="form.count" :min="1" :max="100" />
          <span class="form-tip">单批最多 100 个</span>
        </el-form-item>
        <el-form-item label="激活次数">
          <span class="form-tip form-tip--block">
            固定 <b>1 次</b>：邀请码就是账号的登录标识，一个码只能激活一个账号。
            全家人共用「同一码 + 同一密码」进同一个档案空间；需要数据隔离请再发一个码。
          </span>
        </el-form-item>
        <el-form-item label="渠道">
          <el-select v-model="form.channel" style="width: 160px">
            <el-option v-for="(label, value) in CHANNEL_LABELS" :key="value" :label="label" :value="value" />
          </el-select>
        </el-form-item>
        <el-form-item label="有效期">
          <el-input-number v-model="form.expires_in_days" :min="1" :max="3650" placeholder="留空为长期有效" />
          <span class="form-tip">天（留空 = 长期有效）</span>
        </el-form-item>
        <el-form-item label="批次号">
          <el-input v-model="form.batch_id" placeholder="留空自动生成" maxlength="64" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" placeholder="例如：首轮内测" maxlength="200" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">生成</el-button>
      </template>
    </el-dialog>

    <!-- 生成结果（明文码只此一次） -->
    <el-dialog v-model="resultVisible" title="邀请码已生成" width="520px">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="请立即复制保存：本页面关闭后无法再查看完整邀请码。"
      />

      <template v-if="batchResult">
        <div class="result-meta">
          <div>批次号：<span class="mono">{{ batchResult.batch_id }}</span></div>
          <div>数量：{{ batchResult.count }} 个</div>
          <div>有效期至：{{ batchResult.expires_at ? formatTime(batchResult.expires_at) : '长期有效' }}</div>
        </div>

        <div class="code-list">
          <div v-for="item in batchResult.codes" :key="item.code" class="code-item">
            <span class="mono">{{ item.code }}</span>
            <el-button link type="primary" @click="copy(item.code)">复制</el-button>
          </div>
        </div>
      </template>

      <template #footer>
        <el-button @click="copyAllCodes">复制全部</el-button>
        <el-button type="primary" @click="resultVisible = false">我已保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.form-tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}

/* 说明型提示（不跟在控件后面，自己占一行） */
.form-tip--block {
  display: block;
  margin-left: 0;
  line-height: 1.7;
}

.text-dim {
  color: #c0c4cc;
}

.result-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 14px 0 10px;
  color: #606266;
  font-size: 13px;
}
</style>
