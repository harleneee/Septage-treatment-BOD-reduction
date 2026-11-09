"""Preset input sets for the Streamlit app."""

# Paper's 3-stage conceptual model: 1000 -> 800 -> 150 -> 50 mg/L (95 % overall).
#   primary treatment   1000 -> 800  : 20 %
#   biological          800  -> 150  : 81.25 %
#   polishing           150  -> 50   : 66.67 % (exactly 2/3)
# Mapped onto the app's 4 stages with screening at 0 % (screens/grit chambers
# remove very little BOD in practice; primary settling is where ~20-35 % is removed).
PAPER_EXAMPLE = {
    "influent_bod": 1000.0,
    "removal_pct": (0.0, 20.0, 81.25, 200.0 / 3.0),  # percent, per stage
}
