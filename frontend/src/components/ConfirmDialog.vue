<script setup lang="ts">
defineProps<{ message: string }>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <div class="overlay" @click.self="emit('cancel')">
    <div class="dialog">
      <p class="dialog-message">{{ message }}</p>
      <div class="dialog-actions">
        <button class="danger" @click="emit('confirm')">Yes, delete</button>
        <button @click="emit('cancel')">Cancel</button>
      </div>
    </div>
  </div>
</template>
