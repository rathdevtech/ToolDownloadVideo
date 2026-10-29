import os
import sys
import re
import time
import requests

# Ensure UTF-8 output in Windows terminal
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def sanitize_filename(name, max_len=80):
    """Sanitize title for safe Windows filenames."""
    if not name:
        return "tiktok_video"
    # Remove illegal Windows characters: < > : " / \ | ? *
    clean = re.sub(r'[<>:"/\\|?*\n\r\t]', '', name).strip()
    # Collapse multiple spaces
    clean = re.sub(r'\s+', ' ', clean)
    if len(clean) > max_len:
        clean = clean[:max_len].strip()
    return clean or "tiktok_video"


def read_lines_safely(file_path):
    """Read lines from file with automatic BOM / encoding detection."""
    if not os.path.exists(file_path):
        return []

    with open(file_path, 'rb') as f:
        raw = f.read()

    if not raw:
        return []

    # Detect encoding via BOM or trial
    if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
        encoding = 'utf-16'
    elif raw.startswith(b'\xef\xbb\xbf'):
        encoding = 'utf-8-sig'
    else:
        try:
            raw.decode('utf-8')
            encoding = 'utf-8'
        except UnicodeDecodeError:
            encoding = 'utf-16'

    text = raw.decode(encoding, errors='ignore')
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_video_id(entry):
    """Extract numeric video/photo ID from URL or return entry if already an ID."""
    entry = entry.strip()
    if entry.isdigit():
        return entry

    # Match /video/ID or /photo/ID
    match = re.search(r'/(?:video|photo)/(\d+)', entry)
    if match:
        return match.group(1)

    # Embed URL: /player/v1/ID
    match = re.search(r'/player/v1/(\d+)', entry)
    if match:
        return match.group(1)

    return None


def is_downloadable_media(entry):
    """Check if entry is a downloadable TikTok video, photo post, or ID."""
    entry = entry.strip()
    if entry.isdigit():
        return True
    if '/video/' in entry or '/photo/' in entry or '/player/v1/' in entry:
        return True
    if 'vt.tiktok.com/' in entry or 'vm.tiktok.com/' in entry:
        return True
    return False


def get_downloaded_ids(download_folder):
    """Get set of video/photo IDs already downloaded."""
    downloaded = set()
    if os.path.exists(download_folder):
        for f in os.listdir(download_folder):
            if '[' in f and ']' in f:
                vid_id = f[f.rfind('[') + 1:f.rfind(']')]
                if vid_id:
                    # Handle slide suffix if present
                    vid_id = vid_id.split('_slide')[0].strip()
                    downloaded.add(vid_id)
    return downloaded


def fetch_from_tikwm(target_url, headers, max_retries=2):
    """Fetch video metadata and download URL from TikWM API with retries."""
    api_url = "https://www.tikwm.com/api/"
    data = {
        "url": target_url,
        "hd": 1  # Request HD if available
    }
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(api_url, data=data, headers=headers, timeout=20)
            if resp.status_code == 200:
                res_json = resp.json()
                if res_json.get("code") == 0:
                    return res_json.get("data", {})
        except Exception:
            if attempt < max_retries:
                time.sleep(1.5)
    return None


def stream_download_file(download_url, output_path, headers):
    """Stream download file directly with progress reporting."""
    with requests.get(download_url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        total_size = int(r.headers.get('content-length', 0))
        downloaded = 0
        chunk_size = 64 * 1024  # 64 KB

        with open(output_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        mb_done = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        sys.stdout.write(f"\r    Downloading: {percent:.1f}% ({mb_done:.2f}/{mb_total:.2f} MB)")
                        sys.stdout.flush()

    if total_size > 0:
        sys.stdout.write("\n")


def download_single_item(entry, download_folder, headers):
    """Download a single TikTok video or photo post."""
    entry = entry.strip()
    vid_id = extract_video_id(entry)

    if entry.isdigit():
        target_url = f"https://www.tiktok.com/@user/video/{entry}"
    else:
        target_url = entry

    print(f"  Fetching: {entry}")

    data = fetch_from_tikwm(target_url, headers)

    if data:
        item_id = str(data.get("id") or vid_id or "unknown")
        raw_title = data.get("title") or f"tiktok_{item_id}"
        author = data.get("author", {}).get("unique_id", "user")
        safe_title = sanitize_filename(raw_title)

        # Check for photo slides
        images = data.get("images")
        if images and isinstance(images, list):
            print(f"  [Photo Post] {len(images)} image(s) by @{author}")
            for idx, img_url in enumerate(images, 1):
                img_name = f"{safe_title} [{item_id}]_slide_{idx}.jpeg"
                img_path = os.path.join(download_folder, img_name)
                stream_download_file(img_url, img_path, headers)
            print(f"  [OK] Saved photo slide(s) to: {safe_title} [{item_id}]")
            return True, item_id

        # Video URL
        video_url = data.get("hdplay") or data.get("play") or data.get("wmplay")
        if video_url:
            filename = f"{safe_title} [{item_id}].mp4"
            output_path = os.path.join(download_folder, filename)
            print(f"  [Video] by @{author}: {raw_title[:60]}")
            stream_download_file(video_url, output_path, headers)
            print(f"  [OK] Saved: {filename}")
            return True, item_id

    # Fallback to yt-dlp if available
    try:
        import yt_dlp
        print("  Trying yt-dlp fallback...")
        ydl_opts = {
            'outtmpl': os.path.join(download_folder, '%(title)s [%(id)s].%(ext)s'),
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.download([target_url])
            if res == 0:
                print("  [OK] Downloaded via yt-dlp")
                return True, vid_id
    except Exception as e:
        print(f"  [yt-dlp] Fallback error: {e}")

    return False, vid_id


def download_videos(links_file, download_folder):
    """Main workflow to download TikTok videos from links_ids.txt."""
    if not os.path.exists(download_folder):
        os.makedirs(download_folder, exist_ok=True)

    all_lines = read_lines_safely(links_file)

    if not all_lines:
        print(f"No links or video IDs found in: {links_file}")
        print("Please paste TikTok links or video IDs into that file.")
        return

    # Filter: separate downloadable videos/photos from navigation/tags/profile links
    media_entries = []
    seen_ids = set()
    skipped_count = 0

    for line in all_lines:
        if is_downloadable_media(line):
            vid_id = extract_video_id(line)
            if vid_id:
                if vid_id not in seen_ids:
                    seen_ids.add(vid_id)
                    media_entries.append(line)
            else:
                media_entries.append(line)
        else:
            skipped_count += 1

    downloaded_ids = get_downloaded_ids(download_folder)

    # Filter out already downloaded
    remaining = []
    for entry in media_entries:
        vid_id = extract_video_id(entry)
        if vid_id and vid_id in downloaded_ids:
            continue
        remaining.append(entry)

    print(f"{'=' * 60}")
    print(f"TIKTOK VIDEO & MEDIA DOWNLOADER")
    print(f"{'=' * 60}")
    print(f"Total lines in file:     {len(all_lines)}")
    print(f"Filtered out non-media: {skipped_count} (tags, profiles, navigation)")
    print(f"Valid media items:      {len(media_entries)}")
    print(f"Already downloaded:     {len(media_entries) - len(remaining)}")
    print(f"Remaining to download:  {len(remaining)}")
    print(f"Download folder:        {download_folder}")
    print(f"{'=' * 60}\n")

    if not remaining:
        print("All valid videos and photos are already downloaded!")
        return

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
    }

    success = 0
    failed = 0
    failed_items = []

    for i, entry in enumerate(remaining, 1):
        print(f"[{i}/{len(remaining)}] Processing: {entry}")
        ok, vid_id = download_single_item(entry, download_folder, headers)
        if ok:
            success += 1
            if vid_id:
                downloaded_ids.add(vid_id)
        else:
            failed += 1
            failed_items.append(entry)
            print(f"  [FAILED] Could not download: {entry}")

        if i < len(remaining):
            time.sleep(1.0)
        print()

    # Summary
    print(f"{'=' * 60}")
    print("DOWNLOAD FINISHED")
    print(f"  Successful:             {success}")
    print(f"  Failed:                 {failed}")
    print(f"  Previously downloaded:  {len(media_entries) - len(remaining)}")
    print(f"{'=' * 60}")

    if failed_items:
        failed_file = os.path.join(os.path.dirname(links_file), 'failed_links.txt')
        with open(failed_file, 'w', encoding='utf-8') as f:
            for item in failed_items:
                f.write(item + '\n')
        print(f"\nFailed items saved to: {failed_file}")


if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    LINKS_FILE = os.path.join(BASE_DIR, "links_ids.txt")
    DOWNLOAD_DIR = os.path.join(BASE_DIR, "download")

    download_videos(LINKS_FILE, DOWNLOAD_DIR)
