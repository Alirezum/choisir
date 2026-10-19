<script setup lang="ts">
const logFile = defineModel<string>('log', { required: true })
const seed = defineModel<string>('seed', { required: true })
const dryRun = defineModel<boolean>('dry', { required: true })
const includeHidden = defineModel<boolean>('hidden', { required: true })
const mode = defineModel<'all' | 'files' | 'dirs'>('mode', { required: true })
</script>

<template>
  <div class="panel options">
    <label class="field">
      <span>Log file</span>
      <input v-model="logFile" placeholder="empty = &lt;directory&gt;/.choosier.jsonl" />
    </label>
    <label class="field">
      <span>Seed</span>
      <input v-model="seed" placeholder="empty = random" />
    </label>
    <label class="check">
      <input v-model="dryRun" type="checkbox" />
      Dry run (don't log)
    </label>
    <label class="check">
      <input v-model="includeHidden" type="checkbox" />
      Include hidden
    </label>
    <fieldset class="mode">
      <legend>Mode</legend>
      <label><input v-model="mode" type="radio" value="all" /> Files and dirs</label>
      <label><input v-model="mode" type="radio" value="files" /> Files only</label>
      <label><input v-model="mode" type="radio" value="dirs" /> Dirs only</label>
    </fieldset>
  </div>
</template>
