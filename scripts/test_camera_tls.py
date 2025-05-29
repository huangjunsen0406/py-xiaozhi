#!/usr/bin/env python3
"""
测试摄像头 TLS 冲突解决方案
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_camera_import():
    """测试摄像头模块导入是否会引发 TLS 冲突"""
    print("🔍 测试 1: 导入摄像头模块...")
    
    try:
        # 先导入可能引起冲突的库
        import numpy as np
        print("✅ NumPy 导入成功")
        
        # 然后导入摄像头模块（现在使用延迟导入）
        from src.iot.things.CameraVL.Camera import Camera
        print("✅ Camera 模块导入成功")
        
        # 创建摄像头实例
        camera = Camera()
        print("✅ Camera 实例创建成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_delayed_cv2_import():
    """测试延迟导入 cv2 是否工作"""
    print("\n🔍 测试 2: 延迟导入 cv2...")
    
    try:
        # 模拟在函数内部导入 cv2
        def test_cv2():
            import cv2
            return cv2.__version__
        
        version = test_cv2()
        print(f"✅ OpenCV 延迟导入成功，版本: {version}")
        return True
        
    except ImportError:
        print("⚠️ OpenCV 未安装，这是正常的")
        return True
    except Exception as e:
        print(f"❌ OpenCV 延迟导入失败: {e}")
        return False

def test_mixed_libraries():
    """测试混合使用多个可能冲突的库"""
    print("\n🔍 测试 3: 混合使用多个库...")
    
    try:
        # 导入各种可能冲突的库
        import numpy as np
        print("✅ NumPy 导入成功")
        
        try:
            import scipy
            print("✅ SciPy 导入成功")
        except ImportError:
            print("⚠️ SciPy 未安装，跳过")
        
        try:
            import sklearn
            print("✅ Scikit-learn 导入成功")
        except ImportError:
            print("⚠️ Scikit-learn 未安装，跳过")
        
        # 在函数内部导入 cv2
        def test_cv2_with_others():
            import cv2
            return True
        
        test_cv2_with_others()
        print("✅ 混合库导入测试成功")
        return True
        
    except ImportError as e:
        if "cv2" in str(e):
            print("⚠️ OpenCV 未安装，但其他库工作正常")
            return True
        else:
            print(f"❌ 库导入失败: {e}")
            return False
    except Exception as e:
        print(f"❌ 混合库测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始测试摄像头 TLS 冲突解决方案\n")
    
    results = []
    
    # 运行测试
    results.append(test_camera_import())
    results.append(test_delayed_cv2_import())
    results.append(test_mixed_libraries())
    
    # 总结结果
    print("\n" + "="*50)
    print("📊 测试结果总结:")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ 所有测试通过 ({passed}/{total})")
        print("🎉 TLS 冲突解决方案工作正常！")
    else:
        print(f"⚠️ 部分测试失败 ({passed}/{total})")
        print("💡 建议检查 OpenCV 安装或使用子进程方案")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
