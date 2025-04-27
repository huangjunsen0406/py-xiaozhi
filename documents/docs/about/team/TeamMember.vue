<script setup lang="ts">
import { computed } from 'vue'
import {
  VTIconCode,
  VTIconCodePen,
  VTIconGitHub,
  VTIconGlobe,
  VTIconHeart,
  VTIconLink,
  VTIconLinkedIn,
  VTIconMapPin,
  VTIconX,
  VTLink
} from '@vue/theme'
import type { Member } from './Member'

const props = defineProps<{
  member: Member
}>()

const avatarUrl = computed(() => {
  return (
    props.member.avatarPic ??
    `https://www.github.com/${props.member.socials.github}.png`
  )
})

function arrayify(value: string | string[]): string[] {
  return Array.isArray(value) ? value : [value]
}
</script>

<template>
  <article class="TeamMember">
    <VTLink
      v-if="member.sponsor"
      class="sponsor"
      :href="`https://github.com/sponsors/${member.socials.github}`"
      no-icon
    >
      <VTIconHeart class="sponsor-icon" /> 赞助
    </VTLink>

    <div class="member-content">
      <figure class="avatar">
        <img
          class="avatar-img"
          :src="avatarUrl"
          :alt="`${member.name}'s Profile Picture`"
        />
      </figure>

      <div class="data">
        <h1 class="name">{{ member.name }}</h1>
        <p class="org">
          {{ member.title }}
          <span v-if="member.company" class="nowrap">
            @
            <VTLink
              v-if="member.companyLink"
              class="company link"
              :href="member.companyLink"
              :no-icon="true"
            >
              {{ member.company }}
            </VTLink>
            <span v-else class="company">
              {{ member.company }}
            </span>
          </span>
        </p>

        <div class="profiles">
          <section v-if="member.projects && member.projects.length > 0" class="desc">
            <div class="desc-title">
              <VTIconCode class="desc-icon code" />
            </div>
            <ul class="desc-list">
              <li
                v-for="project in member.projects"
                :key="project.label"
                class="desc-item"
              >
                <VTLink
                  class="desc-link"
                  :href="project.url"
                  :no-icon="true"
                >
                  {{ project.label }}
                </VTLink>
              </li>
            </ul>
          </section>

          <section class="desc">
            <div class="desc-title">
              <VTIconMapPin class="desc-icon" />
            </div>
            <ul class="desc-list">
              <li
                v-for="location in arrayify(member.location)"
                :key="location"
                class="desc-item"
              >
                {{ location }}
              </li>
            </ul>
          </section>

          <section class="desc">
            <div class="desc-title">
              <VTIconGlobe class="desc-icon" />
            </div>
            <ul class="desc-list">
              <li
                v-for="language in member.languages"
                :key="language"
                class="desc-item"
              >
                {{ language }}
              </li>
            </ul>
          </section>

          <section v-if="member.website" class="desc">
            <div class="desc-title">
              <VTIconLink class="desc-icon" />
            </div>
            <p class="desc-text">
              <VTLink
                class="desc-link"
                :href="member.website.url"
                :no-icon="true"
              >
                {{ member.website.label }}
              </VTLink>
            </p>
          </section>

          <div class="social-container">
            <ul class="social-list">
              <li v-if="member.socials.github" class="social-item">
                <VTLink
                  class="social-link"
                  :href="`https://github.com/${member.socials.github}`"
                  :no-icon="true"
                >
                  <VTIconGitHub class="social-icon" />
                </VTLink>
              </li>
              <li v-if="member.socials.twitter" class="social-item">
                <VTLink
                  class="social-link"
                  :href="`https://twitter.com/${member.socials.twitter}`"
                  :no-icon="true"
                >
                  <VTIconX class="social-icon" />
                </VTLink>
              </li>
              <li v-if="member.socials.linkedin" class="social-item">
                <VTLink
                  class="social-link"
                  :href="`https://www.linkedin.com/in/${member.socials.linkedin}`"
                  :no-icon="true"
                >
                  <VTIconLinkedIn class="social-icon" />
                </VTLink>
              </li>
              <li v-if="member.socials.codepen" class="social-item">
                <VTLink
                  class="social-link"
                  :href="`https://codepen.io/${member.socials.codepen}`"
                  :no-icon="true"
                >
                  <VTIconCodePen class="social-icon" />
                </VTLink>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </article>
</template>

<style scoped>
.TeamMember {
  position: relative;
  background-color: var(--vt-c-bg-soft);
  transition: background-color 0.5s;
  border-radius: 8px;
  padding: 32px;
  margin-bottom: 20px;
}

.member-content {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
}

@media (max-width: 511px) {
  .member-content {
    flex-direction: column;
    align-items: center;
  }
}

.vp-doc li + li {
  margin-top: 0;
}

.sponsor {
  position: absolute;
  top: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  border: 1px solid #fd1d7c;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 500;
  color: #fd1d7c;
  transition: color 0.25s, background-color 0.25s;
}

.sponsor:hover {
  color: var(--vt-c-white);
  background-color: #fd1d7c;
}

.sponsor-icon {
  margin-right: 6px;
  width: 14px;
  height: 14px;
  fill: currentColor;
}

.avatar {
  flex-shrink: 0;
  margin: 0;
  display: flex;
  justify-content: flex-start;
  margin-right: 24px;
}

@media (max-width: 511px) {
  .avatar {
    justify-content: center;
    margin-right: 0;
    margin-bottom: 16px;
  }
}

.avatar-img {
  border-radius: 50%;
  width: 110px;
  height: 110px;
  object-fit: cover;
}

.data {
  flex: 1;
  padding-top: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

@media (max-width: 511px) {
  .data {
    padding-top: 16px;
    align-items: center;
    text-align: center;
  }
}

.name {
  font-size: 22px;
  font-weight: 600;
  margin: 0;
}

.org {
  padding-top: 4px;
  line-height: 20px;
  max-width: 320px;
  font-size: 16px;
  font-weight: 500;
  color: var(--vt-c-text-2);
  transition: color 0.5s;
  margin: 0;
}

.company {
  color: var(--vt-c-text-1);
  transition: color 0.25s;
}

.company.link:hover {
  color: var(--vt-c-brand);
  transition: color 0.5s;
}

.profiles {
  padding-top: 16px;
}

@media (max-width: 511px) {
  .profiles {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
}

.desc {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

@media (max-width: 511px) {
  .desc {
    justify-content: center;
  }
}

.desc-title {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
  margin-right: 12px;
  height: 20px;
}

.desc-icon {
  width: 18px;
  height: 18px;
  fill: var(--vt-c-text-2);
  transition: fill 0.25s;
}

.desc-icon.code {
  transform: translateY(1px);
}

.desc-list {
  display: flex;
  flex-wrap: wrap;
  margin: 0;
  padding: 0;
  list-style: none;
}

@media (max-width: 511px) {
  .desc-list {
    justify-content: center;
  }
  
  .desc-text {
    text-align: center;
  }
}

.desc-item {
  line-height: 20px;
  font-size: 14px;
  font-weight: 500;
  color: var(--vt-c-text-1);
  transition: color 0.5s;
}

.desc-item::after {
  margin: 0 8px;
  content: '•';
  color: var(--vt-c-text-3);
  transition: color 0.25s;
}

.desc-item:last-child::after {
  display: none;
}

.desc-text {
  line-height: 20px;
  font-size: 14px;
  font-weight: 500;
  color: var(--vt-c-text-1);
  transition: color 0.25s;
  margin: 0;
}

.desc-link {
  line-height: 20px;
  font-size: 14px;
  font-weight: 500;
  color: var(--vt-c-brand);
  transition: color 0.25s;
}

.desc-link:hover {
  color: var(--vt-c-brand-dark);
}

.social-container {
  margin-top: 12px;
}

.social-list {
  display: flex;
  flex-wrap: wrap;
  padding: 0;
  margin: 0;
  list-style: none;
}

@media (max-width: 511px) {
  .social-container {
    width: 100%;
    display: flex;
    justify-content: center;
  }
  
  .social-list {
    justify-content: center;
  }
}

.social-item {
  margin-right: 12px;
}

.social-link {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 32px;
  height: 32px;
  color: var(--vt-c-text-2);
  transition: color 0.25s;
}

.social-link:hover {
  color: var(--vt-c-text-1);
}

.social-icon {
  width: 24px;
  height: 24px;
  fill: currentColor;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

.nowrap {
  white-space: nowrap;
}
</style>
