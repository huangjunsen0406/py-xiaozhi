document.addEventListener('DOMContentLoaded', () => {
    // 加载赞助者数据
    fetchSponsors();
    
    // 初始化弹窗
    initModal();
});

// 从本地JSON文件加载赞助者数据
async function fetchSponsors() {
    try {
        const response = await fetch('data.json');
        if (!response.ok) {
            throw new Error('Failed to load sponsors data');
        }
        const data = await response.json();
        renderSponsors(data);
    } catch (error) {
        console.error('Error loading sponsors:', error);
        // 如果无法加载JSON，使用默认数据
        renderSponsors(getDefaultSponsors());
    }
}

// 渲染赞助者到页面 - 处理新的不分等级的数据结构
function renderSponsors(data) {
    // 获取赞助者数组，兼容新旧数据结构
    let allSponsors = [];
    
    if (data.sponsors) {
        // 新数据结构
        allSponsors = data.sponsors;
    } else {
        // 旧数据结构（向后兼容）
        allSponsors = [
            ...(data.gold || []), 
            ...(data.silver || []), 
            ...(data.bronze || [])
        ];
    }
    
    // 按名称字母顺序排序
    allSponsors.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'));
    
    // 渲染到页面
    const container = document.getElementById('all-sponsors');
    if (!container) return;
    
    if (allSponsors.length === 0) {
        container.innerHTML = '<p class="empty-message">暂无赞助者，成为第一个赞助者吧！</p>';
        return;
    }
    
    allSponsors.forEach(sponsor => {
        const card = createSponsorCard(sponsor);
        container.appendChild(card);
    });
}

// 创建赞助者卡片
function createSponsorCard(sponsor) {
    const card = document.createElement('div');
    card.className = 'sponsor-card';
    
    // 创建图片或颜色块
    const imageContainer = document.createElement('div');
    imageContainer.className = 'sponsor-image';
    
    if (sponsor.image) {
        const img = document.createElement('img');
        img.src = sponsor.image;
        img.alt = sponsor.name;
        img.onerror = function() {
            // 图片加载失败时，创建颜色块
            this.style.display = 'none';
            imageContainer.appendChild(createColorBlock(sponsor.name));
        };
        imageContainer.appendChild(img);
    } else {
        imageContainer.appendChild(createColorBlock(sponsor.name));
    }
    
    // 创建信息部分
    const infoDiv = document.createElement('div');
    infoDiv.className = 'sponsor-info';
    
    const nameDiv = document.createElement('div');
    nameDiv.className = 'sponsor-name';
    nameDiv.textContent = sponsor.name;
    
    // 添加备注（如果有）
    if (sponsor.note) {
        const noteDiv = document.createElement('div');
        noteDiv.className = 'sponsor-note-text';
        noteDiv.textContent = sponsor.note;
        infoDiv.appendChild(nameDiv);
        infoDiv.appendChild(noteDiv);
    } else {
        infoDiv.appendChild(nameDiv);
    }
    
    const linkAnchor = document.createElement('a');
    linkAnchor.className = 'sponsor-link';
    linkAnchor.href = sponsor.url || '#';
    linkAnchor.target = '_blank';
    linkAnchor.rel = 'noopener noreferrer';
    linkAnchor.textContent = '访问主页';
    
    infoDiv.appendChild(linkAnchor);
    
    // 合并到卡片
    card.appendChild(imageContainer);
    card.appendChild(infoDiv);
    
    // 点击整个卡片跳转
    card.addEventListener('click', (e) => {
        // 如果点击的是链接本身，让链接正常工作
        if (e.target === linkAnchor || linkAnchor.contains(e.target)) {
            return;
        }
        
        if (sponsor.url) {
            window.open(sponsor.url, '_blank', 'noopener,noreferrer');
        }
    });
    
    return card;
}

// 创建颜色块
function createColorBlock(name) {
    const colorBlock = document.createElement('div');
    colorBlock.className = 'color-block';
    colorBlock.style.backgroundColor = getRandomColor(name);
    
    // 显示用户首字母
    const initial = document.createElement('span');
    initial.textContent = name.charAt(0).toUpperCase();
    colorBlock.appendChild(initial);
    
    return colorBlock;
}

// 根据名称生成随机颜色（通过哈希算法保持一致性）
function getRandomColor(name) {
    // 简单的字符串哈希算法
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    // 转换为RGB颜色
    const r = (hash & 0xFF) % 200 + 50;  // 50-250范围，避免太暗或太亮
    const g = ((hash >> 8) & 0xFF) % 200 + 50;
    const b = ((hash >> 16) & 0xFF) % 200 + 50;
    
    return `rgb(${r}, ${g}, ${b})`;
}

// 初始化弹窗
function initModal() {
    const modal = document.getElementById('sponsor-modal');
    const showModalBtn = document.getElementById('show-sponsor-modal');
    const closeModalBtn = document.querySelector('.close-modal');
    const alipayBtn = document.getElementById('alipay-btn');
    const wechatBtn = document.getElementById('wechat-btn');
    const alipayQR = document.getElementById('alipay-qr');
    const wechatQR = document.getElementById('wechat-qr');
    
    if (!modal || !showModalBtn) return;
    
    // 显示弹窗
    showModalBtn.addEventListener('click', (e) => {
        e.preventDefault();
        modal.style.display = 'block';
        // 默认显示支付宝
        showPaymentQR('alipay');
    });
    
    // 关闭弹窗
    closeModalBtn.addEventListener('click', () => {
        modal.style.display = 'none';
    });
    
    // 点击空白处关闭弹窗
    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
    
    // 支付宝按钮
    alipayBtn.addEventListener('click', () => {
        showPaymentQR('alipay');
    });
    
    // 微信按钮
    wechatBtn.addEventListener('click', () => {
        showPaymentQR('wechat');
    });
    
    // 显示指定的支付二维码
    function showPaymentQR(type) {
        // 隐藏所有二维码
        alipayQR.classList.remove('active');
        wechatQR.classList.remove('active');
        
        // 重置按钮样式
        alipayBtn.classList.remove('active');
        wechatBtn.classList.remove('active');
        
        // 显示选中的二维码和激活对应按钮
        if (type === 'alipay') {
            alipayQR.classList.add('active');
            alipayBtn.classList.add('active');
        } else if (type === 'wechat') {
            wechatQR.classList.add('active');
            wechatBtn.classList.add('active');
        }
    }
}

// 默认赞助者数据（当无法加载JSON时使用）
function getDefaultSponsors() {
    return {
         "sponsors": [
            {
                "name": "ZhengDongHang",
                "url": "https://github.com/ZhengDongHang",
                "image": "https://avatars.githubusercontent.com/u/193732878?v=4"
            },
            {
                "name": "YANG-success-last",
                "url": "https://github.com/YANG-success-last",
                "image": "https://tuchuang.junsen.online/i/2025/03/28/2kzeks.jpg"
            },
            {
                "name": "李洪刚",
                "url": "https://github.com/SmartArduino",
                "image": "https://tuchuang.junsen.online/i/2025/03/28/2kfo2p.jpg"
            },
            {
                "name": "kejily",
                "url": "https://github.com/kejily",
                "image": "https://tuchuang.junsen.online/i/2025/03/28/2mpif8.jpg"
            },
            {
                "name": "thomas",
                "url": "",
                "image": "https://tuchuang.junsen.online/i/2025/03/28/2km1gm.jpg"
            },
            {
                "name": "吃饭叫我",
                "url": "",
                "image": "https://tuchuang.junsen.online/i/2025/03/28/2k0i12.jpg"
            }
        ]
    };
}