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
      <template #title>Thành viên đội ngũ</template>
      <template #lead>
        Việc phát triển và bảo trì dự án py-xiaozhi được thực hiện bởi cộng đồng,
        dưới đây là thông tin về một số thành viên nòng cốt và người đóng góp cộng đồng.
      </template>
    </TeamHero>

    <TeamList :members="membersCoreData">
      <template #title>Thành viên nòng cốt</template>
      <template #lead>
        Các thành viên nòng cốt tích cực tham gia phát triển và bảo trì dự án, đóng góp quan trọng cho py-xiaozhi.
      </template>
    </TeamList>

    <TeamList :members="membersPartnerData">
      <template #title>Người đóng góp cộng đồng</template>
      <template #lead>
        Cảm ơn các thành viên cộng đồng sau đây đã hỗ trợ và đồng hành cùng dự án từ những ngày đầu.
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
