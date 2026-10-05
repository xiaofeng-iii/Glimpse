<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowDownTrayIcon,
  SparklesIcon,
} from '@heroicons/vue/24/outline'
import { useUpdatesStore } from '@/stores/updates'
import { useNotificationStore } from '@/stores/notification'
import UpdateNotesContent from '@/components/UpdateNotesContent.vue'
import UpdateNotesPopover from '@/components/UpdateNotesPopover.vue'
import { t } from '@/utils/i18n'

const router = useRouter()
const updates = useUpdatesStore()
const notifications = useNotificationStore()

const updatePopoverOpen = ref(false)
const notesPopoverOpen = ref(false)

watch(notesPopoverOpen, (open) => {
  if (!open) return
  void updates.loadCurrentNotes()
  updates.dismissJustUpdated()
})

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
        type="button"
        class="shell-icon-button update-badge update-badge--available"
        :title="t('updates.badgeAvailable')"
        :aria-label="t('updates.badgeAvailable')"
      >
        <ArrowDownTrayIcon class="h-[15px] w-[15px]" aria-hidden="true" />
      </button>
    </template>
    <UpdateNotesContent
      :notes="updates.updateNotes"
      :loading="updates.updateNotesLoading"
      :partial="updates.updateNotesPartial"
      :raw="updates.updateNotesPartial ? updates.availableUpdate.notes ?? '' : undefined"
    />
    <div class="mt-4 flex items-center gap-2.5">
      <button type="button" class="btn-secondary btn-sm" :disabled="updates.installing" @click="viewDetails">
        {{ t('updates.viewDetails') }}
      </button>
      <button type="button" class="btn-primary btn-sm" :disabled="updates.installing" @click="installNow">
        {{ updates.installing ? t('settings.updateInstalling') : t('settings.updateNow') }}
      </button>
    </div>
  </UpdateNotesPopover>

  <UpdateNotesPopover
    v-else-if="updates.showJustUpdatedBadge"
    v-model:open="notesPopoverOpen"
    :label="t('updates.justUpdated', { version: updates.currentVersion })"
  >
    <template #trigger>
      <button
        type="button"
        class="shell-icon-button update-badge update-badge--notes"
        :title="t('updates.badgeJustUpdated')"
        :aria-label="t('updates.badgeJustUpdated')"
      >
        <SparklesIcon class="h-[15px] w-[15px]" aria-hidden="true" />
      </button>
    </template>
    <UpdateNotesContent
      :notes="updates.currentNotes"
      :loading="updates.currentNotesLoading"
      :error="updates.currentNotesError ? t(updates.currentNotesError) : ''"
    />
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
