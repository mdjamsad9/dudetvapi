import os
import sys
import json
import base64
import urllib.request
import subprocess
from Crypto.Cipher import AES

# Set terminal encoding to UTF-8
sys.stdout.reconfigure(encoding="utf-8")

CONFIG_FILE = "config.json"
STATIC_KEY = b"6ayJ7jo@ao#pxVc%"

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
    if not dec_str.strip().startswith(("[", "{")):
        reconstructed = '[{"id":"1","genre' + dec_str[16:]
        if reconstructed.strip().startswith("["):
            return json.loads(reconstructed)
        reconstructed2 = '[{"id":"1","title' + dec_str[16:]
        return json.loads(reconstructed2)
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
                if name == "eventcats":
                    iv_str = "HsjJTCA7jJztpL2w"
                elif name == "sports":
                    iv_str = "cats/sports.json"
                else:
                    iv_str = "HsjJTCA7jJztpL2w"
                
                print(f"  Decrypting locally using static key and IV '{iv_str}'...")
                decrypted_json = decrypt_local_b5cdbd48(enc_bytes, iv_str)
                
            elif format_type == "deadbeef":
                if not emulator_available:
                    print(f"  Skipping {name}: Requires emulator for native JNI decryption.")
                    continue
                print(f"  Decrypting via JNI emulator decryptor...")
                decrypted_json = decrypt_via_emulator(payload, apk_path, lib_path)
                
            if decrypted_json:
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
                                sub_url = f"https://mymodi.top/{relative_path}"
                                sub_req = urllib.request.Request(sub_url, headers={"User-Agent": "Mozilla/5.0"})
                                with urllib.request.urlopen(sub_req, timeout=15) as sub_res:
                                    sub_json = json.loads(sub_res.read().decode("utf-8"))
                                
                                sub_payload = sub_json.get("data")
                                if sub_payload:
                                    sub_bytes = clean_and_decode_b64(sub_payload)
                                    # Pad IV to 16 bytes
                                    iv_bytes = relative_path.encode("utf-8").ljust(16, b"\x00")[:16]
                                    dec = decrypt_cbc(sub_bytes, STATIC_KEY, iv_bytes)
                                    dec_str = dec.decode("utf-8", errors="ignore")
                                    
                                    sub_data = None
                                    if dec_str.strip().startswith(("[", "{")):
                                        sub_data = json.loads(dec_str)
                                    else:
                                        prefixes = ['[{"id":"1","titl', '[{"id":"1","genre']
                                        for prefix in prefixes:
                                            try:
                                                patched = prefix + dec_str[16:]
                                                sub_data = json.loads(patched)
                                                break
                                            except Exception:
                                                continue
                                                
                                    if sub_data:
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
                if name == "events" and emulator_available:
                    print("  Processing individual channels for each event...")
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

                        try:
                            ch_url = f"https://mymodi.top/channels/{event_id}.json"
                            ch_req = urllib.request.Request(ch_url, headers={"User-Agent": "Mozilla/5.0"})
                            with urllib.request.urlopen(ch_req, timeout=15) as ch_res:
                                ch_json = json.loads(ch_res.read().decode("utf-8"))
                            
                            ch_payload = ch_json.get("data")
                            if ch_payload:
                                dec_ch = decrypt_via_emulator(ch_payload, apk_path, lib_path)
                                if dec_ch:
                                    event_channels = dec_ch
                                    channel_status = "live"  # fresh from server
                                    with open(ch_out_file, "w", encoding="utf-8") as ch_f:
                                        json.dump(dec_ch, ch_f, indent=2, ensure_ascii=False)
                                    print(f"      Saved: {ch_out_file} ({len(dec_ch)} channels) [LIVE]")

                        except Exception as ce:
                            # Server returned 404 or error — check if we have a cached copy
                            if os.path.exists(ch_out_file):
                                try:
                                    with open(ch_out_file, "r", encoding="utf-8") as cached_f:
                                        event_channels = json.load(cached_f)
                                    channel_status = "cached"  # using last known good
                                    print(f"      [CACHED] Using last known data for {event_id} ({len(event_channels)} channels)")
                                except Exception:
                                    channel_status = "unavailable"
                                    print(f"      [UNAVAILABLE] No data for {event_id}: {ce}")
                            else:
                                channel_status = "unavailable"
                                print(f"      [UNAVAILABLE] {event_id}: {ce}")
                            
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
    if emulator_available:
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
                ch_url = f"https://mymodi.top/channels/{ch_id}.json"
                ch_req = urllib.request.Request(ch_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(ch_req, timeout=12) as ch_res:
                    ch_json = json.loads(ch_res.read().decode("utf-8"))
                
                ch_payload = ch_json.get("data")
                if ch_payload:
                    dec_ch = decrypt_via_emulator(ch_payload, apk_path, lib_path)
                    if dec_ch:
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
