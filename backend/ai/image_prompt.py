"""Turn today's entry into a prompt for drawing the day.

The job is to reflect the day back faithfully — what happened, and how it
felt — in a form an image generator can use. Not to decide for the writer what
their day is allowed to look like.

Without an API key a deterministic fallback still assembles a usable prompt
from the entry's own words.
"""

from __future__ import annotations

import re

from backend.ai.client import complete_json, is_available
from backend.models import ImagePromptResponse
from backend.render.document import RenderedDoc

STYLES: dict[str, tuple[str, str]] = {
    "watercolor": ("水彩", "loose watercolour on cold-press paper, soft bleeds, visible paper grain"),
    "ink": ("水墨", "east-asian ink wash, restrained palette, generous negative space"),
    "gouache": ("不透明水彩", "matte gouache, flat shapes, muted mid-tones"),
    "pencil": ("色鉛筆", "coloured pencil on toned paper, gentle hatching"),
    "oil": ("油畫", "oil on canvas, visible brushwork, warm layered colour"),
    "risograph": ("孔版印刷", "two-colour risograph print, slight misregistration, grainy texture"),
    "storybook": ("繪本", "children's picture-book illustration, warm and simple shapes"),
    "photo": ("寫實", "natural-light photography, shallow depth of field, honest and unstyled"),
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt_en": {"type": "string"},
        "prompt_zh": {"type": "string"},
        "mood": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "negative_prompt": {"type": "string"},
    },
    "required": ["prompt_en", "prompt_zh", "mood", "keywords", "negative_prompt"],
    "additionalProperties": False,
}

SYSTEM = """\
You read one day of someone's journal and write a prompt they can hand to an \
image generator to draw that day.

Your job is to reflect the day back to them faithfully:

- Everything in the image comes from what they wrote. The specific things they \
  mentioned — a borrowed bicycle, rain, a hospital corridor, a passage they \
  read, their son waking at 2am — are the subject. Never invent events, and \
  never leave out the thing the day was actually about.
- Carry the *feeling* as well as the facts. If the day was heavy, the image is \
  heavy; if it was relieved, or dull, or quietly grateful, the image is that. \
  Do not brighten a hard day into something the writer would not recognise, \
  and do not add drama to a plain one.
- Whatever they wrote about belongs in the picture — including faith, prayer, \
  scripture, church, or anything else they named. Draw what they wrote.
- One coherent scene. Name the subject, the setting, the time of day, the \
  light, and the palette. Skip camera jargon and quality-booster word salad \
  ("8k", "masterpiece", "trending on artstation").
- `prompt_en` is the working prompt, 40-80 words. `prompt_zh` is the same \
  scene written naturally in Traditional Chinese.
- `mood` is 2-6 Traditional Chinese characters describing the day's feeling. \
  `keywords` are 3-6 concrete things lifted from the entry, in Traditional \
  Chinese.
- `negative_prompt` covers only technical failure modes worth excluding \
  (garbled text, distorted hands, watermarks). It is not a place for taste.
"""


def _fallback(doc: RenderedDoc, style: str) -> ImagePromptResponse:
    style_zh, style_en = STYLES.get(style, STYLES["watercolor"])

    # Skip the digest's own scaffolding (date header, "## section" lines,
    # "- label：" prefixes) so only the writer's words seed the prompt.
    body_lines = [
        re.sub(r"^-\s*[^：]{0,12}：", "", line).strip()
        for line in doc.to_plain_text().splitlines()[1:]
        if line.strip() and not line.lstrip().startswith("#")
    ]
    chunks = [
        c.strip(" 　·-–—")
        for c in re.split(r"[。！？；\n，、,.!?;]", "\n".join(body_lines))
        if 3 <= len(c.strip()) <= 18
    ]
    keywords = chunks[:5] or ["這一天"]
    subject = "、".join(keywords[:4])

    return ImagePromptResponse(
        prompt_en=(
            f"A single scene from one ordinary day, drawn from what happened: "
            f"{subject}. Keep the mood honest and unembellished — natural "
            f"light, everyday surroundings, nothing staged. {style_en}."
        ),
        prompt_zh=(
            f"畫出這一天真實的樣子，畫面裡有：{subject}。"
            f"自然的光線、日常的環境，不用美化，忠實就好。{style_zh}風格。"
        ),
        mood="如實",
        keywords=keywords,
        negative_prompt="garbled text, distorted hands, watermark, signature",
        source="fallback",
    )


def build_image_prompt(
    doc: RenderedDoc, *, style: str = "watercolor"
) -> ImagePromptResponse:
    if not is_available():
        return _fallback(doc, style)

    style_zh, style_en = STYLES.get(style, STYLES["watercolor"])
    user = (
        f"畫風：{style_zh}（{style_en}）\n"
        f"請把這個畫風寫進 prompt_en 與 prompt_zh。\n\n"
        f"--- 今天的日記 ---\n{doc.to_plain_text()}"
    )
    try:
        data = complete_json(
            system=SYSTEM, user=user, schema=_SCHEMA, max_tokens=6000, effort="medium"
        )
        return ImagePromptResponse(**data, source="claude")
    except Exception:  # noqa: BLE001 - a dead API must not break the button
        return _fallback(doc, style)
