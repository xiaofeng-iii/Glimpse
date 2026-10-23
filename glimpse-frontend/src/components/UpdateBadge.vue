<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDownTrayIcon } from '@heroicons/vue/24/outline'
import { useUpdatesStore } from '@/stores/updates'
import { useNotificationStore } from '@/stores/notification'
import UpdateNotesContent from '@/components/UpdateNotesContent.vue'
import UpdateNotesPopover from '@/components/UpdateNotesPopover.vue'
import { t } from '@/utils/i18n'

const router = useRouter()
const updates = useUpdatesStore()
const notifications = useNotificationStore()

const updatePopoverOpen = ref(false)

const viewDetails = async () => {
  updatePopoverOpen.value = false
  await router.push({ path: '/settings', query: { section: 'updates' } })
}

const installNow = async () => {
  const ok = await updates.installUpdate()
  if (!ok) {
    updatePopoverOpen.value = false
    notifications.show(t('settings.updateInstallFailed'), 'error')
  }
}
</script>

<template>
  <UpdateNotesPopover
    v-if="updates.showAvailableBadge && updates.availableUpdate"
    v-model:open="updatePopoverOpen"
    :label="t('settings.updateAvailable', { version: updates.availableUpdate.version })"
  >
    <template #trigger>
      <button
        v-hint-tooltip="t('updates.badgeAvailable')"
        type="button"
        class="shell-icon-button update-badge update-badge--available"
        :aria-label="t('updates.badgeAvailable')"
      >
        <ArrowDownTrayIcon class="h-[15px] w-[15px]" aria-hidden="true" />
      </button>
    </template>
    <UpdateNotesContent :notes="updates.updateNotes" />
    <template #footer>
      <!-- 查看详情只是跳转设置页，下载安装状态在全局 store，不随导航丢失，下载中保持可点 -->
      <button type="button" class="btn-secondary" @click="viewDetails">
        {{ t('updates.viewDetails') }}
      </button>
      <button type="button" class="btn-primary" :disabled="updates.installing" @click="installNow">
        {{ updates.installing ? t('settings.updateInstalling') : t('settings.updateNow') }}
      </button>
    </template>
  </UpdateNotesPopover>
</template>

<style scoped>
/* 顶栏图标按钮与设置齿轮同尺寸同 hover：28px 见方、纯背景反馈，不位移。 */
.update-badge {
  width: 1.75rem;
  height: 1.75rem;
  min-height: 1.75rem;
}

.update-badge:hover {
  transform: none;
}
</style>
