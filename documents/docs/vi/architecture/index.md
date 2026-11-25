---
title: Kiến trúc dự án Py-Xiaozhi
description: Client trợ lý giọng nói Xiaozhi xây dựng trên Python theo thiết kế mô-đun, hỗ trợ đa giao thức truyền thông và tích hợp thiết bị
sidebar: false
pageClass: architecture-page-class
---
<script setup>
import CoreArchitecture from './components/CoreArchitecture.vue'
import ModuleDetails from './components/ModuleDetails.vue'
import TechnologyStack from './components/TechnologyStack.vue'
import ArchitectureFeatures from './components/ArchitectureFeatures.vue'
</script>

<div class="architecture-page">

# Kiến trúc dự án Py-Xiaozhi

<p class="page-description">Client trợ lý giọng nói Xiaozhi xây dựng trên Python theo thiết kế mô-đun, hỗ trợ đa giao thức truyền thông và tích hợp thiết bị</p>

## Kiến trúc cốt lõi

<CoreArchitecture/>

## Chi tiết các mô-đun

<ModuleDetails/>

## Công nghệ sử dụng

<TechnologyStack/>

## Đặc điểm kiến trúc

<ArchitectureFeatures/>
</div>

<style>
.page-description {
  font-size: 1.125rem;
  color: var(--vp-c-text-2);
  margin-bottom: 2rem;
  line-height: 1.6;
}
</style>

<style>
.architecture-page {
  max-width: 100%;
  padding: 0 2rem;
}
</style>
