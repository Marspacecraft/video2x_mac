import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageOps
import cv2
import subprocess
import os
import threading
import queue
import re

# --- 全局变量 ---
CONFIG_FILE = "video2x_config.txt"  # <<< 新增：配置文件名
video2x_path = ""
path_button = None
running_process = None
task_queue = None
progressbar = None

# --- 画布项目相关的全局变量 ---
canvas_bg_image_id, canvas_text_id, canvas_play_button_id = None, None, None
canvas_bg_photo_ref, canvas_play_photo_ref, canvas_pause_photo_ref = None, None, None


# --- 设置保存与加载 ---
def save_settings(path):  # <<< 新增函数
    """将有效的 video2x 路径保存到文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write(path)
    except Exception as e:
        print(f"保存设置时出错: {e}")

def load_settings():  # <<< 新增函数
    """程序启动时加载并验证 video2x 路径"""
    global video2x_path
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                path = f.read().strip()
            # 验证路径是否仍然有效
            if path and os.path.exists(path) and os.path.basename(path) == "video2x":
                video2x_path = path
                print(f"从配置文件加载路径成功: {video2x_path}")
                # 更新UI以反映已加载的路径
                if path_button:
                    path_button.config(fg="lawn green")
                if main_canvas and canvas_text_id:
                    main_canvas.itemconfig(canvas_text_id, text="点击选择视频文件", fill="#FFFF00")
                    main_canvas.tag_bind(canvas_text_id, "<Button-1>", select_video)
            else:
                 print("配置文件中的路径无效或已不存在。")
    except Exception as e:
        print(f"加载设置时出错: {e}")


# --- 图像创建函数 ---
def create_play_button_image(size=100, fill_color=(255, 255, 255), alpha=230, blur_radius=5):
    padding = blur_radius * 2
    temp_img_size = size + padding * 2
    temp_img = Image.new('L', (temp_img_size, temp_img_size), 0)
    draw = ImageDraw.Draw(temp_img)
    x_left = padding + size * 0.30;
    x_right = padding + size * 0.80
    y_top = padding + size * 0.20;
    y_bottom = padding + size * 0.80
    y_center = padding + size / 2
    points = [(x_left, y_top), (x_left, y_bottom), (x_right, y_center)]
    draw.polygon(points, fill=255)
    blurred_img = temp_img.filter(ImageFilter.GaussianBlur(blur_radius))
    final_img = Image.new('RGBA', (temp_img_size, temp_img_size), (0, 0, 0, 0))
    color_layer = Image.new('RGBA', (temp_img_size, temp_img_size), fill_color + (alpha,))
    final_img = Image.composite(color_layer, final_img, blurred_img)
    final_img = final_img.crop((padding, padding, padding + size, padding + size))
    return ImageTk.PhotoImage(final_img)


def create_pause_button_image(size=100, fill_color=(255, 255, 255), alpha=230, blur_radius=5):
    padding = blur_radius * 2
    temp_img_size = size + padding * 2
    temp_img = Image.new('L', (temp_img_size, temp_img_size), 0)
    draw = ImageDraw.Draw(temp_img)
    bar_width = size * 0.15
    gap_width = size * 0.1
    total_width = 2 * bar_width + gap_width
    y_top = padding + size * 0.20
    y_bottom = padding + size * 0.80
    x0_left = padding + (size - total_width) / 2
    x1_left = x0_left + bar_width
    draw.rectangle([x0_left, y_top, x1_left, y_bottom], fill=255)
    x0_right = x1_left + gap_width
    x1_right = x0_right + bar_width
    draw.rectangle([x0_right, y_top, x1_right, y_bottom], fill=255)
    blurred_img = temp_img.filter(ImageFilter.GaussianBlur(blur_radius))
    final_img = Image.new('RGBA', (temp_img_size, temp_img_size), (0, 0, 0, 0))
    color_layer = Image.new('RGBA', (temp_img_size, temp_img_size), fill_color + (alpha,))
    final_img = Image.composite(color_layer, final_img, blurred_img)
    final_img = final_img.crop((padding, padding, padding + size, padding + size))
    return ImageTk.PhotoImage(final_img)


def get_video_thumbnail(video_path):
    cap = cv2.VideoCapture(video_path)
    success, frame = cap.read()
    cap.release()
    if success:
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img)
    return None


def select_video(event=None):
    filetypes = [("MP4 files", "*.mp4"), ("AVI files", "*.avi"), ("MKV files", "*.mkv"), ("All files", "*.*")]
    filename = filedialog.askopenfilename(title="选择视频文件", filetypes=filetypes)
    if filename:
        show_video_thumbnail(filename)


def select_video2x_path():
    global video2x_path
    path = filedialog.askopenfilename(title="请选择 video2x 程序")
    if path:
        basename = os.path.basename(path)
        filename_without_ext = os.path.splitext(basename)[0]
        if filename_without_ext == "video2x":
            video2x_path = path
            save_settings(video2x_path)  # <<< 修改：成功选择后保存路径
            messagebox.showinfo("路径已设置", f"video2x 程序路径已成功设置为:\n{video2x_path}")
            if path_button: path_button.config(fg="lawn green")
            if main_canvas and canvas_text_id:
                main_canvas.itemconfig(canvas_text_id, text="点击选择视频文件", fill="#FFFF00")
                main_canvas.tag_bind(canvas_text_id, "<Button-1>", select_video)
        else:
            messagebox.showwarning("文件错误", f"您选择的文件是 '{basename}'，并非所需的 'video2x' 程序。请重新选择。")


# --- 线程与实时输出逻辑 ---
def run_command_in_thread(command, work_dir):
    global running_process, task_queue
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True,
            text=True, encoding='utf-8', errors='replace', bufsize=1, cwd=work_dir
        )
        running_process = process
        for line in iter(process.stdout.readline, ''):
            task_queue.put(line)
        process.stdout.close()
        return_code = process.wait()
        task_queue.put(f"\n--- 执行完成，退出代码: {return_code} ---")
    except Exception as e:
        task_queue.put(f"\n--- 线程中发生错误: {e} ---")
    finally:
        running_process = None
        task_queue.put(None)  # 使用 None 作为任务结束的信号


def process_queue(input_path, output_path):
    global task_queue, progressbar
    try:
        while True:
            line = task_queue.get_nowait()
            if line is None:
                # 任务结束
                if progressbar:
                    progressbar['value'] = 0
                    progressbar.pack_forget()
                if path_button:
                    path_button.config(state=tk.NORMAL)

                # 检查任务是否成功并显示对比图
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    messagebox.showinfo("任务成功", f"视频处理完成！\n输出文件: {output_path}")
                    show_comparison_view(input_path, output_path)
                else:
                    messagebox.showwarning("任务未完成", "处理被中断或失败，未生成有效的输出文件。")
                    # 恢复到原始的单缩略图视图
                    show_video_thumbnail(input_path)
                return
            else:
                print(line.strip())
                match = re.search(r"\((\d+\.?\d*?)%\)", line)
                if match:
                    percentage = float(match.group(1))
                    if progressbar:
                        progressbar['value'] = percentage
    except queue.Empty:
        pass
    root.after(100, lambda: process_queue(input_path, output_path))


def stop_task_execution():
    global running_process
    if running_process and running_process.poll() is None:
        print("DEBUG: 正在终止运行中的进程...")
        running_process.terminate()
        if task_queue:
            task_queue.put("\n--- 命令已被用户手动停止... ---\n")
    else:
        print("DEBUG: 没有可终止的进程。")


def start_task_execution(video_path):
    global task_queue, progressbar, path_button

    main_canvas.itemconfig(canvas_play_button_id, image=canvas_pause_photo_ref)
    main_canvas.tag_unbind(canvas_play_button_id, "<Button-1>")
    main_canvas.tag_bind(canvas_play_button_id, "<Button-1>", lambda e: stop_task_execution())

    if progressbar:
        progressbar['value'] = 0
        progressbar.pack(side="bottom", fill="x", padx=10, pady=(10, 5))

    if path_button:
        path_button.config(state=tk.DISABLED)

    working_dir = os.path.dirname(video2x_path)
    executable_name = os.path.basename(video2x_path)
    input_dir, input_basename = os.path.split(video_path)
    input_filename, input_ext = os.path.splitext(input_basename)
    output_filename = f"{input_filename}_processed{input_ext}"
    output_path = os.path.join(input_dir, output_filename)
    model_param_map = {"降噪1": "models-se", "降噪2": "models-pro"}
    model_param = model_param_map.get(model_variable.get(), "models-se")
    command_to_run = (
        f'./"{executable_name}" -i "{video_path}" -o "{output_path}" '
        f'-p realcugan -s {scale_variable.get()} --realcugan-model {model_param}'
    )
    print(f"DEBUG: 工作目录: {working_dir}")
    print(f"DEBUG: 执行命令: {command_to_run}")

    task_queue = queue.Queue()

    thread = threading.Thread(target=run_command_in_thread, args=(command_to_run, working_dir))
    thread.daemon = True
    thread.start()

    process_queue(video_path, output_path)


# --- 核心显示函数 ---
def show_comparison_view(input_path, output_path):
    """
    创建一个分屏对比图：左半边是原始视频，右半边是生成视频。
    """
    global canvas_bg_photo_ref  # 使用单个引用来存储最终合成的图像

    main_canvas.delete("all")

    input_thumb = get_video_thumbnail(input_path)
    output_thumb = get_video_thumbnail(output_path)

    if not input_thumb or not output_thumb:
        messagebox.showerror("显示错误", "无法加载一个或两个视频的缩略图。")
        show_video_thumbnail(input_path)  # 如果出错，则回退到原始视图
        return

    # 确保两个缩略图尺寸一致，以输入视频为准
    if input_thumb.size != output_thumb.size:
        # Pillow 9.1.0+ 使用 Image.Resampling.LANCZOS
        resample_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
        output_thumb = output_thumb.resize(input_thumb.size, resample_filter)

    width, height = input_thumb.size

    # --- 核心图像处理 ---
    left_half_box = (0, 0, width // 2, height)
    left_crop = input_thumb.crop(left_half_box)
    right_half_box = (width // 2, 0, width, height)
    right_crop = output_thumb.crop(right_half_box)
    composite_image = Image.new('RGB', (width, height))
    composite_image.paste(left_crop, (0, 0))
    composite_image.paste(right_crop, (width // 2, 0))
    draw = ImageDraw.Draw(composite_image)
    separator_x = width // 2
    draw.line([(separator_x, 0), (separator_x, height)], fill=(255, 255, 0), width=2)
    # --- 图像处理结束 ---

    # 调整窗口和画布大小以适应合成后的图像
    control_frame_height = control_frame.winfo_height()
    new_window_height = height + control_frame_height + 10
    root.resizable(True, True)
    root.geometry(f"{width}x{new_window_height}")
    root.update_idletasks()
    root.resizable(False, False)
    main_canvas.config(width=width, height=height)

    # 将最终合成的图像显示在画布上
    canvas_bg_photo_ref = ImageTk.PhotoImage(composite_image)
    main_canvas.create_image(0, 0, anchor="nw", image=canvas_bg_photo_ref)

    # 添加说明标签
    main_canvas.create_text(
        width / 4, 20, text="原始视频 (左)",
        fill="white", font=("Arial", 14, "bold"), anchor="n"
    )
    main_canvas.create_text(
        width * 3 / 4, 20, text="生成视频 (右)",
        fill="white", font=("Arial", 14, "bold"), anchor="n"
    )


def show_video_thumbnail(video_path):
    global canvas_bg_image_id, canvas_text_id, canvas_play_button_id, canvas_bg_photo_ref
    global canvas_play_photo_ref, canvas_pause_photo_ref, path_button
    thumb = get_video_thumbnail(video_path)
    if thumb:
        thumb_width, thumb_height = thumb.size
        control_frame_height = control_frame.winfo_height()
        new_window_height = thumb_height + control_frame_height + 10
        root.resizable(True, True)
        root.geometry(f"{thumb_width}x{new_window_height}")
        root.update_idletasks()
        root.resizable(False, False)
        main_canvas.config(width=thumb_width, height=thumb_height)
        main_canvas.delete("all")
        canvas_bg_photo_ref = ImageTk.PhotoImage(thumb)
        canvas_bg_image_id = main_canvas.create_image(0, 0, anchor="nw", image=canvas_bg_photo_ref)

        button_size_ratio = 0.15
        dynamic_button_size = int(min(thumb_width, thumb_height) * button_size_ratio)
        min_button_size = 60
        dynamic_button_size = max(dynamic_button_size, min_button_size)
        blur_val = max(3, int(dynamic_button_size * 0.05))
        canvas_play_photo_ref = create_play_button_image(
            size=dynamic_button_size, fill_color=(255, 255, 0), alpha=230, blur_radius=blur_val
        )
        canvas_pause_photo_ref = create_pause_button_image(
            size=dynamic_button_size, fill_color=(255, 255, 0), alpha=230, blur_radius=blur_val
        )
        canvas_play_button_id = main_canvas.create_image(
            thumb_width / 2, thumb_height / 2, anchor="center", image=canvas_play_photo_ref
        )
        main_canvas.video_path = video_path
        main_canvas.tag_bind(canvas_play_button_id, "<Button-1>",
                             lambda e: start_task_execution(e.widget.video_path))

        if path_button:
            path_button.config(
                text="重新选择视频文件",
                command=select_video,
                fg="lawn green",
                state=tk.NORMAL
            )
    else:
        messagebox.showerror("错误", "无法读取视频缩略图。请确保文件是有效的视频格式。")


# --- Tkinter GUI 设置 ---
root = tk.Tk()
root.title("视频增强工具")
root.configure(bg="black")
root.geometry("640x480")

control_frame = tk.Frame(root, bg="black")
control_frame.pack(side="top", fill="x", pady=5, padx=10)

path_button = tk.Button(
    control_frame, text="选择程序路径", command=select_video2x_path, bg="gray20", fg="red",
    activebackground="gray30", activeforeground="white", highlightthickness=0,
    padx=5, relief=tk.FLAT, borderwidth=2
)
path_button.pack(side="left", padx=(0, 15))

model_options = ["降噪1", "降噪2"]
model_variable = tk.StringVar(root)
model_variable.set(model_options[0])
model_label = tk.Label(control_frame, text="选择模型:", fg="white", bg="black", font=("Arial", 10))
model_label.pack(side="left", padx=(0, 5))
model_menu = tk.OptionMenu(control_frame, model_variable, *model_options)
model_menu.config(bg="gray20", fg="white", activebackground="gray30", highlightthickness=0)
model_menu["menu"].config(bg="gray20", fg="white")
model_menu.pack(side="left", padx=(0, 15))

scale_variable = tk.StringVar(root)
scale_options_map = {"降噪1": ["4", "3", "2"], "降噪2": ["3", "2"]}
scale_label = tk.Label(control_frame, text="扩大倍率:", fg="white", bg="black", font=("Arial", 10))
scale_label.pack(side="left", padx=(0, 5))
scale_menu = tk.OptionMenu(control_frame, scale_variable, "")
scale_menu.config(bg="gray20", fg="white", activebackground="gray30", highlightthickness=0, width=5)
scale_menu["menu"].config(bg="gray20", fg="white")
scale_menu.pack(side="left", padx=(0, 10))

progressbar = ttk.Progressbar(control_frame, orient='horizontal', length=100, mode='determinate')


def update_scale_options(*args):
    selected_model = model_variable.get()
    new_options = scale_options_map.get(selected_model, [])
    menu = scale_menu["menu"]
    menu.delete(0, "end")
    if new_options:
        for option in new_options:
            menu.add_command(label=option, command=lambda value=option: scale_variable.set(value))
        scale_variable.set(new_options[0])
    else:
        scale_variable.set("")


model_variable.trace_add('write', update_scale_options)
update_scale_options()

main_canvas = tk.Canvas(root, bg="black", highlightthickness=0)
main_canvas.pack(side="top", fill="both", expand=True)
root.update_idletasks()
canvas_text_id = main_canvas.create_text(
    main_canvas.winfo_width() / 2, main_canvas.winfo_height() / 2,
    text="请先从左上角选择 video2x 程序", fill="gray",
    font=("Arial", 16, "bold"), anchor="center"
)

load_settings() # <<< 修改：在主循环开始前加载设置

print("DEBUG: 程序已启动。")
root.mainloop()
print("DEBUG: 程序已关闭。")