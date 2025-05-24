import{_ as a,c as n,o as i,ae as p}from"./chunks/framework.BGWP4WZ_.js";const d=JSON.parse('{"title":"设备激活流程 v2","description":"","frontmatter":{},"headers":[],"relativePath":"guide/08_设备激活流程.md","filePath":"guide/08_设备激活流程.md"}'),l={name:"guide/08_设备激活流程.md"};function t(h,s,k,e,E,r){return i(),n("div",null,s[0]||(s[0]=[p(`<h1 id="设备激活流程-v2" tabindex="-1">设备激活流程 v2 <a class="header-anchor" href="#设备激活流程-v2" aria-label="Permalink to &quot;设备激活流程 v2&quot;">​</a></h1><h2 id="概述" tabindex="-1">概述 <a class="header-anchor" href="#概述" aria-label="Permalink to &quot;概述&quot;">​</a></h2><p>当前流程是虾哥设备认证v2版本</p><h2 id="激活流程" tabindex="-1">激活流程 <a class="header-anchor" href="#激活流程" aria-label="Permalink to &quot;激活流程&quot;">​</a></h2><p>每个设备都有一个唯一的序列号(Serial Number)和HMAC密钥(HMAC Key)，用于身份验证和安全通信。新设备首次使用时需要通过以下流程进行激活：</p><ol><li>客户端启动时，向服务器发送设备信息，包括序列号、MAC地址和客户端ID</li><li>服务器检查设备是否已激活： <ul><li>如果已激活，客户端正常工作</li><li>如果未激活，服务器返回包含验证码和Challenge的激活请求</li></ul></li><li>客户端显示验证码，提示用户前往xiaozhi.me网站输入验证码</li><li>客户端使用HMAC密钥对Challenge进行签名，并发送给服务器验证</li><li>客户端通过轮询方式等待服务器确认验证结果： <ul><li>如果验证成功，设备激活完成</li><li>如果验证失败或超时，设备激活失败</li></ul></li></ol><h3 id="小智-esp32-设备激活流程图" tabindex="-1">小智 ESP32 设备激活流程图 <a class="header-anchor" href="#小智-esp32-设备激活流程图" aria-label="Permalink to &quot;小智 ESP32 设备激活流程图&quot;">​</a></h3><div class="language- vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang"></span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span>┌────────────────────┐</span></span>
<span class="line"><span>│     设备启动       │</span></span>
<span class="line"><span>└──────────┬─────────┘</span></span>
<span class="line"><span>           ↓</span></span>
<span class="line"><span>┌────────────────────┐</span></span>
<span class="line"><span>│   初始化各组件     │</span></span>
<span class="line"><span>│   连接WiFi/网络    │</span></span>
<span class="line"><span>└──────────┬─────────┘</span></span>
<span class="line"><span>           ↓</span></span>
<span class="line"><span>┌────────────────────┐</span></span>
<span class="line"><span>│  调用CheckVersion  │</span></span>
<span class="line"><span>│  访问OTA服务器     │──→ POST /xiaozhi/ota/</span></span>
<span class="line"><span>└──────────┬─────────┘</span></span>
<span class="line"><span>           ↓</span></span>
<span class="line"><span>┌────────────────────┐</span></span>
<span class="line"><span>│  解析服务器响应    │</span></span>
<span class="line"><span>└──────────┬─────────┘</span></span>
<span class="line"><span>           ↓</span></span>
<span class="line"><span>     ┌─────┴─────┐</span></span>
<span class="line"><span>     ↓           ↓</span></span>
<span class="line"><span>┌─────────┐ ┌─────────┐</span></span>
<span class="line"><span>│是否有新版本│ │是否需要激活│</span></span>
<span class="line"><span>└─────┬───┘ └─────┬───┘</span></span>
<span class="line"><span>      │           │</span></span>
<span class="line"><span>┌─────▼───┐       └───┬─── 否 ──┐</span></span>
<span class="line"><span>│升级固件  │           ↓         ↓</span></span>
<span class="line"><span>└─────────┘  ┌─────────────┐ ┌─────────────┐</span></span>
<span class="line"><span>             │是否有激活码  │ │初始化协议连接│</span></span>
<span class="line"><span>             └──────┬──────┘ │MQTT/WebSocket│</span></span>
<span class="line"><span>                    │        └─────────────┘</span></span>
<span class="line"><span>              ┌────▼───┐</span></span>
<span class="line"><span>              │   是   │</span></span>
<span class="line"><span>              └────┬───┘</span></span>
<span class="line"><span>                   ↓</span></span>
<span class="line"><span>        ┌──────────────────┐</span></span>
<span class="line"><span>        │显示激活码给用户   │</span></span>
<span class="line"><span>        │播放语音提示      │</span></span>
<span class="line"><span>        └────────┬─────────┘</span></span>
<span class="line"><span>                 ↓</span></span>
<span class="line"><span>        ┌──────────────────┐</span></span>
<span class="line"><span>        │ 开始激活流程      │</span></span>
<span class="line"><span>        └────────┬─────────┘</span></span>
<span class="line"><span>                 ↓</span></span>
<span class="line"><span>┌────────────────────────────────┐</span></span>
<span class="line"><span>│        检查设备序列号          │</span></span>
<span class="line"><span>└───────────────┬────────────────┘</span></span>
<span class="line"><span>                ↓</span></span>
<span class="line"><span>         ┌──────┴───────┐</span></span>
<span class="line"><span>         ↓              ↓</span></span>
<span class="line"><span>    ┌─────────┐    ┌─────────┐</span></span>
<span class="line"><span>    │  有序列号 │    │ 无序列号 │</span></span>
<span class="line"><span>    └─────┬────┘    └────┬────┘</span></span>
<span class="line"><span>          │              │</span></span>
<span class="line"><span>┌─────────▼────────┐    │</span></span>
<span class="line"><span>│构造激活载荷JSON:  │    │</span></span>
<span class="line"><span>│- serial_number    │    │</span></span>
<span class="line"><span>│- challenge        │    │</span></span>
<span class="line"><span>│- hmac签名         │    │</span></span>
<span class="line"><span>└─────────┬─────────┘    │</span></span>
<span class="line"><span>          │              │</span></span>
<span class="line"><span>          └──────┬───────┘</span></span>
<span class="line"><span>                 ↓</span></span>
<span class="line"><span>    ┌───────────────────────┐</span></span>
<span class="line"><span>    │发送POST请求到激活端点  │──→ POST /xiaozhi/ota/activate</span></span>
<span class="line"><span>    └────────────┬──────────┘</span></span>
<span class="line"><span>                 ↓</span></span>
<span class="line"><span>     ┌───────────┴───────────┐</span></span>
<span class="line"><span>     ↓           ↓           ↓</span></span>
<span class="line"><span>┌─────────┐ ┌─────────┐ ┌─────────┐</span></span>
<span class="line"><span>│状态码200 │ │状态码202 │ │其他状态码│</span></span>
<span class="line"><span>│激活成功  │ │超时重试  │ │激活失败  │</span></span>
<span class="line"><span>└────┬────┘ └────┬────┘ └────┬────┘</span></span>
<span class="line"><span>     │           │           │</span></span>
<span class="line"><span>     │      ┌────▼─────┐     │</span></span>
<span class="line"><span>     │      │延迟后重试 │     │</span></span>
<span class="line"><span>     │      │最多10次   │     │</span></span>
<span class="line"><span>     │      └────┬─────┘     │</span></span>
<span class="line"><span>     │           │           │</span></span>
<span class="line"><span>     └───────────┼───────────┘</span></span>
<span class="line"><span>                 ↓</span></span>
<span class="line"><span>        ┌──────────────────┐</span></span>
<span class="line"><span>        │设置激活状态标志位 │</span></span>
<span class="line"><span>        └────────┬─────────┘</span></span>
<span class="line"><span>                 ↓</span></span>
<span class="line"><span>        ┌──────────────────┐</span></span>
<span class="line"><span>        │  继续正常运行     │</span></span>
<span class="line"><span>        │  连接MQTT/WS协议  │</span></span>
<span class="line"><span>        └──────────────────┘</span></span></code></pre></div><h3 id="激活数据交互详细流程" tabindex="-1">激活数据交互详细流程 <a class="header-anchor" href="#激活数据交互详细流程" aria-label="Permalink to &quot;激活数据交互详细流程&quot;">​</a></h3><div class="language- vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang"></span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span>┌────────────┐                      ┌────────────┐                      ┌────────────┐</span></span>
<span class="line"><span>│            │                      │            │                      │            │</span></span>
<span class="line"><span>│  设备客户端  │                      │   服务器    │                      │  用户浏览器  │</span></span>
<span class="line"><span>│            │                      │            │                      │            │</span></span>
<span class="line"><span>└─────┬──────┘                      └─────┬──────┘                      └─────┬──────┘</span></span>
<span class="line"><span>      │                                   │                                   │</span></span>
<span class="line"><span>      │  请求设备状态 (MAC, ClientID, SN)   │                                   │</span></span>
<span class="line"><span>      │ ────────────────────────────────&gt; │                                   │</span></span>
<span class="line"><span>      │                                   │                                   │</span></span>
<span class="line"><span>      │  返回激活请求 (验证码, Challenge)    │                                   │</span></span>
<span class="line"><span>      │ &lt;──────────────────────────────── │                                   │</span></span>
<span class="line"><span>      │                                   │                                   │</span></span>
<span class="line"><span>      │ 显示验证码                          │                                   │</span></span>
<span class="line"><span>      │ ┌─────────────┐                   │                                   │</span></span>
<span class="line"><span>      │ │请前往网站输入 │                   │                                   │</span></span>
<span class="line"><span>      │ │验证码: 123456│                   │                                   │</span></span>
<span class="line"><span>      │ └─────────────┘                   │                                   │</span></span>
<span class="line"><span>      │                                   │                                   │</span></span>
<span class="line"><span>      │                                   │          用户访问xiaozhi.me        │</span></span>
<span class="line"><span>      │                                   │ &lt;─────────────────────────────────│</span></span>
<span class="line"><span>      │                                   │                                   │</span></span>
<span class="line"><span>      │                                   │          输入验证码 123456          │</span></span>
<span class="line"><span>      │                                   │ &lt;─────────────────────────────────│</span></span>
<span class="line"><span>      │                                   │                                   │</span></span>
<span class="line"><span>      │ 计算HMAC签名                        │                                   │</span></span>
<span class="line"><span>      │ ┌─────────────┐                   │                                   │</span></span>
<span class="line"><span>      │ │ HMAC(密钥,   │                   │                                   │</span></span>
<span class="line"><span>      │ │  Challenge) │                   │                                   │</span></span>
<span class="line"><span>      │ └─────────────┘                   │                                   │</span></span>
<span class="line"><span>      │                                   │                                   │</span></span>
<span class="line"><span>      │  发送激活请求 (SN, Challenge, 签名)  │                                   │</span></span>
<span class="line"><span>      │ ────────────────────────────────&gt; │                                   │</span></span>
<span class="line"><span>      │                                   │  ┌───────────────┐                │</span></span>
<span class="line"><span>      │                                   │  │ 等待用户输入验证码 │                │</span></span>
<span class="line"><span>      │                                   │  │ 超时返回202    │                │</span></span>
<span class="line"><span>      │                                   │  └───────────────┘                │</span></span>
<span class="line"><span>      │                                   │                                   │</span></span>
<span class="line"><span>      │  轮询等待 (HTTP Long Polling)       │                                   │</span></span>
<span class="line"><span>      │ ────────────────────────────────&gt; │                                   │</span></span>
<span class="line"><span>      │  HTTP 202 (Pending)               │                                   │</span></span>
<span class="line"><span>      │ &lt;──────────────────────────────── │                                   │</span></span>
<span class="line"><span>      │                                   │                                   │</span></span>
<span class="line"><span>      │  继续轮询...                        │                                   │</span></span>
<span class="line"><span>      │ ────────────────────────────────&gt; │                                   │</span></span>
<span class="line"><span>      │                                   │                                   │</span></span>
<span class="line"><span>      │                                   │          验证码验证成功             │</span></span>
<span class="line"><span>      │                                   │───────────────────────────────────│</span></span>
<span class="line"><span>      │                                   │                                   │</span></span>
<span class="line"><span>      │  激活成功 (HTTP 200)                │                                   │</span></span>
<span class="line"><span>      │ &lt;──────────────────────────────── │                                   │</span></span>
<span class="line"><span>      │                                   │                                   │</span></span>
<span class="line"><span>      │ ┌─────────────┐                   │                                   │</span></span>
<span class="line"><span>      │ │设备激活成功！ │                   │                                   │</span></span>
<span class="line"><span>      │ └─────────────┘                   │                                   │</span></span>
<span class="line"><span>      │                                   │                                   │</span></span></code></pre></div><h2 id="设备与服务器通信内容详解" tabindex="-1">设备与服务器通信内容详解 <a class="header-anchor" href="#设备与服务器通信内容详解" aria-label="Permalink to &quot;设备与服务器通信内容详解&quot;">​</a></h2><h3 id="_1-设备信息请求-post-xiaozhi-ota" tabindex="-1">1. 设备信息请求 (POST /xiaozhi/ota/) <a class="header-anchor" href="#_1-设备信息请求-post-xiaozhi-ota" aria-label="Permalink to &quot;1. 设备信息请求 (POST /xiaozhi/ota/)&quot;">​</a></h3><p><strong>请求头</strong>:</p><div class="language- vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang"></span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span>Activation-Version: 2  // 表示支持序列号激活</span></span>
<span class="line"><span>Device-Id: AA:BB:CC:DD:EE:FF  // MAC地址 </span></span>
<span class="line"><span>Client-Id: xxxx-xxxx-xxxx-xxxx  // 设备UUID</span></span>
<span class="line"><span>User-Agent: BOARD_NAME/1.0.0  // 开发板名称和固件版本</span></span>
<span class="line"><span>Content-Type: application/json</span></span></code></pre></div><p><strong>请求体</strong> (POST时):</p><div class="language-json vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">json</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;version&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">2</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;flash_size&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">16777216</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;psram_size&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">8388608</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;minimum_free_heap_size&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">7265024</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;mac_address&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;你的mac地址&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;uuid&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;你的client_id&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;chip_model_name&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;esp32s3&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;chip_info&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;model&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">9</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;cores&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">2</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;revision&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">0</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;features&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">20</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  },</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;application&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;name&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;xiaozhi&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;version&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;1.6.0&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;compile_time&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;2025-04-16T12:00:00Z&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;idf_version&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;v5.3.2&quot;</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  },</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;partition_table&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: [</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;label&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;nvs&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;type&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">1</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;subtype&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">2</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;address&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">36864</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;size&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">24576</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    },</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;label&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;otadata&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;type&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">1</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;subtype&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">0</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;address&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">61440</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;size&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">8192</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    },</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;label&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;app0&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;type&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">0</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;subtype&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">0</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;address&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">65536</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;size&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">1966080</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    },</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;label&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;app1&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;type&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">0</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;subtype&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">0</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;address&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">2031616</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;size&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">1966080</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    },</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;label&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;spiffs&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;type&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">1</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;subtype&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">130</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;address&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">3997696</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;size&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">1966080</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    }</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  ],</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;ota&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;label&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;app0&quot;</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  },</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;board&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;type&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;lc-esp32-s3&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;name&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;立创ESP32-S3开发板&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;features&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: [</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;wifi&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">, </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;ble&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">, </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;psram&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">, </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;octal_flash&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">],</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;ip&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;你的ip地址&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;mac&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;你的mac地址&quot;</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  }</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">}</span></span></code></pre></div><h3 id="_2-服务器响应" tabindex="-1">2. 服务器响应 <a class="header-anchor" href="#_2-服务器响应" aria-label="Permalink to &quot;2. 服务器响应&quot;">​</a></h3><p><strong>响应体</strong>:</p><div class="language-json vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">json</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;firmware&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;version&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;1.0.1&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;url&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;&quot;</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  },</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;activation&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;message&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;请访问xiaozhi.me输入激活码&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;code&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;123456&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;challenge&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;randomstring123456&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;timeout_ms&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">30000</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  },</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;mqtt&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;endpoint&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;mqtt.xiaozhi.me&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;client_id&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;device123&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;username&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;user123&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;password&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;pass123&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;publish_topic&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;&quot;</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  },</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;websocket&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;url&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;wss://api.tenclass.net/xiaozhi/v1/&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;token&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;test-token&quot;</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  }</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">}</span></span></code></pre></div><h3 id="_3-设备激活请求-post-xiaozhi-ota-activate" tabindex="-1">3. 设备激活请求 (POST /xiaozhi/ota/activate) <a class="header-anchor" href="#_3-设备激活请求-post-xiaozhi-ota-activate" aria-label="Permalink to &quot;3. 设备激活请求 (POST /xiaozhi/ota/activate)&quot;">​</a></h3><p><strong>请求体</strong>:</p><div class="language-json vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">json</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;Payload&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;algorithm&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;hmac-sha256&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;serial_number&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;SN-5CD8467B47FB4920&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;challenge&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;dac852d6-4ac4-4650-ba1a-c2a5bf00a766&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;hmac&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;ada4775e3ed93cf9c0eb9ed00444138554ba416af41283a0e5603c77681a8022&quot;</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  }</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">}</span></span></code></pre></div><h3 id="_4-激活响应" tabindex="-1">4. 激活响应 <a class="header-anchor" href="#_4-激活响应" aria-label="Permalink to &quot;4. 激活响应&quot;">​</a></h3><ul><li><strong>成功</strong>: 状态码 200</li><li><strong>等待用户输入验证码</strong>: 状态码 202</li><li><strong>失败</strong>: 状态码 4xx (如401表示未授权，400表示请求错误)</li></ul><p><strong>响应体</strong> (失败时):</p><div class="language-json vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">json</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;error&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;错误原因描述&quot;</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">}</span></span></code></pre></div><h2 id="安全机制" tabindex="-1">安全机制 <a class="header-anchor" href="#安全机制" aria-label="Permalink to &quot;安全机制&quot;">​</a></h2><p>设备激活流程v2版本采用以下安全机制：</p><ol><li><strong>设备唯一标识</strong>：每个设备有一个唯一的序列号(Serial Number)</li><li><strong>HMAC签名验证</strong>：使用HMAC-SHA256算法对Challenge进行签名，确保设备身份的真实性</li><li><strong>验证码验证</strong>：通过要求用户在网页端输入验证码，防止自动化的激活攻击</li><li><strong>轮询等待机制</strong>：使用HTTP Long Polling等待服务器验证结果，适应各种网络环境</li></ol>`,29)]))}const g=a(l,[["render",t]]);export{d as __pageData,g as default};
