<script setup lang="ts">
defineProps<{ headerClass?: string }>()
</script>

<template>
  <div class="panel">
    <div class="panel-header" :class="headerClass"><slot name="header" /></div>
    <slot />
    <div v-if="$slots.actions" class="panel-actions"><slot name="actions" /></div>
  </div>
</template>
