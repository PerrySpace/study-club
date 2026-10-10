<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';

import { adminApi, GAMEPLAY_QUESTION_TYPE_OPTIONS, type SiteConfig } from '@/api/admin';
import { reportError } from '@/utils/error';

/**
 * 站点配置（配置中心）。
 *
 * 这些是**运行期运营参数**：写进 MongoDB（`app_settings` 单文档），
 * api 启动时读一次，改完**立即生效、无需重启、无需发版**（见 core/runtime_config.py）。
 * 与 .env 的分工：端口 / 密钥 / DB 地址等部署项仍在 .env；此处只放会随运营调整的项。
 *
 * 「默认学习目标」与「玩法配置」不是一回事：
 * - 上面那组只在**新建档案**时写入，之后每个孩子各自保留；
 * - 下面这组**全体生效**，客户端每次启动读它 —— 改一下等于给所有孩子换一套玩法。
 */

const loading = ref(false);
const saving = ref(false);

const form = reactive<SiteConfig>({
  require_invite: false,
  registration_open: true,
  announcement: '',
  defaults: {
    daily_new_char_target: 8,
    daily_review_target: 20,
    daily_time_limit_min: 20,
  },
  gameplay: {
    stage_test_every: 5,
    enabled_question_types: GAMEPLAY_QUESTION_TYPE_OPTIONS.map((item) => item.value),
    enable_speak: true,
    show_pictograph: true,
    speak_rate: 0.8,
  },
  grades: [
    { id: 0, label: '学龄前', enabled: true },
    { id: 1, label: '一年级', enabled: true },
    { id: 2, label: '二年级', enabled: true },
    { id: 3, label: '三年级', enabled: true },
    { id: 4, label: '四年级', enabled: true },
    { id: 5, label: '五年级', enabled: true },
    { id: 6, label: '六年级', enabled: true },
  ],
});

// ---------------------------------------------------------------------------
// 年级管理（可任意增删改）
// ---------------------------------------------------------------------------
/** 下一个可用的年级号：取已用最大值 +1，避免 id 撞车。 */
const nextGradeId = computed(() =>
  form.grades.reduce((max, g) => Math.max(max, g.id), 0) + 1,
);

/** 常见中文年级名，用于「一键补齐」时按序命名。 */
const GRADE_NAME_HINT = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '七年级', '八年级', '九年级'];

function addGrade(): void {
  const id = nextGradeId.value;
  form.grades.push({
    id,
    // 命名有据可依：沿用「N年级」的习惯，不让运营凭空想
    label: GRADE_NAME_HINT.includes(`${id}年级`) ? `${id}年级` : `年级 ${id}`,
    enabled: true,
  });
}

function removeGrade(index: number): void {
  form.grades.splice(index, 1);
}

function moveGrade(index: number, delta: number): void {
  const target = index + delta;
  if (target < 0 || target >= form.grades.length) return;
  const [item] = form.grades.splice(index, 1);
  form.grades.splice(target, 0, item);
}

/** 重复 id 必须在保存前拦住：后端会拒绝，且错误信息不直观。 */
const duplicateGradeId = computed(() => {
  const seen = new Set<number>();
  for (const g of form.grades) {
    if (seen.has(g.id)) return true;
    seen.add(g.id);
  }
  return false;
});

const gradeFormInvalid = computed(
  () => form.grades.length === 0 || form.grades.some((g) => !g.label.trim()) || duplicateGradeId.value,
);

/** 题型勾选值（只保留后端认识的题型，顺序由契约决定）。 */
const typeValues = computed(() => GAMEPLAY_QUESTION_TYPE_OPTIONS.map((item) => item.value));

const allTypesChecked = computed(
  () => form.gameplay.enabled_question_types.length === typeValues.value.length,
);
const someTypesChecked = computed(
  () => form.gameplay.enabled_question_types.length > 0 && !allTypesChecked.value,
);

/** 语速展示：越小越慢，「一个字一个字念」到接近正常语速。 */
const rateLabel = computed(() => {
  const r = form.gameplay.speak_rate;
  if (r <= 0.7) return '很慢（逐字念）';
  if (r <= 0.9) return '偏慢（启蒙推荐）';
  if (r <= 1.05) return '正常';
  return '偏快';
});

function toggleAllTypes(value: string | number | boolean): void {
  form.gameplay.enabled_question_types = value ? [...typeValues.value] : [];
}

/** 阶段检测：每学 N 个新字抽查一次旧字（只推新字不回头，是识字最大的坑）。 */
const stageTip = computed(() => {
  const n = form.gameplay.stage_test_every;
  return `每学 ${n} 个新字，插入 1 道旧字抽查；一节课最多抽查 3 次。`;
});

/**
 * 用服务端返回的配置覆盖表单。
 *
 * 逐字段赋值而不是 `Object.assign(form, cfg)`：嵌套段要**深合并**，
 * 直接 assign 会把整个 `gameplay` 换成服务端对象，服务端将来少发一个键就变成 `undefined`。
 */
function applyConfig(cfg: SiteConfig): void {
  form.require_invite = cfg.require_invite;
  form.registration_open = cfg.registration_open;
  form.announcement = cfg.announcement ?? '';
  form.defaults = { ...form.defaults, ...cfg.defaults };
  form.gameplay = { ...form.gameplay, ...cfg.gameplay };
  // 年级表**整表替换**（不是合并）：运营删掉一个年级后，若合并语义会让它删不掉
  form.grades = (cfg.grades ?? []).map((g) => ({ ...g }));
}

async function load(): Promise<void> {
  loading.value = true;
  try {
    applyConfig(await adminApi.getConfig());
  } catch (err) {
    reportError(err, '加载站点配置失败');
  } finally {
    loading.value = false;
  }
}

async function save(): Promise<void> {
  // 年级表是整表替换，非法值会被后端拒绝 —— 先在前端拦下，给出可操作的提示
  if (gradeFormInvalid.value) {
    ElMessage.warning(
      duplicateGradeId.value
        ? '年级序号不能重复'
        : '每个年级都要有名称，且至少保留一个年级',
    );
    return;
  }
  saving.value = true;
  try {
    const cfg = await adminApi.updateConfig({
      require_invite: form.require_invite,
      registration_open: form.registration_open,
      announcement: form.announcement,
      defaults: { ...form.defaults },
      gameplay: {
        ...form.gameplay,
        // 一个题型都不勾 = 孩子进去没题可答，不是合法状态 —— 前端先挡住，
        // 后端 `_normalize_gameplay` 还有一次回落默认全集的双保险。
        enabled_question_types: form.gameplay.enabled_question_types.length
          ? [...form.gameplay.enabled_question_types]
          : [...typeValues.value],
      },
      grades: form.grades.map((g) => ({
        id: Number(g.id),
        label: g.label.trim(),
        enabled: Boolean(g.enabled),
      })),
    });
    // 用服务端归一化后的值回填（越界值会被后端 clamp，回填后界面与服务端一致）
    applyConfig(cfg);
    ElMessage.success('已保存，立即生效');
  } catch (err) {
    reportError(err, '保存失败');
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div v-loading="loading">
    <div class="page-header">
      <h2>站点配置</h2>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </div>

    <p class="page-hint">
      改完<b>立即生效</b>，无需重启或重新部署。部署项（端口 / 密钥 / 数据库地址）仍在
      <span class="mono">.env</span>，不在这里。
    </p>

    <el-card shadow="never" class="section">
      <template #header><b>注册与准入</b></template>
      <el-form label-width="140px">
        <el-form-item label="开放注册">
          <el-switch v-model="form.registration_open" />
          <span class="form-tip">关闭后任何人都无法注册新账号（已有账号不受影响）</span>
        </el-form-item>
        <el-form-item label="邀请码必填">
          <el-switch v-model="form.require_invite" />
          <span class="form-tip">
            开启后注册必须填写有效邀请码；关闭即「免码开放」。
            客户端 <span class="mono">VITE_ENABLE_INVITE_REQUIRED</span> 应与此保持一致，服务端以此为准。
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="section">
      <template #header>
        <div class="card-header">
          <b>年级设置</b>
          <el-button size="small" @click="addGrade">新增年级</el-button>
        </div>
      </template>

      <p class="section-tip">
        年级不再写死一到六，可以按实际需要任意增删（如「幼小衔接」「七年级」）。
        客户端的年级下拉、建档页与文案全部读这份配置，<b>改完无需发版</b>。
      </p>

      <el-table :data="form.grades" border size="small" class="grade-table">
        <el-table-column label="序号" width="110">
          <template #default="{ row }">
            <el-input-number
              v-model="row.id"
              :min="0"
              :max="30"
              :controls="false"
              size="small"
              style="width: 90px"
            />
          </template>
        </el-table-column>
        <el-table-column label="名称">
          <template #default="{ row }">
            <el-input v-model="row.label" maxlength="16" size="small" placeholder="如：一年级" />
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" align="center">
          <template #default="{ $index }">
            <el-button link size="small" :disabled="$index === 0" @click="moveGrade($index, -1)">
              上移
            </el-button>
            <el-button
              link
              size="small"
              :disabled="$index === form.grades.length - 1"
              @click="moveGrade($index, 1)"
            >
              下移
            </el-button>
            <el-button
              link
              type="danger"
              size="small"
              :disabled="form.grades.length === 1"
              @click="removeGrade($index)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <p class="section-tip">
        ⚠️ <b>停用</b>只是不向新用户展示该年级，已有档案照常使用；
        <b>删除</b>则会从下拉里彻底移除 —— 已有档案的年级文案会回退成「N 年级」。
        序号决定内容筛选（只取「该年级及以下」），调整序号会影响新孩子看到的内容范围。
      </p>
    </el-card>

    <el-card shadow="never" class="section">
      <template #header><b>默认学习目标</b></template>
      <el-form label-width="140px">
        <el-form-item label="每日新学（字）">
          <el-input-number v-model="form.defaults.daily_new_char_target" :min="1" :max="50" />
        </el-form-item>
        <el-form-item label="每日复习（字）">
          <el-input-number v-model="form.defaults.daily_review_target" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="每日时长上限（分）">
          <el-input-number v-model="form.defaults.daily_time_limit_min" :min="5" :max="240" />
        </el-form-item>
      </el-form>
      <p class="section-tip">新建孩子档案时作为初始值（已有档案各自保留自己的设置）。</p>
    </el-card>

    <el-card shadow="never" class="section">
      <template #header>
        <div class="card-header">
          <b>玩法配置</b>
          <el-tag size="small" effect="plain" type="warning">全体孩子生效</el-tag>
        </div>
      </template>

      <p class="section-tip">
        这一组是客户端玩法的唯一真源：客户端每次启动读取并据此渲染，改完<b>所有孩子的界面同时变</b>。
        客户端不再自带一份写死的玩法表。
      </p>

      <el-form label-width="140px">
        <el-form-item label="阶段检测">
          <el-input-number v-model="form.gameplay.stage_test_every" :min="3" :max="10" />
          <span class="form-tip">{{ stageTip }}</span>
        </el-form-item>

        <el-form-item label="题型开关">
          <div class="type-block">
            <div class="type-actions">
              <el-checkbox
                :model-value="allTypesChecked"
                :indeterminate="someTypesChecked"
                @change="toggleAllTypes"
              >
                全选
              </el-checkbox>
              <span class="form-tip">不勾选任何一个时，服务端会回落为「全部开放」</span>
            </div>
            <el-checkbox-group v-model="form.gameplay.enabled_question_types">
              <el-checkbox
                v-for="item in GAMEPLAY_QUESTION_TYPE_OPTIONS"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </el-checkbox>
            </el-checkbox-group>
            <span
              v-if="!form.gameplay.enable_speak && form.gameplay.enabled_question_types.includes('speak')"
              class="form-tip form-tip--warn"
            >
              跟读已关闭，「跟读发音」即使勾选也不会出现。
            </span>
          </div>
        </el-form-item>

        <el-form-item label="跟读发音">
          <el-switch v-model="form.gameplay.enable_speak" />
          <span class="form-tip">
            使用浏览器原生语音识别。关闭后跟读题型整块不出现，也不会再请求麦克风权限。
          </span>
        </el-form-item>

        <el-form-item label="朗读语速">
          <el-slider
            v-model="form.gameplay.speak_rate"
            :min="0.6"
            :max="1.2"
            :step="0.05"
            :disabled="!form.gameplay.enable_speak"
            style="width: 260px"
          />
          <span class="form-tip">{{ form.gameplay.speak_rate.toFixed(2) }} · {{ rateLabel }}</span>
        </el-form-item>

        <el-form-item label="字源图">
          <el-switch v-model="form.gameplay.show_pictograph" />
          <span class="form-tip">
            展示象形 emoji / 绑定配图。关闭后「看图选字」会退化为按释义提示出题。
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="section">
      <template #header><b>公告</b></template>
      <el-form label-width="140px">
        <el-form-item label="站内公告">
          <el-input
            v-model="form.announcement"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="留空则不显示公告"
          />
        </el-form-item>
      </el-form>
    </el-card>

    <div class="footer-actions">
      <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
    </div>
  </div>
</template>

<style scoped>
.grade-table {
  margin-bottom: var(--space-sm);
}

.section {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-tip {
  color: #909399;
  font-size: 12px;
}

.form-tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
  line-height: 1.7;
}

.form-tip--warn {
  display: block;
  margin-left: 0;
  color: #e6a23c;
}

.type-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.type-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
