from __future__ import annotations

from dataclasses import dataclass
from string import Template
from typing import Any


FIX_PROMPT = Template(
    """You are a professional copy-editor with expert command of English grammar and style.

Instruction: $instruction

Rules:
- Correct grammar, spelling, punctuation, capitalisation, and awkward phrasing.
- Preserve the author's voice and all intentional stylistic choices.
- Do NOT paraphrase or change the meaning.
- Keep terminology consistent throughout the text.
- Keep line breaks, paragraph structure, bullet lists, numbering, and indentation exactly as-is.
- Leave names, acronyms, URLs, e-mail addresses, numbers, and code blocks unchanged unless unambiguously broken.
- If the text includes mixed languages, only edit the language used in each segment without translating it.
- If the text is already correct, return it unchanged.

Text:
$text

Return format:
- Return ONLY the corrected text.
- No explanations, notes, labels, or surrounding quotes."""
)

SUMMARY_PROMPT = Template(
    """You are a precise and concise summarisation assistant.

Instruction: $instruction

Rules:
- Capture every important fact, date, entity, decision, and action item.
- Use concise bullet points (•) unless the source is a short paragraph, in which case use one concise sentence.
- Preserve the original language unless the instruction explicitly asks for a different language.
- Omit filler phrases and redundancy.
- Do NOT add opinions or information not present in the source.
- Keep critical numbers and units exactly as written.
- If there are explicit tasks, call out owner and due date when present.

Text:
$text

Return format:
- Return ONLY the summary.
- No preamble, no trailing explanation."""
)

TRANSLATE_PROMPT = Template(
    """You are a professional literary and technical translator.

Target language: $language
Instruction: $instruction

Rules:
- Translate every sentence accurately and naturally into $language.
- Match the register (formal/informal/technical) of the original text.
- Preserve paragraph structure, line breaks, bullet points, and numbering.
- Keep proper nouns, brand names, acronyms, URLs, e-mail addresses, numbers, and code blocks unchanged unless translation is required by context.
- Preserve markdown structure, headings, table formatting, and inline code markers.
- If the source is already in $language, return it unchanged.

Text:
$text

Return format:
- Return ONLY the translated text.
- No explanations, no surrounding quotes."""
)

TRANSLATION_LANGUAGES = {
    "translate_ar": "Arabic",
    "translate_en": "English",
    "translate_es": "Spanish",
    "translate_fr": "French",
    "translate_de": "German",
}


@dataclass
class OperationBuilder:
    def build_prompt(self, action: str, text: str, settings: dict[str, Any]) -> str:
        if action == "fix":
            instruction = settings.get("actions", {}).get("fix", {}).get(
                "prompt",
                "Fix grammar, spelling, punctuation, and casing while preserving structure and line breaks.",
            )
            return FIX_PROMPT.substitute(instruction=instruction, text=text)

        if action == "summarize":
            instruction = settings.get("actions", {}).get("summarize", {}).get(
                "prompt",
                "Summarize this text using concise bullet points, preserving key facts and action items.",
            )
            return SUMMARY_PROMPT.substitute(instruction=instruction, text=text)

        if action in TRANSLATION_LANGUAGES:
            instruction = settings.get("actions", {}).get(action, {}).get(
                "prompt", "Translate accurately and naturally."
            )
            return TRANSLATE_PROMPT.substitute(
                language=TRANSLATION_LANGUAGES[action],
                instruction=instruction,
                text=text,
            )

        if action == "translate_custom":
            instruction = settings.get("actions", {}).get(action, {}).get(
                "prompt", "Translate accurately and naturally."
            )
            language = settings.get("selected_custom_language", "English")
            return TRANSLATE_PROMPT.substitute(
                language=language, instruction=instruction, text=text
            )

        raise ValueError(f"Unsupported action: {action}")

    def output_mode_for(self, action: str, settings: dict[str, Any]) -> str:
        return (
            settings.get("actions", {})
            .get(action, {})
            .get("output_mode", settings.get("output_mode", "replace"))
        )

