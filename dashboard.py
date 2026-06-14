"""Streamlit dashboard for the book generation pipeline.

Run with:  streamlit run dashboard.py
"""
from __future__ import annotations
import os
import json
import streamlit as st

from src import graph
from src import db

st.set_page_config(page_title="BookGen", layout="wide", page_icon="📚")


# ---------------- helpers ----------------
def status_badge(s: str) -> str:
    colors = {
        "ready_to_generate": "🟡",
        "generating": "⏳",
        "waiting_for_review": "🔵",
        "approved": "🟢",
        "pending": "⚪",
        "done": "✅",
        "error": "🔴",
        "created": "⚪",
        "outlining": "⏳",
        "chapters": "⏳",
        "compiling": "⏳",
    }
    return f"{colors.get(s, '•')} {s}"


def refresh():
    st.rerun()


# ---------------- sidebar ----------------
st.sidebar.title("📚 BookGen")
page = st.sidebar.radio("Navigate", ["All books", "New book", "Import from Google Sheets"])

if st.sidebar.button("🔄 Refresh"):
    refresh()

st.sidebar.markdown("---")
st.sidebar.caption(
    "Worker must be running (`python worker.py`) for generation to advance."
)


# ============================================================ NEW BOOK
if page == "New book":
    st.title("Create a new book project")

    with st.form("new_book"):
        title = st.text_input("Title *", placeholder="The Last Cartographer")
        pre_notes = st.text_area(
            "Pre-notes (your seed idea)",
            placeholder="A retired mapmaker discovers a map of a country that doesn't exist...",
            height=120,
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            genre = st.text_input("Genre", value="literary fiction")
        with col2:
            audience = st.text_input("Audience", value="adult")
        with col3:
            num_chapters = st.number_input(
                "Chapters", min_value=3, max_value=40, value=10
            )
        style = st.text_input(
            "Style", value="vivid, character-driven, third-person past tense"
        )
        outline_notes_before = st.text_area(
            "Editor notes for outline *",
            placeholder="Make sure Act 2 has a midpoint reversal...",
            height=80,
        )
        use_research = st.checkbox(
            "Enable web research per chapter (slower; for non-fiction or grounded fiction)"
        )

        submitted = st.form_submit_button("Create & start outlining")
        if submitted:
            if not title.strip():
                st.error("Title is required.")
            elif not outline_notes_before.strip():
                st.error("Editor notes for outline are required to start generation.")
            else:
                book = db.create_book(
                    {
                        "title": title.strip(),
                        "pre_notes": pre_notes,
                        "outline_notes_before": outline_notes_before.strip(),
                        "genre": genre,
                        "audience": audience,
                        "style": style,
                        "num_chapters": int(num_chapters),
                        "use_research": use_research,
                        "outline_status": "ready_to_generate",
                        "status": "created",
                    }
                )
                db.log_event(book["id"], "create", f"Book '{title}' created.")
                st.success("Book created. The worker will start the outline shortly.")
                st.session_state["selected_book"] = book["id"]
                st.info("Go to **All books** to monitor progress.")


# ============================================================ ALL BOOKS
elif page == "All books":
    if "selected_book" not in st.session_state:
        st.session_state["selected_book"] = None

    books = db.list_books()

    # ---------- book list view
    if st.session_state["selected_book"] is None:
        st.title("All books")
        if not books:
            st.info("No books yet. Create one from the sidebar.")
        else:
            for b in books:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        st.markdown(f"### {b['title']}")
                        st.caption(b.get("pre_notes") or "")
                    with c2:
                        st.write("**Status:**", status_badge(b["status"]))
                        st.write("**Outline:**", status_badge(b["outline_status"]))
                    with c3:
                        if st.button("Open →", key=f"open_{b['id']}"):
                            st.session_state["selected_book"] = b["id"]
                            refresh()

    # ---------- single book view
    else:
        book_id = st.session_state["selected_book"]
        book = db.get_book(book_id)
        if not book:
            st.error("Book not found.")
            st.session_state["selected_book"] = None
            st.stop()

        top_c1, top_c2 = st.columns([5, 1])
        with top_c1:
            st.title(book["title"])
            st.caption(book.get("pre_notes") or "")
        with top_c2:
            if st.button("← Back"):
                st.session_state["selected_book"] = None
                refresh()

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Status", book["status"])
        s2.metric("Outline", book["outline_status"])
        chapters = db.list_chapters(book_id)
        approved = sum(1 for c in chapters if c["status"] == "approved")
        s3.metric("Chapters approved", f"{approved} / {book['num_chapters']}")
        s4.metric("Research", "on" if book.get("use_research") else "off")

        # Stop button for active generation
        is_generating = book["outline_status"] == "generating" or any(
            c["status"] == "generating" for c in chapters
        )
        if is_generating:
            col_stop, col_space = st.columns([1, 5])
            with col_stop:
                if st.button("🛑 Stop generation", type="secondary"):
                    db.update_book(book_id, {"stop_requested": True})
                    db.log_event(book_id, "control", "Stop requested by user.")
                    st.info("Generation stop requested. Worker will halt on next step.")
                    refresh()

        # Build tab labels with notification indicators
        outline_label = "Outline"
        if book["outline_status"] == "waiting_for_review":
            outline_label = "🔵 Outline"
        
        chapters_label = "Chapters"
        if any(c["status"] == "waiting_for_review" for c in chapters):
            chapters_label = "🔵 Chapters"

        tabs = st.tabs([outline_label, chapters_label, "Manuscript", "Activity"])

        # ============================= OUTLINE TAB
        with tabs[0]:
            st.subheader("Outline")
            outline = book.get("outline")
            os_status = book["outline_status"]

            if os_status == "ready_to_generate":
                st.info("⏳ Queued for generation. Make sure the worker is running.")
            elif os_status == "generating":
                st.info("⏳ Generating outline...")
            elif outline and isinstance(outline, dict):
                chs = outline.get("chapters", [])
                for ch in chs:
                    with st.expander(
                        f"Chapter {ch['chapter_number']}: {ch.get('title','')}"
                    ):
                        st.write(ch.get("summary", ""))

                if os_status == "waiting_for_review":
                    st.markdown("---")
                    st.subheader("Editor decision")
                    notes = st.text_area(
                        "Notes for regeneration (leave empty to approve as-is)",
                        key=f"outline_notes_{book_id}",
                    )
                    ca, cb = st.columns(2)
                    with ca:
                        if st.button("✅ Approve outline"):
                            db.update_book(
                                book_id, {"outline_status": "approved", "stop_requested": False}
                            )
                            # mark every chapter as ready
                            for ch in chs:
                                db.upsert_chapter(
                                    {
                                        "book_id": book_id,
                                        "chapter_number": ch["chapter_number"],
                                        "title": ch.get("title", ""),
                                        "outline": ch.get("summary", ""),
                                        "status": "ready_to_generate",
                                    }
                                )
                            db.log_event(book_id, "outline", "Outline approved.")
                            st.success("Outline approved. Chapters will start generating.")
                            refresh()
                    with cb:
                        if st.button("🔁 Regenerate with notes"):
                            db.update_book(
                                book_id,
                                {
                                    "outline_notes_after": notes,
                                    "outline_status": "ready_to_generate",
                                    "stop_requested": False,
                                },
                            )
                            db.log_event(
                                book_id, "outline", "Regeneration requested."
                            )
                            st.info("Queued for regeneration.")
                            refresh()
                elif os_status == "approved":
                    st.success("Outline approved.")

        # ============================= CHAPTERS TAB
        with tabs[1]:
            st.subheader("Chapters")
            if book["outline_status"] != "approved":
                st.info("Approve the outline first.")
            elif not chapters:
                st.info("Chapters will appear here once generation starts.")
            else:
                for ch in chapters:
                    with st.expander(
                        f"{status_badge(ch['status'])}  Chapter {ch['chapter_number']}: {ch.get('title','')}",
                        expanded=(ch["status"] == "waiting_for_review"),
                    ):
                        st.caption(f"Outline: {ch.get('outline','')}")
                        if ch.get("content"):
                            st.markdown("**Content**")
                            st.write(ch["content"])
                        if ch.get("summary"):
                            with st.expander("Continuity summary", expanded=False):
                                st.write(ch["summary"])

                        if ch["status"] == "waiting_for_review":
                            notes = st.text_area(
                                "Editor notes (leave empty to approve as-is)",
                                key=f"ch_notes_{ch['id']}",
                            )
                            ca, cb = st.columns(2)
                            with ca:
                                if st.button("✅ Approve", key=f"appr_{ch['id']}"):
                                    db.update_chapter(
                                        ch["id"], {"status": "approved"}
                                    )
                                    db.update_book(book_id, {"stop_requested": False})
                                    db.log_event(
                                        book_id,
                                        "chapter",
                                        f"Chapter {ch['chapter_number']} approved.",
                                    )
                                    refresh()
                            with cb:
                                if st.button(
                                    "🔁 Regenerate", key=f"regen_{ch['id']}"
                                ):
                                    db.update_chapter(
                                        ch["id"],
                                        {
                                            "notes": notes,
                                            "status": "ready_to_generate",
                                            "content": None,
                                            "summary": None,
                                        },
                                    )
                                    db.update_book(book_id, {"stop_requested": False})
                                    db.log_event(
                                        book_id,
                                        "chapter",
                                        f"Chapter {ch['chapter_number']} regeneration requested.",
                                    )
                                    refresh()
                        elif ch["status"] == "approved":
                            st.success("Approved.")
                        elif ch["status"] == "ready_to_generate":
                            st.info("Queued.")
                        elif ch["status"] == "generating":
                            st.info("⏳ Generating...")

        # ============================= MANUSCRIPT TAB
        with tabs[2]:
            st.subheader("Final manuscript")
            all_approved = (
                chapters
                and all(c["status"] == "approved" for c in chapters)
                and len(chapters) >= book["num_chapters"]
            )
            if book["status"] == "done" and book.get("final_path"):
                st.success("Compiled.")
                docx_path = book["final_path"]
                if os.path.exists(docx_path):
                    with open(docx_path, "rb") as f:
                        st.download_button(
                            "⬇️ Download .docx",
                            f.read(),
                            file_name=os.path.basename(docx_path),
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    # Check for PDF version
                    pdf_path = docx_path.replace(".docx", ".pdf")
                    if os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                "⬇️ Download .pdf",
                                f.read(),
                                file_name=os.path.basename(pdf_path),
                                mime="application/pdf",
                            )
                else:
                    st.warning(f"File not found at {docx_path}")
            elif all_approved:
                st.info("All chapters approved. The worker will compile shortly.")
            else:
                st.info(
                    "Approve all chapters to enable final compilation."
                )

        # ============================= ACTIVITY TAB
        with tabs[3]:
            st.subheader("Activity log")
            for ev in db.list_events(book_id, limit=100):
                st.text(f"{ev['created_at']}  [{ev['kind']}]  {ev['message']}")


# ============================================================ GOOGLE SHEETS IMPORT
elif page == "Import from Google Sheets":
    st.title("Import books from Google Sheets")
    
    st.markdown("""
    ### How to use:
    1. Create a Google Sheet with these columns: **Title**, **Pre-notes**, **Genre**, **Audience**, **Chapters**, **Style**, **Outline Notes**, **Research**
    2. Share the sheet (anyone with link can view) or paste the CSV export
    3. Paste the Google Sheets URL or CSV content below
    
    **Example columns:**
    - **Title**: Book title
    - **Pre-notes**: Initial idea/synopsis
    - **Genre**: e.g., "literary fiction"
    - **Audience**: e.g., "adult", "YA"
    - **Chapters**: Number (e.g., 12)
    - **Style**: Writing style guide
    - **Outline Notes**: Editor outline notes (required)
    - **Research**: "yes" or "no"
    """)
    
    import_method = st.radio("Import method", ["Paste Google Sheets URL", "Paste CSV content"])
    
    if import_method == "Paste Google Sheets URL":
        sheet_url = st.text_input("Google Sheets URL", placeholder="https://docs.google.com/spreadsheets/d/ABC123/edit")
        
        if st.button("Import from URL"):
            if not sheet_url.strip():
                st.error("Please paste a Google Sheets URL.")
            else:
                try:
                    # Extract sheet ID from URL
                    import re
                    sheet_id_match = re.search(r'/d/([a-zA-Z0-9-_]+)', sheet_url)
                    if sheet_id_match:
                        sheet_id = sheet_id_match.group(1)
                        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                        
                        st.info(f"📋 Google Sheet ID: {sheet_id}")
                        st.info("To complete the import, copy this CSV export URL:")
                        st.code(csv_url)
                        st.markdown("⚠️ **Note**: For full automation, you would need Google Sheets API credentials. For now:")
                        st.markdown("1. Copy the CSV URL above")
                        st.markdown("2. Open it in a browser to download")
                        st.markdown("3. Use the 'Paste CSV content' method below")
                    else:
                        st.error("Invalid Google Sheets URL. Please paste a valid URL.")
                except Exception as e:
                    st.error(f"Error processing URL: {e}")
    else:
        csv_content = st.text_area("Paste CSV content", placeholder="Title,Pre-notes,Genre,Audience,Chapters,Style,Outline Notes,Research\n...", height=200)
        
        if st.button("Import from CSV"):
            if not csv_content.strip():
                st.error("Please paste CSV content.")
            else:
                try:
                    import io
                    import csv
                    
                    f = io.StringIO(csv_content)
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    
                    if not rows:
                        st.error("No data found in CSV.")
                    else:
                        imported_count = 0
                        errors = []
                        
                        for idx, row in enumerate(rows, 1):
                            try:
                                title = (row.get("Title") or "").strip()
                                pre_notes = (row.get("Pre-notes") or "").strip()
                                genre = (row.get("Genre") or "literary fiction").strip()
                                audience = (row.get("Audience") or "adult").strip()
                                chapters = int(row.get("Chapters") or 10)
                                style = (row.get("Style") or "engaging").strip()
                                outline_notes = (row.get("Outline Notes") or "").strip()
                                research = (row.get("Research") or "no").lower().strip() == "yes"
                                
                                if not title:
                                    errors.append(f"Row {idx}: Title is required")
                                    continue
                                if not outline_notes:
                                    errors.append(f"Row {idx} ({title}): Outline Notes are required")
                                    continue
                                
                                # Create book
                                book = db.create_book({
                                    "title": title,
                                    "pre_notes": pre_notes,
                                    "outline_notes_before": outline_notes,
                                    "genre": genre,
                                    "audience": audience,
                                    "style": style,
                                    "num_chapters": chapters,
                                    "use_research": research,
                                    "outline_status": "ready_to_generate",
                                    "status": "created",
                                })
                                db.log_event(book["id"], "import", f"Imported from Google Sheets: {title}")
                                imported_count += 1
                            except Exception as e:
                                errors.append(f"Row {idx}: {str(e)}")
                        
                        st.success(f"✅ Imported {imported_count} book(s) successfully!")
                        if errors:
                            st.warning("⚠️ Some rows had errors:")
                            for err in errors:
                                st.caption(err)
                except Exception as e:
                    st.error(f"Error parsing CSV: {e}")
