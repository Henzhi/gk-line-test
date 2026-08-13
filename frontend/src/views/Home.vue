<template>
  <div>
    <el-card>
      <template #header>欢迎使用公考行测刷题系统</template>
      <div v-if="userInfo">
        <p>当前登录用户：<strong>{{ userInfo.username }}</strong></p>
        <p>用户ID：{{ userInfo.userId }}</p>
      </div>
      <p style="margin-top: 16px; color: #999">
        后端鉴权链路已打通：登录 / 注册 → JWT 签发 → 携带 token 访问受保护接口。
      </p>
      <p style="color: #999">接下来可以开始填充题库数据，接入刷题、模拟考试、错题本等模块。</p>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getUserInfo } from '../api/auth'

const userInfo = ref(null)

onMounted(async () => {
  try {
    const res = await getUserInfo()
    userInfo.value = res.data
  } catch (e) {
    // 错误已在拦截器处理
  }
})
</script>
