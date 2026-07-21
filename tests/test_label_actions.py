import os
import pytest
from gemini import map_label_to_action


def test_map_label_to_action_en():
    name, action = map_label_to_action('person', lang='en')
    assert 'Person' in name or name.lower().startswith('person')
    assert 'slow' in action.lower() or 'step' in action.lower()


def test_map_label_to_action_ar():
    name, action = map_label_to_action('person', lang='ar')
    assert 'شخص' in name
    assert 'تباطأ' in action or 'تحرك' in action


def test_map_label_to_action_tr():
    name, action = map_label_to_action('person', lang='tr')
    assert 'Kişi' in name or 'Kisi' in name
    assert 'yavaş' in action or 'kenara' in action


def test_map_label_fallback_to_en():
    # unknown label should fallback to generic localized string
    name, action = map_label_to_action('unknown_label_xyz', lang='en')
    assert name == 'unknown_label_xyz'
    assert 'Obstacle' in action or 'obstacle' in action.lower()


def test_map_label_default_lang_env():
    os.environ['TTS_LANG'] = 'tr'
    name, action = map_label_to_action('car', lang=None)
    assert 'Araba' in name or 'araba' in name.lower()
    del os.environ['TTS_LANG']
