<script setup lang="ts">
import { Collection, HomeFilled, Picture, VideoCamera, List, Setting } from '@element-plus/icons-vue'
</script>

<template>
  <el-container style="min-height: 100vh">
    <el-header style="background: #001529; display: flex; align-items: center">
      <h1 style="color: #fff; margin: 0; font-size: 20px">
        建筑施工现场安全隐患AI识别系统
      </h1>
    </el-header>
    <el-container>
      <el-aside width="200px" style="background: #001529">
        <el-menu
          :default-active="$route.path"
          router
          background-color="#001529"
          text-color="#fff"
          active-text-color="#1890ff"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>首页</span>
          </el-menu-item>
          <el-menu-item index="/image-detect">
            <el-icon><Picture /></el-icon>
            <span>图片检测</span>
          </el-menu-item>
          <el-menu-item index="/video-detect">
            <el-icon><VideoCamera /></el-icon>
            <span>视频检测</span>
          </el-menu-item>
          <el-menu-item index="/history">
            <el-icon><List /></el-icon>
            <span>历史记录</span>
          </el-menu-item>
          <el-menu-item index="/cases">
            <el-icon><Collection /></el-icon>
            <span>案例库</span>
          </el-menu-item>
          <el-menu-item index="/profiles">
            <el-icon><Setting /></el-icon>
            <span>检测配置</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main style="background: #f0f2f5">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>
