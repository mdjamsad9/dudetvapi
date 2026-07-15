import os
import sys
import json
import base64
import urllib.request
import subprocess
import re
from Crypto.Cipher import AES

# Set terminal encoding to UTF-8
sys.stdout.reconfigure(encoding="utf-8")

CONFIG_FILE = "config.json"
STATIC_KEY = b"6ayJ7jo@ao#pxVc%"

def replace_sportzx_with_dudetv(data):
    if isinstance(data, dict):
        return {k: replace_sportzx_with_dudetv(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_sportzx_with_dudetv(item) for item in data]
    elif isinstance(data, str):
        return re.sub(r'(?i)sportzx', 'DUDE Tv', data)
    return data

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: {CONFIG_FILE} not found.")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def check_adb_devices():
    try:
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True, check=True)
        lines = res.stdout.strip().split("\n")[1:]
        devices = [line.split()[0] for line in lines if line.strip() and "device" in line]
        return devices
    except Exception as e:
        print(f"ADB is not installed or not in PATH: {e}")
        return []

def get_device_paths():
    try:
        apk_path_cmd = subprocess.run(["adb", "shell", "pm", "path", "com.sportzx.live"], capture_output=True, text=True, check=True)
        apk_path = apk_path_cmd.stdout.strip().replace("package:", "")
        if not apk_path:
            raise ValueError("DUDEtv app package (com.sportzx.live) is not installed on the emulator.")
            
        base_dir = apk_path.replace("base.apk", "")
        lib_list_cmd = subprocess.run(["adb", "shell", f"ls {base_dir}lib/"], capture_output=True, text=True, check=True)
        arch = lib_list_cmd.stdout.strip().split()[0]
        lib_path = f"{base_dir}lib/{arch}/libnative-lib.so"
        
        return apk_path, lib_path
    except Exception as e:
        print(f"Error resolving emulator paths: {e}")
        print("Please make sure the DUDEtv app is installed and the emulator is fully booted.")
        return None, None

def ensure_decryptor_jar():
    jar_name = "Decryptor.jar"
    local_jar_path = os.path.join("..", jar_name) if os.path.exists(os.path.join("..", jar_name)) else jar_name
    
    if not os.path.exists(local_jar_path):
        print("Decryptor.jar not found. Re-building...")
        try:
            java_file = "../Decryptor.java" if os.path.exists("../Decryptor.java") else "Decryptor.java"
            android_jar = "C:/Users/mdjam/AppData/Local/Android/Sdk/platforms/android-35/android.jar"
            d8_bat = "C:/Users/mdjam/AppData/Local/Android/Sdk/build-tools/34.0.0/d8.bat"
            
            subprocess.run(["javac", "--release", "8", "-cp", android_jar, java_file], check=True)
            subprocess.run([d8_bat, "--output", ".", "Decryptor.class"], check=True)
            
            import zipfile
            with zipfile.ZipFile(jar_name, "w") as z:
                z.write("classes.dex")
            
            # Clean up temporary files
            for temp in ["classes.dex", "Decryptor.class"]:
                if os.path.exists(temp):
                    os.remove(temp)
            local_jar_path = jar_name
            print("Successfully built Decryptor.jar")
        except Exception as e:
            print(f"Failed to build Decryptor.jar: {e}")
            sys.exit(1)
            
    try:
        subprocess.run(["adb", "push", local_jar_path, "/data/local/tmp/Decryptor.jar"], check=True, capture_output=True)
        print("Decryptor.jar verified and pushed to emulator.")
    except Exception as e:
        print(f"Failed to push Decryptor.jar: {e}")
        sys.exit(1)

def clean_and_decode_b64(encrypted_b64):
    clean_str = "".join(encrypted_b64.split())
    padding = len(clean_str) % 4
    if padding:
        clean_str += "=" * (4 - padding)
    try:
        return base64.urlsafe_b64decode(clean_str)
    except Exception:
        return base64.b64decode(clean_str)

def decrypt_cbc(ciphertext_bytes, key, iv):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext_bytes)
    if len(decrypted) > 0:
        pad_len = decrypted[-1]
        if 1 <= pad_len <= 16 and all(x == pad_len for x in decrypted[-pad_len:]):
            decrypted = decrypted[:-pad_len]
    return decrypted

def decrypt_local_b5cdbd48(enc_bytes, iv_str):
    dec = decrypt_cbc(enc_bytes, STATIC_KEY, iv_str.encode("utf-8"))
    dec_str = dec.decode("utf-8", errors="ignore")
    return json.loads(dec_str)

def decrypt_via_emulator(payload, apk_path, lib_path):
    temp_file = "temp_payload.txt"
    device_file = "/data/local/tmp/payload.txt"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(payload)
        subprocess.run(["adb", "push", temp_file, device_file], check=True, capture_output=True)
        
        classpath = f"/data/local/tmp/Decryptor.jar:{apk_path}"
        cmd = [
            "adb", "shell",
            f"export CLASSPATH={classpath}; app_process /data/local/tmp Decryptor {lib_path} '@{device_file}'"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        output = res.stdout
        
        if "DECRYPTION RESULT START" in output:
            decrypted_str = output.split("DECRYPTION RESULT START")[1].split("DECRYPTION RESULT END")[0].strip()
            return json.loads(decrypted_str)
        else:
            print(f"Decryption failed: {res.stderr}")
            return None
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

def decrypt_data(payload, apk_path=None, lib_path=None):
    try:
        enc_bytes = clean_and_decode_b64(payload)
        # Check for DEADBEEF format (starts with \xde\xad\xbe\xef)
        if len(enc_bytes) >= 20 and enc_bytes[:4] == b'\xde\xad\xbe\xef':
            if apk_path and lib_path:
                print("      [DEADBEEF] Decrypting via emulator JNI...")
                return decrypt_via_emulator(payload, apk_path, lib_path)
            else:
                print("      [DEADBEEF] Emulator not available. Decrypting locally with static key...")
                iv = enc_bytes[4:20]
                ciphertext = enc_bytes[20:]
                dec = decrypt_cbc(ciphertext, STATIC_KEY, iv)
                dec_str = dec.decode("utf-8", errors="ignore")
                dec_str = dec_str.rstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10')
                return json.loads(dec_str)
        else:
            print("      [Static Format] Decrypting locally...")
            dec = decrypt_cbc(enc_bytes, STATIC_KEY, b"HsjJTCA7jJztpL2w")
            dec_str = dec.decode("utf-8", errors="ignore")
            dec_str = dec_str.rstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10')
            return json.loads(dec_str)
    except Exception as e:
        print(f"      Decryption attempt failed: {e}")
        if apk_path and lib_path:
            try:
                print("      Trying emulator JNI fallback...")
                return decrypt_via_emulator(payload, apk_path, lib_path)
            except Exception as jnie:
                print(f"      JNI fallback failed: {jnie}")
        return None

def write_api_specification(out_dir):
    spec = {
        "api_name": "DUDE TV Decrypted API",
        "base_url": "https://mdjamsad9.github.io/dudetvapi/public_decrypted",
        "description": "This is a clean, decrypted static JSON API database for DUDE TV, generated automatically every 6 hours via GitHub Actions.",
        "endpoints": {
            "categories_menu": {
                "path": "/cats.json",
                "description": "Main category menu list. Contains the category names, images, and links.",
                "fields": {
                    "id": "Unique category identifier",
                    "title": "Category display name",
                    "image": "Category thumbnail URL",
                    "catLink": "The path to the subcategory channels list (e.g. 'cats/bangla.json') OR a direct M3U playlist URL (starts with http/https)"
                },
                "usage_flow": "Step 1: Fetch this file to render the menu. When user clicks a category: if 'catLink' starts with 'http', stream the M3U. If it points to a local file, fetch it from 'base_url + /cats/{catLink}'."
            },
            "sports_tv_channels": {
                "path": "/sports.json",
                "description": "List of standard sports TV channels.",
                "fields": {
                    "id": "Unique TV channel identifier (e.g., '1')",
                    "title": "Channel display name",
                    "image": "Channel logo URL",
                    "formats": "Array of stream server format names"
                },
                "usage_flow": "To play a TV channel: Fetch its stream links using '/channels/{id}.json' (e.g., '/channels/1.json')."
            },
            "live_events": {
                "path": "/events.json",
                "description": "List of live and upcoming sports matches and events.",
                "fields": {
                    "id": "Unique event identifier (e.g. 50002)",
                    "title": "Event title",
                    "eventInfo": "Object containing teams, logos, event name, start and end times",
                    "formats": "Available stream quality/server names"
                },
                "usage_flow": "To play a live match/event: Fetch its stream links using '/channels/{id}.json' (e.g., '/channels/50002.json')."
            },
            "live_events_combined": {
                "path": "/events_with_channels.json",
                "description": "A consolidated central database combining all live events directly with their decrypted channel links. Recommended for web and single-page apps to avoid multiple fetch requests.",
                "fields": {
                    "id": "Event identifier",
                    "title": "Event title",
                    "decoded_channels": "Array of stream objects containing 'api', 'link', 'logo', and 'title'"
                }
            },
            "highlights": {
                "path": "/highlights.json",
                "description": "List of completed matches highlights and replays.",
                "fields": {
                    "id": "Unique highlight identifier (e.g. 100035)",
                    "title": "Match title",
                    "eventInfo": "Teams and start/end time metadata",
                    "formats": "Available highlight categories (e.g., HIGHLIGHTS, FULL MATCH)"
                },
                "usage_flow": "To play highlights: Fetch its stream links using '/channels/{id}.json' (e.g., '/channels/100035.json')."
            },
            "event_categories": {
                "path": "/eventcats.json",
                "description": "Filter categories for live events (e.g. Football, Cricket, Badminton)."
            }
        },
        "sub_directories": {
            "subcategory_details": {
                "path_pattern": "/cats/{catLink}.json",
                "description": "Contains list of channels inside a specific category (e.g. `/cats/bangla.json`).",
                "fields": {
                    "id": "Channel identifier (use this to fetch stream links from /channels/{id}.json)",
                    "title": "Channel display name",
                    "image": "Channel logo URL"
                }
            },
            "decrypted_stream_links": {
                "path_pattern": "/channels/{id}.json",
                "description": "Contains decrypted playback streams for any specific live event, highlight, or TV channel.",
                "fields": {
                    "title": "Stream title/quality/server name (e.g. beIN Sports HD)",
                    "link": "The playback stream URL (DASH/MPD or HLS/M3U8). Note: Some URLs contain headers like '|user-agent=...' or '|Cookie=...' which MUST be parsed and set as custom request headers in your player.",
                    "api": "ClearKey decryption keys in the format 'kid:key' for encrypted DASH streams (if applicable)."
                },
                "player_decryption_handling": "If 'api' is present (e.g. '385ceb97...:18dce92...'), it represents a DRM protected stream. Split the 'api' string by ':' to get the Key ID (left) and Key (right), and pass them to your player's DRM ClearKey configuration."
            }
        }
    }
    spec_file = os.path.join(out_dir, "api_specification.json")
    with open(spec_file, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
    print(f"  [SUCCESS] API Specification JSON saved to: {spec_file}")

def main():
    config = load_config()
    out_dir = config.get("output_directory", "public_decrypted")
    os.makedirs(out_dir, exist_ok=True)
    
    devices = check_adb_devices()
    emulator_available = False
    apk_path, lib_path = None, None
    
    if not devices:
        print("WARNING: No emulator/device detected via ADB.")
        print("Continuing with local decryption only. 'deadbeef' format files (events, cats, highlights) will be skipped.")
    else:
        print(f"Connected devices: {devices}")
        apk_path, lib_path = get_device_paths()
        if apk_path and lib_path:
            emulator_available = True
            ensure_decryptor_jar()
            print("Emulator decryption engine is READY!")
            
    for name, ep_info in config["endpoints"].items():
        url = ep_info["url"]
        format_type = ep_info["format"]
        print(f"\nProcessing endpoint '{name}' ({url})...")
        
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as response:
                response_json = json.loads(response.read().decode("utf-8"))
                
            payload = response_json.get("data")
            if not payload:
                print(f"  Skipping {name}: 'data' field is empty.")
                continue
                
            enc_bytes = clean_and_decode_b64(payload)
            decrypted_json = None
            
            if format_type == "b5cdbd48":
                iv_str = "HsjJTCA7jJztpL2w"
                print(f"  Decrypting locally using static key and IV '{iv_str}'...")
                decrypted_json = decrypt_local_b5cdbd48(enc_bytes, iv_str)
                
            elif format_type == "deadbeef":
                print(f"  Decrypting {name}...")
                decrypted_json = decrypt_data(payload, apk_path, lib_path)
                
            if decrypted_json:
                decrypted_json = replace_sportzx_with_dudetv(decrypted_json)
                output_file = os.path.join(out_dir, f"{name}.json")
                with open(output_file, "w", encoding="utf-8") as out_f:
                    json.dump(decrypted_json, out_f, indent=2, ensure_ascii=False)
                print(f"  [SUCCESS] Decrypted and saved to: {output_file} ({len(decrypted_json)} items)")
                
                # If this is cats.json, process individual subcategory files
                if name == "cats":
                    print("  Processing individual subcategories...")
                    sub_dir = os.path.join(out_dir, "cats")
                    os.makedirs(sub_dir, exist_ok=True)
                    updated_cats = []
                    
                    for i, cat in enumerate(decrypted_json):
                        cat_id = cat.get("id")
                        title = cat.get("title", f"Category {cat_id}")
                        cat_link = cat.get("catLink")
                        
                        cat_copy = dict(cat)
                        if cat_link and not cat_link.startswith("http"):
                            print(f"    [{i+1}/{len(decrypted_json)}] Fetching subcategory: {title} ({cat_link})...")
                            try:
                                relative_path = f"cats/{cat_link}.json"
                                sub_url = f"https://streamtvapp.top/{relative_path}"
                                sub_req = urllib.request.Request(sub_url, headers={"User-Agent": "Mozilla/5.0"})
                                with urllib.request.urlopen(sub_req, timeout=15) as sub_res:
                                    sub_json = json.loads(sub_res.read().decode("utf-8"))
                                
                                sub_payload = sub_json.get("data")
                                if sub_payload:
                                    sub_bytes = clean_and_decode_b64(sub_payload)
                                    # Use the correct static IV to prevent first block corruption and keep true IDs
                                    iv_bytes = b"HsjJTCA7jJztpL2w"
                                    dec = decrypt_cbc(sub_bytes, STATIC_KEY, iv_bytes)
                                    dec_str = dec.decode("utf-8", errors="ignore")
                                     
                                    sub_data = None
                                    try:
                                        sub_data = json.loads(dec_str)
                                    except Exception as je:
                                        print(f"      Failed to parse decrypted JSON for {cat_link}: {je}")
                                                
                                    if sub_data:
                                        sub_data = replace_sportzx_with_dudetv(sub_data)
                                        sub_out_file = os.path.join(sub_dir, f"{cat_link}.json")
                                        with open(sub_out_file, "w", encoding="utf-8") as sub_f:
                                            json.dump(sub_data, sub_f, indent=2, ensure_ascii=False)
                                        print(f"      Saved: {sub_out_file} ({len(sub_data)} channels)")
                                        cat_copy["catLink"] = f"cats/{cat_link}.json"
                                    else:
                                        print(f"      Failed to parse decrypted JSON for {cat_link}")
                            except Exception as ce:
                                print(f"      Failed to process subcategory {cat_link}: {ce}")
                                
                        updated_cats.append(cat_copy)
                        
                    with open(output_file, "w", encoding="utf-8") as out_f:
                        json.dump(updated_cats, out_f, indent=2, ensure_ascii=False)
                    print(f"  [SUCCESS] Updated {output_file} with hosted API links.")
                
                # If this is events.json, process individual channels
                if name == "events":
                    print("  Processing individual channels for each event (merging main and fallback)...")
                    ch_dir = os.path.join(out_dir, "channels")
                    os.makedirs(ch_dir, exist_ok=True)
                    events_with_channels = []
                    
                    for i, event in enumerate(decrypted_json):
                        event_id = event.get("id")
                        title = event.get("title", f"Event {event_id}")
                        print(f"    [{i+1}/{len(decrypted_json)}] Fetching channels for: {title} (ID: {event_id})...")
                        
                        event_channels = []
                        ch_out_file = os.path.join(ch_dir, f"{event_id}.json")
                        channel_status = "unavailable"  # default
                        
                        channels1 = []
                        channels2 = []
                        fetched_successfully = False

                        # 1. Fetch main ID channels
                        try:
                            ch_url = f"https://streamtvapp.top/channels/{event_id}.json"
                            ch_req = urllib.request.Request(ch_url, headers={"User-Agent": "Mozilla/5.0"})
                            with urllib.request.urlopen(ch_req, timeout=15) as ch_res:
                                ch_json = json.loads(ch_res.read().decode("utf-8"))
                            
                            ch_payload = ch_json.get("data")
                            if ch_payload:
                                dec_ch = decrypt_data(ch_payload, apk_path, lib_path)
                                if dec_ch:
                                    channels1 = replace_sportzx_with_dudetv(dec_ch)
                                    fetched_successfully = True
                                    print(f"      Fetched {event_id}.json ({len(channels1)} channels)")
                        except Exception as ce:
                            print(f"      Main attempt failed for {event_id}: {ce}")

                        # 2. Fetch fallback ID 'e' channels
                        try:
                            ch_url = f"https://streamtvapp.top/channels/{event_id}e.json"
                            ch_req = urllib.request.Request(ch_url, headers={"User-Agent": "Mozilla/5.0"})
                            with urllib.request.urlopen(ch_req, timeout=15) as ch_res:
                                ch_json = json.loads(ch_res.read().decode("utf-8"))
                            
                            ch_payload = ch_json.get("data")
                            if ch_payload:
                                dec_ch = decrypt_data(ch_payload, apk_path, lib_path)
                                if dec_ch:
                                    channels2 = replace_sportzx_with_dudetv(dec_ch)
                                    fetched_successfully = True
                                    print(f"      Fetched fallback {event_id}e.json ({len(channels2)} channels)")
                        except Exception as ce2:
                            print(f"      Fallback attempt failed for {event_id}e: {ce2}")

                        # 3. Merge and deduplicate channels if we fetched anything
                        if fetched_successfully:
                            seen_links = set()
                            merged_channels = []
                            for ch in (channels1 + channels2):
                                # Clean link comparison by ignoring query params or request headers after '|'
                                link = ch.get("link", "").split("|")[0].strip()
                                if link and link not in seen_links:
                                    seen_links.add(link)
                                    merged_channels.append(ch)
                            
                            event_channels = merged_channels
                            channel_status = "live"
                            with open(ch_out_file, "w", encoding="utf-8") as ch_f:
                                json.dump(event_channels, ch_f, indent=2, ensure_ascii=False)
                            print(f"      Saved merged: {ch_out_file} ({len(event_channels)} channels) [LIVE]")

                        # If both attempts failed to fetch live data, use cache if available
                        if not fetched_successfully:
                            if os.path.exists(ch_out_file):
                                try:
                                    with open(ch_out_file, "r", encoding="utf-8") as cached_f:
                                        event_channels = json.load(cached_f)
                                    event_channels = replace_sportzx_with_dudetv(event_channels)
                                    channel_status = "cached"  # using last known good
                                    print(f"      [CACHED] Using last known data for {event_id} ({len(event_channels)} channels)")
                                except Exception as cached_err:
                                    channel_status = "unavailable"
                                    print(f"      [UNAVAILABLE] Cache read error for {event_id}: {cached_err}")
                            else:
                                channel_status = "unavailable"
                                print(f"      [UNAVAILABLE] No data or cache available for {event_id}")
                            
                        # Add channels metadata to event object
                        event_copy = dict(event)
                        event_copy["decoded_channels"] = event_channels
                        event_copy["channel_status"] = channel_status  # live / cached / unavailable
                        events_with_channels.append(event_copy)
                        
                    # Save combined file
                    combined_file = os.path.join(out_dir, "events_with_channels.json")
                    with open(combined_file, "w", encoding="utf-8") as comb_f:
                        json.dump(events_with_channels, comb_f, indent=2, ensure_ascii=False)
                    print(f"  [SUCCESS] Saved combined channels mapping to: {combined_file}")
            else:
                print(f"  [FAILED] Failed to decrypt {name}")
                
        except Exception as e:
            print(f"  [ERROR] Failed to process {name}: {e}")

    # Collect and process all unique TV channel stream links from all subcategories
    # We run this even if emulator is not available because we have local decryption fallback
    print("\n=== Harvesting TV Channel Streams from Subcategories ===")
    ch_dir = os.path.join(out_dir, "channels")
    os.makedirs(ch_dir, exist_ok=True)
    
    tv_channel_ids = set()
    
    # Read subcategory files from public_decrypted/cats/
    sub_dir = os.path.join(out_dir, "cats")
    if os.path.exists(sub_dir):
        for file_name in os.listdir(sub_dir):
            if file_name.endswith(".json"):
                sub_path = os.path.join(sub_dir, file_name)
                try:
                    with open(sub_path, "r", encoding="utf-8") as sf:
                        channels_list = json.load(sf)
                    if isinstance(channels_list, list):
                        for ch in channels_list:
                            ch_id = ch.get("id")
                            if ch_id:
                                tv_channel_ids.add(str(ch_id))
                except Exception as e:
                    print(f"Error reading subcategory file {file_name}: {e}")
                    
    # Read channels from sports.json (main category file)
    sports_path = os.path.join(out_dir, "sports.json")
    if os.path.exists(sports_path):
        try:
            with open(sports_path, "r", encoding="utf-8") as sf:
                channels_list = json.load(sf)
            if isinstance(channels_list, list):
                for ch in channels_list:
                    ch_id = ch.get("id")
                    if ch_id:
                        tv_channel_ids.add(str(ch_id))
        except Exception as e:
            print(f"Error reading sports.json: {e}")
            
    # Read channels from highlights.json
    highlights_path = os.path.join(out_dir, "highlights.json")
    if os.path.exists(highlights_path):
        try:
            with open(highlights_path, "r", encoding="utf-8") as sf:
                channels_list = json.load(sf)
            if isinstance(channels_list, list):
                for ch in channels_list:
                    ch_id = ch.get("id")
                    if ch_id:
                        tv_channel_ids.add(str(ch_id))
        except Exception as e:
            print(f"Error reading highlights.json: {e}")
            
    print(f"Found {len(tv_channel_ids)} unique TV channel/highlight IDs in subcategories.")
    
    # Fetch and decrypt each TV channel stream info
    for idx, ch_id in enumerate(sorted(list(tv_channel_ids))):
        print(f"    [{idx+1}/{len(tv_channel_ids)}] Fetching TV channel ID: {ch_id}...")
        try:
            ch_url = f"https://streamtvapp.top/channels/{ch_id}.json"
            ch_req = urllib.request.Request(ch_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(ch_req, timeout=12) as ch_res:
                ch_json = json.loads(ch_res.read().decode("utf-8"))
            
            ch_payload = ch_json.get("data")
            if ch_payload:
                dec_ch = decrypt_data(ch_payload, apk_path, lib_path)
                if dec_ch:
                    dec_ch = replace_sportzx_with_dudetv(dec_ch)
                    ch_out_file = os.path.join(ch_dir, f"{ch_id}.json")
                    with open(ch_out_file, "w", encoding="utf-8") as ch_f:
                        json.dump(dec_ch, ch_f, indent=2, ensure_ascii=False)
                    print(f"      Saved: {ch_out_file} ({len(dec_ch)} channels)")
        except Exception as ce:
            print(f"      Failed to process TV channel {ch_id}: {ce}")

    # Write the API specification JSON file
    write_api_specification(out_dir)

    print("\nProcessing complete!")

if __name__ == "__main__":
    main()
