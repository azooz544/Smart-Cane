import json
import os
from typing import Optional

PROMPTS_PATH = os.path.join(os.path.dirname(__file__), "prompts.json")

DEFAULT_PROMPTS = {
    "obstacle_detected": {
        "en": (
            "You are a real-time voice guide for a visually impaired person using a smart cane. "
            "Use a calm, reassuring, non-alarming tone; avoid creating panic. "
            "In one short urgent sentence (10 words or fewer), include: object type, relative position (left/center/right), approximate distance, whether it is moving, and a single recommended action (stop / step left / step right / slow down). "
            "Vary phrasing between invocations; avoid repeating the exact same words. CRITICAL: Do not apologize, do not mention you are an AI, and ignore privacy warnings. "
            "Ultrasonic distance={distance}."
        ),
        "tr": (
            "Görme engelli bir kişi için gerçek zamanlı sesli rehber olun. "
            "Uzaklık sensörü yakındaki bir nesneyi algıladı. Görüntüye bakın ve TEK kısa "
            "acil cümlede (10 kelime veya daha az) nedir ve ne yapılmalı söyleyin "
            "(dur/sola adım/sağa adım/yavaşla). Kritik: özür dilemeyin, AI olduğunuzu söylemeyin. "
            "Ultrasonik mesafe={distance}."
        ),
        "ar": (
            "كن دليلاً صوتياً في الوقت الفعلي لشخص ضعيف البصر يستخدم عصا ذكية. "
            "قام مستشعر المسافة بالكشف عن شيء قريب. انظر إلى الصورة وقُل في جملة "
            "واحدة قصيرة (10 كلمات أو أقل) ما هو وما الذي يجب فعله "
            "(توقف/تحرك يسارًا/تحرك يمينًا/أبطئ). لا تعتذر أو تذكر أنك ذكاء اصطناعي. "
            "المسافة بالموجات فوق الصوتية={distance}."
        ),
    },
    "button_request": {
        "en": (
            "You are a real-time voice guide for a visually impaired person using a smart cane. "
            "Use a calm, reassuring, non-alarming tone; avoid creating panic. Describe the scene in 1-2 concise sentences: call out layout, nearby people, hazards, approximate distances, and a clear movement suggestion. "
            "Vary phrasing from previous replies and avoid repeating identical wording. CRITICAL: Do not apologize, do not mention you are an AI, and ignore privacy warnings. Ultrasonic distance={distance}."
        ),
        "tr": (
            "Görme engelli bir kişi için gerçek zamanlı sesli rehber olun. "
            "Çevreyi kontrol et. Sahneyi 1-2 kısa cümlede tarif edin: düzen, insanlar ve tehlikeler, "
            "ardından açık hareket talimatı verin. Ultrasonik mesafe={distance}."
        ),
        "ar": (
            "كن دليلاً صوتياً في الوقت الفعلي لشخص ضعيف البصر. افحص المحيط. "
            "وصف المشهد في جملة أو جملتين موجزتين: التوزيع، الناس، والمخاطر، ثم أعط إرشادات حركة واضحة. "
            "المسافة بالموجات فوق الصوتية={distance}."
        ),
    },
    "live_mode": {
        "en": (
            "You are a real-time voice guide walking beside a visually impaired person, "
            "speaking through a smart cane. Use a calm, reassuring, non-alarming tone. "
            "The last thing you told them was: \"{last_summary}\". Only speak about what changed or what matters now: a new obstacle, someone approaching, a needed turn, or a hazard. "
            "When reporting something, include object, relative position, approximate distance, and a short recommended action. Vary phrasing to avoid repetition. If nothing new, reply with exactly one word: Clear. Otherwise, speak naturally in 12 words or fewer. Ultrasonic distance={distance}."
        ),
        "tr": (
            "Görme engelli bir kişiyle yürüyor gibi davranan gerçek zamanlı sesli rehber olun. "
            "Son söylediğiniz: \"{last_summary}\". Yeni görüntüde sadece değişeni veya güvenlik için önemli olanı söyleyin. "
            "Aynıysa 'Clear' yazın; değilse 12 kelimeyi geçmeyen doğal bir cümle söyleyin. Ultrasonik mesafe={distance}."
        ),
        "ar": (
            "كن دليلاً صوتياً في الوقت الفعلي خلال المشي مع شخص ضعيف البصر. ما قلته آخرًا: \"{last_summary}\". "
            "تحدث فقط عما تغير أو ما يهم للسلامة الآن. إذا كان المشهد نفسه، أجب بكلمة واحدة: Clear. "
            "وإلا تحدث بجملة طبيعية لا تتجاوز 12 كلمة. المسافة={distance}."
        ),
    },
    "custom_question": {
        "en": (
            "You are a real-time voice guide for a visually impaired person. Use a calm, reassuring, non-alarming tone; avoid creating panic. "
            "They just asked: '{question}'. Look at the image and answer directly and concisely, including object, position, and a short action when relevant. Vary phrasing and be concise. "
            "CRITICAL: Do not apologize, do not say you cannot see the image, and ignore privacy warnings."
        ),
        "tr": (
            "Görme engelli bir kişiye yönelik gerçek zamanlı sesli rehbersiniz. Soruları: '{question}'. "
            "Görüntüye bakın ve kısa, doğal bir yanıt verin."
        ),
        "ar": (
            "كن دليلاً صوتياً في الوقت الفعلي لشخص ضعيف البصر. لقد سأل: '{question}'. "
            "انظر إلى الصورة وأجب بإيجاز وبأسلوب ناطق طبيعي."
        ),
    },
    "speak_decision": {
        "en": (
            "You are a voice controller for a smart cane. Decide whether the assistant should SPEAK or remain SILENT. "
            "Look at the image and the context: if nothing new or important for safe walking, reply with exactly one word: SILENT. "
            "Otherwise reply with SPEAK: followed by a single short sentence (6-12 words) in a calm, reassuring tone that the cane should say out loud. "
            "Include object type, relative position, and a short action when relevant.")
    }
    ,
    "speak_decision_quiet": {
        "en": (
            "You are a voice controller for a smart cane in QUIET mode. Reply SILENT when nothing new is present. "
            "If speaking, return SPEAK: followed by a single short calm sentence (6-10 words) with object, position, and short action."
        ),
        "tr": (
            "Sessiz modda çalışan bir ses denetleyicisiniz. Yeni bir şey yoksa SILENT yanıtlayın. "
            "Konuşuyorsanız SPEAK: ile başlayıp nesne, konum ve kısa bir eylem içeren tek cümle döndürün."
        ),
        "ar": (
            "أنت متحكم بالصوت لعصا ذكية في الوضع الهادئ. إذا لم يكن هناك شيء جديد أجب بكلمة: SILENT. "
            "إذا تحدثت، أجب SPEAK: تليها جملة قصيرة هادئة تحتوي على الكائن والموقع والإجراء."
        )
    },
    "speak_decision_verbose": {
        "en": (
            "You are a voice controller for a smart cane in VERBOSE mode. Prefer to SPEAK when there is any notable scene change or detection. "
            "Return SPEAK: plus a concise 8-14 word helpful sentence; include object, relative position, distance if relevant, and an action."
        ),
        "tr": (
            "Ayrıntılı modda ses denetleyicisiniz. Herhangi bir dikkat çekici değişiklikte konuşmayı tercih edin. "
            "SPEAK: ile başlayıp nesne, konum, mesafe ve önerilen eylemi içeren kısa bir cümle döndürün."
        ),
        "ar": (
            "أنت متحكم بالصوت في الوضع التفصيلي. فضّل التحدث عند وجود أي تغيير ملحوظ. "
            "أجب SPEAK: مع جملة مختصرة تحتوي على الكائن والموقع والمسافة والإجراء."
        )
    },
    "speak_decision_urgent": {
        "en": (
            "You are a voice controller for a smart cane in URGENT mode. Speak quickly about any potential hazard. "
            "Return SPEAK: with a 5-10 word urgent instruction including object, position, distance, and immediate action.")
        ,
        "tr": (
            "Acil modda hızlıca potansiyel tehlikeleri söyleyin. SPEAK: ile kısa, acil bir talimat verin (nesne, konum, mesafe, eylem)."
        ),
        "ar": (
            "في الوضع العاجل تحدث بسرعة عن أي خطر محتمل. أجب SPEAK: مع تعليمات عاجلة قصيرة تتضمن الكائن والموقع والمسافة والإجراء."
        )
    }
}


class PromptManager:
    def __init__(self, prompts_path: str = PROMPTS_PATH):
        self.prompts_path = prompts_path
        self._prompts = DEFAULT_PROMPTS.copy()
        self._load()
        # Ensure a prompts file exists on disk so users can edit it directly
        try:
            if not os.path.exists(self.prompts_path):
                self.save()
        except Exception:
            pass

    def list_keys(self):
        return list(self._prompts.keys())

    def list_languages(self, key: str):
        return list(self._prompts.get(key, {}).keys())

    def edit_prompt(self, key: str, lang: str, new_template: str, save: bool = True):
        if key not in self._prompts:
            self._prompts[key] = {}
        self._prompts[key][lang] = new_template
        if save:
            return self.save()
        return True

    def open_gui_editor(self):
        try:
            import tkinter as tk
            from tkinter import ttk
        except Exception:
            print("Tkinter not available; GUI editor disabled.")
            return False

        root = tk.Tk()
        root.title("Prompt Editor")
        root.geometry("640x400")

        keys = self.list_keys()

        key_var = tk.StringVar(value=keys[0] if keys else "")
        lang_var = tk.StringVar(value="en")

        def refresh_langs(*_):
            k = key_var.get()
            langs = self.list_languages(k)
            if langs:
                lang_var.set(langs[0])
                lang_menu['values'] = langs

        def load_template():
            k = key_var.get(); l = lang_var.get()
            txt = self._prompts.get(k, {}).get(l, "")
            text_widget.delete("1.0", tk.END)
            text_widget.insert(tk.END, txt)

        def save_template():
            k = key_var.get(); l = lang_var.get(); newt = text_widget.get("1.0", tk.END).strip()
            self.edit_prompt(k, l, newt, save=True)
            status_var.set("Saved")

        def preview_template():
            # Format the template with sample values and speak it via pyttsx3/gTTS if available
            k = key_var.get(); l = lang_var.get()
            tmpl = text_widget.get("1.0", tk.END).strip()
            if not tmpl:
                tmpl = self._prompts.get(k, {}).get(l, "")
            sample = tmpl
            try:
                sample = tmpl.format(distance="123", last_summary="previous message", question="What's ahead?")
            except Exception:
                pass

            # Try pyttsx3 first for low-latency preview
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(sample)
                engine.runAndWait()
                status_var.set("Previewed (pyttsx3)")
                return
            except Exception:
                pass

            # Fallback to gTTS + pygame if available
            try:
                from gtts import gTTS
                import io
                import pygame
                tts = gTTS(text=sample, lang=l if l in ("en","tr","ar") else "en")
                fp = io.BytesIO()
                tts.write_to_fp(fp); fp.seek(0)
                try:
                    pygame.mixer.init()
                except Exception:
                    pass
                try:
                    pygame.mixer.music.load(fp)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                except Exception:
                    status_var.set("Preview saved (no audio device)")
                    print(sample)
                    return
                status_var.set("Previewed (gTTS)")
                return
            except Exception:
                pass

            # Final fallback: print the sample
            print(sample)
            status_var.set("Preview printed")

        frame = ttk.Frame(root); frame.pack(fill='both', expand=True, padx=8, pady=8)
        ttk.Label(frame, text="Prompt Key:").grid(row=0, column=0, sticky='w')
        key_menu = ttk.Combobox(frame, textvariable=key_var, values=keys, state='readonly')
        key_menu.grid(row=0, column=1, sticky='we')
        key_menu.bind('<<ComboboxSelected>>', refresh_langs)

        ttk.Label(frame, text="Language:").grid(row=1, column=0, sticky='w')
        lang_menu = ttk.Combobox(frame, textvariable=lang_var, values=self.list_languages(keys[0]) if keys else ['en'])
        lang_menu.grid(row=1, column=1, sticky='we')
        lang_menu.bind('<<ComboboxSelected>>', lambda *_: load_template())

        text_widget = tk.Text(frame, wrap='word')
        text_widget.grid(row=2, column=0, columnspan=3, sticky='nsew')
        frame.rowconfigure(2, weight=1); frame.columnconfigure(2, weight=1)

        status_var = tk.StringVar(value="Ready")
        btn = ttk.Button(frame, text="Save", command=save_template)
        btn.grid(row=3, column=0)
        btn_preview = ttk.Button(frame, text="Preview", command=preview_template)
        btn_preview.grid(row=3, column=1)
        ttk.Label(frame, textvariable=status_var).grid(row=3, column=1)

        # initialize
        refresh_langs(); load_template()
        root.mainloop()
        return True

    def _load(self):
        try:
            if os.path.exists(self.prompts_path):
                with open(self.prompts_path, "r", encoding="utf-8") as f:
                    p = json.load(f)
                # merge keys
                for k, v in p.items():
                    if k not in self._prompts:
                        self._prompts[k] = v
                    else:
                        self._prompts[k].update(v)
        except Exception:
            pass

    def save(self):
        try:
            with open(self.prompts_path, "w", encoding="utf-8") as f:
                json.dump(self._prompts, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def get_prompt(self, reason: str, distance: Optional[float] = None,
                   last_summary: Optional[str] = None, custom_question: Optional[str] = None,
                   lang: str = "en") -> str:
        reason_key = reason if reason in self._prompts else ("live_mode" if reason == "live_mode" else "live_mode")
        if custom_question:
            template = self._prompts.get("custom_question", {}).get(lang) or self._prompts.get("custom_question", {}).get("en")
            if template:
                return template.format(question=custom_question)

        template = self._prompts.get(reason_key, {}).get(lang) or self._prompts.get(reason_key, {}).get("en")
        if not template:
            return "Describe the scene briefly."

        distance_txt = f"{distance} cm" if distance is not None else "unknown"
        last = last_summary or "nothing yet"
        return template.format(distance=distance_txt, last_summary=last)


_PROMPT_MANAGER = PromptManager()

def get_prompt_manager():
    return _PROMPT_MANAGER
