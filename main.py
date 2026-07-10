import os
import sys
import json
import base64
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

def clean_and_decode_b64(encrypted_b64):
    # Remove any whitespaces/newlines
    clean_str = "".join(encrypted_b64.split())
    # Add proper base64 URL-safe padding
    padding = len(clean_str) % 4
    if padding:
        clean_str += "=" * (4 - padding)
    try:
        return base64.urlsafe_b64decode(clean_str)
    except Exception:
        return base64.b64decode(clean_str)

def decrypt_cbc(ciphertext_bytes, key, iv):
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext_bytes) + decryptor.finalize()

def decrypt_deadbeef(enc_bytes, key):
    # Format: 4 bytes Magic (DEADBEEF) + 16 bytes dynamic IV + Ciphertext
    iv = enc_bytes[4:20]
    ciphertext = enc_bytes[20:]
    
    # We decrypt ciphertext with key and the extracted dynamic IV
    decrypted_bytes = decrypt_cbc(ciphertext, key, iv)
    
    # Clean trailing PKCS7 padding bytes
    clean_bytes = decrypted_bytes.rstrip(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10')
    return json.loads(clean_bytes.decode("utf-8"))

def decrypt_b5cdbd48(enc_bytes, key, hardcoded_iv):
    # For b5cdbd48 endpoints, the ciphertext is the raw decrypted bytes (which starts with magic b5cdbd48...).
    # Decrypt everything using AES-128-CBC with the key and hardcoded IV.
    decrypted_bytes = decrypt_cbc(enc_bytes, key, hardcoded_iv)
    
    # Reconstruct the first block (first 16 bytes) by checking prefixes.
    # The output will start with either '[{"id":"1","genre' or '[{"id":"1","title'.
    dec_str_raw = decrypted_bytes.decode("utf-8", errors="replace")
    
    prefixes = ['[{"id":"1","genre', '[{"id":"1","title']
    for prefix in prefixes:
        try:
            reconstructed = prefix + dec_str_raw[16:]
            clean_json = reconstructed.rstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10')
            return json.loads(clean_json)
        except Exception:
            continue
            
    raise ValueError("Failed to correct first-block corruption with known JSON prefixes")

def main():
    # Load configuration
    with open("config.json", "r") as f:
        config = json.load(f)
    
    # Fetch credentials from Environment Variables
    key_var = config["aes_credentials"]["key_env_var"]
    iv_var = config["aes_credentials"]["iv_env_var"]
    
    key = os.environ.get(key_var)
    iv = os.environ.get(iv_var)
    
    if not key or not iv:
        print(f"Error: Environment variables {key_var} and {iv_var} must be set.")
        sys.exit(1)
        
    key_bytes = key.encode("utf-8")
    iv_bytes = iv.encode("utf-8")
    
    out_dir = config["output_directory"]
    os.makedirs(out_dir, exist_ok=True)
    
    # Process each configured endpoint
    for name, ep_info in config["endpoints"].items():
        url = ep_info["url"]
        format_type = ep_info["format"]
        print(f"Fetching from {url}...")
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            
            response_json = r.json()
            encrypted_payload = response_json.get("data")
            
            if not encrypted_payload:
                print(f"Skipping {name}: 'data' key not found.")
                continue
                
            enc_bytes = clean_and_decode_b64(encrypted_payload)
            
            if format_type == "deadbeef":
                decrypted_json = decrypt_deadbeef(enc_bytes, key_bytes)
            elif format_type == "b5cdbd48":
                decrypted_json = decrypt_b5cdbd48(enc_bytes, key_bytes, iv_bytes)
            else:
                print(f"Skipping {name}: Unknown format type {format_type}")
                continue
            
            output_file = os.path.join(out_dir, f"{name}.json")
            with open(output_file, "w", encoding="utf-8") as out_f:
                json.dump(decrypted_json, out_f, indent=2, ensure_ascii=False)
            print(f"Successfully saved decrypted output: {output_file}")
            
        except Exception as e:
            print(f"Failed to process {name}: {e}")

if __name__ == "__main__":
    main()
