import os
import time
import subprocess
import requests

WARMUP_SECONDS = 15

fb_token = os.getenv("FB_TOKEN")
page_id = os.getenv("PAGE_ID")
source = os.getenv("STREAM_SOURCE")
chat_id = os.getenv("TG_CHAT_ID")
bot_token = os.getenv("TG_BOT_TOKEN")
count = int(os.getenv("STREAM_COUNT", 1))

def fix_dash_url(url):
    if not url: return None
    if "scontent-" in url and ".fbcdn.net" in url:
        end = url.find(".fbcdn.net")
        return "https://video.xx.fbcdn.net" + url[end + len(".fbcdn.net"):]
    return url

def extract_key(url):
    if not url: return None
    if "/rtmp/" in url: return url.split("/rtmp/")[-1]
    return url

def get_new_stream():
    try:
        r = requests.post(
            f"https://graph.facebook.com/v17.0/{page_id}/live_videos",
            params={"access_token": fb_token, "status": "UNPUBLISHED", "title": "Key Extract", "description": "Extraction"}
        ).json()
        if "id" not in r: return None, None, None
        live_id = r["id"]
        info = requests.get(
            f"https://graph.facebook.com/v17.0/{live_id}",
            params={"access_token": fb_token, "fields": "stream_url,dash_preview_url"}
        ).json()
        return info.get("stream_url"), live_id, fix_dash_url(info.get("dash_preview_url"))
    except: return None, None, None

def run_extraction(name):
    stream_url, live_id, dash = get_new_stream()
    if not stream_url:
        requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data={"chat_id": chat_id, "text": f"❌ فشل استخراج: {name}"})
        return

    cmd = ["ffmpeg", "-re", "-i", source, "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-f", "flv", stream_url]
    proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    fresh_dash = dash
    for attempt in range(3):
        time.sleep(WARMUP_SECONDS if attempt == 0 else 5)
        try:
            info = requests.get(f"https://graph.facebook.com/v17.0/{live_id}", params={"access_token": fb_token, "fields": "dash_preview_url"}).json()
            d = fix_dash_url(info.get("dash_preview_url"))
            if d:
                fresh_dash = d
                break
        except: pass

    proc.terminate()
    try: proc.wait(timeout=5)
    except: proc.kill()

    key = extract_key(stream_url)
    msg = f"🔑 *{name}*\n\n`{key}`\n\n👁️ DASH:\n`{fresh_dash}`"
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

ts = int(time.time())
for i in range(1, count + 1):
    run_extraction(f"بث{i}_{ts}")
    time.sleep(1)
  
