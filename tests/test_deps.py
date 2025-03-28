import exifread
import ffmpeg
import FreeSimpleGUI as sg  # noqa: N813
import hachoir
import pymediainfo


def test_dependencies():
    print("Testing dependencies...")

    # Test exifread
    print("\nTesting exifread...")
    print(f"exifread version: {exifread.__version__}")

    # Test hachoir
    print("\nTesting hachoir...")
    print(f"hachoir version: {hachoir.__version__}")

    # Test pymediainfo
    print("\nTesting pymediainfo...")
    print(f"pymediainfo version: {pymediainfo.__version__}")

    # Test ffmpeg-python
    print("\nTesting ffmpeg-python...")
    try:
        ffmpeg.probe('dummy')  # This will fail but we just want to verify the import
        print("ffmpeg-python is working")
    except ffmpeg.Error:
        print("ffmpeg-python is working (expected error for dummy file)")

    # Test freesimplegui
    print("\nTesting freesimplegui...")
    print(f"freesimplegui version: {sg.version}")

    print("\nAll dependencies imported successfully!")

if __name__ == "__main__":
    test_dependencies()
