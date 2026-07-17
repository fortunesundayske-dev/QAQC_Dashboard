import os

import pandas as pd
import streamlit as st

import auth
from database.cloudinary_storage import ALLOWED_ATTACHMENT_TYPES, MAX_ATTACHMENT_BYTES, upload_support_attachment
from database.mongo_support import create_ticket, list_tickets, update_ticket_status
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
    submitted = st.form_submit_button("Submit support request", type="primary", use_container_width=True)

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
        support_email = os.getenv("QAQC_SUPPORT_EMAIL", "").strip()
        notified = False
        try:
            if support_email:
                notified = auth.send_email(
                    support_email,
                    f"[{ticket['ticket_id']}] {ticket['subject']}",
                    f"Support request from {username} ({email})\nCategory: {category}\n"
                    f"Attachment: {(attachment or {}).get('url', 'None')}\n\n{message}",
                )
            auth.send_email(email, f"Support request received: {ticket['ticket_id']}", f"We received your request and will respond as soon as possible.\n\nSubject: {subject}")
        except Exception:
            notified = False
        st.success(f"Support request {ticket['ticket_id']} was created." + (" The support team was notified by email." if notified else ""))

is_admin = auth.get_role() == "admin"
tickets = list_tickets(None if is_admin else username)
st.markdown("### " + ("All support tickets" if is_admin else "My support tickets"))
if not tickets:
    st.info("No support tickets found.")
else:
    ticket_rows = []
    for item in tickets:
        row = dict(item)
        row["attachment_url"] = (row.pop("attachment", None) or {}).get("url", "")
        ticket_rows.append(row)
    render_table(pd.DataFrame(ticket_rows), include_internal=True)

if is_admin and tickets:
    st.markdown("### Manage ticket")
    labels = {f"{item['ticket_id']} — {item['subject']}": item for item in tickets}
    selected_label = st.selectbox("Ticket", list(labels))
    selected = labels[selected_label]
    statuses = ["open", "in_progress", "resolved", "closed"]
    status = st.selectbox("Status", statuses, index=statuses.index(selected.get("status", "open")))
    if st.button("Update ticket status", use_container_width=True):
        if update_ticket_status(selected["ticket_id"], status, username):
            st.success("Ticket status updated.")
            st.rerun()
        else:
            st.info("No status change was required.")
