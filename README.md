# Distributed Render Engine (Desktop Edition)

This Python-based utility leverages **parallel processing** and **FFmpeg** to significantly accelerate video transcoding and image-sequence-to-video rendering. By splitting a single large task into smaller chunks and distributing them across multiple CPU cores, it bypasses the single-threaded limitations of standard encoders.

---

## 🚀 Features
* **Dual Mode Rendering**: 
    * **Video Processing**: Automatically splits long videos into segments for faster parallel encoding.
    * **Image Sequence**: Converts folders of images (JPG, PNG, TIFF) into a high-quality MP4 video.
* **Hardware Acceleration Support**: Pre-configured profiles for:
    * **NVIDIA** (`h264_nvenc`)
    * **AMD** (`h264_amf`)
    * **Apple Silicon/Mac** (`h264_videotoolbox`)
    * **Standard CPU** (`libx264`)
* **Intelligent Scaling**: Easily downscale or upscale resolution (e.g., 1080p, 720p) during the render process.
* **Progress Tracking**: Real-time feedback using `tqdm` progress bars.
* **Auto-Concatenation**: Automatically merges all parallel-rendered chunks into a single final file without quality loss.

---

## 🛠 Prerequisites
Before running the engine, ensure you have the following installed:

1.  **FFmpeg**: Must be installed and added to your system's PATH.
2.  **Python 3.x**
3.  **Dependencies**:
    ```bash
    pip install tqdm moviepy
    ```

---

## 📖 How to Use
1.  **Run the script**:
    ```bash
    python render.py
    ```
2.  **Follow the Wizard**:
    * **Input**: Drag and drop your video file or image folder into the terminal.
    * **Output**: Specify a filename (the engine automatically saves it to your **Desktop**).
    * **Scaling**: Set a target height or press Enter to keep original dimensions.
    * **Hardware**: Select the encoder that matches your GPU for maximum speed.
    * **Workers**: Choose how many CPU cores to dedicate to the task.

---

## 🏗 Architecture
The engine utilizes a **Master-Worker** architecture:
* **The Orchestrator**: Analyzes the input, calculates segments/batches, and populates a `JoinableQueue`.
* **The Workers**: Multiple subprocesses that pull tasks from the queue and run isolated FFmpeg commands.
* **The Merger**: A final pass that uses FFmpeg's `concat` protocol to stitch segments together seamlessly.

---

## 💡 Performance Tip
For maximum efficiency on high-core-count CPUs (like Ryzen 9 or Intel i9), set the **Workers** to at least half of your total logical cores. If using hardware encoders like `nvenc`, you can achieve near-instantaneous transcoding for long-form content.
