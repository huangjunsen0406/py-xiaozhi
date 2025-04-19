import{_ as a,c as n,o as i,ae as l}from"./chunks/framework.BGWP4WZ_.js";const k=JSON.parse('{"title":"设备激活流程 v2","description":"","frontmatter":{},"headers":[],"relativePath":"guide/08_设备激活流程（占位）.md","filePath":"guide/08_设备激活流程（占位）.md"}'),p={name:"guide/08_设备激活流程（占位）.md"};function e(t,s,c,o,h,d){return i(),n("div",null,s[0]||(s[0]=[l(`<h1 id="设备激活流程-v2" tabindex="-1">设备激活流程 v2 <a class="header-anchor" href="#设备激活流程-v2" aria-label="Permalink to &quot;设备激活流程 v2&quot;">​</a></h1><h2 id="概述" tabindex="-1">概述 <a class="header-anchor" href="#概述" aria-label="Permalink to &quot;概述&quot;">​</a></h2><p>当前流程是虾哥设备认证v2版本，目前最新固件已经存在，但本项目还未移植</p><h2 id="激活流程" tabindex="-1">激活流程 <a class="header-anchor" href="#激活流程" aria-label="Permalink to &quot;激活流程&quot;">​</a></h2><p>每个设备都有一个唯一的序列号(Serial Number)和HMAC密钥(HMAC Key)，用于身份验证和安全通信。新设备首次使用时需要通过以下流程进行激活：</p><ol><li>客户端启动时，向服务器发送设备信息，包括序列号、MAC地址和客户端ID</li><li>服务器检查设备是否已激活： <ul><li>如果已激活，客户端正常工作</li><li>如果未激活，服务器返回包含验证码和Challenge的激活请求</li></ul></li><li>客户端显示验证码，提示用户前往xiaozhi.me网站输入验证码</li><li>客户端使用HMAC密钥对Challenge进行签名，并发送给服务器验证</li><li>客户端通过轮询方式等待服务器确认验证结果： <ul><li>如果验证成功，设备激活完成</li><li>如果验证失败或超时，设备激活失败</li></ul></li></ol><div class="language- vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang"></span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span>┌────────────┐                      ┌────────────┐                      ┌────────────┐</span></span>
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
<span class="line"><span>      │                                   │                                   │</span></span></code></pre></div><h2 id="安全机制" tabindex="-1">安全机制 <a class="header-anchor" href="#安全机制" aria-label="Permalink to &quot;安全机制&quot;">​</a></h2><p>设备激活流程v2版本采用以下安全机制：</p><ol><li><strong>设备唯一标识</strong>：每个设备有一个唯一的序列号(Serial Number)</li><li><strong>HMAC签名验证</strong>：使用HMAC-SHA256算法对Challenge进行签名，确保设备身份的真实性</li><li><strong>验证码验证</strong>：通过要求用户在网页端输入验证码，防止自动化的激活攻击</li><li><strong>轮询等待机制</strong>：使用HTTP Long Polling等待服务器验证结果，适应各种网络环境</li></ol><h2 id="配置说明" tabindex="-1">配置说明 <a class="header-anchor" href="#配置说明" aria-label="Permalink to &quot;配置说明&quot;">​</a></h2><p>相关配置项在<code>config.json</code>中的<code>SYSTEM_OPTIONS</code>部分：</p><div class="language-json vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">json</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;SYSTEM_OPTIONS&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;CLIENT_ID&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;a45f36c9-c855-4deb-ac46-6847997c29a2&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;DEVICE_ID&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;54:1f:8d:e0:7b:91&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;SERIAL_NUMBER&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;HMAC_KEY&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;ACTIVATED&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">false</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#B31D28;--shiki-light-font-style:italic;--shiki-dark:#FDAEB7;--shiki-dark-font-style:italic;">  ...</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">}</span></span></code></pre></div><ul><li><code>SERIAL_NUMBER</code>: 设备唯一序列号，如果为空则自动生成</li><li><code>HMAC_KEY</code>: HMAC签名密钥，如果为空则自动生成</li><li><code>ACTIVATED</code>: 设备激活状态，激活成功后设置为true</li></ul><h2 id="开发者说明" tabindex="-1">开发者说明 <a class="header-anchor" href="#开发者说明" aria-label="Permalink to &quot;开发者说明&quot;">​</a></h2><p>设备激活相关代码实现：</p><ol><li><code>src/utils/device_activation.py</code>: 设备激活管理类，负责序列号和HMAC密钥管理、签名计算和激活流程</li><li><code>src/application.py</code>中的<code>_check_device_activation()</code>和<code>_handle_activation_result()</code>方法处理设备激活流程</li></ol><p>如需在其他平台上实现兼容的激活流程，需要遵循相同的协议和安全机制。</p><h2 id="常见问题" tabindex="-1">常见问题 <a class="header-anchor" href="#常见问题" aria-label="Permalink to &quot;常见问题&quot;">​</a></h2><ol><li><p><strong>设备激活失败怎么办？</strong></p><ul><li>检查网络连接是否正常</li><li>确保验证码输入正确且未过期</li><li>重启设备重新尝试激活</li></ul></li><li><p><strong>如何手动设置序列号和HMAC密钥？</strong></p><ul><li>可以在<code>config.json</code>中直接设置<code>SERIAL_NUMBER</code>和<code>HMAC_KEY</code></li><li>也可以在<code>config/serial_number.txt</code>和<code>config/hmac_key.txt</code>中手动设置</li></ul></li><li><p><strong>激活过的设备需要重新激活吗？</strong></p><ul><li>正常情况下，设备激活成功后不需要重新激活</li><li>如果设备配置被重置或<code>ACTIVATED</code>被设为false，则需要重新激活</li></ul></li></ol>`,20)]))}const g=a(p,[["render",e]]);export{k as __pageData,g as default};
