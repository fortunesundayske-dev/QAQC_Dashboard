import os

import pandas as pd
import streamlit as st

import auth
from database.audit_log import record_activity
from database.cloudinary_storage import (
    ALLOWED_ATTACHMENT_TYPES,
    MAX_ATTACHMENT_BYTES,
    private_asset_url,
    upload_support_attachment,
)
from database.mongo_support import add_ticket_message, create_ticket, escalate_ticket, list_tickets, update_ticket_status
from database.support_ai import automatic_reply
from database.settings import get_setting
from utils import inject_global_ui, render_navigation, render_page_header, render_table, render_top_nav


st.set_page_config(page_title="Customer Support", layout="wide")
inject_global_ui()
if not auth.login():
    st.stop()
render_navigation()
render_top_nav()

render_page_header("Customer Support", "Create and track help requests with the QA/QC support team.", "Help Centre")
user = auth.current_user() or {}
username = user.get("username", "")
email = user.get("email", "")
with st.form("support_ticket_form", clear_on_submit=True):
    subject = st.text_input("Subject", max_chars=140)
    category = st.selectbox("Category", ["Account access", "Technical issue", "Data issue", "Feature request", "Other"])
    message = st.text_area("How can we help?", height=160, max_chars=4000)
    attachment_file = st.file_uploader(
        "Attachment (optional, maximum 10 MB)",
        type=ALLOWED_ATTACHMENT_TYPES,
        help="Attach a screenshot, PDF, document, spreadsheet, CSV, or text file.",
    )
    submitted = st.form_submit_button("Submit support request", type="primary", width="stretch")

if submitted:
    if len(subject.strip()) < 3 or len(message.strip()) < 10:
        st.error("Enter a subject and at least 10 characters describing the issue.")
    elif attachment_file is not None and attachment_file.size > MAX_ATTACHMENT_BYTES:
        st.error("The attachment is larger than 10 MB.")
    else:
        try:
            attachment = upload_support_attachment(attachment_file) if attachment_file is not None else None
        except Exception as exc:
            st.error(f"The attachment could not be uploaded: {exc}")
            st.stop()
        ticket = create_ticket(username, email, subject, category, message, attachment=attachment)
        try:
            reply, used_ai = automatic_reply(ticket, ticket.get("messages", []))
        except Exception:
            reply, used_ai = automatic_reply({}, []) if not get_setting("OPENAI_API_KEY") else ("AI support is temporarily unavailable. Request a live admin for assistance.", False)
        add_ticket_message(ticket["ticket_id"], "QA/QC Support Assistant", "assistant", reply, is_ai=used_ai)
        record_activity(
            "create_support_ticket", category="support", page="Customer Support",
            target=ticket["ticket_id"],
            details={"category": category, "attachment_added": attachment is not None}, actor=user,
        )
        support_email = str(get_setting("QAQC_SUPPORT_EMAIL", "")).strip()
        notified = False
        try:
            if support_email:
                notified = auth.send_email(
                    support_email,
                    f"[{ticket['ticket_id']}] {ticket['subject']}",
                    f"Support request from {username} ({email})\nCategory: {category}\n"
                    f"Attachment (link expires shortly): "
                    f"{private_asset_url(attachment) if attachment else 'None'}\n\n{message}",
                )
            auth.send_email(email, f"Support request received: {ticket['ticket_id']}", f"We received your request and will respond as soon as possible.\n\nSubject: {subject}")
        except Exception:
            notified = False
        st.success(f"Support request {ticket['ticket_id']} was created." + (" The support team was notified by email." if notified else ""))

is_admin = auth.get_role() == "admin"
tickets = list_tickets(None if is_admin else username)
st.markdown("### " + ("All support tickets" if is_admin else "My support tickets"))
if is_admin:
    waiting_count = sum(1 for item in tickets if item.get("escalated") and item.get("status") not in {"resolved", "closed"})
    if waiting_count:
        st.error(f"{waiting_count} user(s) are waiting for live admin support.")
if not tickets:
    st.info("No support tickets found.")
else:
    ticket_rows = []
    for item in tickets:
        row = dict(item)
        stored_attachment = row.pop("attachment", None) or {}
        try:
            row["attachment_url"] = private_asset_url(stored_attachment) if stored_attachment else ""
        except Exception:
            row["attachment_url"] = "Unavailable"
        ticket_rows.append(row)
    render_table(pd.DataFrame(ticket_rows), include_internal=True)

    st.markdown("### Live support conversation")
    chat_labels = {
        f"{'🔴 ' if item.get('escalated') else ''}{item['ticket_id']} — {item['subject']}": item
        for item in tickets
    }
    chat_label = st.selectbox("Conversation", list(chat_labels), key="support_chat_ticket")
    active_ticket = chat_labels[chat_label]
    if active_ticket.get("escalated"):
        st.warning("Live admin assistance requested." if not is_admin else "This user is waiting for live admin assistance.")
    conversation = active_ticket.get("messages") or [{
        "sender": active_ticket.get("username", "User"),
        "sender_role": "user",
        "message": active_ticket.get("message", ""),
        "created_at": active_ticket.get("created_at", ""),
    }]
    for entry in conversation:
        role = "assistant" if entry.get("sender_role") in {"assistant", "admin"} else "user"
        with st.chat_message(role):
            st.markdown(entry.get("message", ""))
            st.caption(f"{entry.get('sender', 'Support')} · {entry.get('created_at', '')}")

    if not is_admin and not active_ticket.get("escalated"):
        if st.button("Request live admin", type="primary", width="stretch"):
            if escalate_ticket(active_ticket["ticket_id"], username):
                record_activity(
                    "escalate_support_ticket", category="support", page="Customer Support",
                    target=active_ticket["ticket_id"], actor=user,
                )
                support_email = str(get_setting("QAQC_SUPPORT_EMAIL", "")).strip()
                try:
                    if support_email:
                        auth.send_email(
                            support_email,
                            f"Live support requested: {active_ticket['ticket_id']}",
                            f"{username} requested live admin support.\nSubject: {active_ticket['subject']}",
                        )
                except Exception:
                    pass
                st.success("An admin has been notified. Continue in this chat while you wait.")
                st.rerun()

    chat_message = st.chat_input("Reply as admin..." if is_admin else "Message support...")
    if chat_message:
        chat_message = chat_message.strip()
        if not chat_message or len(chat_message) > 4_000:
            st.error("Messages must contain 1-4,000 characters.")
            st.stop()
        sender_role = "admin" if is_admin else "user"
        add_ticket_message(active_ticket["ticket_id"], username, sender_role, chat_message)
        record_activity(
            "reply_support_ticket", category="support", page="Customer Support",
            target=active_ticket["ticket_id"], details={"sender_role": sender_role}, actor=user,
        )
        if not is_admin and not active_ticket.get("escalated"):
            refreshed = next(item for item in list_tickets(username) if item["ticket_id"] == active_ticket["ticket_id"])
            try:
                reply, used_ai = automatic_reply(refreshed, refreshed.get("messages", []))
            except Exception:
                reply, used_ai = "AI support is temporarily unavailable. Request a live admin for assistance.", False
            add_ticket_message(active_ticket["ticket_id"], "QA/QC Support Assistant", "assistant", reply, is_ai=used_ai)
        st.rerun()

if is_admin and tickets:
    st.markdown("### Manage ticket")
    labels = {f"{item['ticket_id']} — {item['subject']}": item for item in tickets}
    selected_label = st.selectbox("Ticket", list(labels))
    selected = labels[selected_label]
    statuses = ["open", "in_progress", "resolved", "closed"]
    status = st.selectbox("Status", statuses, index=statuses.index(selected.get("status", "open")))
    if st.button("Update ticket status", width="stretch"):
        if update_ticket_status(selected["ticket_id"], status, username):
            record_activity(
                "update_support_ticket_status", category="support", page="Customer Support",
                target=selected["ticket_id"], details={"status": status}, actor=user,
            )
            st.success("Ticket status updated.")
            st.rerun()
        else:
            st.info("No status change was required.")
