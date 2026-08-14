from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer


def get_summary(text):
    parser = PlaintextParser.from_string(
        text,
        Tokenizer("english")
    )

    summarizer = TextRankSummarizer()

    sentences = summarizer(parser.document, 2)

    return " ".join(str(sentence) for sentence in sentences)

from collections import Counter
import re


def get_keywords(text, limit=5):
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())

    stop_words = {
        "this", "that", "with", "from", "have", "they",
        "their", "there", "about", "which", "would",
        "could", "should", "into", "also", "more",
        "than", "when", "where", "while", "because",
        "plays", "important", "role", "helps", "strong"
    }

    words = [word for word in words if word not in stop_words]

    counts = Counter(words)

    return [word for word, count in counts.most_common(limit)]