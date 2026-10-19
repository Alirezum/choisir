<script setup lang="ts">
defineProps<{ message: string }>()
</script>

<template>
  <div class="status">{{ message }}</div>
</template>
