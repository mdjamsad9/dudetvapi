# DUDE TV API Scraper & Decryptor Template

This repository automatically fetches, decrypts, and hosts static JSON feeds from the `streamtvapp.top` domain using GitHub Actions.

## How it Works

The scraper runs in a hybrid decryption mode:
1. **Local Python Decryption**: Standard endpoints (like categories and channel lists) are decrypted instantly using static keys and IVs.
2. **Dynamic JNI Decryption**: Secure endpoints (like events, highlights, and stream links) that use dynamic IVs and signature-based encryption are decrypted by running a headless Android Emulator in the GitHub Actions runner, installing the original app, and calling its native JNI library via ADB.

All decrypted outputs are saved in the `public_decrypted/` directory, which can be hosted directly via GitHub Pages to serve as a clean, independent API.

## Repository Structure

- `fetch_and_decrypt.py`: The main automation script that fetches and decrypts all feeds.
- `Decryptor.java`: The Java helper injected into the Android JVM via ADB to invoke JNI decryption.
- `DUDEtv_v2.5.apk`: The original Android application APK used for JNI decryption.
- `config.json`: Configuration specifying the target API URLs.
- `.github/workflows/scheduler.yml`: The GitHub Actions workflow that schedules the run every 6 hours on a macOS cloud runner.

## Setup Instructions

### 1. Enable Workflow Write Permissions on GitHub
For the GitHub Actions workflow to push the decrypted feeds back to your repository:
1. Go to your repository **Settings** on GitHub.
2. In the left sidebar, click on **Actions** > **General**.
3. Scroll down to **Workflow permissions**.
4. Select **"Read and write permissions"** and click **Save**.

### 2. Enable GitHub Pages (Optional but Recommended)
To host the decrypted JSON feeds as a public API:
1. Go to your repository **Settings** > **Pages**.
2. Under **Build and deployment**, set **Source** to `Deploy from a branch`.
3. Select the `main` (or `master`) branch and click **Save**.
4. Your API will be live at: `https://<username>.github.io/<repo>/public_decrypted/`

### 3. Local Execution
If you want to run it on your local PC:
1. Keep an Android emulator running (with the DUDEtv app installed).
2. Install the Python requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the script:
   ```bash
   python fetch_and_decrypt.py
   ```
