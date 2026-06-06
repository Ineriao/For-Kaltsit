<template>
  <div class="pet-root">
    <video
      class="pet-video"
      :src="currentSrc"
      autoplay
      loop
      muted
      playsinline
      preload="auto"
      @dblclick.stop="$emit('open-chat')"
      @contextmenu.prevent="showMenu"
    />
  </div>
</template>

<script setup>
import { onUnmounted } from 'vue'

defineEmits(['open-chat'])

const BASE = 'http://127.0.0.1:8765/model'
const currentSrc = `${BASE}/Relax_alpha.webm`

function showMenu() {
  window.electronAPI?.showPetMenu()
}

onUnmounted(() => {})
</script>

<style scoped>
.pet-root {
  width: 800px;
  height: 800px;
  background: transparent;
  overflow: hidden;
  position: relative;
}

.pet-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center bottom;
  display: block;
  cursor: url('/cursors/Kaltsit-Link.ani'), pointer;
}
</style>
