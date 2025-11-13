---
title: Py-Xiaozhi 项目架构
description: 基于 Python 实现的小智语音客户端，采用模块化设计，支持多种通信协议和设备集成
sidebar: false,
pageClass: architecture-page-class
---
<script setup>
import CoreArchitecture from './components/CoreArchitecture.vue'
import ModuleDetails from './components/ModuleDetails.vue'
import TechnologyStack from './components/TechnologyStack.vue'
import ArchitectureFeatures from './components/ArchitectureFeatures.vue'
</script>

<div class="architecture-page">

# Py-Xiaozhi 项目架构

<p class="page-description">基于 Python 实现的小智语音客户端，采用模块化设计，支持多种通信协议和设备集成</p>

## 核心架构

<CoreArchitecture/>

## 模块详情

<ModuleDetails/>

## 技术栈

<TechnologyStack/>

## 架构特点

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
