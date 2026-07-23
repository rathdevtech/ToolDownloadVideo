import os
import threading
import yt_dlp
from yt_dlp.utils import DownloadError

class CancelledError(Exception):
    """Exception raised to abort download when cancelled by the user."""
    pass

class DownloadManager:
    def __init__(self):
        self.active_downloads = {}  # url -> status dict / cancel flag
        self.lock = threading.Lock()

    def download_video(self, url, output_dir, quality, is_playlist, progress_callback, completion_callback):
        """Starts a download in a new thread."""
        thread = threading.Thread(
            target=self._download_worker,
            args=(url, output_dir, quality, is_playlist, progress_callback, completion_callback),
            daemon=True
        )
        with self.lock:
            self.active_downloads[url] = {
                "thread": thread,
                "cancelled": False
            }
        thread.start()

    def cancel_download(self, url):
        """Signals a download to cancel."""
        with self.lock:
            if url in self.active_downloads:
                self.active_downloads[url]["cancelled"] = True

    def cancel_all(self):
        """Signals all active downloads to cancel."""
        with self.lock:
            for url in self.active_downloads:
                self.active_downloads[url]["cancelled"] = True

    def _download_worker(self, url, output_dir, quality, is_playlist, progress_callback, completion_callback):
        # Determine format selection based on quality choice
        # Best, 1080p, 720p, 480p, Audio Only
        ydl_opts = {
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
            'restrictfilenames': False,
            'noplaylist': not is_playlist,
            'impersonate': 'chrome',
            'no_warnings': True,
        }

        if quality == "Best":
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
        elif quality == "1080p":
            ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
        elif quality == "720p":
            ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
        elif quality == "480p":
            ydl_opts['format'] = 'bestvideo[height<=480]+bestaudio/best[height<=480]'
        elif quality == "Audio Only":
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        def ydl_progress_hook(d):
            # Check for cancellation
            with self.lock:
                if url in self.active_downloads and self.active_downloads[url]["cancelled"]:
                    raise CancelledError("Download cancelled by user")

            status_info = {
                "status": d.get("status", "downloading"),
                "filename": os.path.basename(d.get("filename", "")),
                "total_bytes": d.get("total_bytes") or d.get("total_bytes_estimate") or 0,
                "downloaded_bytes": d.get("downloaded_bytes", 0),
                "speed": d.get("speed", 0),
                "eta": d.get("eta", 0),
                "percentage": 0.0,
            }

            if status_info["total_bytes"] > 0:
                status_info["percentage"] = (status_info["downloaded_bytes"] / status_info["total_bytes"]) * 100
            elif d.get("status") == "finished":
                status_info["percentage"] = 100.0

            # Get video title or metadata if available
            if "info_dict" in d:
                status_info["title"] = d["info_dict"].get("title", status_info["filename"])
            else:
                status_info["title"] = status_info["filename"]

            progress_callback(url, status_info)

        ydl_opts['progress_hooks'] = [ydl_progress_hook]

        error_message = None
        try:
            # We fetch info first or directly download
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except CancelledError:
            error_message = "Cancelled"
        except Exception as e:
            error_message = str(e)

        with self.lock:
            if url in self.active_downloads:
                del self.active_downloads[url]

        completion_callback(url, error_message)
