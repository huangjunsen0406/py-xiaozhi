<script setup>
import { nextTick, onMounted, onUnmounted, ref } from 'vue'

const isVisible = ref(true)
const bannerRef = ref(null)

const updateLayoutOffset = () => {
  if (typeof window === 'undefined') return
  const height = isVisible.value && bannerRef.value ? bannerRef.value.offsetHeight : 0
  document.documentElement.style.setProperty('--vp-banner-height', `${height}px`)
}

const closeBanner = () => {
  isVisible.value = false
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('gitee-vote-2025-banner', 'closed')
  }
  nextTick(() => {
    updateLayoutOffset()
  })
}

onMounted(() => {
  if (typeof localStorage !== 'undefined' && localStorage.getItem('gitee-vote-2025-banner') === 'closed') {
    isVisible.value = false
  }
  
  // Initial update
  nextTick(() => {
    updateLayoutOffset()
    window.addEventListener('resize', updateLayoutOffset)
  })
})

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', updateLayoutOffset)
    document.documentElement.style.removeProperty('--vp-banner-height')
  }
})
</script>

<template>
  <div v-if="isVisible" ref="bannerRef" class="vote-banner">
    <div class="banner-content">
      <div class="message">
        <span class="icon">🎉</span>
        <span class="text">我正在参加 Gitee 2025 最受欢迎的开源软件投票活动，快来给我投票吧！</span>
      </div>
      <a href="https://gitee.com/activity/2025opensource?ident=IDNAQF" target="_blank" class="action-btn">
        立即投票
      </a>
    </div>
    <button class="close-btn" @click="closeBanner" aria-label="Close banner">
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M13 1L1 13M1 1L13 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
  </div>
</template>

<style scoped>
.vote-banner {
  isolation: isolate;
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  z-index: 100;
  background: linear-gradient(135deg, #2b304c 0%, #1c1f30 100%);
  color: #fff;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--vp-font-family-base, 'Inter', sans-serif);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: all 0.3s ease;
}

.banner-content {
  display: flex;
  align-items: center;
  gap: 16px;
  max-width: 1280px;
  margin: 0 auto;
  flex-wrap: wrap;
  justify-content: center;
  padding-right: 24px;
}

.message {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
  letter-spacing: 0.01em;
}

.icon {
  font-size: 16px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(90deg, #42b883 0%, #34a770 100%);
  color: #fff !important;
  font-size: 13px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 99px;
  text-decoration: none;
  transition: all 0.2s cubic-bezier(0.165, 0.84, 0.44, 1);
  box-shadow: 0 2px 6px rgba(66, 184, 131, 0.3);
  white-space: nowrap;
}

.action-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(66, 184, 131, 0.4);
  background: linear-gradient(90deg, #4ac48d 0%, #3bb57b 100%);
}

.action-btn:active {
  transform: translateY(0);
  box-shadow: 0 1px 2px rgba(66, 184, 131, 0.2);
}

.close-btn {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  padding: 6px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background-color: rgba(255, 255, 255, 0.1);
  color: #fff;
}

@media (max-width: 640px) {
  .vote-banner {
    padding: 10px 16px;
  }
  
  .banner-content {
    gap: 12px;
    padding-right: 0;
    flex-direction: column;
    text-align: center;
  }

  .close-btn {
    top: 8px;
    transform: none;
    right: 8px;
  }
}
</style>
