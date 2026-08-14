def split_into_sections(text, sentences_per_section=3):
    sentences = [s.strip() for s in text.split(".") if s.strip()]

    sections = []

    for i in range(0, len(sentences), sentences_per_section):
        section = ". ".join(sentences[i:i + sentences_per_section]) + "."
        sections.append(section)

    return sections

def get_section_media(section, workdir, section_number):
    from .topic import get_keywords
    from .pexels import search_image, search_video, download_image, download_video

    keywords = get_keywords(section)
    search_keyword = " ".join(keywords)

    image_url = search_image(search_keyword)
    video_url = search_video(search_keyword)

    image_path = None
    video_path = None

    if image_url:
        image_path = workdir / f"section_{section_number}.jpg"
        download_image(image_url, image_path)

    if video_url:
        video_path = workdir / f"section_{section_number}.mp4"
        download_video(video_url, video_path)

    return {
        "text": section,
        "keywords": keywords,
        "image_path": image_path,
        "video_path": video_path,
    }