#!/usr/bin/env python3
"""
小红书笔记转PDF工具 - API测试脚本
"""

import requests
import sys

def test_health():
    """测试健康检查接口"""
    try:
        response = requests.get("http://localhost:8000/api/health", timeout=5)
        if response.status_code == 200:
            print("✓ 健康检查通过")
            return True
        else:
            print(f"✗ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 健康检查失败: {e}")
        return False

def test_convert(url: str):
    """测试转换接口"""
    try:
        print(f"\n正在测试转换: {url}")
        response = requests.post(
            "http://localhost:8000/api/convert",
            json={"url": url},
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✓ 转换成功!")
                print(f"  - 图片数量: {data.get('imageCount', 0)}")
                print(f"  - PDF文件: {data.get('filename', '')}")
                print(f"  - 下载链接: http://localhost:8000{data.get('pdfUrl', '')}")
                return True
            else:
                print(f"✗ 转换失败: {data.get('message', '未知错误')}")
                return False
        else:
            print(f"✗ 请求失败: {response.status_code}")
            try:
                error = response.json()
                print(f"  错误信息: {error.get('detail', '未知错误')}")
            except:
                print(f"  响应内容: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"✗ 请求异常: {e}")
        return False

def main():
    print("=" * 50)
    print("小红书笔记转PDF工具 - API测试")
    print("=" * 50)
    
    # 测试健康检查
    print("\n1. 测试健康检查接口...")
    if not test_health():
        print("\n请确保服务已启动: python api/app.py")
        sys.exit(1)
    
    # 测试转换接口
    print("\n2. 测试转换接口...")
    test_url = "http://xhslink.com/o/30nh14AmzrF"
    test_convert(test_url)
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

if __name__ == "__main__":
    main()
