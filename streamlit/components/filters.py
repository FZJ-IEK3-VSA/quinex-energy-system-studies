import streamlit as st

# ----------------------------
# Unterfunktionen für einzelne Filter
# ----------------------------

def _render_mapping_filter(col_name):
    """
    Rendert den Sidebar-Filter für 'Entity' oder 'Property'.
    Bei 'Property' wird zusätzlich ein Unit-Input ermöglicht.
    """
    st.markdown(f"#### {col_name.capitalize()} Mapping")
    groups = st.session_state.regex_groups[col_name]
    new_groups = []

    # Unit-Filter vorbereiten, falls noch nicht existiert
    if col_name == "Property" and "Unit" not in st.session_state.regex_groups:
        st.session_state.regex_groups["Unit"] = [[""] * len(groups)]
    if col_name == "Property" and "Year" not in st.session_state.regex_groups:
        st.session_state.regex_groups["Year"] = [[""] * len(groups)]

    for row_idx, row in enumerate(groups):
        if len(row) < 2:
            row = ["", ""]  # Master + 1 Variant min
        master, variants = row[0], row[1:]

        with st.container():
            num_variants = len(variants)
            cols = st.columns([2] + [2]*num_variants + [0.5, 0.5, 0.5])

            # ----- Class -----     
            new_master = cols[0].text_input(
                f"{col_name}_master_{row_idx}",
                value=master,
                label_visibility="collapsed",
                placeholder="Class label",
                icon=":material/topic:"
            )

            # ----- Keywords -----
            new_variants = []
            for i, v in enumerate(variants):
                new_val = cols[i+1].text_input(
                    f"{col_name}_variant_{row_idx}_{i}", value=v,
                    label_visibility="collapsed", placeholder=f"Keyword{i+1}",
                    icon=":material/search:"
                )
                new_variants.append(new_val)

            # ----- Unit (nur bei Property) -----
            if col_name == "Property" and new_master.strip() != "":
                # ensure session state list length
                if len(st.session_state.regex_groups["Unit"]) <= row_idx:
                    st.session_state.regex_groups["Unit"].append([""])
                if len(st.session_state.regex_groups["Year"]) <= row_idx:
                    st.session_state.regex_groups["Year"].append([""])
                unit_val = st.session_state.regex_groups["Unit"][row_idx][0]
                year_val = st.session_state.regex_groups["Year"][row_idx][0]

                # kleine Spalte für Unit-Input und Year-Input
                unit_col, year_col, _ = st.columns([2, 2, 6])
                with unit_col:
                    new_unit = st.text_input(
                        f"unit_{row_idx}",
                        value=unit_val,
                        label_visibility="collapsed",
                        placeholder="Unit filter (e.g., $/kWh)",
                        icon=":material/search:"
                    )
                    st.session_state.regex_groups["Unit"][row_idx][0] = new_unit
                with year_col:
                    new_year = st.text_input(
                        f"year_{row_idx}",
                        value=year_val,
                        label_visibility="collapsed",
                        placeholder="Year (Mandatory for Currencies)",
                        icon=":material/calendar_today:"
                    )
                    st.session_state.regex_groups["Year"][row_idx][0] = new_year


            # ----- Buttons -----
            if cols[num_variants+1].button("➕", key=f"{col_name}_addvar_{row_idx}"):
                st.session_state.regex_groups[col_name][row_idx].append("")
                st.rerun()

            if cols[num_variants+2].button("❌", key=f"{col_name}_delvar_{row_idx}"):
                if len(st.session_state.regex_groups[col_name][row_idx]) > 2:
                    st.session_state.regex_groups[col_name][row_idx].pop()
                else:
                    st.session_state.regex_groups[col_name][row_idx][1] = ""
                st.rerun()

            if cols[num_variants+3].button("🗑️", key=f"{col_name}_delrow_{row_idx}"):
                del st.session_state.regex_groups[col_name][row_idx]
                if col_name == "Property":
                    if "Unit" in st.session_state.regex_groups and len(st.session_state.regex_groups["Unit"]) > row_idx:
                        del st.session_state.regex_groups["Unit"][row_idx]
                    if "Year" in st.session_state.regex_groups and len(st.session_state.regex_groups["Year"]) > row_idx:
                        del st.session_state.regex_groups["Year"][row_idx]
                st.rerun()

            new_groups.append([new_master] + new_variants)

    if st.button(f"➕ Add Row", key=f"{col_name}_addrow"):
        st.session_state.regex_groups[col_name].append(["", ""])
        if col_name == "Property":
            st.session_state.regex_groups["Unit"].append([""])
            st.session_state.regex_groups["Year"].append([""])
        st.rerun()

    st.session_state.regex_groups[col_name] = new_groups
    return new_groups


# ----------------------------
# Hauptfunktion
# ----------------------------

def render_filters():
    """
    Rendert die Sidebar mit allen Filtern:
    - Entity
    - Property
    - Unit (pro Property-Zeile, optional, nur wenn Property gesetzt)

    Rückgabe:
    - all_groups: dict mit aktuellen Filterwerten
        z.B. {"Entity": [...], "Property": [...], "Unit": [...]}
    """
    all_groups = {}

    with st.expander("🔍 Filters"):
        for col in ["Entity", "Property"]:
            all_groups[col] = _render_mapping_filter(col)

        # Unit- und Year-Filter zurückgeben (falls vorhanden)
        if "Unit" in st.session_state.regex_groups:
            all_groups["Unit"] = st.session_state.regex_groups["Unit"]
        if "Year" in st.session_state.regex_groups:
            all_groups["Year"] = st.session_state.regex_groups["Year"]

    return all_groups
