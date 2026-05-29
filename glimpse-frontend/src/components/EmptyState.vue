<script setup lang="ts">
</script>

<template>
  <div class="flex flex-col items-center justify-center py-16 text-center">
    <!-- Icon -->
    <div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-violet-100 to-pink-100 flex items-center justify-center mb-6">
      <svg class="w-10 h-10 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    </div>

    <!-- Text -->
    <h3 class="text-lg font-medium text-gray-900 mb-2">暂无记忆</h3>
    <p class="text-gray-500 text-sm mb-4">按截图快捷键开始记录</p>

    <!-- Shortcut -->
    <div class="empty-shortcut flex items-center gap-2">
      <kbd class="empty-shortcut-key px-3 py-1.5 rounded-lg text-sm">Ctrl</kbd>
      <span class="empty-shortcut-plus">+</span>
      <kbd class="empty-shortcut-key px-3 py-1.5 rounded-lg text-sm">Shift</kbd>
      <span class="empty-shortcut-plus">+</span>
      <kbd class="empty-shortcut-key px-3 py-1.5 rounded-lg text-sm">G</kbd>
    </div>
  </div>
</template>

<style scoped>
.empty-shortcut {
  color: rgba(23, 32, 51, 0.84);
  font-weight: 700;
}

.empty-shortcut-plus {
  color: var(--shell-accent);
  opacity: 0.92;
}

.empty-shortcut-key {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(35, 93, 103, 0.18);
  color: var(--shell-highlight-strong);
  font-weight: 700;
  box-shadow: 0 8px 18px rgba(35, 93, 103, 0.08);
}
</style>
