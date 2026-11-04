<script setup lang="ts">
defineProps<{ message: string }>()
</script>

<template>
  <footer class="status" role="status" aria-live="polite">
    {{ message }}
  </footer>
</template>
