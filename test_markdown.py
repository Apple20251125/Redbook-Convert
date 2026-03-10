#!/usr/bin/env python3
"""
Test markdown conversion functionality
"""

import os
import sys
import tempfile
import shutil

# Add api directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from app import create_markdown, create_zip, NoteContent

def test_create_markdown():
    """Test create_markdown function"""
    print("Testing create_markdown function...")

    # Create temporary directory
    temp_dir = tempfile.mkdtemp()

    try:
        # Create test image files
        image_paths = []
        for i in range(2):
            img_path = os.path.join(temp_dir, f"image_{i+1}.jpg")
            with open(img_path, 'w') as f:
                f.write("fake image content")
            image_paths.append(img_path)

        # Test markdown creation
        md_path = os.path.join(temp_dir, "test.md")
        create_markdown(
            title="测试标题",
            content="这是测试内容\n第二行内容",
            image_paths=image_paths,
            output_path=md_path
        )

        # Verify markdown file was created
        if os.path.exists(md_path):
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print("✓ Markdown file created successfully")
                print(f"Content preview:\n{content[:200]}...")

                # Check for expected content
                if "# 测试标题" in content:
                    print("✓ Title found in markdown")
                if "这是测试内容" in content:
                    print("✓ Content found in markdown")
                if "![图片" in content:
                    print("✓ Image references found in markdown")

                return True
        else:
            print("✗ Markdown file was not created")
            return False

    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_create_zip():
    """Test create_zip function"""
    print("\nTesting create_zip function...")

    # Create temporary directory
    temp_dir = tempfile.mkdtemp()

    try:
        # Create markdown file
        md_path = os.path.join(temp_dir, "test.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("# Test\n\nContent")

        # Create images directory
        img_dir = os.path.join(temp_dir, "images")
        os.makedirs(img_dir, exist_ok=True)

        # Create test images
        for i in range(2):
            img_path = os.path.join(img_dir, f"image_{i+1}.jpg")
            with open(img_path, 'w') as f:
                f.write("fake image content")

        # Create zip
        zip_path = os.path.join(temp_dir, "test.zip")
        create_zip(md_path, img_dir, zip_path)

        # Verify zip was created
        if os.path.exists(zip_path):
            print("✓ ZIP file created successfully")
            print(f"ZIP size: {os.path.getsize(zip_path)} bytes")

            # List zip contents
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                files = zipf.namelist()
                print(f"ZIP contents: {files}")

                if "test.md" in files:
                    print("✓ Markdown file found in ZIP")
                if any(f.startswith("images/") for f in files):
                    print("✓ Images directory found in ZIP")

                return True
        else:
            print("✗ ZIP file was not created")
            return False

    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_note_content_model():
    """Test NoteContent model"""
    print("\nTesting NoteContent model...")

    try:
        content = NoteContent(
            title="测试标题",
            content="测试内容",
            images=["img1.jpg", "img2.jpg"]
        )

        print(f"✓ NoteContent created: title={content.title}, images={len(content.images)}")
        return True
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        return False

def main():
    print("=" * 60)
    print("Markdown Conversion Functionality Tests")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("NoteContent Model", test_note_content_model()))
    results.append(("create_markdown", test_create_markdown()))
    results.append(("create_zip", test_create_zip()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
