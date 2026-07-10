import os
import sys
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from downloader import DownloadManager

# Set theme and color options
ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class DownloadTaskRow(ctk.CTkFrame):
    def __init__(self, master, url, cancel_callback, remove_callback, **kwargs):
        # Add card-like borders and corner radius
        super().__init__(master, corner_radius=8, border_width=1, border_color="#3e3e3e", **kwargs)
        self.url = url
        self.cancel_callback = cancel_callback
        self.remove_callback = remove_callback

        # Configure Grid layout inside the card
        self.grid_columnconfigure(0,
                                 weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=0) # Title & Status
        self.grid_rowconfigure(1, weight=0) # Progress bar
        self.grid_rowconfigure(2, weight=0) # Details & Button

        # Row 0: Title/URL (left) and Status (right)
        display_url = url[:60] + "..." if len(url) > 60 else url
        self.url_label = ctk.CTkLabel(self, text=display_url, anchor="w", font=("Helvetica", 13, "bold"), text_color="#e0e0e0")
        self.url_label.grid(row=0, column=0, padx=12, pady=(10, 2), sticky="ew")

        self.status_badge = ctk.CTkLabel(self, text="QUEUED", font=("Helvetica", 10, "bold"), text_color="#ffb74d")
        self.status_badge.grid(row=0, column=1, padx=12, pady=(10, 2), sticky="e")

        # Row 1: Progress Bar (spans across both columns)
        self.progress_bar = ctk.CTkProgressBar(self, height=8, progress_color="#1f6aa5")
        self.progress_bar.set(0.0)
        self.progress_bar.grid(row=1, column=0, columnspan=2, padx=12, pady=8, sticky="ew")

        # Row 2: Details/Speed/ETA (left) and Action Button (right)
        self.details_label = ctk.CTkLabel(self, text="Waiting to start...", font=("Helvetica", 11), text_color="#888888")
        self.details_label.grid(row=2, column=0, padx=12, pady=(2, 10), sticky="w")

        self.action_button = ctk.CTkButton(
            self, text="Cancel", width=70, height=24, font=("Helvetica", 11, "bold"),
            fg_color="#d9534f", hover_color="#c9302c", command=self.on_action_click
        )
        self.action_button.grid(row=2, column=1, padx=12, pady=(2, 10), sticky="e")

        self.finished = False

    def update_progress(self, info):
        status = info.get("status", "")
        percentage = info.get("percentage", 0.0)
        self.progress_bar.set(percentage / 100.0)

        title = info.get("title", "")
        if title:
            display_title = title[:60] + "..." if len(title) > 60 else title
            self.url_label.configure(text=display_title)

        if status == "downloading":
            self.status_badge.configure(text="DOWNLOADING", text_color="#29b6f6")
            speed_val = info.get("speed", 0)
            if speed_val:
                if speed_val > 1024 * 1024:
                    speed = f"{speed_val / (1024 * 1024):.1f} MB/s"
                else:
                    speed = f"{speed_val / 1024:.1f} KB/s"
            else:
                speed = "0 KB/s"

            eta_val = info.get("eta", 0)
            eta = f"{eta_val}s" if eta_val else "unknown"
            
            self.details_label.configure(text=f"{percentage:.1f}% completed • Speed: {speed} • ETA: {eta}")
        elif status == "finished":
            self.status_badge.configure(text="PROCESSING", text_color="#ab47bc")
            self.details_label.configure(text="Finalizing video files...")
            self.progress_bar.set(1.0)

    def mark_completed(self, error=None):
        self.finished = True
        if error:
            self.status_badge.configure(text="ERROR", text_color="#e57373")
            self.details_label.configure(text=f"Failed: {error}")
            self.progress_bar.configure(progress_color="#d9534f")
            self.action_button.configure(text="Remove", fg_color="#5bc0de", hover_color="#31b0d5")
        else:
            self.status_badge.configure(text="FINISHED", text_color="#66bb6a")
            self.details_label.configure(text="Successfully downloaded!")
            self.progress_bar.configure(progress_color="#5cb85c")
            self.action_button.configure(text="Remove", fg_color="#5bc0de", hover_color="#31b0d5")

    def on_action_click(self):
        if not self.finished:
            self.cancel_callback(self.url)
            self.status_badge.configure(text="CANCELLING", text_color="#e57373")
        else:
            self.remove_callback(self.url)
            self.destroy()

class VideoDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Multi-URL Video Downloader (TikTok, YouTube, Facebook)")
        self.geometry("900x650")
        self.minsize(800, 500)

        self.downloader = DownloadManager()
        self.task_rows = {}
        self.completed_count = 0
        self.failed_count = 0

        # Default Download Directory
        default_dir = r"D:\Videos"
        if not os.path.exists(default_dir):
            try:
                os.makedirs(default_dir, exist_ok=True)
            except Exception:
                default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                if not os.path.exists(default_dir):
                    default_dir = os.getcwd()
        self.download_dir = tk.StringVar(value=default_dir)

        self._build_ui()

    def _build_ui(self):
        # Grid Configuration
        self.grid_rowconfigure(0, weight=0) # Header
        self.grid_rowconfigure(1, weight=1) # Main area split
        self.grid_columnconfigure(0, weight=1)

        # Header Frame
        header_frame = ctk.CTkFrame(self, corner_radius=0, height=60)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        header_label = ctk.CTkLabel(
            header_frame, 
            text="Multi-URL Video Downloader", 
            font=ctk.CTkFont(family="Helvetica", size=22, weight="bold")
        )
        header_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")

        # Theme Selector
        self.theme_menu = ctk.CTkOptionMenu(
            header_frame, 
            values=["System", "Dark", "Light"],
            command=self.change_theme,
            width=100
        )
        self.theme_menu.grid(row=0, column=1, padx=20, pady=15, sticky="e")

        # Main Workspace Container
        main_pane = ctk.CTkFrame(self, fg_color="transparent")
        main_pane.grid(row=1, column=0, sticky="nsew", padx=15, pady=15)
        main_pane.grid_rowconfigure(0, weight=1)
        main_pane.grid_columnconfigure(0, weight=4) # Left URL list / settings
        main_pane.grid_columnconfigure(1, weight=6) # Right download progress list

        # Left Panel (Inputs and Settings)
        left_panel = ctk.CTkFrame(main_pane)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
        left_panel.grid_rowconfigure(1, weight=1) # URL textbox grows
        left_panel.grid_columnconfigure(0, weight=1)

        # URL Input Section
        url_section_label = ctk.CTkLabel(left_panel, text="Enter Video URLs (one per line):", font=("Helvetica", 14, "bold"))
        url_section_label.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        self.url_textbox = ctk.CTkTextbox(left_panel, wrap="none")
        self.url_textbox.grid(row=1, column=0, padx=15, pady=5, sticky="nsew")
        self.url_textbox.insert("1.0", "# Paste TikTok, YouTube, or Facebook URLs here\n")

        # Settings sub-frame
        settings_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        settings_frame.grid(row=2, column=0, padx=15, pady=15, sticky="ew")
        settings_frame.grid_columnconfigure(1, weight=1)

        # Quality selector
        ctk.CTkLabel(settings_frame, text="Quality:").grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
        self.quality_menu = ctk.CTkOptionMenu(settings_frame, values=["Best", "1080p", "720p", "480p", "Audio Only"])
        self.quality_menu.grid(row=0, column=1, columnspan=2, pady=5, sticky="ew")

        # Destination folder
        ctk.CTkLabel(settings_frame, text="Save To:").grid(row=1, column=0, padx=(0, 10), pady=5, sticky="w")
        self.path_entry = ctk.CTkEntry(settings_frame, textvariable=self.download_dir)
        self.path_entry.grid(row=1, column=1, pady=5, sticky="ew")
        self.browse_btn = ctk.CTkButton(settings_frame, text="Browse", width=70, command=self.browse_directory)
        self.browse_btn.grid(row=1, column=2, padx=(10, 0), pady=5, sticky="e")

        # Download Profile checkbox
        self.profile_var = tk.BooleanVar(value=False)
        self.profile_checkbox = ctk.CTkCheckBox(settings_frame, text="Download Profile / Playlist", variable=self.profile_var)
        self.profile_checkbox.grid(row=2, column=1, columnspan=2, pady=5, sticky="w")


        # Start Downloads button
        self.download_btn = ctk.CTkButton(
            left_panel, 
            text="Start Downloads", 
            font=("Helvetica", 16, "bold"),
            height=40,
            command=self.start_downloads
        )
        self.download_btn.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="ew")

        # Right Panel (Download progress updates)
        right_panel = ctk.CTkFrame(main_pane)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        right_header_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        right_header_frame.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="ew")
        right_header_frame.grid_columnconfigure(0, weight=1)

        right_label = ctk.CTkLabel(right_header_frame, text="Download Progress", font=("Helvetica", 14, "bold"))
        right_label.grid(row=0, column=0, sticky="w")

        self.stats_label = ctk.CTkLabel(right_header_frame, text="Done: 0 | Failed: 0", font=("Helvetica", 12, "bold"), text_color="#a0a0a0")
        self.stats_label.grid(row=0, column=1, sticky="e")

        # Scrollable area for tasks
        self.scrollable_frame = ctk.CTkScrollableFrame(right_panel)
        self.scrollable_frame.grid(row=1, column=0, padx=15, pady=(5, 15), sticky="nsew")

    def browse_directory(self):
        selected = filedialog.askdirectory(initialdir=self.download_dir.get())
        if selected:
            self.download_dir.set(selected)

    def change_theme(self, choice):
        ctk.set_appearance_mode(choice)

    def start_downloads(self):
        raw_text = self.url_textbox.get("1.0", tk.END)
        urls = []
        for line in raw_text.splitlines():
            line = line.strip()
            # Ignore empty lines and comments
            if line and not line.startswith("#"):
                urls.append(line)

        if not urls:
            self.show_toast("No URLs found to download.")
            return

        output_dir = self.download_dir.get()
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                self.show_toast(f"Failed to create directory: {e}")
                return

        quality = self.quality_menu.get()
        is_playlist = self.profile_var.get()

        for url in urls:
            # If already exists, check if it's currently running
            if url in self.task_rows:
                if not self.task_rows[url].finished:
                    continue  # Skip if currently active
                else:
                    # Clean up old finished task row to start fresh
                    self.task_rows[url].destroy()
                    del self.task_rows[url]

            # Create a row in GUI
            row = DownloadTaskRow(
                self.scrollable_frame, 
                url=url, 
                cancel_callback=self.cancel_download,
                remove_callback=self.remove_task_row,
                fg_color="transparent"
            )
            row.pack(fill="x", padx=5, pady=5)
            self.task_rows[url] = row

            # Start thread via DownloadManager
            self.downloader.download_video(
                url=url,
                output_dir=output_dir,
                quality=quality,
                is_playlist=is_playlist,
                progress_callback=self.safe_update_progress,
                completion_callback=self.safe_completion_callback
            )

    def cancel_download(self, url):
        self.downloader.cancel_download(url)

    def remove_task_row(self, url):
        if url in self.task_rows:
            del self.task_rows[url]

    def safe_update_progress(self, url, info):
        # Update UI thread-safely
        self.after(0, self._update_progress, url, info)

    def _update_progress(self, url, info):
        if url in self.task_rows:
            self.task_rows[url].update_progress(info)

    def safe_completion_callback(self, url, error):
        self.after(0, self._completion_callback, url, error)

    def _completion_callback(self, url, error):
        if url in self.task_rows:
            self.task_rows[url].mark_completed(error)
            if error:
                self.failed_count += 1
            else:
                self.completed_count += 1
            self.update_stats_display()

    def update_stats_display(self):
        self.stats_label.configure(text=f"Done: {self.completed_count} | Failed: {self.failed_count}")

    def show_toast(self, message):
        # Basic popup or label warning
        dialog = ctk.CTkInputDialog(text=message, title="Message")
        dialog.destroy()

if __name__ == "__main__":
    app = VideoDownloaderApp()
    app.mainloop()
