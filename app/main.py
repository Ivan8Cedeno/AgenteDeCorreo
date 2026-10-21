import os
import sys

if __package__ in (None, ""):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from app.agent import MailAgent


def main() -> None:
    agent = MailAgent()
    decisions = agent.process_inbox(max_results=3)

    for decision in decisions:
        print(f"ID: {decision['id']} | Accion: {decision['action']} | Prioridad: {decision['priority']}")
        print(f"Resumen: {decision['summary']}")
        if decision.get("spam_status"):
            print(f"Spam: {decision['spam_status']}")
        if decision.get("draft_status"):
            print(f"Borrador: {decision['draft_status']}")
        if decision.get("whatsapp_status"):
            print(f"WhatsApp: {decision['whatsapp_status']}")
        print("-" * 60)


if __name__ == "__main__":
    main()
