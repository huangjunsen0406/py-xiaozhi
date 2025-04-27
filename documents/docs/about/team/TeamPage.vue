<script lang="ts">
import type { Member } from './Member'

const shuffleMembers = (
  members: Member[],
  pinTheFirstMember = false
): void => {
  let offset = pinTheFirstMember ? 1 : 0
  // `i` is between `1` and `length - offset`
  // `j` is between `0` and `length - offset - 1`
  // `offset + i - 1` is between `offset` and `length - 1`
  // `offset + j` is between `offset` and `length - 1`
  let i = members.length - offset
  while (i > 0) {
    const j = Math.floor(Math.random() * i)
    ;[members[offset + i - 1], members[offset + j]] = [
      members[offset + j],
      members[offset + i - 1]
    ]
    i--
  }
}
</script>

<script setup lang="ts">
// @ts-ignore
import { VTLink } from '@vue/theme'
// @ts-ignore
import membersCoreData from './members-core.json'
// @ts-ignore
import membersPartnerData from './members-partner.json'
import TeamHero from './TeamHero.vue'
// @ts-ignore
import TeamList from './TeamList.vue'

shuffleMembers(membersCoreData, true)
shuffleMembers(membersPartnerData)
</script>

<template>
  <div class="TeamPage">
    <TeamHero>
      <template #title>团队成员</template>
      <template #lead>
        py-xiaozhi项目的开发和维护由社区人员负责，
        以下是核心团队成员以及社区贡献者的部分信息。
      </template>
    </TeamHero>

    <TeamList :members="membersCoreData">
      <template #title>核心团队成员</template>
      <template #lead>
        核心团队成员积极参与项目开发和维护，对py-xiaozhi项目做出了重大贡献。
      </template>
    </TeamList>

    <TeamList :members="membersPartnerData">
      <template #title>社区贡献者</template>
      <template #lead>
        感谢以下社区成员在项目初期提供的帮助和支持。
      </template>
    </TeamList>
  </div>
</template>

<style scoped>
.TeamPage {
  padding-bottom: 16px;
}

@media (min-width: 768px) {
  .TeamPage {
    padding-bottom: 96px;
  }
}

.TeamList + .TeamList {
  padding-top: 64px;
}

* {
  list-style: none;
}
</style>
