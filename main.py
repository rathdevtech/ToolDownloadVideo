import os
import sys
import time
import yt_dlp


def get_downloaded_ids(download_folder):
    """Get set of video IDs already downloaded (extracted from filenames)."""
    downloaded = set()
    if os.path.exists(download_folder):
        for f in os.listdir(download_folder):
            # Extract ID from filename pattern: "title [ID].ext"
            if '[' in f and ']' in f:
                vid_id = f[f.rfind('[') + 1:f.rfind(']')]
                if vid_id:
                    downloaded.add(vid_id)
    return downloaded


def extract_video_id(url):
    """Extract video ID from a YouTube URL."""
    url = url.strip()
    if 'shorts/' in url:
        return url.split('shorts/')[-1].split('?')[0].split('&')[0]
    if 'v=' in url:
        return url.split('v=')[-1].split('&')[0]
    if 'youtu.be/' in url:
        return url.split('youtu.be/')[-1].split('?')[0]
    return None


def download_videos(links_file, download_folder):
    # Ensure download folder exists
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    # Read links from file
    with open(links_file, 'r', encoding='utf-8') as f:
        links = [line.strip() for line in f if line.strip()]

    # Filter out already downloaded
    downloaded_ids = get_downloaded_ids(download_folder)
    remaining = []
    for url in links:
        vid_id = extract_video_id(url)
        if vid_id and vid_id in downloaded_ids:
            continue
        remaining.append(url)

    print(f"Total links: {len(links)}")
    print(f"Already downloaded: {len(links) - len(remaining)}")
    print(f"Remaining to download: {len(remaining)}")

    if not remaining:
        print("All videos already downloaded!")
        return

    # yt-dlp options - use Edge cookies from browser
    # Using extractor_args to set the player client to web for better compatibility
    # yt-dlp options - optimized for downloading YouTube Shorts without requiring cookies
    ydl_opts = {
        'outtmpl': os.path.join(download_folder, '%(title)s [%(id)s].%(ext)s'),
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'ignoreerrors': True,
        'no_warnings': False,
        'quiet': False,
        'sleep_interval': 1,
        'max_sleep_interval': 3,
        'retries': 10,
        'fragment_retries': 10,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }

    # Check if a custom valid cookies file exists
    cookie_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
    if os.path.exists(cookie_file):
        with open(cookie_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if 'LOGIN_INFO' in content or 'SID' in content or 'SSID' in content:
                print(f"Using cookies file: {cookie_file}")
                ydl_opts['cookiefile'] = cookie_file

    # Download one by one
    success = 0
    failed = 0
    failed_urls = []

    for i, url in enumerate(remaining, 1):
        print(f"\n{'=' * 60}")
        print(f"[{i}/{len(remaining)}] Downloading: {url}")
        print(f"{'=' * 60}")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.download([url])
                if result == 0:
                    success += 1
                else:
                    failed += 1
                    failed_urls.append(url)
        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1
            failed_urls.append(url)

        # Brief pause between downloads
        if i < len(remaining):
            time.sleep(1)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"DOWNLOAD COMPLETE")
    print(f"  Successful: {success}")
    print(f"  Failed: {failed}")
    print(f"  Previously downloaded: {len(links) - len(remaining)}")
    print(f"{'=' * 60}")

    if failed_urls:
        failed_file = os.path.join(os.path.dirname(links_file), 'failed_links.txt')
        with open(failed_file, 'w', encoding='utf-8') as f:
            for url in failed_urls:
                f.write(url + '\n')
        print(f"\nFailed URLs saved to: {failed_file}")


if __name__ == "__main__":
    LINKS_TXT = r"C:\Users\USer\OneDrive\Desktop\ToolDownloadVideo\links.txt"
    DOWNLOAD_DIR = r"C:\Users\USer\OneDrive\Desktop\ToolDownloadVideo\download"
    download_videos(LINKS_TXT, DOWNLOAD_DIR)
