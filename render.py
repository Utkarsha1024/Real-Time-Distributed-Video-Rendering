import time
import os
import sys
import glob
import shutil
import subprocess
import multiprocessing
from multiprocessing import Process, JoinableQueue, Queue

# --- TQDM Check ---
try:
    from tqdm import tqdm
except ImportError:
    print("!! Error: `tqdm` not installed. Please run: pip install tqdm")
    sys.exit()

# --- MOVIEPY CHECK ---
try:
    from moviepy import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    try:
        from moviepy import VideoFileClip
        MOVIEPY_AVAILABLE = True
    except ImportError:
        MOVIEPY_AVAILABLE = False

# --- DESKTOP DETECTION ---
# This finds the Desktop path on Mac, Windows, and Linux
DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")

# ==========================================
# 1. THE WIZARD
# ==========================================

def get_user_inputs():
    print("\n" + "="*50)
    print("      DISTRIBUTED RENDER ENGINE (Desktop Edition)")
    print("="*50)

    # --- A. Input Path ---
    while True:
        raw_path = input(">> Drag and drop VIDEO FILE or IMAGE FOLDER: ").strip()
        # Clean up path string
        path = raw_path.replace('"', '').replace("'", "").replace("\\ ", " ")
        if os.path.exists(path): break
        print(f"!! Error: Path not found: {path}")

    # Detect Mode
    if os.path.isdir(path):
        mode = "IMAGES"
        print(f"   [Detected Mode: IMAGE SEQUENCE]")
    else:
        mode = "VIDEO"
        print(f"   [Detected Mode: VIDEO PROCESSING]")

    # --- B. Output Filename (Auto-Desktop) ---
    default_name = "output_render.mp4"
    print(f"\n[Output Location]")
    print(f"   Files will be saved to: {DESKTOP_DIR}")
    
    filename = input(f">> Enter Filename [Default: {default_name}]: ").strip()
    if not filename: filename = default_name
    if not filename.endswith(".mp4"): filename += ".mp4"
    
    # Combine Desktop path with filename
    full_output_path = os.path.join(DESKTOP_DIR, filename)

    # --- C. Resolution Scaling ---
    print("\n[Resolution Scaling]")
    print("Enter target HEIGHT (e.g. 1080, 720). Press ENTER to skip.")
    res_input = input(">> Target Height: ").strip()
    
    target_height = None
    if res_input.isdigit():
        target_height = int(res_input)
        print(f"   -> Scaling to Height: {target_height}p")
    else:
        print("   -> Keeping Original Resolution")

    # --- D. Hardware ---
    print("\n[Hardware Acceleration]")
    print("1. NVIDIA (h264_nvenc)")
    print("2. AMD (h264_amf)")
    print("3. Apple (h264_videotoolbox)")
    print("4. CPU (libx264)")
    
    hw_choice = input(">> Select Hardware [1-4]: ").strip()
    
    if hw_choice == '1': encoder = "h264_nvenc"
    elif hw_choice == '2': encoder = "h264_amf"
    elif hw_choice == '3': encoder = "h264_videotoolbox"
    else: encoder = "libx264"

    # --- E. Workers ---
    cores = multiprocessing.cpu_count()
    try:
        w_input = input(f">> Workers (Max: {cores}) [Default: 4]: ").strip()
        workers = int(w_input) if w_input else 4
    except:
        workers = 4

    return path, full_output_path, mode, encoder, workers, target_height

# ==========================================
# 2. THE WORKERS
# ==========================================

def video_worker(task_queue, result_queue, worker_id, encoder, target_height):
    while True:
        task = task_queue.get()
        if task is None:
            task_queue.task_done(); break

        start, end, input_path, idx = task
        # Temp files go in the current working directory (hidden from user usually)
        temp_file = f"temp_vid_{idx}.mp4"
        
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(start), "-to", str(end),
            "-i", input_path
        ]
        
        if target_height:
            cmd.extend(["-vf", f"scale=-2:{target_height}:flags=lanczos"])
            
        cmd.extend(["-c:v", encoder, "-preset", "fast", "-an", temp_file])
        
        if encoder == "h264_videotoolbox": 
            cmd.extend(["-b:v", "6M"])

        try:
            subprocess.run(cmd, check=True)
            result_queue.put(temp_file)
        except:
            result_queue.put(None)
        
        task_queue.task_done()

def image_worker(task_queue, result_queue, worker_id, encoder, target_height):
    while True:
        task = task_queue.get()
        if task is None:
            task_queue.task_done(); break

        batch_idx, image_paths = task
        temp_dir = f"temp_worker_{worker_id}"
        os.makedirs(temp_dir, exist_ok=True)
        
        ext = os.path.splitext(image_paths[0])[1]
        for i, img in enumerate(image_paths):
            link = os.path.join(temp_dir, f"img_{i:04d}{ext}")
            if os.path.exists(link): os.remove(link)
            os.symlink(os.path.abspath(img), link)

        output_chunk = f"temp_chunk_{batch_idx:04d}.mp4"
        
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", "30",
            "-i", f"{temp_dir}/img_%04d{ext}"
        ]

        if target_height:
            cmd.extend(["-vf", f"scale=-2:{target_height}:flags=lanczos"])

        cmd.extend(["-c:v", encoder, "-pix_fmt", "yuv420p", output_chunk])
        
        try:
            subprocess.run(cmd, check=True)
            result_queue.put(output_chunk)
        except:
            result_queue.put(None)

        shutil.rmtree(temp_dir)
        task_queue.task_done()

# ==========================================
# 3. MAIN ORCHESTRATOR
# ==========================================

def main():
    input_path, output_file, mode, encoder, num_workers, target_height = get_user_inputs()
    
    task_queue = JoinableQueue()
    result_queue = Queue()
    
    start_time = time.time()
    total_tasks = 0
    
    print("\n[Analyzing Input...]")
    if mode == "VIDEO":
        if not MOVIEPY_AVAILABLE:
            print("!! Error: pip install moviepy"); return
        
        clip = VideoFileClip(input_path)
        duration = clip.duration
        clip.close()
        
        seg_duration = 10
        for i in range(int(duration // seg_duration) + 1):
            s = i * seg_duration
            e = min((i + 1) * seg_duration, duration)
            if e > s:
                task_queue.put((s, e, input_path, i))
                total_tasks += 1

    elif mode == "IMAGES":
        exts = ['*.jpg', '*.png', '*.jpeg', '*.tif']
        images = []
        for e in exts: images.extend(glob.glob(os.path.join(input_path, e)))
        images.sort()
        if not images: print("No images!"); return
            
        batch_size = 100
        chunks = [images[i:i + batch_size] for i in range(0, len(images), batch_size)]
        for i, chunk in enumerate(chunks):
            task_queue.put((i, chunk))
        total_tasks = len(chunks)

    # Launch Workers
    for _ in range(num_workers): task_queue.put(None)
    
    workers = []
    target = video_worker if mode == "VIDEO" else image_worker
    
    for i in range(num_workers):
        p = Process(target=target, args=(task_queue, result_queue, i, encoder, target_height))
        p.start()
        workers.append(p)
        
    print(f"--- Starting Distributed Render ({total_tasks} Tasks) ---")
    
    temp_files = []
    
    with tqdm(total=total_tasks, unit="chunk", colour="green") as pbar:
        for _ in range(total_tasks):
            result = result_queue.get()
            if result:
                temp_files.append(result)
            else:
                pbar.write("!! Warning: A segment failed.")
            pbar.update(1)
            
    task_queue.join()
    for p in workers: p.join()

    print("\n[Merging Final Output...]")
    
    if mode == "VIDEO":
        temp_files.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))
    else:
        temp_files.sort()

    with open("concat_list.txt", "w") as f:
        for tf in temp_files: f.write(f"file '{tf}'\n")
            
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", "concat_list.txt", "-c", "copy", output_file
    ])
    
    # Cleanup
    for tf in temp_files:
        if os.path.exists(tf): os.remove(tf)
    if os.path.exists("concat_list.txt"): os.remove("concat_list.txt")
    
    print(f"SUCCESS! Video saved to Desktop: {output_file}")
    print(f"Total Time: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    main()