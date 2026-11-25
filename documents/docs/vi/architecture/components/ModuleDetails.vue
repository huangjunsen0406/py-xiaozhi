<template>
  <div class="module-container">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
      <div v-for="(module, index) in modules" :key="index" class="module-card">
        <div class="flex items-start">
          <div class="w-12 h-12 rounded-lg flex items-center justify-center"
            :class="moduleColors[index % moduleColors.length]">
            <component :is="module.icon" class="w-6 h-6 text-white" />
          </div>
          <div class="ml-4 flex-1">
            <h3 class="module-title">{{ module.name }}</h3>
            <ul class="space-y-2">
              <li v-for="(feature, featureIndex) in module.features" :key="featureIndex" class="flex items-start">
                <CheckCircleIcon class="w-5 h-5 text-green-500 mt-1 mr-2 shrink-0" />
                <span class="feature-text">{{ feature }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  CogIcon,
  ArrowsRightLeftIcon,
  DocumentIcon,
  SpeakerXMarkIcon,
  ComputerDesktopIcon,
  LightBulbIcon,
  WrenchIcon,
  CheckCircleIcon,
  CpuChipIcon,
  MapIcon,
  BoltIcon
} from '@heroicons/vue/24/solid';

const modules = [
  {
    name: 'src/bootstrap/',
    icon: CogIcon,
    features: [
      'ServiceContainer điều phối quá trình khởi động và tắt ứng dụng',
      'Tách biệt phiên làm việc, kiểm tra trạng thái và lắp ráp plugin',
      'Nạp các plugin theo đúng thứ tự phụ thuộc'
    ]
  },
  {
    name: 'src/core/',
    icon: BoltIcon,
    features: [
      'Giao tiếp hướng sự kiện qua EventBus',
      'Máy trạng thái thiết bị và trình quản lý giao thức',
      'Thu hồi tập trung tác vụ và tài nguyên'
    ]
  },
  {
    name: 'src/plugins/',
    icon: CpuChipIcon,
    features: [
      'Quản lý vòng đời plugin và cô lập phụ thuộc/lỗi',
      'Âm thanh, UI, phím tắt, từ đánh thức, MCP'
    ]
  },
  {
    name: 'src/protocols/',
    icon: ArrowsRightLeftIcon,
    features: [
      'Hỗ trợ song giao thức WebSocket / MQTT',
      'Truyền tải âm thanh và tin nhắn văn bản thời gian thực'
    ]
  },
  {
    name: 'src/audio_codecs/',
    icon: DocumentIcon,
    features: [
      'Mã hóa/giải mã Opus, tái lấy mẫu SoXR và nạp lại nóng (hot reload)',
      'AudioMixer đa rãnh độc lập (tự động giảm âm nền cho TTS / thông báo / luồng nền)',
      'Bộ giải mã FFmpeg AudioDecoder dùng chung, tách biệt hoàn toàn khỏi nguồn âm thanh'
    ]
  },
  {
    name: 'src/audio_processing/',
    icon: SpeakerXMarkIcon,
    features: [
      'Khử tiếng vọng WebRTC APM tích hợp sẵn (dự phòng mở rộng FarEndSource)',
      'Phát hiện từ đánh thức ngoại tuyến (tái sử dụng luồng PCM từ micro)'
    ]
  },
  {
    name: 'src/media/',
    icon: BoltIcon,
    features: [
      'Nền tảng MediaPlayer dùng chung, không phụ thuộc nguồn âm thanh',
      'Tự động quản lý TTS Audio Focus (giảm âm song song khi có AEC / tạm dừng và phát tiếp khi bỏ qua AEC)',
      'Kiểm tra bảo mật giao thức URL và header yêu cầu, cô lập quyền sở hữu theo owner_id'
    ]
  },
  {
    name: 'src/notifications/',
    icon: LightBulbIcon,
    features: [
      'Giải mã và phát thông báo một chiều dạng luồng từ máy chủ',
      'Đồng bộ sự kiện phụ đề thông báo và quản lý ngắt quãng'
    ]
  },
  {
    name: 'src/mcp/',
    icon: WrenchIcon,
    features: [
      'Công cụ tích hợp sẵn: ứng dụng hệ thống, âm lượng, camera (USB/CSI), chụp màn hình, thời tiết',
      'Quản lý plugin ngoài: nhập từ ZIP/thư mục, RPC hai chiều qua tiến trình con, media_player được kiểm soát',
      'Đăng ký có điều kiện các công cụ điều khiển phát đa phương tiện chung (media.*) khi có plugin ngoài được nạp'
    ]
  },
  {
    name: 'src/ui/',
    icon: ComputerDesktopIcon,
    features: [
      'Lớp ViewPort thống nhất cho GUI / TUI / GPIO',
      'Giao diện chính và cài đặt dùng PySide6 + QML (bao gồm cài đặt và quản lý plugin ngoài)',
      'Khởi động nguội không chiếm tiêu điểm cửa sổ (macOS)'
    ]
  },
  {
    name: 'src/activation/',
    icon: LightBulbIcon,
    features: [
      'Kích hoạt thiết bị và cập nhật OTA',
      'Cửa sổ kích hoạt độc lập'
    ]
  },
  {
    name: 'src/logging/',
    icon: DocumentIcon,
    features: [
      'Ghi nhật ký phân cấp và xoay vòng tệp log',
      'Khởi tạo tường minh'
    ]
  },
  {
    name: 'src/utils/',
    icon: MapIcon,
    features: [
      'Quản lý cấu hình (khớp thiết bị âm thanh theo tên)',
      'Đường dẫn tài nguyên và tiện ích đa nền tảng'
    ]
  }
];

const moduleColors = [
  'bg-blue-600',
  'bg-indigo-600',
  'bg-purple-600',
  'bg-pink-600',
  'bg-red-600',
  'bg-orange-600',
  'bg-amber-600',
  'bg-green-600',
  'bg-teal-600',
  'bg-cyan-600',
  'bg-sky-600'
];
</script>

<style scoped>
.module-container {
  background-color: var(--vp-c-bg);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 40px;
}

.module-card {
  border-radius: 8px;
  padding: 16px;
  transition: background-color 0.2s ease;
}

.module-card:hover {
  background-color: var(--vp-c-bg-soft);
}

.module-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--vp-c-text-1);
  margin-bottom: 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.feature-text {
  color: var(--vp-c-text-2);
  line-height: 1.5;
  font-size: 0.95rem;
}
</style>
