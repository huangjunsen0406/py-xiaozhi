<script setup>
import { ref, onMounted } from 'vue'
import sponsorsData from './data.js'

const sponsors = ref([])
const isLoading = ref(true)
const error = ref(null)

onMounted(() => {
  try {
    // 直接使用导入的数据而不是通过fetch请求
    sponsors.value = sponsorsData.sponsors
    isLoading.value = false
  } catch (err) {
    console.error('加载赞助者数据失败:', err)
    error.value = '加载赞助者数据失败，请刷新页面重试'
    isLoading.value = false
  }
})
</script>

<template>
  <div class="sponsors-container">
    <!-- 头部信息 -->
    <div class="sponsor-header">
      <p>无论是接口资源、设备兼容测试还是资金支持，每一份帮助都让项目更加完善</p>
    </div>

    <!-- 赞助者列表 -->
    <div v-if="isLoading" class="loading">
      <p>正在加载赞助者信息...</p>
    </div>
    
    <div v-else-if="error" class="error">
      <p>{{ error }}</p>
    </div>
    
    <div v-else class="sponsors-grid">
      <div v-for="sponsor in sponsors" :key="sponsor.name" class="sponsor-item">
        <div class="sponsor-avatar">
          <img :src="sponsor.image" :alt="`${sponsor.name} 头像`" loading="lazy">
        </div>
        <div class="sponsor-name">
          <a v-if="sponsor.url" :href="sponsor.url" target="_blank" rel="noopener noreferrer">
            {{ sponsor.name }}
          </a>
          <span v-else>{{ sponsor.name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sponsors-container {
  width: 100%;
}

.sponsor-header {
  text-align: center;
  margin-bottom: 3rem;
}

.sponsors-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 2rem;
  margin: 3rem 0;
}

.sponsor-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  transition: transform 0.2s ease;
}

.sponsor-item:hover {
  transform: translateY(-5px);
}

.sponsor-avatar {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  overflow: hidden;
  margin-bottom: 0.75rem;
  border: 2px solid var(--vp-c-divider);
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.sponsor-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.sponsor-name {
  font-size: 1rem;
  font-weight: 500;
}

.sponsor-name a {
  color: var(--vp-c-brand);
  text-decoration: none;
}

.sponsor-name a:hover {
  text-decoration: underline;
}

.loading, .error {
  text-align: center;
  padding: 2rem;
  color: var(--vp-c-text-2);
}

@media (max-width: 768px) {
  .sponsors-grid {
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    gap: 1.5rem;
  }
  
  .sponsor-avatar {
    width: 70px;
    height: 70px;
  }
}
</style> 