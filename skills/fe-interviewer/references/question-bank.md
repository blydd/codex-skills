# 企业级前端面试题库参考（面向 Vue 3 业务前端岗）

用途：作为**出题覆盖面清单与补充追问来源**。本技能默认使用固定 6 题（见 SKILL.md「固定 6 题」），**生成时直接套用 `assets/面试题与评分表模板.md`，不需要从本库重新挑题**；本库用于两个场景：① 面试官现场想临时加问时，从这里取追问点；② 需要按简历做定制题时，作为考点覆盖面核对清单。

## 模块与考察点

### 1. 项目与工程能力（JD 2 / 11 / 12）

- 独立负责项目的完整链路：需求评审 → 技术选型 → 任务拆解与排期 → 开发 → 联调 → 测试 → 上线 → 监控
- 页面/模块规模、线上量级（PV/DAU、首屏时间、打包体积）与量化方式（Lighthouse、Performance、埋点）
- 组件封装与复用：props / emit / 插槽 / v-model 的接口设计
- 不被后端阻塞的做法：接口约定先行、Mock 数据、契约测试
- 多任务优先级、需求变更控制、风险提前暴露、上线回滚方案

### 2. HTML / CSS（JD 3）

- 盒模型与 `box-sizing`、margin 重叠与 BFC、浮动塌陷与 clearfix
- 布局：flex（主轴/交叉轴、flex:1 的含义、min-width:0 的坑）、grid（fr、minmax、auto-fill）、圣杯/双飞翼（了解即可）
- 居中：flex / grid / 绝对定位 + transform / line-height
- 像素级还原：标注工具、reset、字体行高、二倍图、1px 边框、状态遗漏（空/加载/超长/错误）
- 响应式：viewport、媒体查询断点、rem + postcss-pxtorem、vw + postcss-px-to-viewport、容器查询 `@container`、srcset
- 选择器优先级与层叠、`!important` 的使用边界、z-index 与层叠上下文
- 动画与性能：transform/opacity 走合成层、`will-change`

### 3. 原生 JS 与 ES6（JD 4）

- 数据类型与判断、`typeof null`、NaN、浮点精度
- 作用域与闭包、暂时性死区、var/let/const 循环经典题
- `this` 四种绑定规则与箭头函数、call/apply/bind 与手写 bind
- 原型链、`new` 的过程、class 与继承
- 事件：事件流三阶段、事件委托、`stopPropagation` / `preventDefault`、target vs currentTarget
- 事件循环：宏任务/微任务、async/await 的执行时机、输出顺序题
- 深浅拷贝：`JSON.parse(JSON.stringify())` 的坑、`structuredClone`、带 WeakMap 的递归实现
- 防抖与节流（含手写）、柯里化、数组去重与扁平化
- ES6+：解构、模板字符串、Promise（all/allSettled/race）、Map/Set、可选链 `?.`、`??` vs `||`、模块化
- 常用原生 API：querySelector、classList、dataset、getBoundingClientRect、IntersectionObserver、MutationObserver、ResizeObserver、History API、localStorage/sessionStorage/Cookie 差异

### 4. 浏览器原理与网络（JD 5）

- 多进程/多线程架构、渲染进程内主线程与合成线程、JS 与渲染互斥
- 渲染流水线：DOM → CSSOM → 渲染树 → 布局 → 绘制 → 合成
- script 的 `defer` / `async`、CSS 是否阻塞渲染与 JS
- 重排 / 重绘 / 合成的区别与减少手段、强制同步布局（layout thrashing）
- 输入 URL 到页面显示：DNS、TCP 三次握手与四次挥手、TIME_WAIT、TLS 握手
- HTTP 缓存：强缓存（Cache-Control/Expires）与协商缓存（ETag/Last-Modified）、304
- 状态码：301/302/304/401/403/404/502/504
- HTTPS：混合加密、CA 证书、防中间人；HTTP/1.1 vs 2 vs 3（多路复用、队头阻塞、QUIC）
- 性能指标与优化：LCP / INP / CLS、懒加载、虚拟滚动、骨架屏、SSR/预渲染
- 存储：Cookie 属性（HttpOnly/Secure/SameSite）、LocalStorage/SessionStorage/IndexedDB

### 5. 网络请求与跨域（JD 6）

- 手写原生 XHR（readyState 五档、setRequestHeader 位置、超时、错误处理）
- fetch vs XHR：不 reject HTTP 错误、默认不带 Cookie、无超时与进度、AbortController
- axios：拦截器、取消请求、并发控制、统一错误处理
- 同源策略与跨域：CORS 响应头、简单请求 vs 预检 OPTIONS、`Access-Control-Max-Age`
- 解决方案：CORS、开发代理（Vite `server.proxy`）、Nginx 反向代理、JSONP、postMessage、WebSocket
- 请求头/响应头：Authorization、Cookie、Origin/Referer、Accept-Encoding、If-None-Match、Set-Cookie、ETag
- Content-Type：`application/json` / `x-www-form-urlencoded` / `multipart/form-data`（文件上传）
- 登录态：Cookie+Session vs Token/JWT、无感刷新、401 处理
- 上传进度（`xhr.upload.onprogress`）、大文件分片与断点续传（了解）
- 安全：XSS（不用 v-html 渲染用户输入、转义、CSP）、CSRF（SameSite、Token、校验 Origin）

### 6. Vue 3（JD 8，权重最高）

- `<script setup>` 与 Composition API、组合式函数 `useXxx`、对比 mixin 的优势
- `ref` vs `reactive`、`.value` 的由来、响应式丢失三坑（解构、整体替换、漏写 .value）
- 其他响应式 API：`toRefs`、`readonly`、`shallowRef`、`markRaw`、`toRaw`、`computed`
- 响应式原理：Proxy + Reflect、track/trigger、WeakMap→Map→Set 依赖结构、懒代理；对比 Vue 2 的 `Object.defineProperty`（`$set`、数组七个方法、初始化递归）
- vDOM 与 diff：同层比较、双端对比 + 最长递增子序列、patchFlag、静态提升、Block Tree、事件缓存
- `key` 的作用、为什么不能用 index 或 random
- 组件通信：props/emit、v-model（`modelValue` / `update:modelValue`、多 v-model、`defineModel`）、`defineExpose` + ref、provide/inject、Pinia、事件总线（mitt，Vue 3 已移除 `$on/$off`）、`$attrs`、插槽
- 生命周期映射、`setup` 在 beforeCreate 之前、`onUnmounted` 做清理
- 指令与语法：`v-if` vs `v-show`、v-if/v-for 优先级（Vue 3 中 v-if 更高）、`v-for` 的 key、`v-html` 的风险
- `computed` / `watch` / `watchEffect` 选型、`deep` 与 `immediate`
- `nextTick` 与异步批量更新、微任务队列
- Vue Router：hash vs history（刷新 404 与 Nginx `try_files`）、全局前置守卫做鉴权、路由懒加载、参数变化组件不刷新、动态路由与权限
- Pinia：无 mutations、state/getters/actions、`storeToRefs`、持久化插件；对比 Vuex
- UI 库：Element Plus / Ant Design Vue / Vant（Vue 3 版本对应）、按需引入 `unplugin-vue-components`、样式穿透 `:deep()`、主题定制、表格大数据量
- 项目配置：Vite 的 plugins/alias/proxy/manualChunks/base、环境变量 `VITE_` 前缀与 `import.meta.env`、TypeScript
- 打包优化：路由懒加载、按需引入、CDN + externals、Tree Shaking、gzip/brotli、图片 WebP、关闭 sourcemap、vendor 分包
- 部署：静态产物 + Nginx/OSS+CDN、history fallback、index.html no-cache + 带 hash 资源长缓存
- 常见坑：内存泄漏（定时器/监听/echarts 实例/事件总线未清理）、打包后白屏（base 配错 / 缺 fallback）、生产跨域、keep-alive 与组件 name、Vue 3 移除的 API

### 7. jQuery / DOM / 工程化 / 后台语言与 SQL（JD 7 / 9 / 10 / 11，第 6 题）

- jQuery：`$()` 返回 jQuery 对象、链式调用靠 `return this`、常用 API、事件委托写法、`$.ajax`、`$.fn.extend` 写插件
- `$(document).ready` vs `window.onload`（DOMContentLoaded vs load）
- easyUI / layui vs Element Plus / Ant Design Vue：配置式命令操作 vs 组件化数据驱动、为什么不宜与 Vue 混用
- DOM 性能：DocumentFragment、批量写入、读写分离、事件委托、虚拟滚动、IntersectionObserver 懒加载
- 构建工具：Vite（原生 ESM 按需编译 + esbuild 预构建 + Rollup 打包）vs Webpack（entry/output/loader/plugin/devServer）
- 包管理：npm/yarn/pnpm、lock 文件必须提交、Node 版本固定（.nvmrc）
- 规范：ESLint + Prettier + Stylelint、husky + lint-staged + commitlint、CR、Git 分支模型
- 监控与埋点：Sentry、`window.onerror`、`unhandledrejection`、`app.config.errorHandler`、sourcemap 不上公网
- 后台语言了解程度（JD 10）：会哪一门（Node.js / Python / Java / Go）、用它实际写过什么（起服务 / BFF 聚合接口 / 构建与数据处理脚本）
- SQL 基础：SELECT / WHERE / ORDER BY / LIMIT、INSERT / UPDATE / DELETE
- INNER JOIN vs LEFT JOIN（左表全保留、右表补 NULL）、"查从未下单的用户" LEFT JOIN + IS NULL
- GROUP BY + HAVING（WHERE 分组前、HAVING 分组后；聚合条件只能写 HAVING）
- 索引的作用与代价（加速查询、拖慢写入、不滥用）
- 前端了解后端的目的：看懂接口、能查数据排查问题、与后端协作沟通
- 新标准关注度（JD 9）：容器查询、View Transitions API、Web Components、HTTP/3、Vite 生态、TypeScript、虚拟滚动、Web Vitals

## 难度分层参考

| 层级 | 典型表现 |
|---|---|
| 初级 | 会用 Vue 写页面、能还原静态稿；说不清响应式原理与事件循环；跨域只会说「后端加个头」 |
| 中级 | 能独立负责模块；讲得清 Proxy 响应式、nextTick、key 的作用、跨域方案；能定位首屏慢/白屏这类问题 |
| 高级 | 能主导项目结构与规范；讲得清 diff 与编译期优化、打包分包的取舍、性能量化与治理；能说出多个真实踩坑 |
| 资深 | 能做技术选型与架构演进（组件库/监控/微前端/SSR 的取舍）；能把前端工程化、质量与交付串成体系 |

## 出题红线（不要考）

- AI / 大模型应用开发（JD 未要求）
- React / Angular / Svelte 等非 Vue 框架
- WebGL / Three.js / WebRTC / 微前端源码 / 低代码引擎原理
- 算法与数据结构笔试题（排序、动态规划、复杂链表）
- Node 源码、Koa/Express 中间件原理、数据库深度调优（JD 只要求「了解」）
- Vue 2 的专属配置与 API（只允许在第 6 题里作为对比参照出现）
