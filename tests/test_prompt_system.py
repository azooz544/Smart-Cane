import json
import os

from prompt_system import PromptManager


def test_prompt_save_and_load(tmp_path):
    pfile = tmp_path / "prompts_test.json"
    pm = PromptManager(prompts_path=str(pfile))

    # edit a prompt and save
    pm.edit_prompt("test_key", "en", "Test template {distance}", save=True)
    assert os.path.exists(str(pfile))

    # load a fresh manager from same path and confirm content
    pm2 = PromptManager(prompts_path=str(pfile))
    assert pm2.get_prompt("test_key", distance=42) == "Test template 42 cm"


def test_get_localized_prompt_default():
    pm = PromptManager()
    # ensure available languages return non-empty strings
    s_en = pm.get_prompt("obstacle_detected", distance=10, lang="en")
    s_tr = pm.get_prompt("obstacle_detected", distance=10, lang="tr")
    s_ar = pm.get_prompt("obstacle_detected", distance=10, lang="ar")
    assert isinstance(s_en, str) and len(s_en) > 0
    assert isinstance(s_tr, str) and len(s_tr) > 0
    assert isinstance(s_ar, str) and len(s_ar) > 0
