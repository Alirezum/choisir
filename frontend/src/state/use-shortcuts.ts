import { onMounted, onUnmounted, type Ref } from 'vue'

export interface ShortcutsDeps {
  pick: () => Promise<void> | void
  clearing: Ref<boolean>
}

export interface ShortcutsBinding {
  onKeydown: (event: KeyboardEvent) => void
}

/**
 * Registers the Ctrl+N shortcut. The block condition is the baseline one: the
 * clear confirmation flag or an open dialog/viewer overlay.
 */
export function useShortcuts(deps: ShortcutsDeps): ShortcutsBinding {
  function onKeydown(event: KeyboardEvent): void {
    if (!event.ctrlKey || event.key.toLowerCase() !== 'n') return
    event.preventDefault()
    if (
      deps.clearing.value ||
      document.querySelector('.viewer-overlay, .overlay') !== null
    ) {
      return
    }
    void deps.pick()
  }

  onMounted(() => {
    window.addEventListener('keydown', onKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', onKeydown)
  })

  return { onKeydown }
}
