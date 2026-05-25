<script setup lang="ts">
import type { Member } from './Member'
import TeamMember from './TeamMember.vue'

defineProps<{
  members: Member[]
}>()
</script>

<template>
  <section class="TeamList">
    <div class="container">
      <div class="info">
        <h2 class="title">
          <slot name="title" />
        </h2>
        <p class="lead">
          <slot name="lead" />
        </p>
      </div>

      <div class="members">
        <!-- to skip SSG since the members are shuffled -->
        <ClientOnly>
          <div v-for="member in members" :key="member.name" class="member">
            <TeamMember :member="member" />
          </div>
        </ClientOnly>
      </div>
    </div>
  </section>
</template>

<style scoped>
@media (min-width: 768px) {
  .TeamList {
    padding: 0 32px;
  }
}

.container {
  border-top: 1px solid var(--vt-c-divider-light);
  padding-top: 24px;
}

@media (min-width: 768px) {
  .container {
    margin: 0 auto;
    display: flex;
    align-items: flex-start;
    max-width: 960px;
  }
}

.info {
  flex-shrink: 0;
  padding: 0 24px;
  max-width: 512px;
}

@media (min-width: 768px) {
  .info {
    position: sticky;
    top: calc(var(--vt-banner-height, 0px) + 32px);
    left: 0;
    padding: 0 24px 0 0;
    width: 256px;
  }

  html.banner-dismissed .info {
    top: 32px;
  }
}

@media (min-width: 960px) {
  .info {
    top: calc(var(--vt-banner-height, 0px) + 88px);
    padding: 0 64px 0 0;
    width: 384px;
  }

  html.banner-dismissed .info {
    top: 88px;
  }
}

.title {
  font-size: 20px;
  font-weight: 500;
}

.lead {
  padding-top: 8px;
  line-height: 24px;
  font-size: 14px;
  font-weight: 500;
  color: var(--vt-c-text-2);
}

.members {
  padding-top: 24px;
}

@media (min-width: 768px) {
  .members {
    flex-grow: 1;
    padding-top: 0;
  }
}

.member + .member {
  padding-top: 16px;
}

@media (min-width: 640px) {
  .member {
    margin: 0 auto;
    max-width: 592px;
  }
}

@media (min-width: 768px) {
  .member {
    margin: 0;
    max-width: 100%;
  }
}
</style>
