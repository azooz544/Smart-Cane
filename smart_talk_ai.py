import os
import pyttsx3
from google import genai
from google.oauth2 import service_account

# ===== Config =====
MODEL = "gemini-2.5-flash"
LOCATION = "us-central1"  # try "global" if needed
KEY_FILE_CANDIDATES = [
    "integral-legend-501221-v9-d021cfc393eb.json",  # your new file
    "integral-legend-501221-v9-cc84c59f24e4.json",  # existing file in folder
]


def find_key_file() -> str:
    for f in KEY_FILE_CANDIDATES:
        if os.path.exists(f):
            return f
    raise FileNotFoundError(
        "No service-account JSON file found. Put your JSON key in this folder."
    )


def build_client():
    key_file = find_key_file()
    creds = service_account.Credentials.from_service_account_file(
        key_file,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    project_id = creds.project_id
    if not project_id:
        raise RuntimeError("Could not read project_id from service-account file.")

    print(f"[INFO] Using key file: {key_file}")
    print(f"[INFO] Project: {project_id}, Location: {LOCATION}")

    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=LOCATION,
        credentials=creds,
    )
    return client, project_id


def init_tts():
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        return engine
    except Exception as e:
        print(f"[WARN] Voice engine failed: {e}")
        return None


def speak(engine, text: str):
    if engine is None:
        return
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"[WARN] Could not speak: {e}")


def main():
    try:
        client, project_id = build_client()
    except Exception as e:
        print(f"[ERROR] Setup failed: {e}")
        return

    engine = init_tts()
    history = []

    system_prompt = (
        "You are Smart Cane AI assistant. "
        "Be clear, short, and helpful. "
        "If user asks for safety guidance, prioritize safe actions."
    )

    print("\nSmart Talk AI started.")
    print("Type your message. Type 'exit' to quit.\n")

    while True:
        user_text = input("You: ").strip()
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit", "q"}:
            print("Goodbye!")
            speak(engine, "Goodbye!")
            break

        recent = history[-4:]
        conversation = ""
        for u, a in recent:
            conversation += f"User: {u}\nAssistant: {a}\n"

        prompt = (
            f"{system_prompt}\n\n"
            f"Conversation:\n{conversation}"
            f"User: {user_text}\n"
            f"Assistant:"
        )

        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )
            ai_text = (response.text or "").strip()
            if not ai_text:
                ai_text = "I couldn't generate a response this time."

            print(f"AI: {ai_text}\n")
            speak(engine, ai_text)
            history.append((user_text, ai_text))

        except Exception as e:
            msg = str(e)
            print(f"[ERROR] {msg}")
            if "Agent Platform API has not been used" in msg or "1008" in msg:
                print(
                    f"\nFix:\n"
                    f"1) Enable Vertex API for project {project_id}\n"
                    f"2) Make sure billing is enabled\n"
                    f"3) Run again\n"
                )


if __name__ == "__main__":
    main()
