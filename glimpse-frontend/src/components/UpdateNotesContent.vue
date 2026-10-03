<script setup lang="ts">
import { computed } from 'vue'
import { t } from '@/utils/i18n'
import type { Notes } from '@/utils/updateNotes'
const props = defineProps<{ notes: Notes | null; loading?: boolean; partial?: boolean; raw?: string; error?: string }>()
const categories = ['features', 'improvements', 'fixes'] as const
const hasContent = computed(() => props.notes && (categories.some((key) => props.notes!.sections[key].length) || props.notes.miscellaneous.length))
</script>
<template>
  <div class="space-y-3 break-words text-sm text-[var(--shell-muted)]" aria-live="polite" :aria-busy="loading">
    <p v-if="loading" role="status">{{ t('settings.notesLoading') }}</p>
    <template v-else>
      <p v-if="partial" role="status">{{ t('settings.notesPartial') }}</p>
      <p v-if="error" role="status">{{ error }}</p>
      <div v-else-if="raw !== undefined" class="whitespace-pre-wrap">{{ raw || t('settings.notesUnavailable') }}</div>
      <template v-else-if="notes">
        <p v-if="!hasContent">{{ t('settings.notesUnavailable') }}</p>
        <section v-for="category in categories" :key="category">
          <h3 class="font-semibold text-[var(--shell-ink)]">{{ t(`settings.notes${category}`) }}</h3>
          <ul class="list-disc space-y-1 pl-5"><li v-for="(item, index) in notes.sections[category]" :key="index" class="whitespace-pre-wrap">{{ item }}</li></ul>
        </section>
        <section v-if="notes.miscellaneous.length"><h3 class="font-semibold text-[var(--shell-ink)]">{{ t('settings.notesMisc') }}</h3><p v-for="(body, index) in notes.miscellaneous" :key="index" class="whitespace-pre-wrap">{{ body }}</p></section>
      </template>
    </template>
  </div>
</template>
