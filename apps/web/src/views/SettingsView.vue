<script setup lang="ts">
/**
 * SettingsView —— 设置（家长视图入口）。
 *   I-03 多孩子档案 / S-15 多档案切换 / P-04 自定义计划 / P-02 时长自控
 *   I-04 数据导出（数据真源在服务端，导出对应的是「退出自由」而非「备份」）
 *   R-01 / R-02 / R-03 隐私说明与第三方许可
 *
 * ⚠️ 与旧版的差异：学习数据已全部服务端化，因此
 *   - 「清空本机数据」这个动作不再存在（本机已没有业务数据可清），
 *     取而代之的是「退出登录」（清会话）与「注销账号」（清云端数据）；
 *   - 「从文件导入」同理移除：换设备重新登录即可，不需要家长手动导文件。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';

import {
  DEFAULT_AVATAR,
  useAuthStore,
  useChildStore,
  useContentStore,
} from '@study-club/core';

import AvatarPicker from '@/components/biz/AvatarPicker.vue';
import BaseButton from '@/components/base/BaseButton.vue';
import BaseCard from '@/components/base/BaseCard.vue';
import { useExportImport } from '@/composables/useExportImport';
import { useSpeech } from '@/composables/useSpeech';
import { useToast } from '@/composables/useToast';
import { useUiStore } from '@/stores/ui';
import { gradeLabel, gradeOptions as gradeOptionsFromConfig } from '@/utils/format';

const router = useRouter();
const auth = useAuthStore();
const childStore = useChildStore();
const contentStore = useContentStore();
const { current, children } = storeToRefs(childStore);
const { exportChild, exporting } = useExportImport();
const toast = useToast();
const ui = useUiStore();

// ---- 新建档案 ----
const newNickname = ref('');
const newGrade = ref(1);
const newAvatar = ref<string>(DEFAULT_AVATAR);

// ---- 学习设置 ----
const newCharTarget = ref(8);
const reviewTarget = ref(20);
const timeLimit = ref(20);

// 年级下拉取自服务端下发的年级表（后台可任意增删），而不是写死的常量。
const gradeOptions = computed(() => gradeOptionsFromConfig());

// ---- 朗读设置 ----
// 音色放**本机设置**而不是后台：这是「这台设备、这个孩子」的听感偏好，
// 换一台设备就该换一档；放后台会让一台设备的难听音色影响所有人。
const { canSpeak, voices, voiceURI, setVoice, speak } = useSpeech();

/** 试听文本：三个声调差别大的字，一听就知道音色好坏。 */
const VOICE_PREVIEW = '山，水，火';

async function onVoiceChange(event: Event): Promise<void> {
  const value = (event.target as HTMLSelectElement).value;
  setVoice(value);
  // 换完立刻试听：让用户直接听见结果，而不是「改了但不知道变成什么样」
  await speak(VOICE_PREVIEW, { rate: 0.9 });
}

async function previewVoice(): Promise<void> {
  await speak(VOICE_PREVIEW, { rate: 0.9 });
}

const contentSummary = computed(() => {
  const bundle = contentStore.bundle;
  return {
    version: bundle.manifest.content_version,
    counts: {
      characters: bundle.characters.length,
      poems: bundle.poems.length,
      lessons: bundle.lessons.length,
    },
  };
});

const appVersion = __APP_VERSION__;

/** 头像 URL：动物头像走本地 SVG。 */
function avatarSrc(key: string | null | undefined): string {
  return `/avatars/${key || DEFAULT_AVATAR}.svg`;
}

function syncFromCurrent(): void {
  const child = current.value;
  if (!child) return;
  newCharTarget.value = child.daily_new_char_target;
  reviewTarget.value = child.daily_review_target;
  timeLimit.value = child.daily_time_limit_min;
}

onMounted(() => {
  syncFromCurrent();
  if (!children.value.length) newNickname.value = '';
});
watch(() => current.value?._id, syncFromCurrent);

async function changeAvatar(key: string): Promise<void> {
  const child = current.value;
  if (!child || key === child.avatar_key) return;
  try {
    await childStore.update(child._id, { avatar_key: key });
    toast.success('头像已更新');
  } catch (err) {
    toast.error(err instanceof Error ? err.message : '头像更新失败');
  }
}

async function addChild(): Promise<void> {
  if (!newNickname.value.trim()) {
    toast.warn('请输入昵称');
    return;
  }
  try {
    await childStore.create({
      nickname: newNickname.value.trim(),
      grade: newGrade.value,
      avatarKey: newAvatar.value,
    });
    newNickname.value = '';
    newAvatar.value = DEFAULT_AVATAR;
    toast.success('已创建新档案');
  } catch (err) {
    toast.error(err instanceof Error ? err.message : '创建档案失败');
  }
}

function switchChild(id: string): void {
  childStore.setCurrent(id);
  toast.show('已切换学习档案');
}

const pendingArchive = ref<string | null>(null);

/** 归档采用两步确认（服务端软删除，学习记录不物理删除）。 */
async function archiveChild(id: string, nickname: string): Promise<void> {
  if (pendingArchive.value !== id) {
    pendingArchive.value = id;
    toast.warn(`再点一次「确认归档」即归档「${nickname}」（学习记录不会被删除）`);
    return;
  }
  pendingArchive.value = null;
  try {
    await childStore.remove(id);
    toast.success('已归档该档案');
  } catch (err) {
    toast.error(err instanceof Error ? err.message : '归档失败');
  }
}

async function saveSettings(): Promise<void> {
  const child = current.value;
  if (!child) return;
  try {
    await childStore.update(child._id, {
      daily_new_char_target: Math.max(1, Math.min(30, newCharTarget.value)),
      daily_review_target: Math.max(1, Math.min(100, reviewTarget.value)),
      daily_time_limit_min: Math.max(5, Math.min(120, timeLimit.value)),
    });
    toast.success('学习计划已保存');
  } catch (err) {
    toast.error(err instanceof Error ? err.message : '保存失败');
  }
}

function doExport(): void {
  if (current.value) void exportChild(current.value._id);
}

// ---- 账号 ----
const pendingLogout = ref(false);

async function doLogout(): Promise<void> {
  await auth.logout();
  toast.show('已退出登录');
  await router.replace({ name: 'login' });
}

function onLogoutClick(): void {
  if (!pendingLogout.value) {
    pendingLogout.value = true;
    ui.openModal('退出登录？', '本机只会清除登录凭证，学习数据都保存在服务端，重新登录即可看到。');
    return;
  }
  void doLogout();
}

const pendingDelete = ref(false);

function onDeleteClick(): void {
  if (!pendingDelete.value) {
    pendingDelete.value = true;
    ui.openModal(
      '注销并删除云端数据？',
      '将删除该账号及其名下全部孩子档案与学习记录，**不可恢复**。建议先导出数据。',
    );
    return;
  }
  void doDeleteAccount();
}

async function doDeleteAccount(): Promise<void> {
  try {
    await auth.deleteAccount();
    toast.show('账号已注销');
    await router.replace({ name: 'register' });
  } catch (err) {
    toast.error(err instanceof Error ? err.message : '注销失败，请稍后重试');
  }
}
</script>

<template>
  <section class="stack--lg stack">
    <!-- 档案管理 -->
    <BaseCard title="孩子档案" subtitle="一个账号下可放多个孩子的独立进度">
      <ul class="child-list">
        <li v-for="child in children" :key="child._id" class="child-item">
          <img class="child-item__avatar" :src="avatarSrc(child.avatar_key)" alt="" />
          <div class="child-item__main">
            <span class="child-item__name">{{ child.nickname }}</span>
            <span class="text-sm text-muted">
              {{ gradeLabel(child.grade) }} · 已学 {{ child.stats.total_learned }} 字
            </span>
          </div>
          <span v-if="child._id === current?._id" class="pill">当前</span>
          <BaseButton v-else variant="secondary" @click="switchChild(child._id)">切换</BaseButton>
          <BaseButton variant="ghost" @click="archiveChild(child._id, child.nickname)">
            {{ pendingArchive === child._id ? '确认归档' : '归档' }}
          </BaseButton>
        </li>
      </ul>

      <hr class="divider" />

      <div class="stack--sm stack">
        <p class="section-title">新建档案</p>
        <label class="field">
          <span class="field__label">昵称</span>
          <input v-model="newNickname" class="field__input tap" type="text" maxlength="12" placeholder="例如：小兔子" />
        </label>
        <label class="field">
          <span class="field__label">年级</span>
          <select v-model.number="newGrade" class="field__input tap">
            <option v-for="opt in gradeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </label>
        <div class="field">
          <span class="field__label">头像</span>
          <AvatarPicker v-model="newAvatar" :size="52" />
        </div>
        <BaseButton block @click="addChild">创建档案</BaseButton>
      </div>
    </BaseCard>

    <!-- 头像 -->
    <BaseCard v-if="current" title="头像" subtitle="默认是小兔子；换一个孩子喜欢的伙伴吧">
      <AvatarPicker
        :model-value="current.avatar_key || DEFAULT_AVATAR"
        :size="60"
        @update:model-value="changeAvatar"
      />
    </BaseCard>

    <!-- 学习设置 -->
    <BaseCard v-if="current" title="学习计划" subtitle="P-04 自定义每日目标 · P-02 时长自控">
      <div class="grid grid--2">
        <label class="field">
          <span class="field__label">每日新学字数</span>
          <input v-model.number="newCharTarget" class="field__input tap" type="number" min="1" max="30" />
        </label>
        <label class="field">
          <span class="field__label">每日复习字数</span>
          <input v-model.number="reviewTarget" class="field__input tap" type="number" min="1" max="100" />
        </label>
        <label class="field">
          <span class="field__label">每日时长上限（分钟）</span>
          <input v-model.number="timeLimit" class="field__input tap" type="number" min="5" max="120" />
        </label>
      </div>
      <p class="text-sm text-muted settings-note">
        时长上限为温和提醒，到达后会建议休息；不会强制中断学习。
      </p>
      <template #footer>
        <BaseButton block @click="saveSettings">保存设置</BaseButton>
      </template>
    </BaseCard>

    <!-- 朗读设置：音色与语速 -->
    <BaseCard title="朗读" subtitle="音色与语速都可以按孩子的听感调">
      <template v-if="!canSpeak">
        <p class="info-box">
          这台设备不支持语音朗读（浏览器没有提供朗读能力），朗读按钮会自动隐藏。
        </p>
      </template>

      <template v-else>
        <label class="field">
          <span class="field__label">朗读音色</span>
          <select
            v-if="voices.length"
            class="field__input tap"
            :value="voiceURI"
            @change="onVoiceChange"
          >
            <option value="">自动挑选（推荐）</option>
            <option v-for="v in voices" :key="v.voiceURI" :value="v.voiceURI">
              {{ v.name }}{{ v.localService ? '' : '（需联网）' }}
            </option>
          </select>
          <input v-else class="field__input" type="text" value="正在读取本机音色…" disabled />
        </label>

        <p class="text-sm text-muted settings-note">
          <template v-if="!voices.length">
            正在读取本机音色。若一直没有出现，说明这台设备只装了默认音色 ——
            系统与浏览器决定了可用音色，应用侧无法新增。
          </template>
          <template v-else>
            不同设备的音色差别很大：默认音色有时是「老式朗读机」，机械且听不清声调。
            换一个试试，直到孩子听着舒服为止。
          </template>
        </p>

        <BaseButton variant="secondary" size="md" @click="previewVoice">
          试听一下
        </BaseButton>
        <p class="text-sm text-muted settings-note">试听读的是「山、水、火」—— 声调差别大，最容易听出好坏。</p>
      </template>
    </BaseCard>

    <!-- 数据导出 -->
    <BaseCard title="导出学习数据" subtitle="I-04 数据可迁移性 · P-05 数据说明">
      <p class="info-box">
        ✅ 学习进度保存在<strong>服务端</strong>，换设备或换浏览器只要重新登录就能看到全部记录，
        不再需要手动导入。
      </p>
      <p class="text-sm text-muted settings-note">
        导出得到一个 JSON 文件，包含该孩子的复习计划、答题明细、错题本与徽章，
        可长期留存或用于自行分析。
      </p>
      <div class="row row--wrap backup-actions">
        <BaseButton :disabled="!current || exporting" @click="doExport">
          {{ exporting ? '正在导出…' : '导出进度文件' }}
        </BaseButton>
      </div>
    </BaseCard>

    <!-- 账号 -->
    <BaseCard title="账号" subtitle="数据存于服务端，请妥善保管恢复码">
      <div class="stack--sm stack">
        <p class="text-sm">
          <strong>昵称：</strong>{{ auth.account?.display_name || '—' }}
        </p>
        <p class="text-sm text-muted">
          邀请码身份不含手机号、微信与实名信息；密码为自设口令，服务端只存哈希。
        </p>
      </div>
      <template #footer>
        <div class="row row--wrap backup-actions">
          <BaseButton variant="secondary" @click="onLogoutClick">
            {{ pendingLogout ? '再点一次，确认退出' : '退出登录' }}
          </BaseButton>
          <BaseButton variant="danger" @click="onDeleteClick">
            {{ pendingDelete ? '再点一次，确认注销' : '注销账号' }}
          </BaseButton>
        </div>
      </template>
    </BaseCard>

    <!-- 隐私说明 -->
    <BaseCard title="隐私说明" subtitle="R-01 数据仅用于本产品 · R-02 儿童信息零收集">
      <div class="stack--sm stack">
        <p>
          <strong>数据在哪里：</strong>学习进度、档案、复习计划保存在本产品自有服务器，
          仅与该账号绑定，不用于任何广告或第三方投放。
        </p>
        <p>
          <strong>我们收集什么：</strong>仅孩子昵称、年级与头像选择（用于按年级推荐内容与界面展示）。
          <strong>不收集</strong>手机号、真实姓名、照片、位置信息。
        </p>
        <p>
          <strong>可迁移性：</strong>你可以随时在「导出学习数据」里把全部记录导出为一个 JSON 文件；
          也可以直接注销账号删除云端全部数据。
        </p>
        <p class="text-sm text-muted">
          服务端会记录常规访问日志（IP、时间、UA）用于安全审计；匿名统计若启用，只上报聚合行为计数，不含任何个人标识。
        </p>
      </div>
    </BaseCard>

    <!-- 第三方许可 -->
    <BaseCard title="第三方许可" subtitle="R-03 法定义务，随分发生效">
      <ul class="license-list text-sm">
        <li>汉字拼音数据 <em>pinyin-data</em>（MIT）—— 校对拼音与声调</li>
        <li>笔顺数据 <em>hanzi-writer-data</em>（CC BY-SA 4.0 / MIT）—— 书写笔顺练习</li>
        <li>古诗数据集 <em>chinese-poetry</em>（MIT）—— 校对古诗原文（原文属公有领域）</li>
        <li>本项目代码：MIT；内容：CC BY-SA 4.0</li>
      </ul>
      <p class="text-sm text-muted">完整许可全文见仓库 <code>THIRD_PARTY_NOTICES.md</code> 与 <code>licenses/</code>。</p>
    </BaseCard>

    <!-- 关于 -->
    <BaseCard title="关于">
      <div class="stack--sm stack text-sm">
        <p>应用版本：{{ appVersion }}</p>
        <p>内容版本：{{ contentSummary.version }}</p>
        <p>
          当前内容：{{ contentSummary.counts.characters ?? 0 }} 字 ·
          {{ contentSummary.counts.poems ?? 0 }} 首古诗 ·
          {{ contentSummary.counts.lessons ?? 0 }} 个关卡
        </p>
      </div>
    </BaseCard>
  </section>
</template>

<style scoped>
.child-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.child-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
  flex-wrap: wrap;
}

.child-item__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--color-surface);
  object-fit: contain;
  flex: none;
}

.child-item__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  margin-right: auto;
}

.child-item__name {
  font-weight: 600;
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.field__label {
  font-size: var(--font-sm);
  color: var(--color-text-muted);
}

.field__input {
  width: 100%;
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.settings-note {
  margin-top: var(--space-sm);
}

.info-box {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--color-primary) 12%, var(--color-surface));
}

.backup-actions {
  margin-top: var(--space-md);
}

.license-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  margin-bottom: var(--space-sm);
}

.license-list em {
  font-style: normal;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
</style>
