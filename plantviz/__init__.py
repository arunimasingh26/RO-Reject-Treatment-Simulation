"""plantviz: animated plant view for the RO-reject simulation (Streamlit component)."""
from .component import render_plant
from .payload import build_payload

__all__ = ["render_plant", "build_payload"]
