<script setup lang="ts">
/** NotFoundView —— 404（含「被开关关闭的能力路由」的兜底落点）。 */
import { useRouter } from 'vue-router';

import BaseButton from '@/components/base/BaseButton.vue';
import BaseEmpty from '@/components/base/BaseEmpty.vue';

const router = useRouter();
</script>

<template>
  <section class="page">
    <BaseEmpty title="这个页面不存在" description="地址可能输错了，或者该功能当前未开启。">
      <BaseButton @click="router.replace({ name: 'home' })">回到今日学习</BaseButton>
    </BaseEmpty>
  </section>
</template>

<style scoped>
.page {
  padding-block: var(--space-lg);
}
</style>
