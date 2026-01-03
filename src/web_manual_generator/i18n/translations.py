"""
Internationalization support for Chinese, Japanese, and English.
"""

from typing import Dict, Optional

SUPPORTED_LANGUAGES = ["zh", "ja", "en"]

_current_language = "zh"

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # General
    "untitled_recording": {
        "zh": "\u672a\u547d\u540d\u7684\u5f55\u5236",
        "ja": "\u7121\u984c\u306e\u8a18\u9332",
        "en": "Untitled Recording",
    },
    "recorder": {
        "zh": "\u5f55\u5236\u5668",
        "ja": "\u30ec\u30b3\u30fc\u30c0\u30fc",
        "en": "Recorder",
    },
    "executor": {
        "zh": "\u6267\u884c\u5668",
        "ja": "\u5b9f\u884c\u5668",
        "en": "Executor",
    },

    # Recording messages
    "recording_started": {
        "zh": "\u5f55\u5236\u5df2\u5f00\u59cb\u3002\u5728\u6d4f\u89c8\u5668\u4e2d\u64cd\u4f5c\uff0c\u64cd\u4f5c\u5c06\u88ab\u81ea\u52a8\u8bb0\u5f55\u3002",
        "ja": "\u8a18\u9332\u304c\u958b\u59cb\u3055\u308c\u307e\u3057\u305f\u3002\u30d6\u30e9\u30a6\u30b6\u3067\u64cd\u4f5c\u3059\u308b\u3068\u3001\u64cd\u4f5c\u304c\u81ea\u52d5\u7684\u306b\u8a18\u9332\u3055\u308c\u307e\u3059\u3002",
        "en": "Recording started. Actions in the browser will be automatically recorded.",
    },
    "recording_stopped": {
        "zh": "\u5f55\u5236\u5df2\u505c\u6b62\u3002\u5171\u8bb0\u5f55\u4e86 {steps} \u4e2a\u6b65\u9aa4\u3002",
        "ja": "\u8a18\u9332\u304c\u505c\u6b62\u3057\u307e\u3057\u305f\u3002{steps} \u30b9\u30c6\u30c3\u30d7\u304c\u8a18\u9332\u3055\u308c\u307e\u3057\u305f\u3002",
        "en": "Recording stopped. {steps} steps were recorded.",
    },
    "navigate_to": {
        "zh": "\u5bfc\u822a\u5230 {url}",
        "ja": "{url} \u306b\u79fb\u52d5",
        "en": "Navigate to {url}",
    },
    "click_element": {
        "zh": "\u70b9\u51fb {element}",
        "ja": "{element} \u3092\u30af\u30ea\u30c3\u30af",
        "en": "Click {element}",
    },
    "input_value": {
        "zh": "\u8f93\u5165 \"{value}\"",
        "ja": "\"{value}\" \u3092\u5165\u529b",
        "en": "Input \"{value}\"",
    },
    "waiting_for_input": {
        "zh": "\u7b49\u5f85\u8f93\u5165",
        "ja": "\u5165\u529b\u5f85\u3061",
        "en": "Waiting for Input",
    },
    "press_enter": {
        "zh": "\u6309\u56de\u8f66\u7ee7\u7eed",
        "ja": "Enter\u3092\u62bc\u3057\u3066\u7d9a\u884c",
        "en": "Press Enter to continue",
    },

    # Execution messages
    "execution_started": {
        "zh": "\u5f00\u59cb\u6267\u884c {count} \u4e2a\u6b65\u9aa4...",
        "ja": "{count} \u30b9\u30c6\u30c3\u30d7\u306e\u5b9f\u884c\u3092\u958b\u59cb...",
        "en": "Starting execution of {count} steps...",
    },
    "execution_completed": {
        "zh": "\u6267\u884c\u5b8c\u6210\u3002\u6210\u529f: {success}/{total}",
        "ja": "\u5b9f\u884c\u5b8c\u4e86\u3002\u6210\u529f: {success}/{total}",
        "en": "Execution completed. Success: {success}/{total}",
    },
    "executing": {
        "zh": "\u6b63\u5728\u6267\u884c...",
        "ja": "\u5b9f\u884c\u4e2d...",
        "en": "Executing...",
    },
    "confirm_step": {
        "zh": "\u786e\u8ba4\u6267\u884c: {action} - {description}",
        "ja": "\u5b9f\u884c\u78ba\u8a8d: {action} - {description}",
        "en": "Confirm execution: {action} - {description}",
    },
    "step_failed_prompt": {
        "zh": "\u6b65\u9aa4\u5931\u8d25: {error}\n[R]\u91cd\u8bd5 [S]\u8df3\u8fc7 [Q]\u9000\u51fa",
        "ja": "\u30b9\u30c6\u30c3\u30d7\u5931\u6557: {error}\n[R]\u518d\u8a66\u884c [S]\u30b9\u30ad\u30c3\u30d7 [Q]\u7d42\u4e86",
        "en": "Step failed: {error}\n[R]etry [S]kip [Q]uit",
    },
    "enter_value": {
        "zh": "\u8bf7\u8f93\u5165 {selector} \u7684\u503c",
        "ja": "{selector} \u306e\u5024\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044",
        "en": "Please enter value for {selector}",
    },
    "perform_custom_action": {
        "zh": "\u8bf7\u6267\u884c\u64cd\u4f5c: {description}\uff0c\u5b8c\u6210\u540e\u6309\u56de\u8f66",
        "ja": "\u64cd\u4f5c\u3092\u5b9f\u884c\u3057\u3066\u304f\u3060\u3055\u3044: {description}\u3002\u5b8c\u4e86\u5f8c\u306bEnter\u3092\u62bc\u3057\u3066\u304f\u3060\u3055\u3044",
        "en": "Please perform action: {description}. Press Enter when done",
    },

    # Manual generation
    "manual_title": {
        "zh": "\u64cd\u4f5c\u624b\u518c",
        "ja": "\u64cd\u4f5c\u30de\u30cb\u30e5\u30a2\u30eb",
        "en": "Operation Manual",
    },
    "table_of_contents": {
        "zh": "\u76ee\u5f55",
        "ja": "\u76ee\u6b21",
        "en": "Table of Contents",
    },
    "prerequisites": {
        "zh": "\u524d\u7f6e\u6761\u4ef6",
        "ja": "\u524d\u63d0\u6761\u4ef6",
        "en": "Prerequisites",
    },
    "step": {
        "zh": "\u6b65\u9aa4",
        "ja": "\u30b9\u30c6\u30c3\u30d7",
        "en": "Step",
    },
    "action": {
        "zh": "\u64cd\u4f5c",
        "ja": "\u64cd\u4f5c",
        "en": "Action",
    },
    "description": {
        "zh": "\u8bf4\u660e",
        "ja": "\u8aac\u660e",
        "en": "Description",
    },
    "notes": {
        "zh": "\u6ce8\u610f\u4e8b\u9879",
        "ja": "\u6ce8\u610f\u4e8b\u9805",
        "en": "Notes",
    },
    "generated_at": {
        "zh": "\u751f\u6210\u65f6\u95f4",
        "ja": "\u751f\u6210\u65e5\u6642",
        "en": "Generated at",
    },
    "video_tutorial": {
        "zh": "\u89c6\u9891\u6559\u7a0b",
        "ja": "\u30d3\u30c7\u30aa\u30c1\u30e5\u30fc\u30c8\u30ea\u30a2\u30eb",
        "en": "Video Tutorial",
    },

    # CLI messages
    "cli_description": {
        "zh": "Web \u64cd\u4f5c\u624b\u518c\u751f\u6210\u5668 - \u6d4f\u89c8\u5668\u81ea\u52a8\u5316\u4e0e\u6587\u6863\u751f\u6210\u5de5\u5177",
        "ja": "Web\u64cd\u4f5c\u30de\u30cb\u30e5\u30a2\u30eb\u30b8\u30a7\u30cd\u30ec\u30fc\u30bf\u30fc - \u30d6\u30e9\u30a6\u30b6\u81ea\u52d5\u5316\u3068\u30c9\u30ad\u30e5\u30e1\u30f3\u30c8\u751f\u6210\u30c4\u30fc\u30eb",
        "en": "Web Manual Generator - Browser automation and documentation tool",
    },
    "record_help": {
        "zh": "\u5f55\u5236\u6d4f\u89c8\u5668\u64cd\u4f5c",
        "ja": "\u30d6\u30e9\u30a6\u30b6\u64cd\u4f5c\u3092\u8a18\u9332",
        "en": "Record browser actions",
    },
    "run_help": {
        "zh": "\u6267\u884c\u5f55\u5236\u7684\u811a\u672c",
        "ja": "\u8a18\u9332\u3055\u308c\u305f\u30b9\u30af\u30ea\u30d7\u30c8\u3092\u5b9f\u884c",
        "en": "Execute recorded script",
    },
    "generate_help": {
        "zh": "\u4ece\u5f55\u5236\u751f\u6210\u64cd\u4f5c\u624b\u518c",
        "ja": "\u8a18\u9332\u304b\u3089\u64cd\u4f5c\u30de\u30cb\u30e5\u30a2\u30eb\u3092\u751f\u6210",
        "en": "Generate manual from recording",
    },

    # Action types
    "action_navigate": {
        "zh": "\u5bfc\u822a",
        "ja": "\u30ca\u30d3\u30b2\u30fc\u30c8",
        "en": "Navigate",
    },
    "action_click": {
        "zh": "\u70b9\u51fb",
        "ja": "\u30af\u30ea\u30c3\u30af",
        "en": "Click",
    },
    "action_fill": {
        "zh": "\u8f93\u5165",
        "ja": "\u5165\u529b",
        "en": "Input",
    },
    "action_select": {
        "zh": "\u9009\u62e9",
        "ja": "\u9078\u629e",
        "en": "Select",
    },
    "action_check": {
        "zh": "\u52fe\u9009",
        "ja": "\u30c1\u30a7\u30c3\u30af",
        "en": "Check",
    },
    "action_hover": {
        "zh": "\u60ac\u505c",
        "ja": "\u30db\u30d0\u30fc",
        "en": "Hover",
    },
    "action_scroll": {
        "zh": "\u6eda\u52a8",
        "ja": "\u30b9\u30af\u30ed\u30fc\u30eb",
        "en": "Scroll",
    },
    "action_wait": {
        "zh": "\u7b49\u5f85",
        "ja": "\u5f85\u6a5f",
        "en": "Wait",
    },
    "action_custom": {
        "zh": "\u81ea\u5b9a\u4e49",
        "ja": "\u30ab\u30b9\u30bf\u30e0",
        "en": "Custom",
    },
}


def get_text(key: str, lang: Optional[str] = None) -> str:
    """
    Get translated text for a key.

    Args:
        key: Translation key
        lang: Language code (zh, ja, en). Uses current language if not specified.

    Returns:
        Translated string, or key if not found
    """
    lang = lang or _current_language

    if key in TRANSLATIONS:
        return TRANSLATIONS[key].get(lang, TRANSLATIONS[key].get("en", key))
    return key


def set_language(lang: str) -> None:
    """
    Set the current language.

    Args:
        lang: Language code (zh, ja, en)
    """
    global _current_language
    if lang in SUPPORTED_LANGUAGES:
        _current_language = lang
    else:
        raise ValueError(f"Unsupported language: {lang}. Supported: {SUPPORTED_LANGUAGES}")


def get_language() -> str:
    """Get the current language."""
    return _current_language


def get_action_name(action: str, lang: Optional[str] = None) -> str:
    """Get localized name for an action type."""
    return get_text(f"action_{action}", lang)
