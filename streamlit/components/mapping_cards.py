import streamlit as st
import html


def inject_mapping_card_styles():
    st.markdown(
        """
        <style>
        .mapping-section {
            border-radius: 12px;
            padding: 0.45rem 0.65rem;
            margin: 0.12rem 0 0.45rem 0;
            border: 1px solid transparent;
        }
        .mapping-section h4 {
            margin: 0;
            font-size: 0.92rem;
            font-weight: 630;
            letter-spacing: 0.01em;
        }
        .mapping-section p {
            margin: 0.3rem 0 0 0;
            font-size: 0.85rem;
            opacity: 0.9;
        }
        .mapping-entity {
            background: linear-gradient(135deg, rgba(8, 145, 178, 0.08), rgba(14, 116, 144, 0.03));
            border-color: rgba(8, 145, 178, 0.25);
        }
        .mapping-property {
            background: linear-gradient(135deg, rgba(34, 197, 94, 0.08), rgba(22, 163, 74, 0.03));
            border-color: rgba(34, 197, 94, 0.25);
        }
        .mapping-chip-wrap {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin: 0.3rem 0 0.45rem 0;
        }
        .mapping-chip {
            border-radius: 999px;
            padding: 0.18rem 0.52rem;
            font-size: 0.75rem;
            border: 1px solid rgba(100, 116, 139, 0.35);
            background: rgba(148, 163, 184, 0.12);
        }
        .mapping-chip.hidden-chip {
            background: rgba(156, 163, 175, 0.12) !important;
            border-color: rgba(148, 163, 184, 0.18) !important;
            color: rgba(55, 65, 81, 0.9) !important;
            opacity: 0.95;
        }
        .mapping-empty {
            border-radius: 12px;
            border: 1px dashed rgba(148, 163, 184, 0.6);
            padding: 0.8rem;
            font-size: 0.86rem;
            color: rgba(71, 85, 105, 1);
            background: rgba(248, 250, 252, 0.6);
            margin-bottom: 0.6rem;
        }

        /* Compact expander layout to reduce vertical space */
        [data-testid="stExpander"] {
            margin-bottom: 0.35rem;
            border: 1px solid rgba(148, 163, 184, 0.4);
            border-radius: 12px;
            overflow: hidden;
        }
        [data-testid="stExpander"] details summary {
            padding: 0.3rem 0.55rem !important;
            min-height: 0 !important;
        }
        [data-testid="stExpander"] details > div {
            padding: 0.35rem 0.55rem 0.45rem !important;
        }

        /* Keywords input: gray border and lower height */
        [data-testid="stTextArea"] textarea {
            border: 1px solid rgba(148, 163, 184, 0.78) !important;
            border-radius: 10px !important;
            min-height: 52px !important;
            padding: 0.42rem 0.56rem !important;
            line-height: 1.25 !important;
        }
        [data-testid="stTextArea"] textarea[aria-label="Exclude Keywords"] {
            background: rgba(239, 68, 68, 0.12) !important;
            border-color: rgba(220, 38, 38, 0.55) !important;
        }
        [data-testid="stTextArea"] textarea[aria-label="Exclude Keywords"]:focus {
            border-color: rgba(220, 38, 38, 0.9) !important;
            box-shadow: 0 0 0 1px rgba(220, 38, 38, 0.28) !important;
        }
        [data-testid="stTextArea"] label {
            margin-bottom: 0.15rem !important;
        }
        [data-testid="stTextArea"] {
            margin-bottom: 0.2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    

def render_keyword_chips(variants):
    chips = [v.strip() for v in variants if isinstance(v, str) and v.strip()]
    if not chips:
        st.caption("No keywords yet.")
        return

    safe_chips = "".join(
        [f"<span class='mapping-chip'>{html.escape(chip)}</span>" for chip in chips[:10]]
    )
    st.markdown(f"<div class='mapping-chip-wrap'>{safe_chips}</div>", unsafe_allow_html=True)


def render_hidden_label_chip(label: str):
    """Render a small, subtle chip for a hidden class label."""
    txt = str(label).strip() if label is not None else ""
    if not txt:
        return
    safe = html.escape(txt)
    st.markdown(
        f"<div class='mapping-chip-wrap'><span class='mapping-chip hidden-chip'>{safe}</span></div>",
        unsafe_allow_html=True,
    )


def render_mapping_empty_state(col_name: str):
    st.markdown(
        f"<div class='mapping-empty'>No {col_name.lower()} class defined yet. Add your first class to begin mapping.</div>",
        unsafe_allow_html=True,
    )
