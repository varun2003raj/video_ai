import os
from pathlib import Path
import requests


def search_image(query):
    api_key = os.getenv("PEXELS_API_KEY")

    url = "https://api.pexels.com/v1/search"

    headers = {
        "Authorization": api_key
    }

    params = {
        "query": query,
        "per_page": 1
    }

    response = requests.get(url, headers=headers, params=params)

    response.raise_for_status()

    data = response.json()

    if data["photos"]:
        return data["photos"][0]["src"]["large"]

    return None

def download_image(image_url, save_path: Path):
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()

    save_path.parent.mkdir(parents=True, exist_ok=True)

    save_path.write_bytes(response.content)

    return save_path

def search_video(query):
    api_key = os.getenv("PEXELS_API_KEY")

    url = "https://api.pexels.com/videos/search"

    headers = {
        "Authorization": api_key
    }

    params = {
        "query": query,
        "per_page": 1
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if data["videos"]:
        video_files = data["videos"][0]["video_files"]

        # Prefer HD video
        for video_file in video_files:
            if video_file.get("width", 0) >= 720:
                return video_file["link"]

        if video_files:
            return video_files[0]["link"]

    return None

def download_video(video_url, save_path: Path):
    response = requests.get(video_url, timeout=60)
    response.raise_for_status()

    save_path.parent.mkdir(parents=True, exist_ok=True)

    save_path.write_bytes(response.content)

    return save_path