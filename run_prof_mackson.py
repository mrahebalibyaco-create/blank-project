import os
import json
import time
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime

# Google Gen AI (new SDK)
from google import genai
from google.genai import types

# Optional scheduler (commented by default)
import schedule

# --- CONFIGURATION ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

YOUR_EMAIL_ADDRESS = os.getenv("YOUR_EMAIL_ADDRESS", "your_email@example.com")
YOUR_EMAIL_PASSWORD = os.getenv("YOUR_EMAIL_PASSWORD", "your_app_password")  # Use an app-specific password
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "recipient_email@example.com")

OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "articles")
MASTER_PROMPT_PATH = os.getenv("MASTER_PROMPT_PATH", "prof_mackson_prompt.json")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-1.5-pro-latest")

# --- LOAD THE BRAIN ---
with open(MASTER_PROMPT_PATH, "r", encoding="utf-8") as f:
    master_prompt_data = json.load(f)

# Ensure output folder exists
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Configure the Gemini client (new SDK)
client = genai.Client(api_key=GEMINI_API_KEY)

# Prepare system instruction as an initial system message
system_instruction = types.Message(
    role="system",
    parts=[types.Part(text=json.dumps(master_prompt_data))]
)

# Create a chat session with system instruction
chat = client.chats.create(
    model=MODEL_NAME,
    history=[system_instruction]
)


def _extract_json(text: str):
    """
    Attempt to parse JSON from a model response robustly.
    - First try direct json.loads
    - If that fails, try to locate the first balanced JSON object in the text
    """
    # Strip common formatting wrappers
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned.strip("`").strip()
        # If fenced blocks like ```json ... ```
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

    # Direct attempt
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Try to find balanced JSON object by braces
    start_idx = cleaned.find("{")
    if start_idx == -1:
        raise ValueError("No JSON object found in response.")

    depth = 0
    for idx in range(start_idx, len(cleaned)):
        ch = cleaned[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start_idx:idx + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    break

    raise ValueError("Unable to parse JSON from response text.")


def send_email(subject: str, body: str):
    """Send an email via Gmail SMTP using an app password."""
    print("--- Sending Email ---")
    print(f"Subject: {subject}")
    print(f"Body Preview: {body[:200]}...")

    msg = EmailMessage()
    msg["From"] = YOUR_EMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls(context=context)
            server.login(YOUR_EMAIL_ADDRESS, YOUR_EMAIL_PASSWORD)
            server.send_message(msg)
        print("--- Email Sent ---")
    except Exception as e:
        print(f"Email sending failed: {e}")


def run_daily_research_cycle():
    print(f"\n--- Starting Daily Research Cycle at {datetime.now()} ---")

    try:
        # 1. Generate a new topic
        print("Step 1: Generating new topic...")
        directive_1 = master_prompt_data["autonomous_operational_directives"]["directive_1_daily_topic_generation"]["command"]
        response_1 = chat.send_message(directive_1)
        topic_text = response_1.text
        topic_data = _extract_json(topic_text)
        title = topic_data["title"]
        abstract = topic_data["abstract"]
        print(f"Generated Title: {title}")

        # 2. Get the outline
        print("Step 2: Generating outline...")
        directive_2 = master_prompt_data["autonomous_operational_directives"]["directive_2_deep_research_and_outline"]["command"]
        response_2 = chat.send_message(directive_2.format(title=title, abstract=abstract))
        outline = response_2.text
        print("Outline Generated.")

        # 3. Write the full article
        print("Step 3: Writing full article...")
        directive_3 = master_prompt_data["autonomous_operational_directives"]["directive_3_full_article_composition"]["command"]
        response_3 = chat.send_message(directive_3.format(outline=outline))
        article_text = response_3.text
        print("Article Composition Complete.")

        # Save the article to a .txt file
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip()
        filename = f"{datetime.now().strftime('%Y-%m-%d')}_{safe_title.replace(' ', '_')}.txt"
        filepath = os.path.join(OUTPUT_FOLDER, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(article_text)
        print(f"Article saved to {filepath}")

        # 4. Generate the email report
        print("Step 4: Generating email report...")
        directive_4 = master_prompt_data["autonomous_operational_directives"]["directive_4_reporting_and_summarization"]["command"]
        # Send a snippet of the article to save tokens
        response_4 = chat.send_message(directive_4.format(title=title, full_article_text=article_text[:4000]))
        email_data = _extract_json(response_4.text)

        # 5. Send the email
        send_email(email_data.get("email_subject", f"Research Article Complete: {title}"),
                   email_data.get("email_body", abstract))

        print(f"--- Cycle Complete at {datetime.now()} ---")

    except Exception as e:
        print(f"An error occurred: {e}")
        # Optionally, send an error email notification here


# --- SCHEDULER ---
# Uncomment to enable daily run at 1:00 AM
# schedule.every().day.at("01:00").do(run_daily_research_cycle)
# print("Scheduler started. Prof. Mackson will run daily at 1:00 AM.")
# while True:
#     schedule.run_pending()
#     time.sleep(1)

# For testing, run it once immediately:
if __name__ == "__main__":
    run_daily_research_cycle()