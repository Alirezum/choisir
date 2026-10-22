<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

const props = defineProps<{ message: string }>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()

const dialog = ref<HTMLElement | null>(null)
const cancelButton = ref<HTMLButtonElement | null>(null)

const lines = computed(() => props.message.split('\n'))
const title = computed(() => lines.value[0] ?? props.message)
const detail = computed(() => lines.value.slice(1).join('\n'))

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('cancel')
    return
  }
  if (event.key !== 'Tab') return
  const buttons = dialog.value?.querySelectorAll<HTMLButtonElement>('button')
  if (buttons === undefined || buttons.length === 0) return
  const first = buttons[0]
  const last = buttons[buttons.length - 1]
  if (first === undefined || last === undefined) return
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

onMounted(() => {
  cancelButton.value?.focus()
})
</script>

<template>
  <div
    class="overlay"
    @click.self="emit('cancel')"
    @keydown="onKeydown"
  >
    <div
      ref="dialog"
      class="dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
    >
      <h2 id="confirm-title" class="dialog-title">{{ title }}</h2>
      <p v-if="detail !== ''" class="dialog-detail">{{ detail }}</p>
      <div class="dialog-actions">
        <button ref="cancelButton" type="button" @click="emit('cancel')">
          Keep history
        </button>
        <button class="danger" type="button" @click="emit('confirm')">
          Clear history
        </button>
      </div>
    </div>
  </div>
</template>
